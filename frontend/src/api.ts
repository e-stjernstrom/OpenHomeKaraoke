// Talking to the OpenHomeKaraoke server (app.py).

export type SplitState = 'done' | 'processing' | 'queued' | 'failed' | 'off' | 'unavailable' | 'stopped';
export type SplitterState = 'running' | 'stopped' | 'off' | 'unavailable';

export interface SplitInfo {
  state: SplitState;
  model: string;
  progress?: number;
  ahead?: number;
  error?: string;
}

export interface Status {
  now_playing: string | null;
  now_playing_user: string | null;
  now_playing_file: string | null;
  up_next: string | null;
  next_user: string | null;
  is_paused: boolean;
  volume: number | null;
  transpose_value: number;
  seektrack_value: number | null;
  seektrack_max: number | null;
  audio_delay: number | null;
  vol_norm: boolean;
  play_speed: number | null;
  vocal_info: number;
  split: SplitInfo | null;
  splitter: SplitterState;
  subtitle_delay?: number | null;
  show_subtitle?: boolean;
}

export interface QueueItem {
  user: string;
  file: string;
  title: string;
  split: SplitInfo | null;
}

export interface Config {
  lang: string;
  dir: 'ltr' | 'rtl';
  strings: string[];
  langs: [string, string][];
  admin: boolean;
  admin_enabled: boolean;
  asr: boolean;
  use_vlc: boolean;
  high_quality: boolean;
  tv_lang: string;
  platform: string;
  is_pi: boolean;
  version: string;
  url: string;
  https_port: number;
}

export interface Song {
  file: string;
  title: string;
  queued: boolean;
}

export interface YouTubeResult {
  title: string;
  url: string;
  id: string;
  duration: string;
}

export interface ModelInfo {
  id: string;
  status: 'ready' | 'missing' | 'downloading' | string;
}

export interface Settings {
  url: string;
  version: string;
  os: string;
  platform: string;
  cpu: number;
  memory: { free: number; total: number };
  disk: { free: number; total: number };
  download_path: string;
  num_songs: number;
  youtubedl_version: string;
  streamer: boolean | null;
  splitter: SplitterState;
  splitter_missing: string;
  splitter_device: string | null;
  admin: boolean;
  admin_enabled: boolean;
  is_pi: boolean;
  save_delays?: boolean;
  norm_vol?: boolean;
  vocal_split?: boolean;
  vocal_model?: string;
  models?: ModelInfo[];
  server_lang?: string;
}

export interface OkResponse {
  ok: boolean;
  message?: string;
  error?: string;
}

/** Path segments may contain anything (song titles, user names): encode them fully. */
export const seg = (s: string | number) =>
  encodeURIComponent(String(s)).replace(/['()*!]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase());

export async function getText(url: string): Promise<string> {
  const r = await fetch(url, { credentials: 'same-origin' });
  const text = await r.text();
  if (!r.ok) throw new HttpError(r.status, text);
  return text;
}

export class HttpError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
  /** The server's error message, if it sent one as JSON. */
  get serverMessage(): string | undefined {
    try {
      return JSON.parse(this.body).error || JSON.parse(this.body).message;
    } catch {
      return undefined;
    }
  }
}

export async function getJson<T>(url: string): Promise<T> {
  const text = await getText(url);
  return (text ? JSON.parse(text) : null) as T;
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  if (!r.ok) throw new HttpError(r.status, text);
  return (text ? JSON.parse(text) : null) as T;
}

export async function postBlob<T>(url: string, blob: Blob): Promise<T> {
  const r = await fetch(url, { method: 'POST', credentials: 'same-origin', body: blob });
  const text = await r.text();
  if (!r.ok) throw new HttpError(r.status, text);
  return (text ? JSON.parse(text) : null) as T;
}

// ---------------------------------------------------------------- server events (WebSocket)

export type ServerEvent =
  | { type: 'status'; data: Status }
  | { type: 'seek'; time: number }
  | { type: 'queue'; data: QueueItem[] }
  | { type: 'notify'; message: string; category?: string; timeout?: number }
  | { type: 'download'; url: string; state: number | string | null; progress?: number };

type Listener = (e: ServerEvent) => void;
type ConnListener = (connected: boolean) => void;

/** One WebSocket per page, reconnecting with back-off when the server restarts or Wi-Fi drops. */
export class EventSocket {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private connListeners = new Set<ConnListener>();
  private retry = 0;
  private closed = false;
  connected = false;

  start() {
    this.closed = false;
    this.open();
  }

  stop() {
    this.closed = true;
    const ws = this.ws;
    this.ws = null;
    ws?.close();
    this.setConnected(false);
  }

  on(l: Listener) {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }

  onConnection(l: ConnListener) {
    this.connListeners.add(l);
    return () => this.connListeners.delete(l);
  }

  private setConnected(c: boolean) {
    if (this.connected === c) return;
    this.connected = c;
    this.connListeners.forEach((l) => l(c));
  }

  private open() {
    const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    const ws = new WebSocket(proto + location.host + '/ws_init');
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.setConnected(true);
    };
    ws.onmessage = (ev) => {
      if (this.ws !== ws) return;
      let e: ServerEvent;
      try {
        e = JSON.parse(ev.data);
      } catch {
        return; // not one of ours (e.g. an old server version)
      }
      if (e && typeof e === 'object' && 'type' in e) this.listeners.forEach((l) => l(e));
    };
    ws.onclose = () => {
      if (this.ws !== ws) return; // an older socket, already replaced
      this.setConnected(false);
      if (this.closed) return;
      const delay = Math.min(10000, 500 * 2 ** this.retry++);
      setTimeout(() => this.open(), delay);
    };
    ws.onerror = () => ws.close();
  }
}

// ---------------------------------------------------------------- helpers

export function hhmmss(sec: number | null | undefined): string {
  if (sec == null || !isFinite(sec) || sec < 0) sec = 0;
  const s = Math.floor(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const mm = String(m).padStart(h ? 2 : 1, '0');
  const ss = String(r).padStart(2, '0');
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function getCookie(name: string): string | undefined {
  const m = document.cookie.split('; ').find((c) => c.startsWith(name + '='));
  return m ? decodeURIComponent(m.slice(name.length + 1)) : undefined;
}

export function setCookie(name: string, value: string, days = 3650) {
  const exp = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${exp}; path=/; SameSite=Lax`;
}
