#!/usr/bin/env python3
"""Background vocal splitter for OpenHomeKaraoke.

Goes through the song library one file at a time and writes an instrumental track to
<songs>/nonvocal/<song>.m4a and a vocal track to <songs>/vocal/<song>.m4a (whichever of the two
folders exist). With the stereo (L-R/L+R) method the results are named .<song>.m4a instead.

Normally started by app.py as a child process; it can also be run by hand:
	python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1
"""

import os, sys, time, json, argparse, subprocess, traceback
from urllib.parse import quote

import numpy as np
import requests
import soundfile as sf
import torch
import librosa

from lib import dataset
from lib import nets
from lib import spec_utils
from lib.vocal_dirs import ensure_vocal_dirs, is_split_disabled
from constants import media_types

# ffmpeg cannot decode .zip (mp3+cdg bundles), so those are not split
SPLITTABLE_TYPES = [t for t in media_types if t != '.zip']
FAILED_FILE = '.vocal_failed.json'
LOCK_FILE = '.vocal_splitter.lock'


class Cancelled(Exception):
	"""Vocal splitting was switched off while a song was being processed."""


class DecodeError(Exception):
	"""ffmpeg could not turn the song into a wav file (damaged or not a media file)."""


class Separator(object):

	def __init__(self, model, device=None, batchsize=1, cropsize=256, postprocess=False):
		self.model = model
		self.offset = model.offset
		self.device = device
		self.batchsize = batchsize
		self.cropsize = cropsize
		self.postprocess = postprocess

	def _postprocess(self, X_spec, mask):
		if self.postprocess:
			mask_mag = np.abs(mask)
			mask_mag = spec_utils.merge_artifacts(mask_mag)
			mask = mask_mag * np.exp(1.j * np.angle(mask))

		y_spec = X_spec * mask
		v_spec = X_spec - y_spec

		return y_spec, v_spec

	def _separate(self, X_spec_pad, roi_size):
		patches = (X_spec_pad.shape[2] - 2 * self.offset) // roi_size

		self.model.eval()
		with torch.no_grad():
			mask_list = []
			# To reduce the overhead, dataloader is not used. Batches are cut out of the
			# spectrogram on the fly instead of copying every crop up front.
			for i in range(0, patches, self.batchsize):
				X_batch = np.asarray([X_spec_pad[:, :, j * roi_size: j * roi_size + self.cropsize]
				                      for j in range(i, min(i + self.batchsize, patches))])
				X_batch = torch.from_numpy(X_batch).to(self.device)

				mask = self.model.predict_mask(X_batch)

				mask = mask.detach().cpu().numpy()
				mask = np.concatenate(mask, axis=2)
				mask_list.append(mask)

			mask = np.concatenate(mask_list, axis=2)

		return mask

	def separate(self, X_spec, scale=None):
		"""scale: the value the input is normalised by. Defaults to this spectrogram's own peak;
		pass the whole song's peak when separating it segment by segment."""
		n_frame = X_spec.shape[2]
		pad_l, pad_r, roi_size = dataset.make_padding(n_frame, self.cropsize, self.offset)
		X_spec_pad = np.pad(X_spec, ((0, 0), (0, 0), (pad_l, pad_r)), mode='constant')
		X_spec_pad /= (scale or np.abs(X_spec).max() or 1.0)

		mask = self._separate(X_spec_pad, roi_size)
		mask = mask[:, :, :n_frame]

		y_spec, v_spec = self._postprocess(X_spec, mask)

		return y_spec, v_spec

	def separate_tta(self, X_spec, scale=None):
		n_frame = X_spec.shape[2]
		scale = scale or np.abs(X_spec).max() or 1.0
		pad_l, pad_r, roi_size = dataset.make_padding(n_frame, self.cropsize, self.offset)
		X_spec_pad = np.pad(X_spec, ((0, 0), (0, 0), (pad_l, pad_r)), mode='constant')
		X_spec_pad /= scale

		mask = self._separate(X_spec_pad, roi_size)

		pad_l += roi_size // 2
		pad_r += roi_size // 2
		X_spec_pad = np.pad(X_spec, ((0, 0), (0, 0), (pad_l, pad_r)), mode='constant')
		X_spec_pad /= scale

		mask_tta = self._separate(X_spec_pad, roi_size)
		mask_tta = mask_tta[:, :, roi_size // 2:]
		mask = (mask[:, :, :n_frame] + mask_tta[:, :, :n_frame]) * 0.5

		y_spec, v_spec = self._postprocess(X_spec, mask)

		return y_spec, v_spec


# ---------------------------------------------------------------------------- audio in / out

def ffm_video2wav(input_fn, output_fn, sr=44100):
	"""Decode any media file to a wav file. Raises DecodeError if ffmpeg fails.
	The built-in DNN model is trained on 44100 Hz; it still runs on other rates but does not work well."""
	# Never leave the previous song's wav lying around: if decoding fails, it would be split
	# and saved under this song's name.
	if os.path.exists(output_fn):
		os.remove(output_fn)
	# Arguments are passed as a list (no shell), so file names need no quoting or escaping.
	r = subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', input_fn, '-vn', '-f', 'wav', '-ar', str(sr), output_fn],
	                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
	if r.returncode != 0 or not os.path.isfile(output_fn) or os.path.getsize(output_fn) <= 44:
		msg = r.stderr.decode('utf-8', 'replace').strip().splitlines()
		raise DecodeError('ffmpeg could not decode the file' + (f': {msg[-1]}' if msg else ''))


class M4AWriter(object):
	"""Streams float32 audio into ffmpeg, which encodes it to AAC/m4a. No big temporary wav file is needed."""

	def __init__(self, path, sr, channels, br='128k'):
		self.path = path
		self.channels = channels
		self.proc = subprocess.Popen(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(sr), '-ac', str(channels),
		                              '-i', 'pipe:0', '-c:a', 'aac', '-b:a', br, path],
		                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

	def write(self, wave):
		"""wave: array of shape (channels, samples)"""
		wave = np.asarray(wave, dtype='<f4').reshape(self.channels, -1)
		self.proc.stdin.write(np.ascontiguousarray(wave.T).tobytes())

	def close(self):
		self.proc.stdin.close()
		err = self.proc.stderr.read().decode('utf-8', 'replace').strip()
		if self.proc.wait() != 0:
			raise RuntimeError(f'ffmpeg could not encode {os.path.basename(self.path)}: {err[-300:]}')

	def abort(self):
		if self.proc.poll() is None:
			self.proc.kill()
			self.proc.wait()


def read_stereo(f, start, stop):
	"""Read samples [start, stop) of an open SoundFile as a (2, n) float32 array."""
	f.seek(start)
	x = f.read(stop - start, dtype='float32', always_2d=True).T
	if x.shape[0] == 1:
		x = np.vstack([x, x])  # mono to stereo
	return np.ascontiguousarray(x[:2])


def split_vocal_by_stereo(in_wav, outputs, args, check=lambda: None):
	"""Traditional karaoke trick for MTV audio: L-R is the instruments, L+R the vocals (mono results).
	outputs: {'nonvocal': path, 'vocal': path}, either may be missing."""
	with sf.SoundFile(in_wav) as f:
		if f.channels < 2:
			raise ValueError('the stereo L-R/L+R method needs a stereo file, this one is mono')
		writers = {k: M4AWriter(p, f.samplerate, 1) for k, p in outputs.items()}
		try:
			block = 30 * f.samplerate
			for start in range(0, f.frames, block):
				check()
				x = read_stereo(f, start, min(f.frames, start + block))
				if 'nonvocal' in writers:
					writers['nonvocal'].write(x[0] - x[1])
				if 'vocal' in writers:
					writers['vocal'].write(x[0] + x[1])
			for w in writers.values():
				w.close()
		except BaseException:
			for w in writers.values():
				w.abort()
			raise


def split_vocal_by_dnn(in_wav, outputs, args, check=lambda: None):
	"""Separate a song with the DNN, segment by segment, so memory use does not grow with song length.

	Each segment is separated together with `margin` samples of context on both sides (more than
	the model's own context of model.offset frames), and only its middle part is kept. Neighbouring
	segments overlap by `xfade` samples and are cross-faded. The input is normalised by the peak of
	the whole song (found in a first pass), as in the original whole-song version.
	outputs: {'nonvocal': path, 'vocal': path}, either may be missing."""
	hop, n_fft = args.hop_length, args.n_fft
	with sf.SoundFile(in_wav) as f:
		sr, n = f.samplerate, f.frames
		if n == 0:
			raise ValueError('the file has no audio')
		# The model works on windows of roi_size frames, and its output depends on where that window
		# grid falls. Segment starts and margins are multiples of the grid, so every segment uses the
		# same grid as a whole-song run and gives the same result (apart from the discarded margins).
		roi_size = dataset.make_padding(1, args.cropsize, args.model.offset)[2]
		unit = roi_size * hop
		seg = max(1, round(args.segment * sr / unit)) * unit
		margin = unit * int(np.ceil((args.model.offset + 4) / roi_size))
		xfade = 4 * hop

		starts = list(range(0, n, seg))
		if len(starts) > 1 and n - starts[-1] < 2 * xfade:
			starts.pop()  # fold a very short tail into the previous segment
		bounds = list(zip(starts, starts[1:] + [n]))
		windows = [(max(0, s - margin), min(n, e + xfade + margin)) for s, e in bounds]

		scale = None
		if len(bounds) > 1:
			print('Measuring peak level ...', end=' ', flush=True)
			scale = 0.0
			for a, b in windows:
				check()
				scale = max(scale, float(np.abs(spec_utils.wave_to_spectrogram(read_stereo(f, a, b), hop, n_fft)).max()))
			print('done', flush=True)

		sp = Separator(args.model, args.device, args.batchsize, args.cropsize, args.postprocess)
		writers = {k: M4AWriter(p, sr, 2) for k, p in outputs.items()}
		tails = {}
		try:
			for k, ((s, e), (a, b)) in enumerate(zip(bounds, windows)):
				check()
				X_spec = spec_utils.wave_to_spectrogram(read_stereo(f, a, b), hop, n_fft)
				y_spec, v_spec = (sp.separate_tta if args.tta else sp.separate)(X_spec, scale)
				keep = slice(s - a, min(e + xfade, n) - a)
				for key, spec in (('nonvocal', y_spec), ('vocal', v_spec)):
					if key not in writers:
						continue
					wave = np.asarray([librosa.istft(spec[c], hop_length=hop, length=b - a) for c in range(2)])[:, keep]
					if key in tails:
						t = tails.pop(key)
						w = np.linspace(0.0, 1.0, t.shape[1], endpoint=False, dtype=np.float32)
						wave[:, :t.shape[1]] = t * (1.0 - w) + wave[:, :t.shape[1]] * w
					if e < n:
						writers[key].write(wave[:, :-xfade])
						tails[key] = wave[:, -xfade:]
					else:
						writers[key].write(wave)
				print(f'  segment {k + 1}/{len(bounds)} done', flush=True)
			for w in writers.values():
				w.close()
		except BaseException:
			for w in writers.values():
				w.abort()
			raise


# ---------------------------------------------------------------------------- library bookkeeping

song_path = ''
last_completed = ''
use_DNN = True


def method_key(bn):
	return ('dnn:' if use_DNN else 'stereo:') + bn


def file_signature(bn):
	st = os.stat(os.path.join(song_path, bn))
	return [st.st_size, int(st.st_mtime)]


def load_failed():
	try:
		with open(os.path.join(song_path, FAILED_FILE), encoding='utf-8') as fp:
			return json.load(fp)
	except (OSError, ValueError):
		return {}


def mark_failed(bn, err):
	"""Remember that this file could not be split, so it is not retried (and does not crash the
	splitter again) until the file changes, e.g. after it is downloaded again."""
	failed = load_failed()
	try:
		failed[method_key(bn)] = {'signature': file_signature(bn), 'error': f'{type(err).__name__}: {err}'[:300],
		                          'time': time.strftime('%Y-%m-%d %H:%M:%S')}
		path = os.path.join(song_path, FAILED_FILE)
		with open(path + '.tmp', 'w', encoding='utf-8') as fp:
			json.dump(failed, fp, ensure_ascii=False, indent=1)
		os.replace(path + '.tmp', path)
	except OSError as e:
		print(f'Could not update {FAILED_FILE}: {e}', flush=True)


def server_url(args):
	return f"{'https' if args.ssl else 'http'}://localhost:{args.port}"


def get_next_file(args):
	global song_path, use_DNN
	try:
		obj = requests.get(f'{server_url(args)}/get_vocal_todo_list/{args.device.type}/{quote(last_completed, safe="")}',
		                   timeout=10, verify=False).json()
		song_path = obj['download_path'].rstrip('/\\')
		use_DNN = obj['use_DNN']
	except Exception:
		if not song_path:
			print('OpenHomeKaraoke is not running and --download-path is not specified, exiting ...')
			sys.exit()
		obj = {'queue': []}

	if is_split_disabled(song_path):
		return None
	dirs = [d for d in ('nonvocal', 'vocal') if os.path.isdir(os.path.join(song_path, d))]
	if not dirs:
		return None
	prefix = '' if use_DNN else '.'
	failed = load_failed()

	def needs_work(bn):
		if bn.startswith('.') or os.path.splitext(bn)[1].lower() not in SPLITTABLE_TYPES:
			return False
		if not os.path.isfile(os.path.join(song_path, bn)):
			return False
		if all(os.path.isfile(os.path.join(song_path, d, f'{prefix}{bn}.m4a')) for d in dirs):
			return False
		rec = failed.get(method_key(bn))
		return not (rec and rec.get('signature') == file_signature(bn))

	# songs that are playing or queued first, then the rest of the library
	for bn in [os.path.basename(fn) for fn in obj['queue']] + sorted(os.listdir(song_path)):
		if needs_work(bn):
			return bn
	return None


# ---------------------------------------------------------------------------- process control

def parent_alive(pid):
	if not pid:
		return True
	try:
		import psutil
		return psutil.pid_exists(pid)
	except ImportError:
		if os.name == 'nt':
			return True
		try:
			os.kill(pid, 0)
			return True
		except OSError:
			return False


def acquire_lock(folder):
	"""Only one splitter may work on a song folder (e.g. one started by app.py and one by hand)."""
	fp = open(os.path.join(folder, LOCK_FILE), 'a+')
	try:
		if os.name == 'nt':
			import msvcrt
			fp.seek(0)
			msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
		else:
			import fcntl
			fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
	except OSError:
		fp.close()
		return None
	return fp


def lower_priority(nice):
	if nice <= 0:
		return
	try:
		if hasattr(os, 'nice'):
			os.nice(nice)
		else:
			import psutil
			psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
	except Exception as e:
		print(f'Could not lower the process priority: {e}', flush=True)


def load_model(args, device):
	model = nets.CascadedNet(args.n_fft, args.hop_length, 32, 128, True)
	try:
		state = torch.load(args.pretrained_model, map_location='cpu', weights_only=True)
	except TypeError:  # torch < 1.13 has no weights_only
		state = torch.load(args.pretrained_model, map_location='cpu')
	model.load_state_dict(state)
	return model.to(device)


def fall_back_to_cpu(args, err):
	"""A CUDA error (old GPU not supported by this PyTorch build, out of GPU memory, driver problem, ...)
	should not stop vocal splitting: continue on the CPU for the rest of this run."""
	print(f'GPU error, switching to CPU: {err}', flush=True)
	args.device = torch.device('cpu')
	try:
		args.model = args.model.to(args.device)
	except Exception:
		args.model = load_model(args, args.device)
	try:
		torch.cuda.empty_cache()
	except Exception:
		pass


def process_file(bn, args, in_wav, check):
	dirs = [d for d in ('nonvocal', 'vocal') if os.path.isdir(os.path.join(song_path, d))]
	prefix = '' if use_DNN else '.'
	partial = {d: os.path.join(song_path, d, f'.partial.{os.getpid()}.m4a') for d in dirs}
	final = {d: os.path.join(song_path, d, f'{prefix}{bn}.m4a') for d in dirs}
	method = f'DNN on {args.device.type.upper()}' if use_DNN else 'stereo L-R/L+R'
	print(f'Start processing {bn} ({method}):', flush=True)
	t0 = time.time()
	try:
		ffm_video2wav(os.path.join(song_path, bn), in_wav, args.sr)
		duration = sf.info(in_wav).duration
		(split_vocal_by_dnn if use_DNN else split_vocal_by_stereo)(in_wav, partial, args, check)
		for d in dirs:
			os.replace(partial[d], final[d])
	finally:
		for p in list(partial.values()) + [in_wav]:
			if os.path.exists(p):
				os.remove(p)
	took = time.time() - t0
	print(f'Done {bn}: {duration:.0f}s of audio in {took:.0f}s ({duration / max(took, 1e-3):.2f}x real time)', flush=True)


def main(argv):
	global song_path, last_completed

	p = argparse.ArgumentParser()
	p.add_argument('--download-path', '-d', help = "Path for downloaded songs. Will be overridden by the one from HTTP request. "
					"Set this to forcefully run the vocal-splitter even when OpenHomeKaraoke is not running.", default = '')
	p.add_argument('--port', type = int, default = 5000, help = 'HTTP port of OpenHomeKaraoke (default: 5000)')
	p.add_argument('--ssl', action = 'store_true', help = 'OpenHomeKaraoke runs with --ssl (HTTPS)')
	p.add_argument('--parent-pid', type = int, default = 0, help = 'Exit when this process (app.py) is gone')
	p.add_argument('--gpu', '-g', type = int, help = 'CUDA device ID for GPU inference, set to -1 to force to use CPU (default will try to use GPU if available)', default = None)
	p.add_argument('--threads', type = int, default = max(1, (os.cpu_count() or 2) // 2),
	               help = 'CPU threads for inference (default: half of the CPU cores, so that video playback stays smooth)')
	p.add_argument('--nice', type = int, default = 10, help = 'Lower the process priority by this much (default: 10, 0 = do not change)')
	p.add_argument('--segment', type = float, default = 60, help = 'Seconds of audio separated at a time; limits memory use (default: 60)')
	p.add_argument('--pretrained_model', '-P', type = str, default = 'models/baseline.pth')
	p.add_argument('--sr', '-r', type = int, default = 44100)
	p.add_argument('--n_fft', '-f', type = int, default = 2048)
	p.add_argument('--hop_length', '-H', type = int, default = 1024)
	p.add_argument('--batchsize', '-B', type = int, default = 4)
	p.add_argument('--cropsize', '-c', type = int, default = 256)
	p.add_argument('--postprocess', '-p', action = 'store_true')
	p.add_argument('--tta', '-t', action = 'store_true')
	p.add_argument('--ramdir', '-rd', help = 'Temporary directory on RAMDISK to reduce I/O load',
	               default = 'z:/' if sys.platform.startswith('win') else '/dev/shm')
	args = p.parse_args(argv)

	song_path = os.path.expanduser(args.download_path).rstrip('/\\')
	if args.ssl:
		import urllib3
		urllib3.disable_warnings()

	lower_priority(args.nice)
	torch.set_num_threads(max(1, args.threads))

	# Determine the GPU device and load the DNN model
	print('Loading vocal-splitter model ...', end = ' ', flush = True)
	args.device = torch.device('cpu')
	args.model = load_model(args, args.device)
	if (args.gpu is None or args.gpu >= 0) and torch.cuda.is_available():
		try:
			gpu = torch.device(f'cuda:{0 if args.gpu is None else args.gpu}')
			args.model = args.model.to(gpu)
			args.device = gpu
		except Exception as e:
			print(f'cannot use the GPU ({e}), using CPU ...', end = ' ', flush = True)
			args.model = load_model(args, args.device)
	print(f'done (device: {args.device}, CPU threads: {torch.get_num_threads()})', flush = True)

	# set song_path global variable from local server
	get_next_file(args)
	ensure_vocal_dirs(song_path)
	lock = acquire_lock(song_path)
	if lock is None:
		print(f'Another vocal splitter is already working on {song_path}, exiting ...', flush = True)
		return

	# Use RAMDISK for the large temporary .wav file for speed up if available
	RAMDIR = args.ramdir if os.path.isdir(args.ramdir) else song_path
	in_wav = os.path.join(RAMDIR, f'.vocal_splitter.{os.getpid()}.input.wav')

	def check():
		if not parent_alive(args.parent_pid):
			print('OpenHomeKaraoke has exited, exiting ...', flush = True)
			sys.exit()
		if is_split_disabled(song_path):
			raise Cancelled()

	# Main loop
	while True:
		if not parent_alive(args.parent_pid):
			print('OpenHomeKaraoke has exited, exiting ...', flush = True)
			return
		next_file = get_next_file(args)
		if not next_file:
			time.sleep(2)
			continue

		try:
			process_file(next_file, args, in_wav, check)
			last_completed = next_file
		except Cancelled:
			print('Vocal splitting was switched off, stopped.', flush = True)
		except KeyboardInterrupt:
			raise
		except Exception as e:
			if use_DNN and args.device.type == 'cuda' and not isinstance(e, DecodeError):
				fall_back_to_cpu(args, e)
				continue  # retry the same song on the CPU
			traceback.print_exc()
			print(f'Skipping {next_file}: {e}', flush = True)
			mark_failed(next_file, e)


if __name__ == '__main__':
	main(sys.argv[1:])
