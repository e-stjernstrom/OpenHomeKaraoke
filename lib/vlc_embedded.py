"""VLC inside the pygame window on macOS.

On Linux and Windows a separate VLC process draws into the pygame window (--drawable-xid /
--drawable-hwnd). macOS has no such option: another process cannot draw into our window, so VLC
opened its own window. Here libvlc runs inside this process and draws into the pygame window's
NSView (libvlc_media_player_set_nsobject).

EmbeddedVLCClient keeps the interface of VLCClient: command() takes the same commands as VLC's
HTTP interface ("pl_pause", "volume&val=+10", ...) and returns the same kind of status XML, so
karaoke.py does not need to know which one it talks to. Each song gets a new libvlc instance with
the same options the VLC process got, like the one-process-per-song VLCClient.

Only ctypes is used (no python-vlc): libvlc comes from the installed VLC.app.
"""
import os, time, ctypes, logging, threading
from types import SimpleNamespace
from html import escape

from lib.vlcclient import VLCClient

# libvlc_state_t
NOTHING, OPENING, BUFFERING, PLAYING, PAUSED, STOPPED, ENDED, ERROR = range(8)
TRACK_TYPES = {0: 'Audio', 1: 'Video', 2: 'Subtitle'}
HTTP_VOLUME_100 = 256  # VLC's HTTP interface reports volume 256 for 100 %

# Options of the VLC process that make no sense in-process (window, HTTP interface, mac GUI).
# The value says how many arguments follow the option.
DROP_OPTIONS = {
	'--fullscreen': 0, '--play-and-exit': 0, '--no-embedded-video': 0, '--video-on-top': 0,
	'--volume-save': 0, '--extraintf': 1, '--http-port': 1, '--http-password': 1, '--intf': 1,
	'--no-macosx-video-autoresize': 0, '--no-macosx-show-playback-buttons': 0,
	'--no-macosx-show-playmode-buttons': 0, '--no-macosx-interfacestyle': 0,
	'--macosx-nativefullscreenmode': 0, '--macosx-continue-playback=2': 0,
}


class _Track(ctypes.Structure):
	# start of libvlc_media_track_t (VLC 3); only i_type is read
	_fields_ = [('codec', ctypes.c_uint32), ('original_fourcc', ctypes.c_uint32),
	            ('id', ctypes.c_int), ('type', ctypes.c_int)]


def libvlc_dirs(vlc_path):
	"""Folders that may hold libvlc.dylib, for the VLC given by --vlc-path and the default VLC.app."""
	dirs = []
	if vlc_path:
		real = os.path.realpath(vlc_path)
		dirs.append(os.path.join(os.path.dirname(real), 'lib'))
		if os.path.isfile(real) and os.path.getsize(real) < 4096:
			# Homebrew's /opt/homebrew/bin/vlc is a small script that runs VLC.app
			try:
				for word in open(real, errors='ignore').read().split():
					word = word.strip('"\'')
					if word.endswith('/MacOS/VLC'):
						dirs.append(os.path.join(os.path.dirname(word), 'lib'))
			except OSError:
				pass
	dirs.append('/Applications/VLC.app/Contents/MacOS/lib')
	dirs.append(os.path.expanduser('~/Applications/VLC.app/Contents/MacOS/lib'))
	return dirs


def load_libvlc(vlc_path):
	for d in libvlc_dirs(vlc_path):
		if not os.path.isfile(os.path.join(d, 'libvlc.dylib')):
			continue
		plugins = os.path.join(os.path.dirname(d), 'plugins')
		if os.path.isdir(plugins):
			os.environ.setdefault('VLC_PLUGIN_PATH', plugins)
		core = os.path.join(d, 'libvlccore.dylib')
		if os.path.isfile(core):
			ctypes.CDLL(core)
		lib = ctypes.CDLL(os.path.join(d, 'libvlc.dylib'))
		_declare(lib)
		return lib
	raise OSError('libvlc.dylib not found in: ' + ', '.join(libvlc_dirs(vlc_path)))


