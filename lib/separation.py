"""Separation backends for vocal_splitter.py.

A backend turns a piece of a song into an instrumental and a vocal track. vocal_splitter.py
feeds it the song segment by segment, so every backend describes how it may be cut:

	sr          sample rate the backend expects (the song is decoded at this rate)
	unit        segment starts and context margins are multiples of this many samples. The
	            networks work on a fixed grid of time windows and their output depends on where
	            that grid falls; cutting on the grid gives the same result as one whole-song run.
	margin      samples of context separated together with each segment and then discarded
	xfade       samples by which neighbouring segments overlap and are cross-faded
	peak(x)     the level the backend normalises by, measured on a piece of the song; the whole
	            song's peak is the maximum over all pieces
	separate(x, scale) -> (instrumental, vocals), both shaped like x (2, n)
	to(device)  move the network to another torch device

Backends: BaselineBackend (the original CascadedNet in models/baseline.pth) and VRBackend (UVR
VR models, lib/uvr5).
"""

import numpy as np
import torch
import librosa

from lib import dataset, nets, spec_utils


def load_state(path):
	try:
		return torch.load(path, map_location='cpu', weights_only=True)
	except TypeError:  # torch < 1.13 has no weights_only
		return torch.load(path, map_location='cpu')


def _fit(wave, n):
	"""Cut or zero-pad (channels, m) to (channels, n)."""
	if wave.shape[1] >= n:
		return wave[:, :n]
	return np.pad(wave, ((0, 0), (0, n - wave.shape[1])))


class Separator(object):
	"""Mask inference of the baseline CascadedNet on a spectrogram."""

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

		return self._postprocess(X_spec, mask)

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

		return self._postprocess(X_spec, mask)


class BaselineBackend(object):
	name = 'baseline'

	def __init__(self, path, device, sr=44100, n_fft=2048, hop_length=1024, cropsize=256, batchsize=4,
	             postprocess=False, tta=False):
		self.path, self.sr, self.n_fft, self.hop = path, sr, n_fft, hop_length
		self.cropsize, self.batchsize, self.postprocess, self.tta = cropsize, batchsize, postprocess, tta
		self.model = nets.CascadedNet(n_fft, hop_length, 32, 128, True)
		self.model.load_state_dict(load_state(path))
		self.to(device)
		roi_size = dataset.make_padding(1, cropsize, self.model.offset)[2]
		self.unit = roi_size * hop_length
		self.margin = self.unit * int(np.ceil((self.model.offset + 4) / roi_size))
		self.xfade = 4 * hop_length

	def to(self, device):
		self.device = device
		self.model = self.model.to(device)
		return self

	def peak(self, x):
		return float(np.abs(spec_utils.wave_to_spectrogram(x, self.hop, self.n_fft)).max())

	def separate(self, x, scale=None):
		X_spec = spec_utils.wave_to_spectrogram(x, self.hop, self.n_fft)
		sp = Separator(self.model, self.device, self.batchsize, self.cropsize, self.postprocess)
		y_spec, v_spec = (sp.separate_tta if self.tta else sp.separate)(X_spec, scale)
		n = x.shape[1]
		return tuple(np.asarray([librosa.istft(s[c], hop_length=self.hop, length=n) for c in range(2)])
		             for s in (y_spec, v_spec))


