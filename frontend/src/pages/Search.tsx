import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListSubheader from '@mui/material/ListSubheader';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import MoreVertRounded from '@mui/icons-material/MoreVertRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import ClearRounded from '@mui/icons-material/ClearRounded';
import MicRounded from '@mui/icons-material/MicRounded';
import AddRounded from '@mui/icons-material/AddRounded';
import CheckRounded from '@mui/icons-material/CheckRounded';
import DownloadRounded from '@mui/icons-material/DownloadRounded';
import ErrorOutlineRounded from '@mui/icons-material/ErrorOutlineRounded';
import LibraryMusicRounded from '@mui/icons-material/LibraryMusicRounded';
import SmartDisplayRounded from '@mui/icons-material/SmartDisplayRounded';
import { getJson, hhmmss, HttpError, postBlob, postJson, type OkResponse, type YouTubeResult } from '../api';
import { useApp } from '../state';
import { S } from '../strings';
import { useEnqueue, useLibrary } from '../library';

const hostOf = (u: string) => {
  try {
    return new URL(u).hostname;
  } catch {
    return '';
  }
};
const isUrl = (s: string) => /^https?:\/\/\S+$/i.test(s.trim());

/** High quality / subtitles for downloads, remembered on this device (localStorage). Until the
 *  user picks, high quality follows the server's --high-quality option. */
type DownloadPrefs = { hq: boolean; subs: boolean };
const PREFS_KEY = 'ohk.downloadPrefs';
const prefsListeners = new Set<() => void>();
let savedPrefs: Partial<DownloadPrefs> | null = null;
const readPrefs = (): Partial<DownloadPrefs> => {
  if (!savedPrefs) {
    try {
      savedPrefs = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') || {};
    } catch {
      savedPrefs = {};
    }
  }
  return savedPrefs!;
};
const writePrefs = (p: Partial<DownloadPrefs>) => {
  savedPrefs = { ...readPrefs(), ...p };
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(savedPrefs));
  } catch {
    /* private mode: remembered until the page is reloaded */
  }
  prefsListeners.forEach((f) => f());
};
const subscribePrefs = (f: () => void) => {
  prefsListeners.add(f);
  return () => void prefsListeners.delete(f);
};
function useDownloadPrefs(): [DownloadPrefs, (p: Partial<DownloadPrefs>) => void] {
  const { config } = useApp();
  const saved = useSyncExternalStore(subscribePrefs, readPrefs);
  return [{ hq: saved.hq ?? config.high_quality, subs: saved.subs ?? false }, writePrefs];
}

/** The remembered download settings as switches, so it is visible what one tap downloads. */
function DownloadPrefSwitches() {
  const { t } = useApp();
  const [prefs, setPrefs] = useDownloadPrefs();
  const sw = (label: string, key: keyof DownloadPrefs) => (
    <FormControlLabel
      control={<Switch size="small" checked={prefs[key]} onChange={(e) => setPrefs({ [key]: e.target.checked })} />}
      label={<Typography variant="body2">{label}</Typography>}
    />
  );
  return (
    <>
      {sw(t(S.highQuality), 'hq')}
      {sw(t(S.includeSubtitles), 'subs')}
    </>
  );
}

