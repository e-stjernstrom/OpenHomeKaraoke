#!/usr/bin/env python3

import argparse, datetime, json, locale, os, sys, io, shutil
import subprocess, threading, time, traceback, webbrowser
from functools import wraps

import psutil, tempfile
from unidecode import unidecode
from flask import *
from flask.logging import logging
from pydub import AudioSegment as AudSeg
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from karaoke import *
from constants import VERSION
from collections import defaultdict
from lib.get_platform import *
from lib.vlcclient import get_default_vlc_path
from lib.vocal_dirs import ensure_vocal_dirs, is_split_disabled, set_split_enabled
from lib import vocal_models as vm
from lib import browser_cookies

try:
	from urllib.parse import quote, unquote
except ImportError:
	from urllib import quote, unquote

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True	##DEBUG
app.secret_key = os.urandom(24)
admin_password = K = args = None
sock = Sock(app)
os.texts = defaultdict(lambda: "")
getString = lambda ii: os.texts[ii]
getString1 = lambda lang, ii: os.langs[lang].get(ii, os.langs['en_US'][ii])
getString2 = lambda ii: getString1(request.client_lang, ii)
S_ADMIN_ONLY = 249  # 'Only the administrator can do this.'


# ---------------------------------------------------------------------------- web page events
#
# The web page (frontend/, built into static/app/) is one page that talks to this server through
# the JSON routes below and a WebSocket. The server pushes events as JSON objects with a "type":
#   status    {data: <same as /nowplaying>}         playing song, player state, split status
#   seek      {time: seconds}                       playing position, about once a second
#   queue     {data: <same as /get_queue>}          the queue changed
#   notify    {message, category, timeout?}         a message for this user
#   download  {url, state}                          a download started from this page has ended
# The page never executes what it receives (the old page did, see git history).

@sock.route('/ws_init')
def ws_init(sock):
	key = sock.sock.getpeername()[0]
	ip2websock.setdefault(key, []).append(sock)
	ip2lang[key] = request.client_lang  # used to localize notifications pushed to this client
	try:
		while sock.connected:
			try:
				cmd = sock.receive()
				wscmd(key, cmd)
			except ConnectionClosed:
				break
			except Exception:
				traceback.print_exc()
	finally:
		# remove only this socket: a newer page from the same address may already be connected
		socks = ip2websock.get(key, [])
		if sock in socks:
			socks.remove(sock)
		if not socks:
			ip2websock.pop(key, None)
			ip2lang.pop(key, None)

def wscmd(client_ip, cmd):
	# kept for clients of the old page that are still open
	if not isinstance(cmd, str):
		return
	if cmd.startswith('pop_from_queue '):
		name = cmd.split(' ', 1)[1]
		K.queue_edit(name, 'delete')
	elif cmd.startswith('addsongs '):
		lst = cmd[9:].split('\t')
		for fn in lst[1:]:
			K.enqueue(fn, lst[0])

def broadcast(event):
	for ip in list(ip2websock.keys()):
		ws_send(ip, event)

def status_thread():
	cached_status, cached_queue = '', ''
	while True:
		K.event_dirty.wait(1)

		status = nowplaying(False)
		if not status: continue

		status_full = dict(status)
		status.pop('seektrack_value', None)
		status_str = json.dumps(status)
		if status_str != cached_status:
			K.status_dirty = True
			cached_status = status_str

		queue = queue_payload()
		queue_str = json.dumps(queue)
		if queue_str != cached_queue:
			cached_queue = queue_str
			broadcast({'type': 'queue', 'data': queue})

		if not K.status_dirty:
			if not K.is_file_playing():
				continue
			tm = K.get_state().get('time', None)
			if tm is not None:
				broadcast({'type': 'seek', 'time': tm})
			continue

		broadcast({'type': 'status', 'data': status_full})
		K.status_dirty = False


@app.before_request
def preprocessor():
	client_lang = request.cookies.get('lang', None)
	if client_lang is None:
		lang_str = request.headers.get('Accept-Language', os.lang)
		for k in [j for i in lang_str.split(';') for j in i.split(',')]:
			client_lang = find_language(k.strip())
			if client_lang is not None:
				break
	request.client_lang = find_language(client_lang or os.lang)


def filename_from_path(file_path, remove_youtube_id = True):
	rc = os.path.basename(file_path)
	rc = os.path.splitext(rc)[0]
	if remove_youtube_id:
		try:
			rc = rc.split("---")[0]  # removes youtube id if present
		except TypeError:
			rc = rc.split("---".encode("utf-8"))[0]
	return rc


def is_admin():
	if (admin_password == None):
		return True
	if ('admin' in request.cookies):
		a = request.cookies.get("admin")
		if (a == admin_password):
			return True
	return False


