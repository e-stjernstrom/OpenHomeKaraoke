import { useEffect, useRef, useState } from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Fab from '@mui/material/Fab';
import Slider from '@mui/material/Slider';
import Tooltip from '@mui/material/Tooltip';
import Divider from '@mui/material/Divider';
import Chip from '@mui/material/Chip';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Skeleton from '@mui/material/Skeleton';
import ReplayRounded from '@mui/icons-material/ReplayRounded';
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded';
import PauseRounded from '@mui/icons-material/PauseRounded';
import SkipNextRounded from '@mui/icons-material/SkipNextRounded';
import VolumeDownRounded from '@mui/icons-material/VolumeDownRounded';
import VolumeUpRounded from '@mui/icons-material/VolumeUpRounded';
import AddRounded from '@mui/icons-material/AddRounded';
import RemoveRounded from '@mui/icons-material/RemoveRounded';
import ExpandMoreRounded from '@mui/icons-material/ExpandMoreRounded';
import MicExternalOffRounded from '@mui/icons-material/MicExternalOffRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import GraphicEqRounded from '@mui/icons-material/GraphicEqRounded';
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded';
import { getText, hhmmss, seg, type Status } from '../api';
import { useApp } from '../state';
import { S } from '../strings';
import VocalSwitch from '../components/VocalSwitch';
import { HelpButton, useConfirm } from '../components/Dialogs';

export default function HomePage() {
  const { status, t, go } = useApp();
  if (status === null) {
    return (
      <Stack spacing={2}>
        <Skeleton variant="rounded" height={120} />
        <Skeleton variant="rounded" height={320} />
      </Stack>
    );
  }
  const playing = !!status.now_playing;
  return (
    <Stack spacing={2}>
      {playing ? (
        <NowPlaying status={status} />
      ) : (
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 5 }}>
            <MicExternalOffRounded sx={{ fontSize: 48, color: 'text.secondary' }} />
            <Typography variant="h6" sx={{ mt: 1 }}>
              {t(S.nothingPlaying)}
            </Typography>
            <Button variant="contained" color="secondary" startIcon={<SearchRounded />} sx={{ mt: 2 }} onClick={() => go('search')}>
              {t(S.findASong)}
            </Button>
          </CardContent>
        </Card>
      )}
      <UpNext status={status} />
      {playing && <PlayerControls status={status} />}
    </Stack>
  );
}

function NowPlaying({ status }: { status: Status }) {
  const { t } = useApp();
  return (
    <Card>
      <CardContent>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          <Typography variant="overline" color="text.secondary" sx={{ flex: 1 }}>
            {t(S.nowSinging)}
          </Typography>
          {!status.is_paused && <GraphicEqRounded fontSize="small" sx={{ color: 'highlight.main' }} aria-hidden />}
        </Stack>
        <Typography variant="h5" component="h2" sx={{ color: 'highlight.main', wordBreak: 'break-word' }}>
          {status.now_playing}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {t(S.addedBy, status.now_playing_user || '')}
        </Typography>
        <Box sx={{ mt: 2 }}>
          <VocalSwitch status={status} />
        </Box>
      </CardContent>
    </Card>
  );
}

function UpNext({ status }: { status: Status }) {
  const { t, go } = useApp();
  return (
    <Card>
      <ListItemButton onClick={() => go('queue')} sx={{ py: 1.5 }}>
        <ListItemText
          primary={
            <Typography variant="overline" color="text.secondary" sx={{ display: 'block' }}>
              {t(S.upNext)}
            </Typography>
          }
          secondary={
            status.up_next ? (
              <>
                <Typography component="span" variant="subtitle1" sx={{ color: 'text.primary', display: 'block' }} noWrap>
                  {status.up_next}
                </Typography>
                <Typography component="span" variant="body2" color="text.secondary">
                  {t(S.addedBy, status.next_user || '')}
                </Typography>
              </>
            ) : (
              <Typography component="span" variant="body2" color="text.secondary">
                {t(S.noSongQueued)}
              </Typography>
            )
          }
        />
        <ChevronRightRounded sx={{ color: 'text.secondary', transform: (th) => (th.direction === 'rtl' ? 'scaleX(-1)' : undefined) }} />
      </ListItemButton>
    </Card>
  );
}

/** A value that follows the server but not while the user is dragging or stepping it. */
function useLocal<T>(server: T, holdMs = 1500) {
  const [local, setLocal] = useState(server);
  const busyUntil = useRef(0);
  useEffect(() => {
    if (Date.now() > busyUntil.current) setLocal(server);
  }, [server]);
  const set = (v: T) => {
    busyUntil.current = Date.now() + holdMs;
    setLocal(v);
  };
  return [local, set] as const;
}