/** Library matches first (instant), then YouTube on demand. A pasted link downloads directly. */
export default function SearchPage() {
  const { t, config, go } = useApp();
  const [q, setQ] = useState('');
  const { songs } = useLibrary();
  const enqueue = useEnqueue();
  const [yt, setYt] = useState<YouTubeResult[] | null>(null);
  const [ytBusy, setYtBusy] = useState(false);
  const [ytError, setYtError] = useState('');
  const [karaokeOnly, setKaraokeOnly] = useState(true);
  const [dl, setDl] = useState<{ url: string; title: string } | null>(null);
  const startDownload = useStartDownload();
  const [voiceOpen, setVoiceOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const query = q.trim();
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const local = useMemo(
    () => (words.length && songs ? songs.filter((s) => words.every((w) => s.title.toLowerCase().includes(w))).slice(0, 30) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [songs, words.join(' ')],
  );

  useEffect(() => setYt(null), [query]);

  const searchYouTube = () => {
    if (!query || isUrl(query)) return;
    setYtBusy(true);
    setYtError('');
    getJson<{ results: YouTubeResult[] }>(`/api/search?q=${encodeURIComponent(query)}&karaoke=${karaokeOnly}`)
      .then((r) => setYt(r.results))
      .catch(() => setYtError(t(S.youtubeSearchFailed)))
      .finally(() => setYtBusy(false));
  };

  return (
    <Stack spacing={2}>
      <TextField
        inputRef={inputRef}
        fullWidth
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== 'Enter') return;
          if (isUrl(query)) startDownload(query, query);
          else searchYouTube();
          (e.target as HTMLInputElement).blur();
        }}
        placeholder={t(S.searchPlaceholder)}
        slotProps={{
          htmlInput: { enterKeyHint: 'search', 'aria-label': t(S.search) },
          input: {
            sx: { borderRadius: 7, bgcolor: 'background.paper' },
            startAdornment: (
              <InputAdornment position="start">
                <SearchRounded />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                {q && (
                  <IconButton aria-label={t(S.clear)} onClick={() => (setQ(''), inputRef.current?.focus())}>
                    <ClearRounded />
                  </IconButton>
                )}
                {config.asr && (
                  <IconButton aria-label={t(S.searchByVoice)} onClick={() => setVoiceOpen(true)} edge="end">
                    <MicRounded />
                  </IconButton>
                )}
              </InputAdornment>
            ),
          },
        }}
      />

      {!query && (
        <Box sx={{ px: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {t(S.pasteLink)}
          </Typography>
          <Button color="secondary" startIcon={<LibraryMusicRounded />} sx={{ mt: 1, ml: -1 }} onClick={() => go('library')}>
            {t(S.browseLibrary)}
          </Button>
        </Box>
      )}

      {isUrl(query) && (
        <Card>
          <CardContent>
            <Typography variant="body2" sx={{ wordBreak: 'break-all', mb: 1 }}>
              {query}
            </Typography>
            <LinkDownload url={query} onOptions={() => setDl({ url: query, title: query })} />
          </CardContent>
        </Card>
      )}

      {query && !isUrl(query) && (
        <>
          <Card>
            <List disablePadding subheader={<ListSubheader sx={{ bgcolor: 'transparent' }}>{t(S.inYourLibrary)}</ListSubheader>}>
              {local.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ px: 2, pb: 1.5 }}>
                  {t(S.notInLibrary)}
                </Typography>
              )}
              {local.map((s) => (
                <ListItem
                  key={s.file}
                  disablePadding
                  secondaryAction={
                    s.queued ? (
                      <CheckRounded sx={{ color: 'text.secondary', mr: 1 }} aria-label={t(S.alreadyQueued)} />
                    ) : (
                      <IconButton edge="end" color="secondary" aria-label={t(S.addToQueue)} onClick={() => enqueue(s)}>
                        <AddRounded />
                      </IconButton>
                    )
                  }
                >
                  <ListItemButton onClick={() => !s.queued && enqueue(s)} sx={{ pr: 7 }}>
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      <LibraryMusicRounded fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary={s.title} secondary={s.queued ? t(S.alreadyQueued) : undefined} />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          </Card>

          <Card>
            <CardContent sx={{ pb: yt ? 0 : undefined }}>
              <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                <Button
                  variant={yt ? 'text' : 'contained'}
                  color="secondary"
                  startIcon={ytBusy ? <CircularProgress size={18} color="inherit" /> : <SmartDisplayRounded />}
                  onClick={searchYouTube}
                  disabled={ytBusy}
                  sx={{ textTransform: 'none' }}
                >
                  {t(S.searchYouTubeFor, query)}
                </Button>
                <FormControlLabel
                  control={<Switch size="small" checked={karaokeOnly} onChange={(e) => setKaraokeOnly(e.target.checked)} />}
                  label={<Typography variant="body2">{t(S.karaokeOnly)}</Typography>}
                />
                <DownloadPrefSwitches />
              </Stack>
              {ytError && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {ytError}
                </Alert>
              )}
            </CardContent>
            {yt && (
              <List disablePadding subheader={<ListSubheader sx={{ bgcolor: 'transparent' }}>{t(S.onYouTube)}</ListSubheader>}>
                {yt.length === 0 && (
                  <ListItem>
                    <ListItemText secondary={t(S.noResults)} />
                  </ListItem>
                )}
                {yt.map((r) => (
                  <YouTubeRow key={r.id} r={r} onOptions={() => setDl({ url: r.url, title: r.title })} />
                ))}
              </List>
            )}
          </Card>
        </>
      )}

      <DownloadDialog item={dl} onClose={() => setDl(null)} />
      {voiceOpen && <VoiceDialog onClose={() => setVoiceOpen(false)} onText={(text) => setQ(text)} />}
    </Stack>
  );
}

