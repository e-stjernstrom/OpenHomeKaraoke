# Ported from RVC uvr5_pack/lib_v5/nets_61968KB.py (MIT, see LICENSE). Attribute names are kept
# so that the published weights load unchanged.
import torch
import torch.nn.functional as F
from torch import nn

from . import layers


class BaseASPPNet(nn.Module):
	def __init__(self, nin, ch, dilations=(4, 8, 16)):
		super().__init__()
		self.enc1 = layers.Encoder(nin, ch, 3, 2, 1)
		self.enc2 = layers.Encoder(ch, ch * 2, 3, 2, 1)
		self.enc3 = layers.Encoder(ch * 2, ch * 4, 3, 2, 1)
		self.enc4 = layers.Encoder(ch * 4, ch * 8, 3, 2, 1)

		self.aspp = layers.ASPPModule(ch * 8, ch * 16, dilations)

		self.dec4 = layers.Decoder(ch * (8 + 16), ch * 8, 3, 1, 1)
		self.dec3 = layers.Decoder(ch * (4 + 8), ch * 4, 3, 1, 1)
		self.dec2 = layers.Decoder(ch * (2 + 4), ch * 2, 3, 1, 1)
		self.dec1 = layers.Decoder(ch * (1 + 2), ch, 3, 1, 1)

	def __call__(self, x):
		h, e1 = self.enc1(x)
		h, e2 = self.enc2(h)
		h, e3 = self.enc3(h)
		h, e4 = self.enc4(h)

		h = self.aspp(h)

		h = self.dec4(h, e4)
		h = self.dec3(h, e3)
		h = self.dec2(h, e2)
		h = self.dec1(h, e1)
		return h


class CascadedASPPNet(nn.Module):
	def __init__(self, n_fft):
		super().__init__()
		self.stg1_low_band_net = BaseASPPNet(2, 32)
		self.stg1_high_band_net = BaseASPPNet(2, 32)

		self.stg2_bridge = layers.Conv2DBNActiv(34, 16, 1, 1, 0)
		self.stg2_full_band_net = BaseASPPNet(16, 32)

		self.stg3_bridge = layers.Conv2DBNActiv(66, 32, 1, 1, 0)
		self.stg3_full_band_net = BaseASPPNet(32, 64)

		self.out = nn.Conv2d(64, 2, 1, bias=False)
		self.aux1_out = nn.Conv2d(32, 2, 1, bias=False)
		self.aux2_out = nn.Conv2d(32, 2, 1, bias=False)

		self.max_bin = n_fft // 2
		self.output_bin = n_fft // 2 + 1

		self.offset = 128

	def forward(self, x, aggressiveness=None):
		"""Inference only: returns the instrumental magnitude (mask * input)."""
		mix = x.detach()
		x = x.clone()[:, :, :self.max_bin]

		bandw = x.size()[2] // 2
		aux1 = torch.cat([self.stg1_low_band_net(x[:, :, :bandw]), self.stg1_high_band_net(x[:, :, bandw:])], dim=2)

		h = torch.cat([x, aux1], dim=1)
		aux2 = self.stg2_full_band_net(self.stg2_bridge(h))

		h = torch.cat([x, aux1, aux2], dim=1)
		h = self.stg3_full_band_net(self.stg3_bridge(h))

		mask = torch.sigmoid(self.out(h))
		mask = F.pad(input=mask, pad=(0, 0, 0, self.output_bin - mask.size()[2]), mode='replicate')

		if aggressiveness:
			sb = aggressiveness['split_bin']
			mask[:, :, :sb] = torch.pow(mask[:, :, :sb], 1 + aggressiveness['value'] / 3)
			mask[:, :, sb:] = torch.pow(mask[:, :, sb:], 1 + aggressiveness['value'])

		return mask * mix

	def predict(self, x_mag, aggressiveness=None):
		h = self.forward(x_mag, aggressiveness)
		if self.offset > 0:
			h = h[:, :, :, self.offset:-self.offset]
			assert h.size()[3] > 0
		return h
