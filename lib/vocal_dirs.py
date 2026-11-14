import logging, os

# The vocal splitter only works on a song folder that has a nonvocal/ and/or vocal/ sub-folder,
# and the web UI only enables the instrumental/vocal switch when both exist.
# They are created automatically the first time a song folder is used. A marker file records
# that this happened, so a user who deletes the folders to turn vocal splitting off
# does not see them come back on the next start.
MARKER = '.vocal_dirs_initialized'
SUBDIRS = ('nonvocal', 'vocal')


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
			         'To turn vocal splitting off, delete those folders. '
			         'They will not be created again while this file exists.\n')
	except OSError as e:
		logging.warning(f'Could not create the vocal/nonvocal folders in {song_dir}: {e}')
		return False
	if created:
		logging.info(f'Created vocal/nonvocal folders in {song_dir} (first run)')
	return created