/** The server's download state of one URL, kept current by WebSocket events. */
function useDownloadState(url: string) {
  const { onServerEvent } = useApp();
  const [state, setState] = useState<number | string | null>(null);
  const [since, setSince] = useState<number | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  useEffect(() => {
    setState(null);
    getJson<number | string>('/check_download?url=' + encodeURIComponent(url))
      // a late answer must not undo a download started meanwhile
      .then((v) => setState((prev) => (prev !== null ? prev : v === '' ? null : v)))
      .catch(() => {});
    const started = (e: Event) => {
      if ((e as CustomEvent<string>).detail !== url) return;
      setState(1);
      setSince(Date.now());
    };
    window.addEventListener('ohk-download', started);
    const off = onServerEvent((e) => {
      if (e.type !== 'download' || e.url !== url) return;
      setState(e.state);
      setProgress(e.progress ?? null);
      if (e.state === 1) setSince((t) => t ?? Date.now());
    });
    return () => {
      window.removeEventListener('ohk-download', started);
      off();
    };
  }, [url, onServerEvent]);
  // 1: downloading, 0 / '00': done, -1: failed, '01': downloaded but not found (see Karaoke.download_video)
  return { busy: state === 1, done: state === 0 || state === '00', failed: state === -1 || state === '01', refused: state === -1, since, progress };
}

/** Seconds since `since`, updated every second. */
function useElapsed(since: number | null, on: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!on) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [on]);
  return on && since ? Math.max(0, (now - since) / 1000) : null;
}

function useStartDownload() {
  const { t, user, notify } = useApp();
  const [prefs] = useDownloadPrefs();
  return (url: string, title: string, opts?: { enqueue: boolean; subs: boolean; hq: boolean }) => {
    const o = opts ?? { enqueue: true, ...prefs };
    window.dispatchEvent(new CustomEvent('ohk-download', { detail: url }));
    postJson<OkResponse>('/download', {
      song_url: url,
      song_added_by: user,
      enqueue: o.enqueue,
      include_subtitles: o.subs,
      high_quality: o.hq,
    })
      .then(() => notify({ message: o.enqueue ? t(S.downloadingQueued, title) : `${t(S.downloading)} ${title}` }))
      .catch(() => notify({ message: t(S.downloadFailed), severity: 'error' }));
  };
}

/** Download a pasted link (YouTube, Bilibili, … whatever yt-dlp supports), with what is happening. */
function LinkDownload({ url, onOptions }: { url: string; onOptions: () => void }) {
  const { t } = useApp();
  const start = useStartDownload();
  const { busy, done, failed, refused, since, progress } = useDownloadState(url);
  const secs = useElapsed(since, busy);
  if (busy)
    return (
      <Box>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
          <CircularProgress size={20} color="secondary" />
          <Typography variant="body2" sx={{ flex: 1 }}>
            {t(S.downloading)}
            {progress !== null ? ` ${Math.round(progress * 100)}%` : ''}
          </Typography>
          {secs !== null && (
            <Typography variant="body2" color="text.secondary">
              {hhmmss(secs)}
            </Typography>
          )}
        </Stack>
        <LinearProgress
          color="secondary"
          variant={progress !== null ? 'determinate' : 'indeterminate'}
          value={(progress ?? 0) * 100}
          sx={{ mt: 1.5, borderRadius: 1 }}
        />
        {secs !== null && secs > 120 && (
          <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 1 }}>
            {t(S.downloadSlow)}
          </Typography>
        )}
      </Box>
    );
  return (
    <Stack spacing={1}>
      {done && <Alert severity="success">{t(S.downloadDone)}</Alert>}
      {failed && (
        <Alert severity="error">{refused && !/(^|\.)(youtube\.com|youtu\.be)$/.test(hostOf(url)) ? t(S.downloadFailedSite) : t(S.downloadFailed)}</Alert>
      )}
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
        <Button variant="contained" color="secondary" startIcon={<DownloadRounded />} onClick={() => start(url, url)}>
          {t(S.download)}
        </Button>
        <Button color="secondary" onClick={onOptions}>
          {t(S.downloadOptions)}
        </Button>
      </Stack>
      <Stack direction="row" useFlexGap sx={{ flexWrap: 'wrap' }}>
        <DownloadPrefSwitches />
      </Stack>
    </Stack>
  );
}

