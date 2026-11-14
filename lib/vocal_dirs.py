import logging, os

# The vocal splitter writes its results to <songs>/nonvocal and <songs>/vocal and only works on a
# song folder that has at least one of them. Playback only looks for the current song's file there.
# The folders are created automatically the first time a song folder is used. A marker file records
# that this happened, so folders the user deleted on purpose do not come back on the next start.
MARKER = '.vocal_dirs_initialized'
SUBDIRS = ('nonvocal', 'vocal')
DISABLED_MARKER = '.vocal_split_disabled'	# see is_split_disabled() below


def ensure_vocal_dirs(song_dir):
	"""Create <song_dir>/nonvocal and <song_dir>/vocal on first use. Returns True if it created anything."""
	song_dir = (song_dir or '').rstrip('/\\')
	if not song_dir or not os.path.isdir(song_dir):
		return False
	marker = os.path.join(song_dir, MARKER)
	if os.path.exists(marker):
		return False
	created = False
	try:
		for sub in SUBDIRS:
			path = os.path.join(song_dir, sub)
			if not os.path.isdir(path):
				os.makedirs(path)
				created = True
		with open(marker, 'w') as fp:
			fp.write('nonvocal/ and vocal/ were created automatically on first run.\n'
			         'They will not be created again while this file exists. To turn background '
			         'vocal splitting off without losing finished tracks, use the switch on the '
			         'Info page (it creates ' + DISABLED_MARKER + ').\n')
	except OSError as e:
		logging.warning(f'Could not create the vocal/nonvocal folders in {song_dir}: {e}')
		return False
	if created:
		logging.info(f'Created vocal/nonvocal folders in {song_dir} (first run)')
	return created


# Off switch for the background vocal splitter. When this file exists in the song folder,
# the splitter leaves the library alone; results that already exist in nonvocal/ and vocal/
# can still be played. Set from the web UI (Info page) or by creating the file by hand.


def is_split_disabled(song_dir):
	return bool(song_dir) and os.path.exists(os.path.join(song_dir.rstrip('/\\'), DISABLED_MARKER))


def set_split_enabled(song_dir, enabled):
	"""Turn background vocal splitting on or off for a song folder. Turning it on also
	re-creates nonvocal/ and vocal/ in case the user deleted them."""
	song_dir = song_dir.rstrip('/\\')
	marker = os.path.join(song_dir, DISABLED_MARKER)
	try:
		if enabled:
			if os.path.exists(marker):
				os.remove(marker)
			for sub in SUBDIRS:
				os.makedirs(os.path.join(song_dir, sub), exist_ok=True)
		else:
			with open(marker, 'w') as fp:
				fp.write('Background vocal splitting is turned off for this folder. '
				         'Delete this file (or use the switch on the Info page) to turn it on again.\n')
		return True
	except OSError as e:
		logging.warning(f'Could not turn vocal splitting {"on" if enabled else "off"} in {song_dir}: {e}')
		return False
