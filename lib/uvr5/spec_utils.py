# Multi-band spectrogram helpers, ported from RVC uvr5_pack/lib_v5/spec_utils.py and
# model_param_init.py (MIT, see LICENSE). Only what VR inference needs is kept.
import json
import math
import os

import librosa
import numpy as np

PARAM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modelparams')

# resampy (kaiser_*) and samplerate (sinc_*) are not dependencies of OpenHomeKaraoke; soxr comes with librosa
_RES_TYPE = {'kaiser_fast': 'soxr_hq', 'kaiser_best': 'soxr_vhq', 'sinc_fastest': 'soxr_hq',
             'sinc_medium': 'soxr_hq', 'sinc_best': 'soxr_vhq', 'scipy': 'fft'}


def resample(y, orig_sr, target_sr, res_type):
	if orig_sr == target_sr:
		return y
	return librosa.resample(y, orig_sr=orig_sr, target_sr=target_sr, res_type=_RES_TYPE.get(res_type, res_type))


class ModelParameters(object):
	def __init__(self, name='4band_v2'):
		def int_keys(d):
			return {int(k) if k.isdigit() else k: v for k, v in d}

		with open(os.path.join(PARAM_DIR, name + '.json'), encoding='utf-8') as f:
			self.param = json.load(f, object_pairs_hook=int_keys)
		for k in ['mid_side', 'mid_side_b', 'mid_side_b2', 'stereo_w', 'stereo_n', 'reverse']:
			self.param.setdefault(k, False)
		# All bands of the supported parameter sets advance at the same frame rate
		hops = {b['hl'] * self.param['sr'] / b['sr'] for b in self.param['band'].values()}
		if len(hops) != 1:
			raise ValueError(f'{name}: bands with different frame rates are not supported')
		self.hop = int(hops.pop())  # in samples at param['sr']


def wave_to_spectrogram(wave, hop_length, n_fft):
	"""wave: (2, n) -> complex spectrogram (2, n_fft//2+1, frames)"""
	return librosa.stft(np.asfortranarray(wave), n_fft=n_fft, hop_length=hop_length).astype(np.complex64)


def spectrogram_to_wave(spec, hop_length):
	return librosa.istft(np.asfortranarray(spec), hop_length=hop_length)


def combine_spectrograms(specs, mp):
	l = min([specs[i].shape[2] for i in specs])
	spec_c = np.zeros(shape=(2, mp.param['bins'] + 1, l), dtype=np.complex64)
	offset = 0
	bands_n = len(mp.param['band'])

	for d in range(1, bands_n + 1):
		bp = mp.param['band'][d]
		h = bp['crop_stop'] - bp['crop_start']
		spec_c[:, offset:offset + h, :l] = specs[d][:, bp['crop_start']:bp['crop_stop'], :l]
		offset += h

	if offset > mp.param['bins']:
		raise ValueError('Too much bins')

	# lowpass filter
	if mp.param['pre_filter_start'] > 0:
		if bands_n == 1:
			spec_c = fft_lp_filter(spec_c, mp.param['pre_filter_start'], mp.param['pre_filter_stop'])
		else:
			gp = 1
			for b in range(mp.param['pre_filter_start'] + 1, mp.param['pre_filter_stop']):
				g = math.pow(10, -(b - mp.param['pre_filter_start']) * (3.5 - gp) / 20.0)
				gp = g
				spec_c[:, b, :] *= g

	return np.asfortranarray(spec_c)


def cmb_spectrogram_to_wave(spec_m, mp, extra_bins_h=None, extra_bins=None):
	bands_n = len(mp.param['band'])
	offset = 0
	wave = None

	for d in range(1, bands_n + 1):
		bp = mp.param['band'][d]
		spec_s = np.zeros(shape=(2, bp['n_fft'] // 2 + 1, spec_m.shape[2]), dtype=np.complex64)
		h = bp['crop_stop'] - bp['crop_start']
		spec_s[:, bp['crop_start']:bp['crop_stop'], :] = spec_m[:, offset:offset + h, :]

		offset += h
		if d == bands_n:  # higher
			if extra_bins_h:  # high-end process (mirroring)
				max_bin = bp['n_fft'] // 2
				spec_s[:, max_bin - extra_bins_h:max_bin, :] = extra_bins[:, :extra_bins_h, :]
			if bp['hpf_start'] > 0:
				spec_s = fft_hp_filter(spec_s, bp['hpf_start'], bp['hpf_stop'] - 1)
			w = spectrogram_to_wave(spec_s, bp['hl'])
			wave = w if bands_n == 1 else np.add(wave, w)
		else:
			sr = mp.param['band'][d + 1]['sr']
			if d == 1:  # lower
				spec_s = fft_lp_filter(spec_s, bp['lpf_start'], bp['lpf_stop'])
				wave = resample(spectrogram_to_wave(spec_s, bp['hl']), bp['sr'], sr, 'sinc_fastest')
			else:  # mid
				spec_s = fft_hp_filter(spec_s, bp['hpf_start'], bp['hpf_stop'] - 1)
				spec_s = fft_lp_filter(spec_s, bp['lpf_start'], bp['lpf_stop'])
				wave2 = np.add(wave, spectrogram_to_wave(spec_s, bp['hl']))
				wave = resample(wave2, bp['sr'], sr, 'scipy')

	return wave  # (2, n), unlike the original which returned wave.T


def fft_lp_filter(spec, bin_start, bin_stop):
	g = 1.0
	for b in range(bin_start, bin_stop):
		g -= 1 / (bin_stop - bin_start)
		spec[:, b, :] = g * spec[:, b, :]
	spec[:, bin_stop:, :] *= 0
	return spec


def fft_hp_filter(spec, bin_start, bin_stop):
	g = 1.0
	for b in range(bin_start, bin_stop, -1):
		g -= 1 / (bin_start - bin_stop)
		spec[:, b, :] = g * spec[:, b, :]
	spec[:, 0:bin_stop + 1, :] *= 0
	return spec


def mirroring(spec_m, input_high_end, mp):
	"""The 'mirroring' high-end process: rebuild the bins above the model's range from the
	model output just below it, keeping the input's phase and never exceeding the input level."""
	pfs = mp.param['pre_filter_start']
	mirror = np.flip(np.abs(spec_m[:, pfs - 10 - input_high_end.shape[1]:pfs - 10, :]), 1)
	mirror = mirror * np.exp(1.0j * np.angle(input_high_end))
	return np.where(np.abs(input_high_end) <= np.abs(mirror), input_high_end, mirror)