function PlayerControls({ status }: { status: Status }) {
  const { t, config, user, seekTime, refreshStatus } = useApp();
  const confirm = useConfirm();
  const call = (url: string) => getText(url).catch(() => {});

  const max = status.seektrack_max ?? 0;
  const [seek, setSeek] = useState<number | null>(null);
  const shownTime = seek ?? seekTime ?? 0;

  const [vol, setVol] = useLocal(status.volume ?? 0);
  const [key, setKey] = useLocal(Number(status.transpose_value) || 0, 2500);
  const [speed, setSpeed] = useLocal(status.play_speed ?? 1);
  const keyTimer = useRef<number | undefined>(undefined);

  const changeKey = (k: number) => {
    k = Math.max(-12, Math.min(12, k));
    setKey(k);
    // each change reloads the player, so wait until the user stops tapping
    window.clearTimeout(keyTimer.current);
    keyTimer.current = window.setTimeout(() => call('/transpose/' + k), 700);
  };

  const skip = async () => {
    const own = status.now_playing_user === user || status.now_playing_user === 'Random';
    if (!own && !(await confirm({ title: t(S.skipSong), text: t(S.confirmSkip), confirm: t(S.skipSong) }))) return;
    call('/skip');
  };

  const pct = (v: number) => `${Math.round((v / 256) * 100)}%`;
  const keyLabel = key === 0 ? t(S.originalKey) : `${key > 0 ? '+' : ''}${key}${t(S.semitones) ? ' ' + t(S.semitones) : ''}`;

  return (
    <Card>
      <CardContent>
        {/* transport */}
        <Stack direction="row" spacing={3} sx={{ alignItems: 'center', justifyContent: 'center', my: 1 }}>
          <Tooltip title={t(S.restartSong)}>
            <IconButton size="large" aria-label={t(S.restartSong)} onClick={() => call('/restart')}>
              <ReplayRounded fontSize="large" />
            </IconButton>
          </Tooltip>
          <Fab
            color="secondary"
            aria-label={t(S.playPause)}
            onClick={() => getText('/pause').then(() => setTimeout(refreshStatus, 300))}
          >
            {status.is_paused ? <PlayArrowRounded fontSize="large" /> : <PauseRounded fontSize="large" />}
          </Fab>
          <Tooltip title={t(S.skipSong)}>
            <IconButton size="large" aria-label={t(S.skipSong)} onClick={skip}>
              <SkipNextRounded fontSize="large" />
            </IconButton>
          </Tooltip>
        </Stack>

        {/* position */}
        <Slider
          aria-label={t(S.nowPlaying)}
          min={0}
          max={Math.max(1, max)}
          value={Math.min(shownTime, max || 1)}
          onChange={(_, v) => setSeek(v as number)}
          onChangeCommitted={(_, v) => {
            call('/seek/' + Math.round(v as number));
            setTimeout(() => setSeek(null), 1000);
          }}
          sx={{ mt: 1 }}
        />
        <Stack direction="row" sx={{ justifyContent: 'space-between', mt: -1 }}>
          <Typography variant="caption" color="text.secondary">
            {hhmmss(shownTime)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {hhmmss(max)}
          </Typography>
        </Stack>

        {/* volume */}
        <Stack direction="row" spacing={2} sx={{ alignItems: 'center', mt: 2 }}>
          <VolumeDownRounded sx={{ color: 'text.secondary' }} />
          <Slider
            aria-label={t(S.volume)}
            min={0}
            max={512}
            step={8}
            value={vol}
            valueLabelDisplay="auto"
            valueLabelFormat={pct}
            onChange={(_, v) => setVol(v as number)}
            onChangeCommitted={(_, v) => call('/vol/' + v)}
          />
          <VolumeUpRounded sx={{ color: 'text.secondary' }} />
          <Typography variant="body2" sx={{ minWidth: 44, textAlign: 'end' }}>
            {pct(vol)}
          </Typography>
        </Stack>
        {status.vol_norm && <Chip size="small" label={t(S.volumeNormalized)} sx={{ mt: 1 }} />}

        {config.use_vlc && (
          <>
            <Divider sx={{ my: 2 }} />
            {/* key */}
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <Typography variant="subtitle2" sx={{ flex: 1 }}>
                {t(S.key)}
              </Typography>
              <HelpButton title={t(S.key)} text={t(S.helpSemitones)} />
            </Stack>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 0.5 }}>
              <IconButton aria-label="−1" onClick={() => changeKey(key - 1)} disabled={key <= -12} sx={{ border: 1, borderColor: 'divider' }}>
                <RemoveRounded />
              </IconButton>
              <Typography variant="h6" sx={{ flex: 1, textAlign: 'center' }} aria-live="polite">
                {keyLabel}
              </Typography>
              <IconButton aria-label="+1" onClick={() => changeKey(key + 1)} disabled={key >= 12} sx={{ border: 1, borderColor: 'divider' }}>
                <AddRounded />
              </IconButton>
            </Stack>
            <Box sx={{ textAlign: 'center', minHeight: 36 }}>
              {key !== 0 && (
                <Button size="small" color="secondary" onClick={() => changeKey(0)}>
                  {t(S.originalKey)}
                </Button>
              )}
            </Box>

            {/* speed */}
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 1 }}>
              <Typography variant="subtitle2" sx={{ flex: 1 }}>
                {t(S.speed)}
              </Typography>
              <Typography variant="body2">{speed.toFixed(2)}×</Typography>
              <HelpButton title={t(S.speed)} text={t(S.helpSpeed)} />
            </Stack>
            <Slider
              aria-label={t(S.speed)}
              min={0.8}
              max={1.2}
              step={0.01}
              marks={[{ value: 1 }]}
              value={speed}
              onChange={(_, v) => setSpeed(v as number)}
              onChangeCommitted={(_, v) => call('/play_speed/' + v)}
            />
            <Box sx={{ textAlign: 'center', minHeight: 36 }}>
              {Math.abs(speed - 1) > 0.001 && (
                <Button
                  size="small"
                  color="secondary"
                  onClick={() => {
                    setSpeed(1);
                    call('/play_speed/1');
                  }}
                >
                  {t(S.normalSpeed)}
                </Button>
              )}
            </Box>
          </>
        )}
      </CardContent>

      <FineTune status={status} />
    </Card>
  );
}

