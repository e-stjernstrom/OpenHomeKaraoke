import { useEffect, useMemo, useRef, useState } from 'react';
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
import SearchRounded from '@mui/icons-material/SearchRounded';
import ClearRounded from '@mui/icons-material/ClearRounded';
import MicRounded from '@mui/icons-material/MicRounded';
import AddRounded from '@mui/icons-material/AddRounded';
import CheckRounded from '@mui/icons-material/CheckRounded';
import DownloadRounded from '@mui/icons-material/DownloadRounded';
import ErrorOutlineRounded from '@mui/icons-material/ErrorOutlineRounded';
import LibraryMusicRounded from '@mui/icons-material/LibraryMusicRounded';
import SmartDisplayRounded from '@mui/icons-material/SmartDisplayRounded';
import { getJson, HttpError, postBlob, postJson, type OkResponse, type YouTubeResult } from '../api';
import { useApp } from '../state';
import { S } from '../strings';
import { useEnqueue, useLibrary } from '../library';
import { HelpButton } from '../components/Dialogs';

const isUrl = (s: string) => /^https?:\/\/\S+$/i.test(s.trim());

/** Library matches first (instant), then YouTube on demand. A pasted link downloads directly. */
export default function SearchPage() {
  const { t, config } = useApp();
  const [q, setQ] = useState('');
  const { songs } = useLibrary();
  const enqueue = useEnqueue();
  const [yt, setYt] = useState<YouTubeResult[] | null>(null);
  const [ytBusy, setYtBusy] = useState(false);
  const [ytError, setYtError] = useState('');
  const [karaokeOnly, setKaraokeOnly] = useState(true);
  const [dl, setDl] = useState<{ url: string; title: string } | null>(null);
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
          if (isUrl(query)) setDl({ url: query, title: query });
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
        <Typography variant="body2" color="text.secondary" sx={{ px: 1 }}>
          {t(S.pasteLink)}
        </Typography>
      )}

      {isUrl(query) && (
        <Card>
          <CardContent>
            <Typography variant="body2" sx={{ wordBreak: 'break-all', mb: 2 }}>
              {query}
            </Typography>
            <Button variant="contained" color="secondary" startIcon={<DownloadRounded />} onClick={() => setDl({ url: query, title: query })}>
              {t(S.download)}
            </Button>
          </CardContent>
        </Card>
      )}

      {query && !isUrl(query) && (
        <>
          <Card>
            <List disablePadding subheader={<ListSubheader sx={{ bgcolor: 'transparent' }}>{t(S.inYourLibrary)}</ListSubheader>}>
              {local.length === 0 && (
                <ListItem>
                  <ListItemText secondary={t(S.noResults)} />
                </ListItem>
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
                  <ListItemButton onClick={() => !s.queued && enqueue(s)} disabled={s.queued} sx={{ pr: 7 }}>
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
                  <YouTubeRow key={r.id} r={r} onDownload={() => setDl({ url: r.url, title: r.title })} />
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

function YouTubeRow({ r, onDownload }: { r: YouTubeResult; onDownload: () => void }) {
  const { t, onServerEvent } = useApp();
  const [state, setState] = useState<number | string | null>(null);
  useEffect(() => {
    getJson<number>('/check_download?url=' + encodeURIComponent(r.url))
      .then((v) => setState(v === 1 ? null : v))
      .catch(() => {});
    const started = (e: Event) => (e as CustomEvent<string>).detail === r.url && setState(1);
    window.addEventListener('ohk-download', started);
    const off = onServerEvent((e) => e.type === 'download' && e.url === r.url && setState(e.state));
    return () => {
      window.removeEventListener('ohk-download', started);
      off();
    };
  }, [r.url, onServerEvent]);
  // 1: downloading, 0 / '00': done, -1 / '01': failed (see Karaoke.download_video)
  const busy = state === 1;
  const done = state === 0 || state === '00';
  const failed = state === -1 || state === '01';
  return (
    <ListItem
      disablePadding
      secondaryAction={
        busy ? (
          <CircularProgress size={22} color="secondary" sx={{ mr: 1 }} aria-label={t(S.downloading)} />
        ) : done ? (
          <CheckRounded sx={{ color: 'success.main', mr: 1 }} aria-label={t(S.downloadDone)} />
        ) : (
          <IconButton edge="end" color={failed ? 'error' : 'secondary'} aria-label={t(S.download)} onClick={onDownload}>
            {failed ? <ErrorOutlineRounded /> : <DownloadRounded />}
          </IconButton>
        )
      }
    >
      <ListItemButton onClick={onDownload} disabled={busy || done} sx={{ pr: 7, gap: 1.5 }}>
        <Box
          component="img"
          loading="lazy"
          src={`https://i.ytimg.com/vi/${r.id}/default.jpg`}
          alt=""
          sx={{ width: 64, height: 48, objectFit: 'cover', borderRadius: 1, flexShrink: 0, bgcolor: 'action.hover' }}
        />
        <ListItemText
          primary={r.title}
          secondary={busy ? t(S.downloading) : failed ? t(S.downloadFailed) : r.duration}
          slotProps={{ primary: { sx: { display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' } } }}
        />
      </ListItemButton>
    </ListItem>
  );
}

function DownloadDialog({ item, onClose }: { item: { url: string; title: string } | null; onClose: () => void }) {
  const { t, user, config, notify } = useApp();
  const [enqueue, setEnqueue] = useState(true);
  const [subs, setSubs] = useState(false);
  const [hq, setHq] = useState(config.high_quality);
  const go = () => {
    if (!item) return;
    postJson<OkResponse>('/download', {
      song_url: item.url,
      song_added_by: user,
      enqueue,
      include_subtitles: subs,
      high_quality: hq,
    })
      .then(() => {
        window.dispatchEvent(new CustomEvent('ohk-download', { detail: item.url }));
        notify({ message: t(S.downloading) + ' ' + item.title });
      })
      .catch(() => notify({ message: t(S.downloadFailed), severity: 'error' }));
    onClose();
  };
  const opt = (label: string, help: string, v: boolean, set: (b: boolean) => void) => (
    <Stack direction="row" sx={{ alignItems: 'center' }}>
      <FormControlLabel sx={{ flex: 1 }} control={<Switch checked={v} onChange={(e) => set(e.target.checked)} />} label={label} />
      <HelpButton title={label} text={help} />
    </Stack>
  );
  return (
    <Dialog open={!!item} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t(S.download)}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 1, wordBreak: 'break-word' }}>{item?.title}</DialogContentText>
        {opt(t(S.addAfterDownload), t(S.helpAddAfterDownload), enqueue, setEnqueue)}
        {opt(t(S.includeSubtitles), t(S.helpSubtitles), subs, setSubs)}
        {opt(t(S.highQuality), t(S.helpHighQuality), hq, setHq)}
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
