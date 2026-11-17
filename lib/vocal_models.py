"""Vocal-separation models: which ones exist, where their weights are, and where their results go.

Used by both app.py/karaoke.py (no PyTorch needed) and vocal_splitter.py.

Result files, for a song <song> in the song folder:
	baseline (the original built-in model)   nonvocal/<song>.m4a        vocal/<song>.m4a
	LR (stereo L-R / L+R trick)              nonvocal/.<song>.m4a       vocal/.<song>.m4a
	HP5, HP2, HP3 (UVR VR models)            nonvocal/<id>/<song>.m4a   vocal/<id>/<song>.m4a
"""

import os

DEFAULT_MODEL = 'HP5'
SELECTED_FILE = '.vocal_model'  # in the song folder; holds the model chosen on the Info page

WEIGHTS_URL = 'https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/uvr5_weights/'

# UVR VR models (lib/uvr5). 'swap': the model's primary output is the vocals, not the instruments.
VR_MODELS = {
	'HP5': {'file': 'HP5_only_main_vocal.pth', 'size': 63454827, 'swap': False,
	        'sha256': '5908891829634926119720241e8573d97cbeb8277110a7512bdb0bd7563258ee'},
	'HP2': {'file': 'HP2_all_vocals.pth', 'size': 63454827, 'swap': False,
	        'sha256': '39796caa5db18d7f9382d8ac997ac967bfd85f7761014bb807d2543cc844ef05'},
	'HP3': {'file': 'HP3_all_vocals.pth', 'size': 63454827, 'swap': True,
	        'sha256': '45e6b65199e781b4a6542002699be9f19cd3d1cb7d1558bc2bfbcd84674dfe28'},
}
# Neural-network models, best first. Playback falls back along this list.
DNN_MODELS = ['HP5', 'HP2', 'HP3', 'baseline']
ALL_MODELS = DNN_MODELS + ['LR']
SUBDIRS = ('nonvocal', 'vocal')

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def weight_dirs():
	"""Where VR weights are looked for, in order. The second one is used when the program folder
	is read-only (e.g. a system-wide install)."""
	cache = os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache')
	return [os.path.join(APP_DIR, 'models', 'vr'), os.path.join(cache, 'OpenHomeKaraoke', 'models', 'vr')]


def find_weights(model):
	"""Path of a downloaded VR model, or None."""
	info = VR_MODELS[model]
	for d in weight_dirs():
		p = os.path.join(d, info['file'])
		if os.path.isfile(p) and os.path.getsize(p) == info['size']:
			return p
	return None


def is_downloading(model):
	info = VR_MODELS[model]
	return any(os.path.isfile(os.path.join(d, info['file'] + '.part')) for d in weight_dirs())


def model_status(model):
	"""'ready', 'downloading' or 'missing' (VR weights not downloaded yet). baseline/LR are always ready."""
	if model not in VR_MODELS:
		return 'ready'
	if find_weights(model):
		return 'ready'
	return 'downloading' if is_downloading(model) else 'missing'


def normalize(model, default=DEFAULT_MODEL):
	for m in ALL_MODELS:
		if str(model).lower() == m.lower():
			return m
	return default


def get_selected(song_dir):
	try:
		with open(os.path.join(song_dir, SELECTED_FILE), encoding='utf-8') as f:
			return normalize(f.read().strip())
	except OSError:
		return DEFAULT_MODEL


def set_selected(song_dir, model):
	model = normalize(model)
	try:
		with open(os.path.join(song_dir, SELECTED_FILE), 'w', encoding='utf-8') as f:
			f.write(model + '\n')
	except OSError:
		pass
	return model


def result_name(model, bn):
	"""Path of a result file relative to nonvocal/ or vocal/"""
	if model == 'baseline':
		return bn + '.m4a'
	if model == 'LR':
		return '.' + bn + '.m4a'
	return os.path.join(model, bn + '.m4a')


def result_path(song_dir, kind, model, bn):
	return os.path.join(song_dir, kind, result_name(model, bn))


def all_result_paths(song_dir, bn):
	"""Every possible result file of a song (for delete and rename), in a fixed order."""
	return [result_path(song_dir, kind, m, bn) for kind in SUBDIRS for m in ALL_MODELS]


def fallback_order(model):
	"""Models whose results may be played when `model` is selected, in order of preference.
	A neural-network model falls back to the other neural-network results; LR stands alone."""
	if model == 'LR':
		return ['LR']
	return [model] + [m for m in DNN_MODELS if m != model]


def find_result(song_dir, kind, model, bn):
	"""(path, model) of the best existing result for the selected model, or ('', None)."""
	for m in fallback_order(model):
		p = result_path(song_dir, kind, m, bn)
		if os.path.isfile(p):
			return p, m
	return '', None


def result_model(path):
	"""Which model made a result file (from its path), or None."""
	parts = path.replace('\\', '/').split('/')
	if len(parts) < 2:
		return None
	if parts[-1].startswith('.'):
		return 'LR'
	if parts[-2] in VR_MODELS:
		return parts[-2]
	if parts[-2] in SUBDIRS:
		return 'baseline'
	return None


def download_weights(model, base_url=WEIGHTS_URL, check=lambda: None, log=print):
	"""Download a VR model's weights (about 63 MB) and check its SHA-256. Returns the path.
	Raises an exception if the download fails or the file does not match."""
	import hashlib
	import requests
	info = VR_MODELS[model]
	url = base_url.rstrip('/') + '/' + info['file']
	last_err = None
	for d in weight_dirs():
		try:
			os.makedirs(d, exist_ok=True)
			part = os.path.join(d, info['file'] + '.part')
			open(part, 'ab').close()  # is the folder writable?
		except OSError as e:
			last_err = e
			continue
		log(f'Downloading the {model} vocal-separation model ({info["size"] / 1e6:.0f} MB) from {url} to {d} ...')
		h = hashlib.sha256()
		try:
			with requests.get(url, stream=True, timeout=30) as r:
				r.raise_for_status()
				with open(part, 'wb') as f:
					for chunk in r.iter_content(1 << 20):
						check()
						f.write(chunk)
						h.update(chunk)
			if h.hexdigest() != info['sha256']:
				raise ValueError(f'the downloaded {info["file"]} is damaged (SHA-256 does not match)')
			path = os.path.join(d, info['file'])
			os.replace(part, path)
			log(f'Downloaded {path}')
			return path
		finally:
			if os.path.exists(part):
				os.remove(part)
	raise OSError(f'no writable folder for the model weights: {last_err}')
