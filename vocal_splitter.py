#!/usr/bin/env python3
"""Background vocal splitter for OpenHomeKaraoke.

Goes through the song library one file at a time and writes an instrumental track to
<songs>/nonvocal/ and a vocal track to <songs>/vocal/ (whichever of the two folders exist), with
the model chosen on the Info page (see lib/vocal_models.py for the models and file names).
The UVR VR models (HP5 by default) are downloaded the first time they are needed; if that is
not possible, the built-in baseline model is used meanwhile.

The network runs on an NVIDIA GPU (CUDA) or an Apple Silicon GPU (MPS) when one is available,
otherwise on the CPU. Any GPU error switches to the CPU for the rest of the run.

Normally started by app.py as a child process; it can also be run by hand:
	python vocal_splitter.py -d ~/pikaraoke-songs --gpu -1
"""

import os, sys, time, json, argparse, subprocess, traceback
from urllib.parse import quote

# On Apple Silicon, run the few operations MPS does not support on the CPU instead of failing.
# Must be set before torch is imported.
os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')

import numpy as np
import requests
import soundfile as sf
import torch

from lib.separation import BaselineBackend, VRBackend
from lib.vocal_dirs import ensure_vocal_dirs, is_split_disabled
from lib import vocal_models as vm
from constants import media_types

# ffmpeg cannot decode .zip (mp3+cdg bundles), so those are not split
SPLITTABLE_TYPES = [t for t in media_types if t != '.zip']
FAILED_FILE = '.vocal_failed.json'
LOCK_FILE = '.vocal_splitter.lock'


class Cancelled(Exception):
	"""Vocal splitting was switched off while a song was being processed."""


class DecodeError(Exception):
	"""ffmpeg could not turn the song into a wav file (damaged or not a media file)."""


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


def split_vocal_by_dnn(in_wav, outputs, backend, segment=60, check=lambda: None):
	"""Separate a song with a neural-network backend (lib/separation.py), segment by segment, so
	memory use does not grow with song length.

	Each segment is separated together with backend.margin samples of context on both sides and
	only its middle part is kept. Segment starts and margins are multiples of backend.unit, the
	model's window grid, so every segment uses the same grid as a whole-song run and gives the same
	result. Neighbouring segments overlap by backend.xfade samples and are cross-faded. The input
	is normalised by the peak of the whole song (found in a first pass), as in a whole-song run.
	outputs: {'nonvocal': path, 'vocal': path}, either may be missing."""
	with sf.SoundFile(in_wav) as f:
		sr, n = f.samplerate, f.frames
		if n == 0:
			raise ValueError('the file has no audio')
		unit, margin, xfade = backend.unit, backend.margin, backend.xfade
		seg = max(1, round(segment * sr / unit)) * unit

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
				scale = max(scale, backend.peak(read_stereo(f, a, b)))
			print('done', flush=True)

		writers = {k: M4AWriter(p, sr, 2) for k, p in outputs.items()}
		tails = {}
		try:
			for k, ((s, e), (a, b)) in enumerate(zip(bounds, windows)):
				check()
				inst, voc = backend.separate(read_stereo(f, a, b), scale)
				keep = slice(s - a, min(e + xfade, n) - a)
				for key, wave in (('nonvocal', inst), ('vocal', voc)):
					if key not in writers:
						continue
					wave = np.array(wave[:, keep], dtype=np.float32)
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
selected_model = vm.DEFAULT_MODEL  # chosen on the Info page
# Old failed-list keys stay valid: the baseline model used to be called 'dnn', L-R/L+R 'stereo'
FAILED_PREFIX = {'baseline': 'dnn', 'LR': 'stereo'}
DOWNLOAD_RETRY = 3600  # seconds to wait before trying a failed weights download again


def method_key(model, bn):
	return FAILED_PREFIX.get(model, model) + ':' + bn


def file_signature(bn):
	st = os.stat(os.path.join(song_path, bn))
	return [st.st_size, int(st.st_mtime)]


def load_failed():
	try:
		with open(os.path.join(song_path, FAILED_FILE), encoding='utf-8') as fp:
			return json.load(fp)
	except (OSError, ValueError):
		return {}