def admin_only(f):
	@wraps(f)
	def wrapper(*a, **kw):
		if not is_admin():
			return jsonify(ok = False, error = getString2(S_ADMIN_ONLY)), 403
		return f(*a, **kw)
	return wrapper


def is_song_file(path):
	"""Only songs of the library may be queued, renamed or deleted from the web page."""
	try:
		return os.path.isfile(path) and os.path.realpath(os.path.dirname(path)) == os.path.realpath(K.download_path.rstrip('/\\'))
	except Exception:
		return False


# ---------------------------------------------------------------------------- the page

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'app')

@app.route("/")
def root():
	index = os.path.join(APP_DIR, 'index.html')
	if not os.path.isfile(index):
		return ('The web interface is not built. Run "npm install" and "npm run build" in the frontend folder, '
		        'see doc/ for details.'), 500
	resp = send_file(index, mimetype = 'text/html')
	resp.headers['Cache-Control'] = 'no-cache'
	return resp

RTL_LANGS = {'ar', 'fa', 'he', 'ur', 'yi', 'ps', 'sd', 'ug'}

@app.route("/api/config")
def api_config():
	"""Everything the page needs at start: its strings in the user's language, and what this
	server can do."""
	lang = request.client_lang
	texts = os.langs[lang]
	en = os.langs['en_US']
	n = max(max(en.keys()), max(texts.keys()))
	strings = [''] + [texts.get(i) or en.get(i, '') for i in range(1, n + 1)]
	return jsonify(
		lang = lang,
		dir = 'rtl' if lang.split('_')[0] in RTL_LANGS else 'ltr',
		strings = strings,
		langs = [[k, v[1]] for k, v in os.langs.items()],
		admin = is_admin(),
		admin_enabled = admin_password != None,
		asr = bool(getattr(args, 'cloud', '')),
		use_vlc = K.use_vlc,
		high_quality = K.high_quality,
		platform = K.platform,
		is_pi = get_platform() == "raspberry_pi",
		version = VERSION,
		url = K.url,
		https_port = (K.port if K.ssl else K.port + 1),
	)


# ---------------------------------------------------------------------------- now playing and player

def split_payload(path):
	return K.split_states([path]).get(path) if path else None

@app.route("/nowplaying")
def nowplaying(return_json=True):
	try:
		if K.switchingSong:
			return "" if return_json else {}
		next_song = K.queue[0]["title"] if K.queue else None
		next_user = K.queue[0]["user"] if K.queue else None
		s = K.get_state()
		rc = {
			"now_playing": K.now_playing,
			"now_playing_user": K.now_playing_user,
			"now_playing_file": K.now_playing_filename,
			"up_next": next_song,
			"next_user": next_user,
			"is_paused": s.get('state', 'paused') == 'paused',
			"volume": s['volume'],
			"transpose_value": K.now_playing_transpose,
			"seektrack_value": s['time'],
			"seektrack_max": s['length'],
			"audio_delay": s['audiodelay'],
			"vol_norm": K.normalize_vol,
			"play_speed": s['rate'],
			"vocal_info": K.get_vocal_info(),
			"split": split_payload(K.now_playing_filename),
			"splitter": K.splitter_state(),
		}
		if K.has_subtitle:
			rc['subtitle_delay'] = s['subtitledelay']
			rc['show_subtitle'] = K.show_subtitle
		return json.dumps(rc) if return_json else rc
	except Exception as e:
		logging.error(f"Problem loading /nowplaying, OpenHomeKaraoke may still be starting up: {e}\n{traceback.format_exc()}")
		return "" if return_json else {}


@app.route("/skip")
def skip():
	K.skip()
	return ''

@app.route("/pause")
def pause():
	K.pause()
	return json.dumps(K.is_paused)

@app.route("/transpose/<semitones>", methods = ["GET"])
def transpose(semitones):
	K.play_transposed(semitones)
	return ''

@app.route("/play_vocal/<mode>", methods = ["GET"])
def play_vocal(mode):
	K.play_vocal(mode)
	return ''

@app.route("/play_speed/<speed>", methods = ["GET"])
def play_speed(speed):
	K.play_speed_set(speed)
	return ''

@app.route("/seek/<goto_sec>", methods = ["GET"])
def seek(goto_sec):
	K.seek(goto_sec)
	return ''

@app.route("/audio_delay/<delay_val>", methods = ["GET"])
def audio_delay(delay_val):
	return json.dumps(K.set_audio_delay(delay_val))

@app.route("/subtitle_delay/<delay_val>", methods = ["GET"])
def subtitle_delay(delay_val):
	return json.dumps(K.set_subtitle_delay(delay_val))

@app.route("/toggle_subtitle")
def toggle_subtitle():
	K.toggle_subtitle()
	return ''

@app.route("/restart")
def restart():
	K.restart()
	return ''

@app.route("/vol_up")
def vol_up():
	return str(K.vol_up())