const fmtDuration = (d: string) => {
  const m = /^(\d+):(\d+):(\d+)/.exec(d || '');
  return m ? hhmmss(+m[1] * 3600 + +m[2] * 60 + +m[3]) : d;
};

function YouTubeRow({ r, onOptions }: { r: YouTubeResult; onOptions: () => void }) {
  const { t } = useApp();
  const start = useStartDownload();
  const { busy, done, failed, since, progress } = useDownloadState(r.url);
  const secs = useElapsed(since, busy);
  const download = () => start(r.url, r.title);
  return (
    <ListItem
      disablePadding
      secondaryAction={
        <Stack direction="row" sx={{ alignItems: 'center' }}>
          {busy ? (
            <CircularProgress size={22} color="secondary" sx={{ mx: 1 }} aria-label={t(S.downloading)} />
          ) : done ? (
            <CheckRounded sx={{ color: 'success.main', mx: 1 }} aria-label={t(S.downloadDone)} />
          ) : (
            <IconButton color={failed ? 'error' : 'secondary'} aria-label={t(S.download)} onClick={download}>
              {failed ? <ErrorOutlineRounded /> : <DownloadRounded />}
            </IconButton>
          )}
          <IconButton edge="end" aria-label={t(S.downloadOptions)} onClick={onOptions} disabled={busy || done}>
            <MoreVertRounded />
          </IconButton>
        </Stack>
      }
    >
      <ListItemButton onClick={download} disabled={busy || done} sx={{ pr: 12, gap: 1.5 }}>
        <Box
          component="img"
          loading="lazy"
          src={`https://i.ytimg.com/vi/${r.id}/default.jpg`}
          alt=""
          sx={{ width: 64, height: 48, objectFit: 'cover', borderRadius: 1, flexShrink: 0, bgcolor: 'action.hover' }}
        />
        <ListItemText
          primary={r.title}
          secondary={
            busy
              ? `${t(S.downloading)}${progress !== null ? ` ${Math.round(progress * 100)}%` : ''}${secs !== null ? ` · ${hhmmss(secs)}` : ''}`
              : failed
                ? t(S.downloadFailed)
                : done
                  ? t(S.downloadDone)
                  : fmtDuration(r.duration)
          }
          slotProps={{ primary: { sx: { display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' } } }}
        />
      </ListItemButton>
    </ListItem>
  );
}

function DownloadDialog({ item, onClose }: { item: { url: string; title: string } | null; onClose: () => void }) {
  const { t } = useApp();
  const start = useStartDownload();
  const [prefs, setPrefs] = useDownloadPrefs();
  const [enqueue, setEnqueue] = useState(true);
  const [subs, setSubs] = useState(prefs.subs);
  const [hq, setHq] = useState(prefs.hq);
  useEffect(() => {
    // start from the remembered settings each time the dialog opens
    if (!item) return;
    setEnqueue(true);
    setSubs(prefs.subs);
    setHq(prefs.hq);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item]);
  const go = () => {
    if (item) {
      setPrefs({ subs, hq }); // what is picked here is used for the next downloads too
      start(item.url, item.title, { enqueue, subs, hq });
    }
    onClose();
  };
  const opt = (label: string, hint: string, v: boolean, set: (b: boolean) => void) => (
    <FormControlLabel
      sx={{ alignItems: 'flex-start', my: 0.5, mx: 0 }}
      control={<Switch checked={v} onChange={(e) => set(e.target.checked)} />}
      label={
        <Box sx={{ pt: 1 }}>
          <Typography variant="body2">{label}</Typography>
          {hint && (
            <Typography variant="caption" color="text.secondary">
              {hint}
            </Typography>
          )}
        </Box>
      }
    />
  );
  return (
    <Dialog open={!!item} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t(S.downloadOptions)}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 1, wordBreak: 'break-word' }}>{item?.title}</DialogContentText>
        <Stack>
          {opt(t(S.addAfterDownload), '', enqueue, setEnqueue)}
          {opt(t(S.includeSubtitles), t(S.subtitlesHint), subs, setSubs)}
          {opt(t(S.highQuality), t(S.hqHint), hq, setHq)}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t(S.cancel)}</Button>
        <Button variant="contained" color="secondary" startIcon={<DownloadRounded />} onClick={go}>
          {t(S.download)}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** Hold-free voice search: record until Done, then the server recognises it (needs --cloud and HTTPS). */
function VoiceDialog({ onClose, onText }: { onClose: () => void; onText: (s: string) => void }) {
  const { t, config, notify } = useApp();
  const enqueue = useEnqueue();
  const [phase, setPhase] = useState<'start' | 'listening' | 'working' | 'result'>('start');
  const [result, setResult] = useState<{ text: string; matches: { file: string; title: string }[] } | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const secure = window.isSecureContext && !!navigator.mediaDevices;
  const httpsUrl = `https://${location.hostname}:${config.https_port}/#/search`;

  useEffect(() => {
    if (!secure) return;
    let stream: MediaStream | undefined;
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((s) => {
        stream = s;
        const r = new MediaRecorder(s);
        const chunks: Blob[] = [];
        r.ondataavailable = (e) => chunks.push(e.data);
        r.onstop = () => {
          s.getTracks().forEach((tr) => tr.stop());
          setPhase('working');
          postBlob<{ text: string; matches: { file: string; title: string }[] }>('/api/voice_find', new Blob(chunks, { type: r.mimeType }))
            .then((res) => {
              setResult(res);
              setPhase('result');
              if (res.text) onText(res.text);
            })
            .catch((e) => {
              notify({ message: e instanceof HttpError && e.status === 501 ? t(S.voiceNotSetUp) : t(S.noResults), severity: 'error' });
              onClose();
            });
        };
        rec.current = r;
        r.start();
        setPhase('listening');
      })
      .catch(() => {
        notify({ message: t(S.micNeedsPermission), severity: 'error' });
        onClose();
      });
    return () => {
      if (rec.current?.state === 'recording') {
        rec.current.onstop = null;
        rec.current.stop();
      }
      stream?.getTracks().forEach((tr) => tr.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t(S.searchByVoice)}</DialogTitle>
      <DialogContent>
        {!secure ? (
          <DialogContentText>{t(S.needHttps)}</DialogContentText>
        ) : phase === 'result' && result ? (
          result.matches.length ? (
            <List dense>
              {result.matches.slice(0, 10).map((m) => (
                <ListItemButton
                  key={m.file}
                  onClick={() => {
                    enqueue(m);
                    onClose();
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 36 }}>
                    <AddRounded fontSize="small" />
                  </ListItemIcon>
                  <ListItemText primary={m.title} />
                </ListItemButton>
              ))}
            </List>
          ) : (
            <DialogContentText>{t(S.noMatchSpoken, result.text)}</DialogContentText>
          )
        ) : (
          <Stack spacing={2} sx={{ alignItems: 'center', py: 2 }}>
            {phase === 'working' ? <CircularProgress color="secondary" /> : <MicRounded color="secondary" sx={{ fontSize: 56 }} />}
            <Typography color="text.secondary" sx={{ textAlign: 'center' }}>
              {phase === 'listening' ? t(S.helpListening) : t(S.listening)}
            </Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {!secure ? (
          <Button color="secondary" href={httpsUrl}>
            {t(S.open)}
          </Button>
        ) : phase === 'listening' ? (
          <Button variant="contained" color="secondary" onClick={() => rec.current?.stop()}>
            {t(S.done)}
          </Button>
        ) : null}
        <Button onClick={onClose}>{t(S.close)}</Button>
      </DialogActions>
    </Dialog>
  );
}