def mark_failed(model, bn, err):
	"""Remember that this file could not be split, so it is not retried (and does not crash the
	splitter again) until the file changes, e.g. after it is downloaded again."""
	failed = load_failed()
	try:
		failed[method_key(model, bn)] = {'signature': file_signature(bn), 'error': f'{type(err).__name__}: {err}'[:300],
		                                 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
		path = os.path.join(song_path, FAILED_FILE)
		with open(path + '.tmp', 'w', encoding='utf-8') as fp:
			json.dump(failed, fp, ensure_ascii=False, indent=1)
		os.replace(path + '.tmp', path)
	except OSError as e:
		print(f'Could not update {FAILED_FILE}: {e}', flush=True)


def server_url(args):
	return f"{'https' if args.ssl else 'http'}://localhost:{args.port}"


def poll_server(args):
	"""Ask OpenHomeKaraoke for the song folder, the play queue and the selected model.
	Without a running OpenHomeKaraoke, use --download-path and the model saved in the song folder."""
	global song_path, selected_model
	try:
		obj = requests.get(f'{server_url(args)}/get_vocal_todo_list/{args.device.type}/{quote(last_completed, safe="")}',
		                   timeout=10, verify=False).json()
		song_path = obj['download_path'].rstrip('/\\')
		if 'model' in obj:
			selected_model = vm.normalize(obj['model'])
		else:  # older app.py
			selected_model = vm.DEFAULT_MODEL if obj.get('use_DNN', True) else 'LR'
	except Exception:
		if not song_path:
			print('OpenHomeKaraoke is not running and --download-path is not specified, exiting ...')
			sys.exit()
		obj = {'queue': []}
		selected_model = vm.get_selected(song_path)
	if args.model:
		selected_model = vm.normalize(args.model)
	return obj


def get_next_file(obj, model):
	dirs = [d for d in vm.SUBDIRS if os.path.isdir(os.path.join(song_path, d))]
	if not dirs:
		return None
	failed = load_failed()

	def needs_work(bn):
		if bn.startswith('.') or os.path.splitext(bn)[1].lower() not in SPLITTABLE_TYPES:
			return False
		if not os.path.isfile(os.path.join(song_path, bn)):
			return False
		if all(os.path.isfile(vm.result_path(song_path, d, model, bn)) for d in dirs):
			return False
		rec = failed.get(method_key(model, bn))
		return not (rec and rec.get('signature') == file_signature(bn))

	# songs that are playing or queued first, then the rest of the library
	for bn in [os.path.basename(fn) for fn in obj['queue']] + sorted(os.listdir(song_path)):
		if needs_work(bn):
			return bn
	return None


# ---------------------------------------------------------------------------- models and devices

def pick_device(args):
	"""CUDA if available, else Apple Silicon (MPS), else CPU. --gpu -1 forces the CPU,
	--gpu N picks CUDA device N."""
	if args.gpu is not None and args.gpu < 0:
		return torch.device('cpu')
	if torch.cuda.is_available():
		return torch.device(f'cuda:{0 if args.gpu is None else args.gpu}')
	mps = getattr(torch.backends, 'mps', None)
	if args.gpu is None and mps is not None and mps.is_available():
		return torch.device('mps')
	return torch.device('cpu')


def empty_gpu_cache():
	for mod in ('cuda', 'mps'):
		try:
			getattr(torch, mod).empty_cache()
		except Exception:
			pass


class Models(object):
	"""Loads separation backends when they are first needed (downloading VR weights if missing)
	and keeps at most one VR model in memory."""

	def __init__(self, args):
		self.args = args
		self.loaded = {}
		self.download_failed = {}  # model -> time of the last failed download

	def effective(self, model, check):
		"""The model to split with now: the selected one, or baseline while the selected VR model
		cannot be downloaded."""
		if model not in vm.VR_MODELS or vm.find_weights(model):
			return model
		if time.time() - self.download_failed.get(model, 0) < DOWNLOAD_RETRY:
			return 'baseline'
		try:
			vm.download_weights(model, self.args.model_url, check, log=lambda s: print(s, flush=True))
			return model
		except Cancelled:
			raise
		except Exception as e:
			self.download_failed[model] = time.time()
			print(f'Could not download the {model} model ({type(e).__name__}: {e}); using the baseline model '
			      f'for now, will try again in {DOWNLOAD_RETRY // 60} minutes.', flush=True)
			return 'baseline'

	def _load(self, model, device):
		a = self.args
		if model == 'baseline':
			return BaselineBackend(a.pretrained_model, device, a.sr, a.n_fft, a.hop_length, a.cropsize, a.batchsize,
			                       a.postprocess, a.tta)
		info = vm.VR_MODELS[model]
		return VRBackend(model, vm.find_weights(model), device, info['swap'], a.aggressiveness, a.vr_batchsize, a.tta)

	def get(self, model):
		if model not in self.loaded:
			for m in [m for m in self.loaded if m in vm.VR_MODELS]:
				del self.loaded[m]  # one VR model at a time (each uses a few hundred MB)
			empty_gpu_cache()
			try:
				self.loaded[model] = self._load(model, self.args.device)
			except Exception as e:
				if self.args.device.type == 'cpu':
					raise
				print(f'Cannot use the {self.args.device.type.upper()} for {model} ({e}), using the CPU ...', flush=True)
				self.args.device = torch.device('cpu')
				self.loaded = {m: b.to(self.args.device) for m, b in self.loaded.items()}
				self.loaded[model] = self._load(model, self.args.device)
		return self.loaded[model]

	def fall_back_to_cpu(self, err):
		"""A GPU error (old GPU not supported by this PyTorch build, out of GPU memory, an operation
		MPS cannot do, driver problem, ...) should not stop vocal splitting: continue on the CPU for
		the rest of this run."""
		print(f'{self.args.device.type.upper()} error, switching to CPU: {err}', flush=True)
		self.args.device = torch.device('cpu')
		for m in list(self.loaded):
			try:
				self.loaded[m] = self.loaded[m].to(self.args.device)
			except Exception:
				del self.loaded[m]  # reloaded on the CPU when needed
		empty_gpu_cache()


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


def process_file(bn, model, args, models, in_wav, check):
	dirs = [d for d in vm.SUBDIRS if os.path.isdir(os.path.join(song_path, d))]
	partial = {d: os.path.join(song_path, d, f'.partial.{os.getpid()}.m4a') for d in dirs}
	final = {d: vm.result_path(song_path, d, model, bn) for d in dirs}
	backend = None if model == 'LR' else models.get(model)
	method = 'stereo L-R/L+R' if backend is None else f'{model} model on {args.device.type.upper()}'
	print(f'Start processing {bn} ({method}):', flush=True)
	t0 = time.time()
	try:
		ffm_video2wav(os.path.join(song_path, bn), in_wav, args.sr if backend is None else backend.sr)
		duration = sf.info(in_wav).duration
		if backend is None:
			split_vocal_by_stereo(in_wav, partial, args, check)
		else:
			split_vocal_by_dnn(in_wav, partial, backend, args.segment, check)
		for d in dirs:
			os.makedirs(os.path.dirname(final[d]), exist_ok=True)
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
	p.add_argument('--model', '-m', choices = vm.ALL_MODELS, default = None,
	               help = 'Use this model instead of the one chosen on the Info page')
	p.add_argument('--gpu', '-g', type = int, help = 'CUDA device ID for GPU inference, set to -1 to force to use CPU '
	               '(default: use an NVIDIA (CUDA) or Apple Silicon (MPS) GPU if available)', default = None)
	p.add_argument('--threads', type = int, default = max(1, (os.cpu_count() or 2) // 2),
	               help = 'CPU threads for inference (default: half of the CPU cores, so that video playback stays smooth)')
	p.add_argument('--nice', type = int, default = 10, help = 'Lower the process priority by this much (default: 10, 0 = do not change)')
	p.add_argument('--segment', type = float, default = 60, help = 'Seconds of audio separated at a time; limits memory use (default: 60)')
	p.add_argument('--pretrained_model', '-P', type = str, default = 'models/baseline.pth', help = 'Weights of the baseline model')
	p.add_argument('--aggressiveness', type = int, default = 10, help = 'VR models: how strongly vocals are removed, 0-20 (default: 10, as in UVR)')
	p.add_argument('--vr-batchsize', type = int, default = 1, help = 'VR models: windows per batch (default: 1, uses the least memory)')
	p.add_argument('--model-url', default = vm.WEIGHTS_URL, help = argparse.SUPPRESS)
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
	args.device = pick_device(args)
	print(f'Vocal splitter: device {args.device}, CPU threads {torch.get_num_threads()}', flush = True)
	models = Models(args)

	# set song_path global variable from local server
	poll_server(args)
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
		obj = poll_server(args)
		if is_split_disabled(song_path):
			time.sleep(2)
			continue
		try:
			model = models.effective(selected_model, check)
		except Cancelled:
			continue
		next_file = get_next_file(obj, model)
		if not next_file:
			time.sleep(2)
			continue

		try:
			process_file(next_file, model, args, models, in_wav, check)
			last_completed = next_file
		except Cancelled:
			print('Vocal splitting was switched off, stopped.', flush = True)
		except KeyboardInterrupt:
			raise
		except Exception as e:
			if model != 'LR' and args.device.type != 'cpu' and not isinstance(e, DecodeError):
				models.fall_back_to_cpu(e)
				continue  # retry the same song on the CPU
			traceback.print_exc()
			print(f'Skipping {next_file}: {e}', flush = True)
			mark_failed(model, next_file, e)


if __name__ == '__main__':
	main(sys.argv[1:])
