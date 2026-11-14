import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import Box from '@mui/material/Box';
import CheckCircleOutlineRounded from '@mui/icons-material/CheckCircleOutlineRounded';
import HourglassTopRounded from '@mui/icons-material/HourglassTopRounded';
import ScheduleRounded from '@mui/icons-material/ScheduleRounded';
import ErrorOutlineRounded from '@mui/icons-material/ErrorOutlineRounded';
import DoNotDisturbOnOutlined from '@mui/icons-material/DoNotDisturbOnOutlined';
import { getText, type SplitInfo, type Status } from '../api';
import { useApp } from '../state';
import { S } from '../strings';

export function modelName(m: string | undefined) {
  return m === 'baseline' ? 'Baseline' : m === 'LR' ? 'L-R/L+R' : m || '';
}

type Mode = 'nonvocal' | 'mixed' | 'vocal';

/** What the vocal_info bits from /nowplaying say (see Karaoke.get_vocal_info). */
export function vocalBits(info: number) {
  const dnn = !!(info & 0x40);
  const modeNum = (info >> 4) & 3;
  return {
    instrumental: !!(dnn ? info & 1 : info & 4),
    vocal: !!(dnn ? info & 2 : info & 8),
    mode: (modeNum === 1 ? 'nonvocal' : modeNum === 3 ? 'vocal' : 'mixed') as Mode,
  };
}

/** Music / Mixed / Voice for the playing song, and a line that says why a choice is not available. */
export default function VocalSwitch({ status }: { status: Status }) {
  const { t, config } = useApp();
  const bits = vocalBits(status.vocal_info);
  const set = (m: Mode | null) => {
    if (!m || m === bits.mode) return;
    getText('/play_vocal/' + m).catch(() => {});
  };
  return (
    <Stack spacing={1}>
      <ToggleButtonGroup
        exclusive
        fullWidth
        size="small"
        color="secondary"
        value={bits.mode}
        onChange={(_, v) => set(v)}
        aria-label={t(S.vocalRemoval)}
      >
        <ToggleButton value="nonvocal" disabled={!bits.instrumental}>
          {t(S.music)}
        </ToggleButton>
        <ToggleButton value="mixed">{t(S.mixed)}</ToggleButton>
        <ToggleButton value="vocal" disabled={!bits.vocal}>
          {t(S.voice)}
        </ToggleButton>
      </ToggleButtonGroup>
      <SplitLine split={status.split} hasOlder={bits.instrumental} admin={config.admin} />
    </Stack>
  );
}

/** One line about the instrumental of a song: ready, being made (with progress), waiting, failed, off. */
export function SplitLine({ split, hasOlder, admin, dense }: { split: SplitInfo | null; hasOlder?: boolean; admin?: boolean; dense?: boolean }) {
  const { t, refreshStatus } = useApp();
  if (!split) return null;
  const model = modelName(split.model);
  const act = (url: string) => () => getText(url).finally(() => setTimeout(refreshStatus, 800));
  let icon = <ScheduleRounded fontSize="inherit" />;
  let text = '';
  let action: React.ReactNode = null;
  let color = 'text.secondary';
  switch (split.state) {
    case 'done':
      icon = <CheckCircleOutlineRounded fontSize="inherit" />;
      text = t(S.splitDone, model);
      break;
    case 'processing':
      icon = <HourglassTopRounded fontSize="inherit" />;
      text = t(S.splitProcessing, `${Math.round((split.progress ?? 0) * 100)}%`);
      break;
    case 'queued':
      text = split.ahead ? t(S.splitQueued, split.ahead) : t(S.splitQueuedNext);
      break;
    case 'failed':
      icon = <ErrorOutlineRounded fontSize="inherit" />;
      text = t(S.splitFailed);
      color = 'error.main';
      break;
    case 'off':
      icon = <DoNotDisturbOnOutlined fontSize="inherit" />;
      text = t(S.splitOff);
      if (admin) action = <Button size="small" color="secondary" onClick={act('/vocal_split/true')}>{t(S.turnOn)}</Button>;
      break;
    case 'stopped':
      icon = <ErrorOutlineRounded fontSize="inherit" />;
      text = t(S.splitStopped);
      if (admin) action = <Button size="small" color="secondary" onClick={act('/bg-process/vocal-restart')}>{t(S.restart)}</Button>;
      break;
    case 'unavailable':
      icon = <DoNotDisturbOnOutlined fontSize="inherit" />;
      text = t(S.splitUnavailable);
      break;
  }
  const older = (split.state === 'processing' || split.state === 'queued') && hasOlder ? t(S.splitOlderResult, model) : '';
  return (
    <Box>
      <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', color, minHeight: dense ? 20 : 30 }}>
        <Box component="span" sx={{ display: 'flex', fontSize: dense ? 16 : 18 }}>
          {icon}
        </Box>
        <Typography variant={dense ? 'caption' : 'body2'} sx={{ flex: 1 }} title={split.error || undefined}>
          {text}
          {split.state !== 'done' && split.state !== 'unavailable' && split.state !== 'off' && !dense && ` · ${model}`}
        </Typography>
        {action}
      </Stack>
      {split.state === 'processing' && (
        <LinearProgress variant="determinate" color="secondary" value={(split.progress ?? 0) * 100} sx={{ mt: 0.5, borderRadius: 1 }} />
      )}
      {older && !dense && (
        <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 0.5 }}>
          {older}
        </Typography>
      )}
    </Box>
  );
}
