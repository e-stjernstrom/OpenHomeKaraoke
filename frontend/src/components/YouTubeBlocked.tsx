import { useEffect, useState } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import BlockRounded from '@mui/icons-material/BlockRounded';
import LibraryMusicRounded from '@mui/icons-material/LibraryMusicRounded';
import { getJson } from '../api';
import { useApp } from '../state';
import { S } from '../strings';

/** GET /api/youtube_status */
type YouTubeStatus = { blocked_ago: number | null; pot: 'running' | 'missing' | 'off'; cookies: boolean };
const NOTICE_MINUTES = 30;
const BLOCKED_EVENT = 'ohk-youtube-blocked';

/** When YouTube refuses a download as a suspected bot: say so plainly and what helps instead,
 *  since trying again right away is refused too. The admin also sees what to change on the server. */
export function YouTubeBlockedDialog() {
  const { t, config, go, onServerEvent } = useApp();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<YouTubeStatus | null>(null);
  useEffect(
    () =>
      onServerEvent((e) => {
        if (e.type !== 'download' || e.reason !== 'blocked') return;
        window.dispatchEvent(new Event(BLOCKED_EVENT));
        setOpen(true);
        getJson<YouTubeStatus>('/api/youtube_status').then(setStatus).catch(() => {});
      }),
    [onServerEvent],
  );
  const adminTip =
    config.admin && status
      ? status.pot === 'missing'
        ? S.ytBlockedAdminInstall
        : status.pot === 'off'
          ? S.ytBlockedAdminOff
          : !status.cookies
            ? S.ytBlockedAdminCookies
            : null
      : null;
  const close = () => setOpen(false);
  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="xs" aria-labelledby="yt-blocked-title">
      <DialogTitle id="yt-blocked-title" sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
        <BlockRounded color="error" />
        {t(S.ytBlockedTitle)}
      </DialogTitle>
      <DialogContent>
        <DialogContentText>{t(S.ytBlockedText)}</DialogContentText>
        <Typography variant="subtitle2" sx={{ mt: 2 }}>
          {t(S.ytBlockedWhatToDo)}
        </Typography>
        <Box component="ol" sx={{ pl: 2.5, my: 1, '& li': { mb: 0.75 } }}>
          <Typography component="li" variant="body2">
            {t(S.ytBlockedSingLibrary)}
          </Typography>
          <Typography component="li" variant="body2">
            {t(S.ytBlockedLater)}
          </Typography>
          <Typography component="li" variant="body2">
            {t(S.ytBlockedNetwork)}
          </Typography>
        </Box>
        {adminTip && (
          <Alert severity="info" sx={{ mt: 1, wordBreak: 'break-word' }}>
            {t(adminTip)}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>{t(S.close)}</Button>
        <Button
          variant="contained"
          color="secondary"
          startIcon={<LibraryMusicRounded />}
          onClick={() => {
            close();
            go('library');
          }}
        >
          {t(S.browseLibrary)}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** On the search page: YouTube refused a download recently (asked by any phone), so a new try will
 *  most likely be refused too. Shown for NOTICE_MINUTES. */
export function YouTubeBlockedNotice() {
  const { t } = useApp();
  const [ago, setAgo] = useState<number | null>(null);
  useEffect(() => {
    const load = () =>
      getJson<YouTubeStatus>('/api/youtube_status')
        .then((s) => setAgo(s.blocked_ago))
        .catch(() => {});
    load();
    window.addEventListener(BLOCKED_EVENT, load);
    const timer = window.setInterval(load, 60000);
    return () => {
      window.removeEventListener(BLOCKED_EVENT, load);
      window.clearInterval(timer);
    };
  }, []);
  if (ago === null || ago > NOTICE_MINUTES * 60) return null;
  return <Alert severity="warning">{t(S.ytBlockedNotice, Math.max(1, Math.round(ago / 60)))}</Alert>;
}
