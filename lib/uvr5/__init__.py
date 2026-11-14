"""VR-architecture vocal separation models of Ultimate Vocal Remover (UVR5), used for the
HP2_all_vocals, HP3_all_vocals and HP5_only_main_vocal weights.

The network code and the multi-band spectrogram helpers are ported from the uvr5_pack of
Retrieval-based-Voice-Conversion-WebUI (tag 2.2.231006, infer/lib/uvr5_pack/lib_v5), which comes
from UVR (github.com/Anjok07/ultimatevocalremovergui) and vocal-remover (github.com/tsurumeso/vocal-remover).
MIT licensed, see LICENSE in this folder.

Changes from the original: librosa >= 0.10 keyword arguments, no resampy/samplerate packages
needed (the input is decoded at 44100 Hz by ffmpeg, so the kaiser_fast load step is not used),
unused training-only code removed, and the uninitialised Nyquist bin in cmb_spectrogram_to_wave
is now zero.
"""
