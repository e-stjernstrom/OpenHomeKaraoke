"""Where each song stands in background vocal splitting, for the web page.

The splitter (vocal_splitter.py) runs as its own process. It reports the song it is working on in
PROGRESS_FILE in the song folder, and records songs it could not split in FAILED_FILE. The web
server reads both to tell users whether the instrumental of a song is ready, being made, waiting,
failed, or will not be made because splitting is off.
"""
import json, os, time

from lib import vocal_models as vm

PROGRESS_FILE = '.vocal_progress.json'
FAILED_FILE = '.vocal_failed.json'
# Old failed-list keys stay valid: the baseline model used to be called 'dnn', L-R/L+R 'stereo'
FAILED_PREFIX = {'baseline': 'dnn', 'LR': 'stereo'}


def method_key(model, bn):
	return FAILED_PREFIX.get(model, model) + ':' + bn


def file_signature(song_dir, bn):
	st = os.stat(os.path.join(song_dir, bn))
	return [st.st_size, int(st.st_mtime)]


def load_failed(song_dir):
	try:
		with open(os.path.join(song_dir, FAILED_FILE), encoding='utf-8') as fp:
			return json.load(fp)
	except (OSError, ValueError):
		return {}


def failed_record(failed, song_dir, model, bn):
	"""The failure record of this song for this model, if it is still valid (the file has not
	changed since)."""
	rec = failed.get(method_key(model, bn))
	try:
		return rec if rec and rec.get('signature') == file_signature(song_dir, bn) else None
	except OSError:
		return None


# ------------------------------------------------------------------ written by the splitter

def write_progress(song_dir, bn, model, fraction):
	path = os.path.join(song_dir, PROGRESS_FILE)
	try:
		with open(path + '.tmp', 'w', encoding='utf-8') as fp:
			json.dump({'file': bn, 'model': model, 'progress': round(max(0.0, min(1.0, fraction)), 3),
			           'pid': os.getpid(), 'time': time.time()}, fp)
		os.replace(path + '.tmp', path)
	except OSError:
		pass


def clear_progress(song_dir):
	try:
		os.remove(os.path.join(song_dir, PROGRESS_FILE))
	except OSError:
		pass


def read_progress(song_dir):
	try:
		with open(os.path.join(song_dir, PROGRESS_FILE), encoding='utf-8') as fp:
			return json.load(fp)
	except (OSError, ValueError):
		return None


# ------------------------------------------------------------------ read by the web server

def has_result(song_dir, model, bn):
	dirs = [d for d in vm.SUBDIRS if os.path.isdir(os.path.join(song_dir, d))]
	return bool(dirs) and all(os.path.isfile(vm.result_path(song_dir, d, model, bn)) for d in dirs)


def song_states(song_dir, files, model, splitter):
	"""State of each song in `files` (full paths, in the order the splitter works on them: the
	playing song, then the queue).

	splitter: 'running', 'stopped' (switched on but the process is not running), 'off' (switched
	off) or 'unavailable' (PyTorch etc. missing, or --no-vocal).

	Returns {path: {'state': ..., 'model': ..., ...}} with state one of
	  done        the instrumental and vocal tracks of the selected model exist
	  processing  being split now; 'progress' is 0..1
	  queued      waiting; 'ahead' songs come first
	  failed      the splitter could not split this file; 'error' says why
	  off / unavailable / stopped   nothing will happen until the splitter runs
	"""
	song_dir = song_dir.rstrip('/\\')
	failed = load_failed(song_dir)
	prog = read_progress(song_dir) if splitter == 'running' else None
	out, ahead = {}, 0
	for path in files:
		bn = os.path.basename(path)
		st = {'model': model}
		if has_result(song_dir, model, bn):
			st['state'] = 'done'
		elif prog and prog.get('file') == bn:
			st.update(state='processing', progress=prog.get('progress', 0), model=prog.get('model', model))
			ahead += 1
		elif failed_record(failed, song_dir, model, bn):
			st.update(state='failed', error=failed_record(failed, song_dir, model, bn).get('error', ''))
		elif splitter != 'running':
			st['state'] = splitter
		else:
			st.update(state='queued', ahead=ahead)
			ahead += 1
		out[path] = st
	return out
