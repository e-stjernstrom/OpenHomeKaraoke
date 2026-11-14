"""Browser cookies for yt-dlp (YouTube sign-in, to pass its "confirm you're not a bot" check).

- default_spec(): what --browser-cookies auto means on this machine.
- pin_profile(): "chrome" -> "chrome:Default" (the profile Chrome used last). Without a profile
  yt-dlp takes the most recently changed file named "Cookies" anywhere under Chrome's folder,
  which may be an old copy instead of the profile you are signed in with.
- check(): read the cookies once and say whether YouTube is signed in (cookie names only).
"""
import os, json, time

CHROME_ROOTS = {
	'osx': '~/Library/Application Support/Google/Chrome',
	'linux': '~/.config/google-chrome',
	'windows': '%LOCALAPPDATA%\\Google\\Chrome\\User Data',
}
OSX_FIREFOX = '~/Library/Application Support/Firefox/Profiles'
OSX_CHROME_APP = '/Applications/Google Chrome.app'

# text for the log when cookies cannot be read
HINTS = {
	'osx': "On macOS, give the app you start OpenHomeKaraoke from (e.g. Terminal) Full Disk Access: "
	       "System Settings > Privacy & Security > Full Disk Access, then quit and reopen it.",
}


def _path(p):
	return os.path.expanduser(os.path.expandvars(p))


def default_spec(platform):
	"""--cookies-from-browser value for 'auto' on macOS ('' if no browser found). Chrome is
	preferred over the default browser (often Safari, which needs extra permissions)."""
	if platform != 'osx':
		return ''
	if os.path.isdir(OSX_CHROME_APP) or os.path.isdir(_path(CHROME_ROOTS['osx'])):
		return 'chrome'
	if os.path.isdir(_path(OSX_FIREFOX)):
		return 'firefox'
	return 'safari'


def chrome_profile(platform):
	"""Folder name of the Chrome profile used last ('' if unknown or unreadable)."""
	root = _path(CHROME_ROOTS.get(platform, ''))
	try:
		with open(os.path.join(root, 'Local State'), encoding='utf-8') as f:
			prof = json.load(f).get('profile', {})
	except Exception:
		return ''
	for name in [prof.get('last_used')] + list(prof.get('info_cache', {})):
		if name and os.path.isdir(os.path.join(root, name)):
			return name
	return ''


def pin_profile(spec, platform):
	"""'chrome' (or 'chrome+keyring') -> 'chrome:<profile>'. Anything else is returned unchanged."""
	browser = spec.split(':', 1)[0]
	if ':' in spec or browser.split('+', 1)[0].lower() != 'chrome':
		return spec
	profile = chrome_profile(platform)
	return f'{browser}:{profile}' if profile else spec


class _Quiet:
	def debug(self, msg, *a, **k): pass
	def info(self, msg, *a, **k): pass
	def warning(self, msg, *a, **k): pass
	def error(self, msg, *a, **k): pass
	def progress_bar(self, *a, **k): return None


def check(cookies_opt):
	"""Read the cookies of a yt-dlp cookie option list. Returns (count, signed_in, error);
	error is '' when they could be read. Only cookie names are looked at."""
	if not cookies_opt:
		return 0, False, ''
	try:
		if cookies_opt[0] == '--cookies':
			import http.cookiejar
			jar = http.cookiejar.MozillaCookieJar(cookies_opt[1])
			jar.load(ignore_discard=True, ignore_expires=True)
		else:
			import yt_dlp
			from yt_dlp.cookies import extract_cookies_from_browser
			browser, profile, keyring, container = \
				yt_dlp.parse_options(list(cookies_opt)).ydl_opts['cookiesfrombrowser']
			jar = extract_cookies_from_browser(browser, profile, _Quiet(), keyring=keyring, container=container)
	except Exception as e:
		return 0, False, f'{type(e).__name__}: {e}'
	cookies = list(jar)
	signed_in = any(c.name == 'LOGIN_INFO' and c.domain.endswith('youtube.com') for c in cookies)
	return len(cookies), signed_in, ''


_last_check = (0.0, None)


def unreadable(cookies_opt, max_age=60):
	"""The reason the cookies cannot be read, or '' if they can (cached for max_age seconds)."""
	global _last_check
	t, result = _last_check
	if result is None or time.time() - t > max_age:
		result = check(cookies_opt)[2]
		_last_check = (time.time(), result)
	return result