def _declare(lib):
	P, I, I64, F = ctypes.c_void_p, ctypes.c_int, ctypes.c_int64, ctypes.c_float
	sigs = {
		'libvlc_new': (P, [I, ctypes.POINTER(ctypes.c_char_p)]),
		'libvlc_release': (None, [P]),
		'libvlc_errmsg': (ctypes.c_char_p, []),
		'libvlc_media_new_path': (P, [P, ctypes.c_char_p]),
		'libvlc_media_release': (None, [P]),
		'libvlc_media_tracks_get': (ctypes.c_uint, [P, ctypes.POINTER(ctypes.POINTER(ctypes.POINTER(_Track)))]),
		'libvlc_media_tracks_release': (None, [ctypes.POINTER(ctypes.POINTER(_Track)), ctypes.c_uint]),
		'libvlc_media_player_new_from_media': (P, [P]),
		'libvlc_media_player_release': (None, [P]),
		'libvlc_media_player_set_nsobject': (None, [P, P]),
		'libvlc_media_player_play': (I, [P]),
		'libvlc_media_player_stop': (None, [P]),
		'libvlc_media_player_pause': (None, [P]),
		'libvlc_media_player_set_pause': (None, [P, I]),
		'libvlc_media_player_get_state': (I, [P]),
		'libvlc_media_player_get_time': (I64, [P]),
		'libvlc_media_player_set_time': (None, [P, I64]),
		'libvlc_media_player_get_length': (I64, [P]),
		'libvlc_media_player_get_position': (F, [P]),
		'libvlc_media_player_get_rate': (F, [P]),
		'libvlc_media_player_set_rate': (I, [P, F]),
		'libvlc_audio_get_volume': (I, [P]),
		'libvlc_audio_set_volume': (I, [P, I]),
		'libvlc_audio_get_delay': (I64, [P]),
		'libvlc_audio_set_delay': (I, [P, I64]),
		'libvlc_video_get_spu_delay': (I64, [P]),
		'libvlc_video_set_spu_delay': (I, [P, I64]),
	}
	for name, (res, args) in sigs.items():
		fn = getattr(lib, name)
		fn.restype, fn.argtypes = res, args


def nsview_of_pygame_window(wm_info):
	"""The content NSView of the pygame (SDL2) window, from pygame.display.get_wm_info()."""
	window = wm_info.get('window')
	if window is None:
		return None
	if not isinstance(window, int):  # pygame 2 returns the NSWindow* in a capsule
		get = ctypes.pythonapi.PyCapsule_GetPointer
		get.restype, get.argtypes = ctypes.c_void_p, [ctypes.py_object, ctypes.c_char_p]
		window = get(window, b'window')
	objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
	objc.sel_registerName.restype = ctypes.c_void_p
	objc.sel_registerName.argtypes = [ctypes.c_char_p]
	objc.objc_msgSend.restype = ctypes.c_void_p
	objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
	return objc.objc_msgSend(window, objc.sel_registerName(b'contentView')) or None


def _number(text, default=0.0):
	try:
		return float(text)
	except (TypeError, ValueError):
		return default