/** Audio and subtitle delay, folded away: rarely needed. */
function FineTune({ status }: { status: Status }) {
  const { t } = useApp();
  const hasSub = 'subtitle_delay' in status;
  return (
    <Accordion disableGutters elevation={0} square sx={{ bgcolor: 'transparent', '&:before': { display: 'none' }, borderTop: 1, borderColor: 'divider' }}>
      <AccordionSummary expandIcon={<ExpandMoreRounded />}>
        <Typography variant="subtitle2">{t(S.fineTune)}</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stepper
          label={t(S.audioDelay)}
          help={t(S.helpAudioDelay)}
          value={status.audio_delay}
          digits={2}
          url="/audio_delay/"
          labels={[88, 90]}
        />
        {hasSub && (
          <>
            <FormControlLabel
              control={
                <Switch checked={!!status.show_subtitle} onChange={() => getText('/toggle_subtitle')} />
              }
              label={t(S.showSubtitles)}
              sx={{ mt: 1 }}
            />
            <Stepper
              label={t(S.subtitleDelay)}
              help={t(S.helpSubtitleDelay)}
              value={status.subtitle_delay ?? 0}
              digits={1}
              url="/subtitle_delay/"
              labels={[85, 87]}
            />
          </>
        )}
      </AccordionDetails>
    </Accordion>
  );
}

function Stepper({
  label,
  help,
  value,
  digits,
  url,
  labels,
}: {
  label: string;
  help: string;
  value: number | null | undefined;
  digits: number;
  url: string;
  labels: [number, number];
}) {
  const { t } = useApp();
  const [v, setV] = useLocal(value ?? 0);
  const [text, setText] = useState<string | null>(null);
  const send = (arg: string) =>
    getText(url + seg(arg)).then((r) => {
      const n = parseFloat(r);
      if (isFinite(n)) setV(n);
    });
  return (
    <Box sx={{ mt: 1 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <Typography variant="body2" sx={{ flex: 1 }}>
          {label}
        </Typography>
        <HelpButton title={label} text={help} />
      </Stack>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <IconButton aria-label={t(labels[0] as never)} onClick={() => send('-')} sx={{ border: 1, borderColor: 'divider' }}>
          <RemoveRounded />
        </IconButton>
        <Box
          component="input"
          inputMode="decimal"
          aria-label={label}
          value={text ?? v.toFixed(digits)}
          onFocus={() => setText(v.toFixed(digits))}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setText(e.target.value.replace(/[^0-9.\-]/g, ''))}
          onBlur={() => {
            if (text !== null && text !== '' && isFinite(parseFloat(text))) send(String(parseFloat(text)));
            setText(null);
          }}
          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          sx={{
            flex: 1,
            minWidth: 0,
            textAlign: 'center',
            font: 'inherit',
            fontSize: '1.25rem',
            color: 'text.primary',
            bgcolor: 'transparent',
            border: 'none',
            borderBottom: 1,
            borderColor: 'divider',
            py: 0.5,
            '&:focus': { outline: 'none', borderColor: 'secondary.main' },
          }}
        />
        <IconButton aria-label={t(labels[1] as never)} onClick={() => send('+')} sx={{ border: 1, borderColor: 'divider' }}>
          <AddRounded />
        </IconButton>
      </Stack>
    </Box>
  );
}