@app.route("/vol_down")
def vol_down():
	return str(K.vol_down())

@app.route("/vol/<volume>")
def vol_set(volume):
	return str(K.vol_set(volume))


# ---------------------------------------------------------------------------- users and languages

@app.route("/get_lang_list")
def get_lang_list():
	return json.dumps({k: v[1] for k, v in os.langs.items()}, sort_keys = False)

@app.route("/auto_username")
def auto_username():
	return f'user-{len(ip2websock)+1}'

@app.route("/change_language/<language>")
@admin_only
def change_language(language):
	try:
		set_language(language)
	except:
		logging.error(f"Failed to set server language to {language}")
	return os.lang

@app.route("/api/login", methods = ["POST"])
def api_login():
	p = (request.get_json(silent = True) or {}).get('password', '')
	if admin_password is None or p != admin_password:
		return jsonify(ok = False, error = getString2(2)), 403
	resp = jsonify(ok = True, message = getString2(1))
	resp.set_cookie('admin', admin_password, expires = datetime.datetime.now() + datetime.timedelta(days = 90), samesite = 'Lax')
	return resp

@app.route("/api/logout", methods = ["POST", "GET"])
def api_logout():
	resp = jsonify(ok = True, message = getString2(3))
	resp.set_cookie('admin', '', expires = 0)
	return resp

@app.route("/user_rename/<old_name>/<new_name>")
def user_rename(old_name, new_name):
	dirty = False
	for q in K.queue:
		if q['user'] == old_name:
			q['user'] = new_name
			dirty = True
	if K.now_playing_user == old_name:
		K.now_playing_user = new_name
		K.status_dirty = True
	if dirty:
		K.update_queue()
	return ''


# ---------------------------------------------------------------------------- vocal splitter

@app.route("/get_vocal_todo_list/<vocal_device>/")
@app.route("/get_vocal_todo_list/<vocal_device>/<path:last_completed>")
def get_vocal_todo_list(vocal_device, last_completed=''):
	K.vocal_device = vocal_device
	if last_completed in K.rename_history:
		K.rename(last_completed, os.path.splitext(K.rename_history[last_completed])[0])
		K.rename_history.pop(last_completed)
	q = ([K.now_playing_filename] if K.now_playing_filename else []) + [i['file'] for i in K.queue]
	return json.dumps({'download_path': K.download_path, 'queue': q, 'use_DNN': K.use_DNN_vocal, 'model': K.vocal_model})

@app.route("/save_delays/<state>")
@admin_only
def set_save_delays(state):
	K.set_save_delays(state.lower() == 'true')
	return ''

@app.route("/set_vocal_mode/<mode>")
@admin_only
def set_vocal_mode(mode):
	# old on/off switch: true = neural network (default model), false = L-R/L+R
	K.set_vocal_model(vm.DEFAULT_MODEL if mode.lower() == 'true' else 'LR')
	return ''

@app.route("/set_vocal_model/<model>")
@admin_only
def set_vocal_model(model):
	K.set_vocal_model(model)
	K.status_dirty = True
	return ''

@app.route("/vocal_split/<state>")
@admin_only
def vocal_split(state):
	enabled = state.lower() == 'true'
	set_split_enabled(K.download_path, enabled)
	if enabled:
		K.vocal_restart()
	else:
		K.vocal_stop()
	K.status_dirty = True
	return ''

@app.route("/norm_vol/<mode>", methods = ["GET"])
@admin_only
def norm_vol(mode):
	K.enable_vol_norm(mode.lower() == 'true')
	return ''

@app.route("/bg-process/<cmd>")
@admin_only
def bg_process(cmd):
	if cmd == 'streamer-restart':
		K.streamer_restart()
	elif cmd == 'streamer-stop':
		K.streamer_stop()
	elif cmd == 'vocal-restart':
		K.vocal_restart()
	elif cmd == 'vocal-stop':
		K.vocal_stop()
	K.status_dirty = True
	return ''


# ---------------------------------------------------------------------------- queue

def queue_payload():
	states = K.split_states([q['file'] for q in K.queue])
	return [dict(q, split = states.get(q['file'])) for q in K.queue]

@app.route("/get_queue", methods = ["GET"])
def get_queue():
	return jsonify(queue_payload())

@app.route("/queue/addrandom", methods = ["GET"])
def add_random():
	amount = int(request.args.get("amount", 3))
	rc = K.queue_add_random(amount)
	return jsonify(ok = bool(rc), message = (getString2(4) % amount) if rc else getString2(5))

def own_queue_song(song, user):
	"""Whether `song` is in the queue and was added by `user` (people may take back their own songs)."""
	return bool(user) and any(q['file'] == song and q['user'] == user for q in K.queue)