class VRBackend(object):
	"""UVR VR-architecture models (HP2_all_vocals, HP3_all_vocals, HP5_only_main_vocal), as run by
	UVR5 / RVC with their defaults: 4band_v2 parameters, window 512, aggressiveness 10, high-end
	'mirroring', no post-processing."""

	window_size = 512

	def __init__(self, name, path, device, swap=False, aggressiveness=10, batchsize=1, tta=False):
		from lib.uvr5 import nets as vr_nets, spec_utils as vr_spec
		self.vr_spec = vr_spec
		self.name, self.path, self.swap, self.batchsize, self.tta = name, path, swap, batchsize, tta
		self.mp = vr_spec.ModelParameters('4band_v2')
		self.sr = self.mp.param['sr']
		self.model = vr_nets.CascadedASPPNet(self.mp.param['bins'] * 2)
		self.model.load_state_dict(load_state(path))
		self.model.eval()
		self.to(device)
		self.aggressiveness = {'value': aggressiveness / 100, 'split_bin': self.mp.param['band'][1]['crop_stop']}
		offset = self.model.offset
		roi_size = self.window_size - 2 * offset
		self.unit = roi_size * self.mp.hop
		# The model sees `offset` frames on each side; the band filters and the resampling between
		# bands need a little more, so keep a whole grid unit plus another one.
		self.margin = self.unit * (int(np.ceil((offset + 4) / roi_size)) + 1)
		self.xfade = 4 * self.mp.hop

	def to(self, device):
		self.device = device
		self.model = self.model.to(device)
		return self

	def _spectrogram(self, x):
		"""Multi-band spectrogram (as AudioPre._path_audio_ in RVC) and the input's high end."""
		mp, vs = self.mp, self.vr_spec
		bands = mp.param['band']
		bands_n = len(bands)
		waves, specs = {}, {}
		high_end_h = high_end = None
		for d in range(bands_n, 0, -1):
			bp = bands[d]
			if d == bands_n:
				waves[d] = np.asarray(x, dtype=np.float32)
			else:
				waves[d] = vs.resample(waves[d + 1], bands[d + 1]['sr'], bp['sr'], bp['res_type'])
			specs[d] = vs.wave_to_spectrogram(waves[d], bp['hl'], bp['n_fft'])
			if d == bands_n:
				high_end_h = (bp['n_fft'] // 2 - bp['crop_stop']) + (mp.param['pre_filter_stop'] - mp.param['pre_filter_start'])
				high_end = specs[d][:, bp['n_fft'] // 2 - high_end_h:bp['n_fft'] // 2, :]
		return vs.combine_spectrograms(specs, mp), high_end_h, high_end

	def peak(self, x):
		return float(np.abs(self._spectrogram(x)[0]).max())

	def _execute(self, X_mag_pad, roi_size, n_window):
		preds = []
		with torch.no_grad():
			for i in range(0, n_window, self.batchsize):
				batch = np.asarray([X_mag_pad[:, :, j * roi_size:j * roi_size + self.window_size]
				                    for j in range(i, min(i + self.batchsize, n_window))])
				pred = self.model.predict(torch.from_numpy(batch).to(self.device), self.aggressiveness)
				preds.append(np.concatenate(pred.detach().cpu().numpy(), axis=2))
		return np.concatenate(preds, axis=2)

	def _inference(self, X_mag, scale):
		"""Instrumental magnitude, as utils.inference in RVC (scale: the whole song's peak)."""
		coef = scale or float(X_mag.max()) or 1.0
		X_mag_pre = (X_mag / coef).astype(np.float32)
		n_frame = X_mag_pre.shape[2]
		pad_l, pad_r, roi_size = dataset.make_padding(n_frame, self.window_size, self.model.offset)
		n_window = int(np.ceil(n_frame / roi_size))
		X_mag_pad = np.pad(X_mag_pre, ((0, 0), (0, 0), (pad_l, pad_r)), mode='constant')
		pred = self._execute(X_mag_pad, roi_size, n_window)[:, :, :n_frame]
		if self.tta:
			pad_l += roi_size // 2
			pad_r += roi_size // 2
			X_mag_pad = np.pad(X_mag_pre, ((0, 0), (0, 0), (pad_l, pad_r)), mode='constant')
			pred_tta = self._execute(X_mag_pad, roi_size, n_window + 1)[:, :, roi_size // 2:][:, :, :n_frame]
			pred = (pred + pred_tta) * 0.5
		return pred * coef

	def separate(self, x, scale=None):
		vs, mp = self.vr_spec, self.mp
		X_spec, high_end_h, high_end = self._spectrogram(x)
		X_mag = np.abs(X_spec)
		pred = self._inference(X_mag, scale)
		y_spec = pred * np.exp(1.j * np.angle(X_spec))
		v_spec = X_spec - y_spec
		n = x.shape[1]
		out = []
		for spec in (y_spec, v_spec):
			extra = vs.mirroring(spec, high_end, mp)
			out.append(_fit(np.asarray(vs.cmb_spectrogram_to_wave(spec, mp, high_end_h, extra), dtype=np.float32), n))
		inst, voc = out
		return (voc, inst) if self.swap else (inst, voc)
