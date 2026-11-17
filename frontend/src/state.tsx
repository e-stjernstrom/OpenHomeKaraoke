import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  EventSocket,
  getCookie,
  getJson,
  getText,
  seg,
  setCookie,
  type Config,
  type QueueItem,
  type ServerEvent,
  type Status,
} from './api';
import type { StringId } from './strings';

export type Page = 'home' | 'queue' | 'search' | 'library' | 'settings';
export const PAGES: Page[] = ['home', 'queue', 'search', 'library', 'settings'];

export interface Snack {
  id: number;
  message: string;
  severity?: 'error' | 'warning' | 'success' | 'info';
  action?: { label: string; onClick: () => void };
  timeout?: number;
}

interface AppState {
  config: Config;
  t: (id: StringId, ...args: (string | number)[]) => string;
  status: Status | null;
  seekTime: number | null;
  queue: QueueItem[];
  connected: boolean;
  user: string;
  setUser: (name: string) => void;
  needsName: boolean;
  notify: (s: Omit<Snack, 'id'>) => void;
  snacks: Snack[];
  dismissSnack: (id: number) => void;
  page: Page;
  go: (p: Page) => void;
  refreshStatus: () => void;
  refreshQueue: () => void;
  reloadConfig: () => Promise<void>;
  onServerEvent: (l: (e: ServerEvent) => void) => () => void;
}

const Ctx = createContext<AppState | null>(null);

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useApp outside AppProvider');
  return v;
}

/** Strip the few HTML tags old translations contain; the page shows plain text only. */
function plain(s: string) {
  return s.replace(/<[^>]+>/g, '');
}

export function makeT(strings: string[]) {
  return (id: StringId, ...args: (string | number)[]) => {
    let s = plain(strings[id] ?? '');
    for (const a of args) {
      // some machine-translated lines have a broken placeholder ("% S", "%с"): then append
      if (s.includes('%s')) s = s.replace('%s', String(a));
      else if (s.includes('%d')) s = s.replace('%d', String(a));
      else s = `${s} ${a}`;
    }
    return s.trim();
  };
}

function pageFromHash(): Page {
  const h = location.hash.replace(/^#\/?/, '') as Page;
  return PAGES.includes(h) ? h : 'home';
}

export function AppProvider({ initialConfig, children }: { initialConfig: Config; children: ReactNode }) {
  const [config, setConfig] = useState(initialConfig);
  const [status, setStatus] = useState<Status | null>(null);
  const [seekTime, setSeekTime] = useState<number | null>(null);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [connected, setConnected] = useState(true);
  const [user, setUserState] = useState(getCookie('user') || '');
  const [snacks, setSnacks] = useState<Snack[]>([]);
  const [page, setPage] = useState<Page>(pageFromHash());
  const socket = useMemo(() => new EventSocket(), []);
  const snackId = useRef(0);

  const t = useMemo(() => makeT(config.strings), [config.strings]);

  const notify = useCallback((s: Omit<Snack, 'id'>) => {
    setSnacks((list) => [...list, { ...s, id: ++snackId.current }]);
  }, []);
  const dismissSnack = useCallback((id: number) => setSnacks((list) => list.filter((s) => s.id !== id)), []);

  const refreshStatus = useCallback(() => {
    getText('/nowplaying')
      .then((text) => {
        if (text) {
          const s = JSON.parse(text) as Status;
          setStatus(s);
          setSeekTime(s.seektrack_value);
        }
      })
      .catch(() => {});
  }, []);
  const refreshQueue = useCallback(() => {
    getJson<QueueItem[]>('/get_queue').then(setQueue).catch(() => {});
  }, []);

  const reloadConfig = useCallback(async () => {
    const c = await getJson<Config>('/api/config');
    setConfig(c);
  }, []);

  const setUser = useCallback(
    (name: string) => {
      const n = name.trim();
      if (!n) return;
      if (user && user !== n) getText(`/user_rename/${seg(user)}/${seg(n)}`).catch(() => {});
      setCookie('user', n);
      setUserState(n);
    },
    [user],
  );

  // live updates from the server
  useEffect(() => {
    const off = socket.on((e) => {
      switch (e.type) {
        case 'status':
          setStatus(e.data);
          setSeekTime(e.data.seektrack_value);
          break;
        case 'seek':
          setSeekTime(e.time);
          break;
        case 'queue':
          setQueue(e.data);
          break;
        case 'notify': {
          const sev = e.category?.includes('danger')
            ? 'error'
            : e.category?.includes('warning')
              ? 'warning'
              : e.category?.includes('success')
                ? 'success'
                : undefined;
          notify({ message: e.message, severity: sev, timeout: e.timeout });
          break;
        }
      }
    });
    const offConn = socket.onConnection((c) => {
      setConnected(c);
      if (c) {
        refreshStatus();
        refreshQueue();
      }
    });
    socket.start();
    refreshStatus();
    refreshQueue();
    return () => {
      off();
      offConn();
      socket.stop();
    };
  }, [socket, notify, refreshStatus, refreshQueue]);

  // navigation through the URL hash, so that Back works and pages can be bookmarked
  useEffect(() => {
    const h = () => setPage(pageFromHash());
    window.addEventListener('hashchange', h);
    return () => window.removeEventListener('hashchange', h);
  }, []);
  const go = useCallback((p: Page) => {
    if (pageFromHash() !== p) location.hash = '#/' + p;
    window.scrollTo({ top: 0 });
  }, []);

  const onServerEvent = useCallback((l: (e: ServerEvent) => void) => socket.on(l), [socket]);

  const value: AppState = {
    config,
    t,
    status,
    seekTime,
    queue,
    connected,
    user,
    setUser,
    needsName: !user,
    notify,
    snacks,
    dismissSnack,
    page,
    go,
    refreshStatus,
    refreshQueue,
    reloadConfig,
    onServerEvent,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