@app.route("/queue/edit", methods = ["GET", "POST"])
def queue_edit():
	d = request.values.to_dict() | (request.get_json(silent = True) or {})
	action = d.get("action", "")
	if not is_admin():
		# without the admin password: only remove your own song, or undo that
		song, user = unquote(d.get("song", "")), d.get('user', '')
		allowed = (action == 'delete' and own_queue_song(song, user)) or \
		          (action == 'insert' and bool(user) and user != 'Random')
		if not allowed:
			return jsonify(ok = False, error = getString2(S_ADMIN_ONLY)), 403
	if action == "clear":
		K.queue_clear()
		return jsonify(ok = True, message = getString2(6))
	if action == "move":
		ok = K.queue_edit(None, "move", src = d.get('from'), tgt = d.get('to'), size = d.get('size'))
		return jsonify(ok = bool(ok))
	song = unquote(d.get("song", ""))
	if action == "insert":
		ok = is_song_file(song) and K.queue_insert(d.get('index', 0), song, d.get('user', 'Pikaraoke'))
		return jsonify(ok = bool(ok))
	if action in ("up", "down", "top", "delete"):
		return jsonify(ok = bool(K.queue_edit(song, action)))
	return jsonify(ok = False, error = 'unknown action'), 400

@app.route("/enqueue", methods = ["POST", "GET"])
def enqueue():
	d = request.values.to_dict() | (request.get_json(silent = True) or {})
	song = d.get('song') or d.get('song-to-add', '')
	user = d.get('user') or d.get('song-added-by', 'Pikaraoke')
	rc = is_song_file(song) and K.enqueue(song, user)
	return json.dumps({"song": filename_from_path(song), "success": bool(rc)})


# ---------------------------------------------------------------------------- library

@app.route("/api/library")
def api_library():
	songs = K.available_songs
	if request.args.get('sort') == 'date':
		songs = sorted(songs, key = lambda x: os.path.getctime(x) if os.path.exists(x) else 0, reverse = True)
	queued = {q['file'] for q in K.queue}
	return jsonify([{'file': s, 'title': K.filename_from_path(s), 'queued': s in queued} for s in songs])

@app.route("/suggest")
def suggest():
	q = request.args.get('q', '').lower()
	res = {K.filename_from_path(s):s for s in K.available_songs if q in s.lower()}
	return json.dumps(res)

@app.route("/refresh")
@admin_only
def refresh():
	K.get_available_songs()
	return jsonify(ok = True, count = len(K.available_songs))

@app.route("/files/delete", methods = ["GET", "POST"])
@admin_only
def delete_file():
	song_path = request.values.get("song", "")
	if not is_song_file(song_path):
		return jsonify(ok = False, error = getString2(21)), 400
	if K.is_song_in_queue(song_path) or song_path == K.now_playing_filename:
		return jsonify(ok = False, error = getString2(19) + filename_from_path(song_path)), 409
	K.delete(song_path)
	return jsonify(ok = True, message = getString2(20) + filename_from_path(song_path))

@app.route("/edit_song", methods = ["POST"])
@admin_only
def rename():
	d = request.values.to_dict() | (request.get_json(silent = True) or {})
	old_name, new_name = d.get("old_file_name", ""), d.get("new_file_name", "").strip()
	if not is_song_file(old_name) or not new_name or os.sep in new_name or '/' in new_name:
		return jsonify(ok = False, error = getString2(220)), 400
	if old_name == K.now_playing_filename:
		return jsonify(ok = False, error = getString2(22) + filename_from_path(old_name)), 409
	file_extension = os.path.splitext(old_name)[1]
	if os.path.isfile(os.path.join(K.download_path, new_name + file_extension)):
		return jsonify(ok = False, error = getString2(24) % (filename_from_path(old_name), new_name + file_extension)), 409
	K.rename(old_name, new_name)
	return jsonify(ok = True, message = getString2(25) % (filename_from_path(old_name), new_name))


# ---------------------------------------------------------------------------- YouTube

@app.route("/api/search")
def api_search():
	q = request.args.get('q', '').strip()
	if not q:
		return jsonify(results = [])
	karaoke_only = request.args.get('karaoke', 'false') == 'true'
	try:
		rc = K.get_search_results(q + (" karaoke" if karaoke_only else ""))
	except Exception as e:
		logging.error(f'YouTube search failed: {e}')
		return jsonify(results = [], error = str(e)[:300]), 502
	return jsonify(results = [{'title': t, 'url': u, 'id': i, 'duration': d} for t, u, i, d in rc])

def transform_boolean(dct, S):
	return {k: ((v in ('on', True, 'true')) if k in S else v) for k, v in dct.items()}

