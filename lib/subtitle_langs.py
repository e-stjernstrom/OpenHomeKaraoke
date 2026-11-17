"""Subtitle languages: which ones to download and which embedded track to show.

Languages come as the app's language codes ('zh_CN', 'en_US', 'ja') or YouTube's subtitle codes
('zh-Hant', 'pt-BR'). Chinese is told apart by script: Simplified (zh-Hans, zh-CN, ...) and
Traditional (zh-Hant, zh-TW, zh-HK, ...).

- pick(): from the subtitles a video has, one per wanted language, in that order; if none of them
  exists, the video's own language.
- pick_track(): which embedded subtitle track to show. Files downloaded with a language list carry
  the tag ohk_subtitles and have their tracks in that order: track 0. Older files (all languages,
  alphabetical, so often Arabic first): the first track in a wanted language, else track 0.
"""
import json, subprocess

HANS = ('zh-hans', 'zh-cn', 'zh-sg', 'zh-my')
HANT = ('zh-hant', 'zh-tw', 'zh-hk', 'zh-mo')
LIMIT = 3  # at most this many languages per song
TAG = 'ohk_subtitles'  # mp4 tag written on download: the wanted languages, in order


def normalize(code):
	"""'zh_CN' -> 'zh-hans', 'zh-TW' -> 'zh-hant', 'en_US' -> 'en-us', 'JA' -> 'ja' ('' if empty)."""
	parts = (code or '').replace('_', '-').lower().split('-')
	if parts[0] == 'zh' and len(parts) > 1:
		tag = 'zh-' + parts[1]
		return 'zh-hant' if tag in HANT else 'zh-hans' if tag in HANS else 'zh'
	return '-'.join(p for p in parts if p)


def wanted_list(*codes):
	"""Normalized, without duplicates or empty ones, in order."""
	out = []
	for c in codes:
		n = normalize(c)
		if n and n not in out:
			out.append(n)
	return out


def _matches(want, keys):
	"""YouTube subtitle keys for one wanted language, best match first."""
	low = {k: k.lower() for k in keys}
	base = want.split('-')[0]
	if base == 'zh':
		group = HANT if want == 'zh-hant' else HANS if want == 'zh-hans' else HANS + HANT
		return [k for g in group for k in keys if low[k] == g or low[k].startswith(g + '-')] + \
		       [k for k in keys if low[k] == 'zh']
	return [k for k in keys if low[k] == want] + [k for k in keys if low[k] == base] + \
	       [k for k in keys if low[k].startswith(base + '-') and low[k] != want]


def pick(keys, wanted, original=''):
	"""Subtitle keys to download, in order (empty: none fits)."""
	keys = list(keys)
	chosen = []
	for w in wanted:
		for k in _matches(w, keys):
			if k not in chosen:
				chosen.append(k)
				break
		if len(chosen) >= LIMIT:
			break
	if not chosen and original:
		chosen = _matches(normalize(original), keys)[:1]
	return chosen


def youtube_dl_class(wanted):
	"""yt_dlp.YoutubeDL subclass that downloads the subtitles pick() chooses, looking at what each
	video has (the --sub-langs option alone cannot fall back to the video's own language)."""
	import re, yt_dlp

	class YoutubeDL(yt_dlp.YoutubeDL):
		def process_video_result(self, info_dict, download=True):
			if self.params.get('writesubtitles'):
				# the video's own language; YouTube also marks it in the automatic captions as xx-orig
				orig = info_dict.get('language') or next((k[:-5] for k in info_dict.get('automatic_captions') or {}
				                                          if k.endswith('-orig')), '')
				keys = pick((info_dict.get('subtitles') or {}).keys(), wanted, orig)
				self.to_screen(f'[info] Subtitles wanted: {", ".join(wanted) or "-"} (video language: {orig or "?"}); '
				               f'available: {", ".join(info_dict.get("subtitles") or {}) or "none"}; '
				               f'taking: {", ".join(keys) or "none"}')
				# exact keys, in this order (also the order they are embedded in)
				self.params['subtitleslangs'] = ['^' + re.escape(k) + '$' for k in keys] or ['(?!)']
			return super().process_video_result(info_dict, download)

	return YoutubeDL


def postprocessor_args(wanted):
	"""yt-dlp option that tags the file when the subtitles are embedded (see pick_track)."""
	return ['--postprocessor-args', 'EmbedSubtitle:-movflags +faststart+use_metadata_tags '
	        f'-metadata {TAG}={",".join(wanted) or "-"}']


def regex_list(wanted):
	"""--sub-langs value for an external yt-dlp (no fallback to the video's own language there)."""
	out = []
	for w in wanted:
		base = w.split('-')[0]
		group = HANT if w == 'zh-hant' else HANS if w == 'zh-hans' else ()
		out += [g + '.*' for g in group] or [w, base + '(-.*)?']
	return ','.join('(?i)' + o for o in out)


# --- playback ---

_SCRIPT_HINTS = {
	'zh-hans': ('simplified', 'china', 'mainland', 'singapore', '简体', '簡體'),
	'zh-hant': ('traditional', 'taiwan', 'hong kong', 'macao', 'macau', '繁體', '繁体'),
}


def _track_lang(stream):
	from yt_dlp.utils import ISO639Utils
	tags = stream.get('tags') or {}
	lang = (tags.get('language') or '').lower()
	return (ISO639Utils.long2short(lang) or lang) if len(lang) == 3 else lang, \
	       ' '.join([tags.get('title') or '', tags.get('handler_name') or '']).lower()


def _track_fits(want, stream):
	lang, title = _track_lang(stream)
	base = want.split('-')[0]
	if lang.split('-')[0] != base:
		return False
	if base == 'zh' and want in _SCRIPT_HINTS:
		other = 'zh-hant' if want == 'zh-hans' else 'zh-hans'
		return not any(h in title for h in _SCRIPT_HINTS[other])
	return True


def probe(path):
	"""(subtitle streams, the file's ohk_subtitles tag or '')."""
	try:
		out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries',
		                      f'stream=index:stream_tags=language,title,handler_name:format_tags={TAG}',
		                      '-of', 'json', path], capture_output=True, text=True, timeout=15).stdout
		info = json.loads(out or '{}')
		return info.get('streams', []), (info.get('format', {}).get('tags') or {}).get(TAG, '')
	except Exception:
		return [], ''


def pick_track(path, wanted):
	"""Index (among subtitle tracks) to show, or None if the file has no subtitles."""
	streams, tag = probe(path)
	if not streams:
		return None
	if tag:
		return 0
	for w in wanted:
		for i, s in enumerate(streams):
			if _track_fits(w, s):
				return i
	return 0