class EmbeddedVLCClient(VLCClient):

	def __init__(self, port = 5002, path = None, qrcode = None, url = None, get_view = None):
		super().__init__(port = port, path = path, qrcode = qrcode, url = url)
		self.lib = load_libvlc(self.path)
		self.get_view = get_view  # returns the NSView to draw into, or None
		self.args = []
		skip = 0
		for a in self.cmd_base[1:]:
			if skip:
				skip -= 1
			elif a in DROP_OPTIONS:
				skip = DROP_OPTIONS[a]
			else:
				self.args.append(a)
		self.instance = self.media = self.player = None
		self.file_path = None
		self.wanted_volume = None  # applied as soon as VLC has an audio output
		self.lib_lock = threading.RLock()  # guards the libvlc objects against release while in use
		logging.info("VLC runs inside the pygame window (libvlc). Options: " + " ".join(self.args))

	# ---------------------------------------------------------------- start / stop

	def play_file(self, file_path, volume, params = []):
		# A web thread starting a song makes VLC wait for the main thread (it creates the video
		# view there). So the main thread must keep pumping events while it waits for the lock.
		if threading.current_thread() is threading.main_thread():
			while not self.play_lock.acquire(timeout = 0.05):
				self._wait(0)
			try:
				return self._play_file(file_path, volume, params)
			finally:
				self.play_lock.release()
		with self.play_lock:
			return self._play_file(file_path, volume, params)

	def _play_file(self, file_path, volume, params = []):
		try:
			file_path = self.process_file(file_path)
			self.is_transposing = True
			self.kill()
			args = [a.encode() for a in self.args + list(params)]
			logging.info("libvlc options: %s, file: %s" % (self.args + list(params), file_path))
			lib = self.lib
			instance = lib.libvlc_new(len(args), (ctypes.c_char_p * len(args))(*args))
			if not instance:
				raise Exception("libvlc could not start: %s" % lib.libvlc_errmsg())
			media = lib.libvlc_media_new_path(instance, file_path.encode())
			player = lib.libvlc_media_player_new_from_media(media) if media else None
			if not player:
				if media:
					lib.libvlc_media_release(media)
				lib.libvlc_release(instance)
				raise Exception("libvlc could not open " + file_path)
			view = self.get_view() if self.get_view else None
			if view:
				lib.libvlc_media_player_set_nsobject(player, view)
			with self.lib_lock:
				self.instance, self.media, self.player = instance, media, player
				self.file_path = file_path
				self.wanted_volume = round(volume) if volume else None
			lib.libvlc_media_player_play(player)

			# wait until VLC reports the streams (same rule as for the VLC process)
			deadline = time.time() + self.startup_timeout
			while True:
				self._wait(0.1)
				with self.lib_lock:
					if self.player is not player:
						raise Exception("stopped during startup")
					state = lib.libvlc_media_player_get_state(player)
					ready = state in (PLAYING, PAUSED) and self._track_types()
				if state in (ENDED, ERROR, STOPPED):
					raise Exception(f"VLC stopped during startup (state {state})")
				if ready:
					break
				if time.time() > deadline:
					raise Exception(f"VLC did not report the media within {self.startup_timeout}s")

			# the volume can only be set once there is an audio output
			deadline = time.time() + 5
			while time.time() < deadline:
				with self.lib_lock:
					if self.player is not player or self._apply_volume():
						break
				self._wait(0.1)
			with self.lib_lock:
				if self.player is not player:
					raise Exception("stopped during startup")
				xml = self._status_xml()
			self.last_status_text = xml
			self.is_transposing = False
			return xml

		except Exception as e:
			logging.error("Playing file failed: " + str(e))
			self.kill()
			self.is_transposing = False
			return None

	def kill(self):
		with self.lib_lock:
			instance, media, player = self.instance, self.media, self.player
			self.instance = self.media = self.player = None
		# outside the lock: stopping waits for the main thread (VLC removes its video view there)
		if player:
			logging.debug("Stopping libvlc player")
			self.lib.libvlc_media_player_stop(player)
			self.lib.libvlc_media_player_release(player)
		if media:
			self.lib.libvlc_media_release(media)
		if instance:
			self.lib.libvlc_release(instance)

	def is_running(self):
		if self.is_transposing:
			return True
		with self.lib_lock:
			if self.player is None:
				return False
			state = self.lib.libvlc_media_player_get_state(self.player)
		if state in (ENDED, ERROR, STOPPED):
			self.kill()  # like --play-and-exit
			return False
		return True

	def get_status(self):
		# in-process status is cheap, so always read it fresh (no 1 s cache as for HTTP)
		if self.is_transposing:
			return self.last_status_text
		self.command()
		return self.last_status_text

	# ---------------------------------------------------------------- HTTP-style commands

	def command(self, command = '', save_status=True):
		self.last_status_time = time.time()
		with self.lib_lock:
			if self.player is None:
				return SimpleNamespace(text = self.last_status_text, status_code = 500)
			try:
				self._run_command(command)
				xml = self._status_xml()
			except Exception as e:
				logging.error(f"VLC command '{command}' failed: {type(e).__name__}: {e}")
				return SimpleNamespace(text = self.last_status_text, status_code = 500)
		if command == 'pl_stop':
			self.kill()
		if self.is_transposing and save_status:
			return SimpleNamespace(text = self.last_status_text, status_code = 200)
		if save_status:
			self.last_status_text = xml
			os.K.has_video = "<info name='Type'>Video</info>" in xml
		if not os.K.now_playing and self.file_path:
			os.K.now_playing_filename = self.file_path
			os.K.now_playing = os.K.filename_from_path(self.file_path)
		return SimpleNamespace(text = xml, status_code = 200)

	def _run_command(self, command):
		lib, mp = self.lib, self.player
		name, _, rest = command.partition('&')
		val = rest[4:] if rest.startswith('val=') else ''
		if name == 'pl_pause':
			lib.libvlc_media_player_pause(mp)  # toggles, like the HTTP interface
		elif name == 'pl_play':
			lib.libvlc_media_player_set_pause(mp, 0)
		elif name == 'seek':
			length = lib.libvlc_media_player_get_length(mp) / 1000
			now = lib.libvlc_media_player_get_time(mp) / 1000
			if val.endswith('%'):
				target = length * _number(val[:-1]) / 100
			elif val[:1] in '+-' and val:
				target = now + _number(val)
			else:
				target = _number(val)
			lib.libvlc_media_player_set_time(mp, int(max(0, target) * 1000))
		elif name == 'volume':
			now = self._http_volume()
			if val.endswith('%'):
				target = HTTP_VOLUME_100 * _number(val[:-1]) / 100
			elif val[:1] in '+-' and val:
				target = now + _number(val)
			else:
				target = _number(val, now)
			self.wanted_volume = int(round(min(max(target, 0), 2 * HTTP_VOLUME_100)))
			self._apply_volume()
		elif name == 'rate':
			lib.libvlc_media_player_set_rate(mp, _number(val, 1.0))
		elif name == 'audiodelay':
			lib.libvlc_audio_set_delay(mp, int(_number(val) * 1e6))
		elif name == 'subdelay':
			lib.libvlc_video_set_spu_delay(mp, int(_number(val) * 1e6))
		elif name in ('', 'pl_stop'):
			pass
		else:
			logging.warning(f"Unknown VLC command ignored: {command}")

	# ---------------------------------------------------------------- status

	def _apply_volume(self):
		"""Set the wanted volume. True when VLC took it."""
		if self.wanted_volume is None or self.player is None:
			return True
		percent = round(self.wanted_volume * 100 / HTTP_VOLUME_100)
		if self.lib.libvlc_audio_get_volume(self.player) == percent:
			return True
		return self.lib.libvlc_audio_set_volume(self.player, percent) == 0 and \
		       self.lib.libvlc_audio_get_volume(self.player) == percent

	def _http_volume(self):
		percent = self.lib.libvlc_audio_get_volume(self.player)
		if percent < 0:  # no audio output yet
			return self.wanted_volume if self.wanted_volume is not None else HTTP_VOLUME_100
		return int(round(percent * HTTP_VOLUME_100 / 100))

	def _track_types(self):
		if not self.media:
			return []
		tracks = ctypes.POINTER(ctypes.POINTER(_Track))()
		n = self.lib.libvlc_media_tracks_get(self.media, ctypes.byref(tracks))
		try:
			return [TRACK_TYPES.get(tracks[i].contents.type, 'Unknown') for i in range(n)]
		finally:
			if n:
				self.lib.libvlc_media_tracks_release(tracks, n)

	def _status_xml(self):
		"""Status in the form of VLC's /requests/status.xml (only the fields karaoke.py reads)."""
		lib, mp = self.lib, self.player
		if self.wanted_volume is not None:
			self._apply_volume()
		state = {PLAYING: 'playing', PAUSED: 'paused', OPENING: 'playing',
		         BUFFERING: 'playing'}.get(lib.libvlc_media_player_get_state(mp), 'stopped')
		streams = ''.join(f"<category name='Stream {i}'><info name='Type'>{t}</info></category>"
		                  for i, t in enumerate(self._track_types()))
		return (
			"<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\" ?>\n<root>"
			f"<volume>{self._http_volume()}</volume>"
			f"<state>{state}</state>"
			f"<time>{max(0, lib.libvlc_media_player_get_time(mp)) // 1000}</time>"
			f"<length>{max(0, lib.libvlc_media_player_get_length(mp)) // 1000}</length>"
			f"<position>{max(0.0, lib.libvlc_media_player_get_position(mp))}</position>"
			f"<rate>{lib.libvlc_media_player_get_rate(mp)}</rate>"
			f"<audiodelay>{lib.libvlc_audio_get_delay(mp) / 1e6}</audiodelay>"
			f"<subtitledelay>{lib.libvlc_video_get_spu_delay(mp) / 1e6}</subtitledelay>"
			"<information><category name='meta'>"
			f"<info name='filename'>{escape(os.path.basename(self.file_path or ''))}</info></category>"
			f"{streams}</information></root>"
		)