@app.route("/download", methods = ["POST"])
def download():
	dct = request.form.to_dict() | (request.get_json(silent = True) or {})
	dct = transform_boolean({k: dct[k] for k in ('song_url', 'song_added_by', 'enqueue', 'include_subtitles', 'high_quality') if k in dct},
	                        {'enqueue', 'include_subtitles', 'high_quality'})
	if not dct.get('song_url'):
		return jsonify(ok = False), 400
	if K.downloading_songs.get(dct['song_url']) == 1:
		# already being downloaded (e.g. tapped twice): do not start a second copy
		return jsonify(ok = True, busy = True, message = getString2(285))
	# download in the background since this can take a few minutes
	t = threading.Thread(target = K.download_video, kwargs = dct|{'client_ip': request.remote_addr, 'client_lang': request.client_lang})
	t.daemon = True
	t.start()
	return jsonify(ok = True, message = getString2(16) + dct["song_url"] + '\n' + getString2(17 if dct.get('enqueue', False) else 18))

@app.route("/check_download", methods = ["POST", "GET"])
def check_download():
	# 1 downloading, 0 / '00' done, -1 / '01' failed, '' never asked for
	ret = K.downloading_songs.get(request.values.get('url', None), '')
	return json.dumps(ret)


# ---------------------------------------------------------------------------- settings page

@app.route("/qrcode")
def qrcode():
	return send_file(K.qr_code_path, mimetype = "image/png")

@app.route("/logo")
def logo():
	return send_file(K.logo_path)

@app.route("/api/settings")
def api_settings():
	memory = psutil.virtual_memory()
	disk = psutil.disk_usage(K.download_path)
	rc = dict(
		url = K.url,
		version = VERSION,
		os = sys.platform,
		platform = K.platform,
		cpu = psutil.cpu_percent(),
		memory = {'free': memory.available, 'total': memory.total},
		disk = {'free': disk.free, 'total': disk.total},
		download_path = K.download_path,
		num_songs = len(K.available_songs),
		youtubedl_version = K.youtubedl_version,
		streamer = K.streamer_alive() if K.platform == 'linux' else None,
		splitter = K.splitter_state(),
		splitter_missing = K.vocal_splitter_missing(),
		splitter_device = getattr(K, 'vocal_device', None),
		admin = is_admin(),
		admin_enabled = admin_password != None,
		is_pi = get_platform() == "raspberry_pi",
	)
	if is_admin():
		rc.update(
			save_delays = bool(K.save_delays),
			norm_vol = K.normalize_vol,
			vocal_split = not is_split_disabled(K.download_path),
			vocal_model = K.vocal_model,
			models = [{'id': m, 'status': vm.model_status(m)} for m in vm.ALL_MODELS],
			server_lang = os.lang,
		)
	return jsonify(rc)


# ---------------------------------------------------------------------------- speech recognition

def run_asr():
	global args
	with open(f'{K.tmp_dir}/rec.webm', 'rb') as f:
		r = requests.post(args.cloud+'/run_asr', files={'file': f}, timeout=8)
	asr_output = json.loads(r.text) if r.status_code==200 else {}
	return asr_output, r

@app.route('/api/voice_find', methods=['POST'])
def api_voice_find():
	"""Recognise what the user said and look for matching songs in the library (needs --cloud)."""
	if not getattr(args, 'cloud', ''):
		return jsonify(text = '', matches = [], error = 'no speech recognition server (--cloud)'), 501
	with open(f'{K.tmp_dir}/rec.webm', 'wb') as fp:
		fp.write(request.data)
	try:
		asr_output, r = run_asr()
	except Exception as e:
		return jsonify(text = '', matches = [], error = str(e)[:300]), 502
	if not isinstance(asr_output, dict) or not asr_output.get('text'):
		return jsonify(text = '', matches = [])
	res = findMedia(K.download_path, asr_postprocess(asr_output['text']), lang = asr_output.get('language')) or []
	return jsonify(text = asr_output['text'], matches = [{'file': s, 'title': filename_from_path(s)} for s in res])

@app.route('/get_ASR', methods=['POST'])
@app.route('/get_ASR/<path:cmd>', methods=['POST'])
def get_ASR(cmd=''):
	with open(f'{K.tmp_dir}/rec.webm', 'wb') as fp:
		fp.write(request.data)
	asr_output, r = run_asr()
	return asr_output.get('text', ''), r.status_code


# ---------------------------------------------------------------------------- TV screen in a browser

@app.route("/splash")
def splash():
	return render_template("splash.html", url = K.url)


# ---------------------------------------------------------------------------- system

# Delay system commands so that the page gets its answer first
def delayed_halt(cmd):
	time.sleep(3)
	K.vocal_stop()
	K.queue_clear()  # stop all pending omxplayer processes
	K.stop()
	if cmd == 0:
		os.system('(sleep 2 && tmux kill-session -t PiKaraoke) &')
		sys.exit()
	if cmd == 1:
		os.system("shutdown now")
	if cmd == 2:
		os.system("reboot")
	if cmd == 3:
		process = subprocess.Popen(["raspi-config", "--expand-rootfs"])
		process.wait()
		os.system("reboot")

