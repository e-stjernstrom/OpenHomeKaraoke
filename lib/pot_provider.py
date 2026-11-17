"""bgutil PO token provider for YouTube downloads (see scripts/setup_bgutil.py).

The yt-dlp plugin (pip bgutil-ytdlp-pot-provider) asks a local HTTP server for tokens, by default at
127.0.0.1:4416. start() runs that server from third_party/bgutil when it is installed, or uses one
that already answers there (e.g. left over from a crash, or a Docker container).
"""
import atexit, importlib.util, json, os, shutil, subprocess, time, urllib.request

PORT = 4416
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_JS = os.path.join(ROOT, 'third_party', 'bgutil', 'server', 'build', 'main.js')
SETUP = 'python scripts/setup_bgutil.py'
_proc = None  # the server started here, if any


def plugin_installed():
	try:
		return importlib.util.find_spec('yt_dlp_plugins.extractor.getpot_bgutil_http') is not None
	except ModuleNotFoundError:
		return False


def ping(port=PORT, timeout=1.0):
	"""Version of the bgutil server answering on this port, or '' if none."""
	try:
		with urllib.request.urlopen(f'http://127.0.0.1:{port}/ping', timeout=timeout) as r:
			return str(json.load(r).get('version', '?'))
	except Exception:
		return ''


def start(log_path, port=PORT, wait=15):
	"""Make sure a bgutil server runs. Returns (ok, message for the startup log)."""
	global _proc
	if not plugin_installed():
		return False, f'not installed (optional; to add it: {SETUP})'
	version = ping(port)
	if version:
		return True, f'bgutil {version} already running on 127.0.0.1:{port}'
	node = shutil.which('node')
	if not os.path.isfile(SERVER_JS):
		return False, f'bgutil plugin found but not its server, run: {SETUP}'
	if not node:
		return False, 'bgutil needs Node.js 22 or newer, node was not found'
	with open(log_path, 'w') as log:
		proc = subprocess.Popen([node, SERVER_JS, '-p', str(port), '-H', '127.0.0.1'], cwd=os.path.dirname(SERVER_JS),
		                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
	_proc = proc
	atexit.register(stop)
	deadline = time.time() + wait
	while time.time() < deadline:
		if proc.poll() is not None:
			return False, f'bgutil server exited (code {proc.returncode}), see {log_path}'
		version = ping(port, 0.5)
		if version:
			return True, f'bgutil {version} started on 127.0.0.1:{port} (pid {proc.pid}), log: {log_path}'
		time.sleep(0.3)
	return False, f'bgutil server did not answer within {wait}s, see {log_path}'


def stop():
	"""Stop the server started by start() (app.py ends with os._exit, which skips atexit)."""
	global _proc
	proc, _proc = _proc, None
	if proc is not None and proc.poll() is None:
		proc.terminate()
		try:
			proc.wait(5)
		except subprocess.TimeoutExpired:
			proc.kill()