@app.route("/quit")
@admin_only
def quit():
	threading.Thread(target = delayed_halt, args = [0]).start()
	return jsonify(ok = True, message = getString2(35))

@app.route("/shutdown")
@admin_only
def shutdown():
	threading.Thread(target = delayed_halt, args = [1]).start()
	return jsonify(ok = True, message = getString2(37))

@app.route("/reboot")
@admin_only
def reboot():
	threading.Thread(target = delayed_halt, args = [2]).start()
	return jsonify(ok = True, message = getString2(39))

@app.route("/update_ytdl")
@admin_only
def update_ytdl():
	threading.Thread(target=lambda: K.upgrade_youtubedl()).start()
	return jsonify(ok = True, message = getString2(32))

@app.route("/expand_fs")
@admin_only
def expand_fs():
	if get_platform() != "raspberry_pi":
		return jsonify(ok = False, error = getString2(42)), 400
	threading.Thread(target = delayed_halt, args = [3]).start()
	return jsonify(ok = True, message = getString2(41))


def get_default_dl_dir():
	return os.path.expanduser("~/pikaraoke-songs")

def get_default_tmp_dir():
	return '/dev/shm' if os.path.isdir('/dev/shm') else tempfile.gettempdir()

def get_default_browser_cookie(platform):
	platform = 'linux' if platform=='raspberry_pi' else platform
	if platform == 'osx':
		# the default browser is not detectable on macOS here (webbrowser says 'default')
		return browser_cookies.pin_profile(browser_cookies.default_spec(platform), platform)
	def_cookie_loc = defaultdict(lambda:defaultdict(lambda:''))
	def_cookie_loc['linux']['firefox'] = '$HOME/.mozilla/firefox/'
	def_cookie_loc['linux']['chrome'] = '$HOME/.config/google-chrome/'
	def_cookie_loc['linux']['chromium'] = '$HOME/.config/chromium/'
	def_cookie_loc['windows']['firefox'] = '%APPDATA%\\Mozilla\\Firefox\\Profiles'
	def_cookie_loc['windows']['chrome'] = '%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Network'
	def_cookie_loc['windows']['edge'] = '%LOCALAPPDATA%\\Microsoft\\Edge\\User Data\\Default\\Network'
	def_cookie_loc['windows']['ie'] = '%USERPROFILE%\\AppData\\Roaming\\Microsoft\\Windows\\Cookies'
	def_cookie_loc['osx']['firefox'] = '$HOME/Library/Application Support/Firefox/Profiles/'
	def_cookie_loc['osx']['chrome'] = '$HOME/Library/Application Support/Google/Chrome/'
	def_cookie_loc['osx']['safari'] = '$HOME/Library/Cookies/'
	try:
		if platform == 'windows':
			browsers = ['firefox', 'chrome', 'ie', 'edge']
			from winreg import OpenKey, HKEY_CURRENT_USER, QueryValueEx
			with OpenKey(HKEY_CURRENT_USER,
						 r"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice") as key:
				browser = QueryValueEx(key, 'Progid')[0].lower()
			default_browser = [b for b in browsers if browser.startswith(b)][0]
		else:
			default_browser = webbrowser.get().name.lower()
	except:
		return ''
	ret = os.path.expandvars(def_cookie_loc[platform][default_browser])
	return f'{default_browser}:{ret}' if ret else ''


if __name__ == "__main__":
	platform = get_platform()
	default_port = 5000
	default_volume = 0
	default_splash_delay = 3
	default_log_level = logging.INFO

	default_dl_dir = get_default_dl_dir()
	default_omxplayer_path = "/usr/bin/omxplayer"
	default_adev = "both"
	default_vlc_path = get_default_vlc_path(platform)
	default_vlc_port = 5002

	# parse CLI args
	parser = argparse.ArgumentParser()

	parser.add_argument(
		"-p", "--port", type=int,
		help = f"Desired http/https port (default: {default_port})",
		default = default_port,
	)
	parser.add_argument(
		"-d", "--download-path",
		help = f"Desired path for downloaded songs. (default: {default_dl_dir})",
		default = default_dl_dir,
	)
	parser.add_argument(
		"-sd", "--save-delays",
		help = f"Filename for saving subtitle/audio/etc. delays for each song, can be: 1. auto(default): if <download-path>/.delays exist, then enable; 2. yes: save; 3. no: do not save; 4. <filename>: specific file for storing the delays",
		default = 'auto',
	)
	parser.add_argument(
		"-o", "--omxplayer-path",
		help = f"Path of omxplayer. Only important to raspberry pi hardware. (default: {default_omxplayer_path})",
		default = default_omxplayer_path,
	)
	parser.add_argument(
		"-y", "--youtubedl-path",
		help = f"Path of youtube-dl. (default: '', use pip package yt-dlp)",
		default = '',
	)
	parser.add_argument(
		"-v", "--volume",
		help = f"If using omxplayer, the initial player volume is specified in millibels. Negative values ok. (default: {default_volume} , Note: 100 millibels = 1 decibel).",
		default = default_volume,
	)
	parser.add_argument(
		"-V", "--run-vocal",
		help = "Deprecated, kept for old scripts: the vocal splitter now starts automatically on all platforms when PyTorch is installed",
		action = 'store_true',
	)
	parser.add_argument(
		"--no-vocal",
		help = "Do not start the background vocal splitter (existing instrumental/vocal tracks can still be played)",
		action = 'store_true',
	)
	parser.add_argument(
		"-nv", "--normalize-vol",
		help = "Enable volume normalization",
		action = 'store_true',
	)
	parser.add_argument(
		"-s", "--splash-delay",
		help = f"Delay during splash screen between songs (in secs). (default: {default_splash_delay} )",
		type = float,
		default = default_splash_delay,
	)
	parser.add_argument(
		"-L", "--lang",
		help = f"Set display language (default: None, set according to the current system locale {locale.getdefaultlocale()[0]})",
		default = locale.getdefaultlocale()[0],
	)
	parser.add_argument(
		"-l", "--log-level",
		help = f"Logging level int value (DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50). (default: {default_log_level} )",
		default = default_log_level,
	)
	parser.add_argument(
		"--hide-ip",
		action = "store_true",
		help = "Hide IP address from the screen.",
	)
	parser.add_argument(
		"--hide-raspiwifi-instructions",
		action = "store_true",
		help = "Hide RaspiWiFi setup instructions from the splash screen.",
	)
	parser.add_argument(
		"--hide-splash-screen",
		action = "store_true",
		help = "Hide splash screen before/between songs.",
	)
	parser.add_argument(
		"--adev",
		help = f"Pass the audio output device argument to omxplayer. Possible values: hdmi/local/both/alsa[:device]."
		       f" If you are using a rpi USB soundcard or Hifi audio hat, try: 'alsa:hw:0,0' Default: '{default_adev}'",
		default = default_adev,
	)
	parser.add_argument(
		"--dual-screen",
		action = "store_true",
		help = "Output video to both HDMI ports (raspberry pi 4 only)",
	)
	parser.add_argument(
		"--high-quality", "-hq",
		action = "store_true",
		help = "Download higher quality video. Note: requires ffmpeg and may cause CPU, download speed, and other performance issues",
	)
	parser.add_argument(
		"--use-omxplayer",
		action = "store_true",
		help = "Use OMX Player to play video instead of the default VLC Player. This may be better-performing on older raspberry pi devices."
		       " Certain features like key change and cdg support wont be available. Note: if you want to play audio to the headphone jack on a rpi,"
		       " you'll need to configure this in raspi-config: 'Advanced Options > Audio > Force 3.5mm (headphone)'",
	)
	parser.add_argument(
		"--use-vlc",
		action = "store_true",
		help = "Use VLC Player to play video. Enabled by default. Note: if you want to play audio to the headphone jack on a rpi, see troubleshooting steps in README.md",
	)
	parser.add_argument(
		"--vlc-path",
		help = f"Full path to VLC (Default: {default_vlc_path})",
		default = default_vlc_path,
	)
	parser.add_argument(
		"--vlc-port",
		help = f"HTTP port for VLC remote control api (Default: {default_vlc_port})",
		default = default_vlc_port,
	)
	parser.add_argument(
		"--logo-path",
		help = "Path to a custom logo image file for the splash screen. Recommended dimensions ~ 500x500px",
		default = None,
	)
	parser.add_argument(
		"--show-overlay",
		action = "store_true",
		help = "Show overlay on top of video with pikaraoke QR code and IP",
	)
	parser.add_argument(
		'-w', "--windowed",
		action = "store_true",
		help = "Start PiKaraoke in windowed mode",
	)
	parser.add_argument(
		'-c', "--browser-cookies",
		default = "auto",
		help = "YouTube downloader can use browser cookies from the specified path (see the --cookies-from-browser option of yt-dlp), it can also be auto (default): automatically determine based on OS; none: do not use any browser cookies",
	)
	parser.add_argument(
		"--admin-password",
		help = "Administrator password, for locking down certain features of the web UI such as queue editing, player controls, song editing, and system shutdown. If unspecified, everyone is an admin.",
		default = None,
	)
	parser.add_argument(
		"--ssl", "-ssl",
		help = "Use HTTPS instead of HTTP (browser microphone access requires HTTPS)",
		action = 'store_true'
	)
	parser.add_argument(
		"--temp", "-tp",
		default = None,
		help = "Temporary folder location",
	)
	parser.add_argument(
		'--cloud', '-C',
		default='',
		help='cloud URL for DNN-based vocal split and speech recognition',
	)
	args = parser.parse_args()

	set_language(args.lang)

	if (args.admin_password):
		admin_password = args.admin_password


	args.tmp_dir = os.path.expanduser(args.temp or get_default_tmp_dir())
	args.cloud = args.cloud.rstrip('/')

	# Set browser cookies location for YouTube downloader
	if args.browser_cookies.lower() == 'none':
		args.cookies_opt = []
	elif args.browser_cookies.lower() == 'auto':
		path = get_default_browser_cookie(platform)
		args.cookies_opt = ['--cookies-from-browser', path] if path else []
	else:
		# Support both cookies.txt files and browser names
		if args.browser_cookies.endswith('.txt'):
			args.cookies_opt = ['--cookies', args.browser_cookies]
		else:
			args.cookies_opt = ['--cookies-from-browser', browser_cookies.pin_profile(args.browser_cookies, platform)]

	# Read the cookies once now (before the karaoke window opens) and say whether YouTube is
	# signed in. If they cannot be read, go on without them so search and other sites still work.
	if args.cookies_opt:
		source = args.cookies_opt[1]
		count, signed_in, error = browser_cookies.check(args.cookies_opt)
		if error:
			print(f"YouTube sign-in: cannot read cookies from {source} ({error}). Continuing without them; "
			      f"YouTube may then ask to confirm you're not a bot. {browser_cookies.HINTS.get(platform, '')}")
			args.cookies_opt = []
		else:
			print(f"YouTube sign-in: {count} cookies from {source}, signed in to YouTube: "
			      + ("yes" if signed_in else "NO (sign in to YouTube in that browser, or downloads may be refused)"))

	# Handle OMX player if specified
	if platform == "raspberry_pi" and args.use_omxplayer:
		args.use_vlc = False
	else:
		args.use_vlc = True

	# check if required binaries exist, auto pip install yt-dlp if needed
	if not os.path.isfile(args.youtubedl_path):
		args.youtubedl_path = ''
		try:
			import yt_dlp
		except:
			try:
				import pip
				pip.main(['install', 'yt-dlp'])
			except:
				print(getString(44) + args.youtubedl_path)
				sys.exit(1)
	if args.use_vlc and not os.path.isfile(args.vlc_path):
		print(getString(45) + args.vlc_path)
		sys.exit(1)
	if platform == "raspberry_pi" and not args.use_vlc and not os.path.isfile(args.omxplayer_path):
		print(getString(46) + args.omxplayer_path)
		sys.exit(1)

	# setup/create download directory if necessary
	args.dl_path = os.path.expanduser(args.download_path).rstrip('/')+'/'
	if platform == 'windows':	# on Windows, VLC cannot open filenames containing '/'
		args.dl_path = escape_win_filename(args.dl_path)
	if not os.path.exists(args.dl_path):
		print(getString(47) + args.dl_path)
		os.makedirs(args.dl_path)
	ensure_vocal_dirs(args.dl_path)

	# determine whether to save/load delays
	args.dft_delays_file = args.dl_path+'.delays'
	if args.save_delays == 'auto':
		args.save_delays = args.dft_delays_file if os.path.exists(args.dft_delays_file) else None
	elif args.save_delays == 'yes':
		args.save_delays = args.dft_delays_file
	elif args.save_delays == 'no':
		args.save_delays = None

	# The web page needs --port (http) and, without --ssl, --port+1 (https). If one is taken, the
	# QR code would point to another program: on macOS port 5000 belongs to AirPlay Receiver,
	# which answers with an empty page. Move to the next free pair instead.
	def port_free(port):
		import socket
		with socket.socket() as s:
			s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # like Flask, so TIME_WAIT is fine
			try:
				s.bind(('0.0.0.0', port))
				return True
			except OSError:
				return False
	web_ports = lambda p: [p] if args.ssl else [p, p + 1]
	if not all(port_free(q) for q in web_ports(args.port)):
		for p in range(args.port + 2, args.port + 200, 2):
			if args.use_vlc and int(args.vlc_port) in web_ports(p):
				continue
			if all(port_free(q) for q in web_ports(p)):
				print(f"Port {args.port} is used by another program (on macOS usually AirPlay Receiver). "
				      f"Using port {p} instead; the QR code shows the new address.")
				args.port = p
				break

	# Configure karaoke process
	os.K = K = Karaoke(args)

	if not args.ssl:
		threading.Thread(target=lambda:app.run(host='0.0.0.0', port=args.port+1, threaded = True, ssl_context=('cert.pem', 'key.pem'))).start()
	threading.Thread(target=lambda:app.run(host='0.0.0.0', port=args.port, threaded = True, ssl_context=('cert.pem', 'key.pem') if args.ssl else None)).start()

	threading.Thread(target=status_thread).start()

	K.run()
	os._exit(0)	# force-stop all flask threads and exit
