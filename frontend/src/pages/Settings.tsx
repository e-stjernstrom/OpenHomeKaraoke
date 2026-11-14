import { useCallback, useEffect, useState, type ReactNode } from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Switch from '@mui/material/Switch';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Divider from '@mui/material/Divider';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Skeleton from '@mui/material/Skeleton';
import ContentCopyRounded from '@mui/icons-material/ContentCopyRounded';
import LockOpenRounded from '@mui/icons-material/LockOpenRounded';
import LogoutRounded from '@mui/icons-material/LogoutRounded';
import RefreshRounded from '@mui/icons-material/RefreshRounded';
import SystemUpdateAltRounded from '@mui/icons-material/SystemUpdateAltRounded';
import PowerSettingsNewRounded from '@mui/icons-material/PowerSettingsNewRounded';
import RestartAltRounded from '@mui/icons-material/RestartAltRounded';
import ExitToAppRounded from '@mui/icons-material/ExitToAppRounded';
import SdCardRounded from '@mui/icons-material/SdCardRounded';
import { getJson, getText, postJson, type OkResponse, type Settings } from '../api';
import { useApp } from '../state';
import { S, type StringId } from '../strings';
import { errorText } from '../library';
import { HelpButton, useConfirm } from '../components/Dialogs';

const gb = (b: number) => (b / 1024 ** 3).toFixed(1) + ' GB';

export default function SettingsPage() {
  const { config } = useApp();
  const [s, setS] = useState<Settings | null>(null);
  const load = useCallback(() => {
    getJson<Settings>('/api/settings').then(setS).catch(() => {});
  }, []);
  useEffect(load, [load, config.admin]);

  return (
    <Stack spacing={2}>
      <ShareCard />
      <AdminCard />
      {!s ? (
        <Skeleton variant="rounded" height={240} />
      ) : (
        <>
          {s.admin && <VocalCard s={s} reload={load} />}
          {s.admin && <PlaybackCard s={s} reload={load} />}
          {s.admin && <ServerLanguageCard s={s} reload={load} />}
          {s.admin && <LibraryCard s={s} reload={load} />}
          <AboutCard s={s} reload={load} />
          {s.admin && <DangerCard s={s} />}
        </>
      )}
    </Stack>
  );
}

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} action={action} slotProps={{ title: { variant: 'h6' } }} sx={{ pb: 0 }} />
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Toggle({ label, help, checked, onChange }: { label: string; help?: string; checked: boolean; onChange: (b: boolean) => void }) {
  return (
    <Stack direction="row" sx={{ alignItems: 'center' }}>
      <FormControlLabel sx={{ flex: 1, mr: 0 }} control={<Switch checked={checked} onChange={(e) => onChange(e.target.checked)} />} label={label} />
      {help && <HelpButton title={label} text={help} />}
    </Stack>
  );
}

// ---------------------------------------------------------------- invite people

function ShareCard() {
  const { t, config, notify } = useApp();
  const copy = () =>
    navigator.clipboard
      ?.writeText(config.url)
      .then(() => notify({ message: t(S.linkCopied), severity: 'success' }))
      .catch(() => {});
  return (
    <Section title={t(S.share)}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ alignItems: 'center' }}>
        <Box component="img" src="/qrcode" alt="QR" sx={{ width: 160, height: 160, borderRadius: 1, bgcolor: '#fff', p: 1 }} />
        <Box sx={{ flex: 1, minWidth: 0, textAlign: { xs: 'center', sm: 'start' } }}>
          <Typography variant="body2" color="text.secondary">
            {t(S.helpShare)}
          </Typography>
          <Typography variant="h6" sx={{ wordBreak: 'break-all', my: 1 }}>
            {config.url}
          </Typography>
          {navigator.clipboard && (
            <Button startIcon={<ContentCopyRounded />} color="secondary" onClick={copy}>
              {t(S.copyLink)}
            </Button>
          )}
        </Box>
      </Stack>
    </Section>
  );
}

// ---------------------------------------------------------------- administrator

function AdminCard() {
  const { t, config, notify, reloadConfig } = useApp();
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  if (!config.admin_enabled) return null;
  const login = () =>
    postJson<OkResponse>('/api/login', { password: pw })
      .then(() => {
        setPw('');
        setErr('');
        reloadConfig();
      })
      .catch((e) => setErr(errorText(e, t(S.adminPasswordWrong))));
  const logout = () =>
    getText('/api/logout').then(() => {
      reloadConfig();
      notify({ message: t(S.logOut) });
    });
  return (
    <Section title={t(S.administrator)} action={<HelpButton title={t(S.administrator)} text={t(S.helpAdmin)} />}>
      {config.admin ? (
        <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Chip color="secondary" icon={<LockOpenRounded />} label={t(S.loggedInAsAdmin)} />
          <Box sx={{ flex: 1 }} />
          <Button startIcon={<LogoutRounded />} onClick={logout}>
            {t(S.logOut)}
          </Button>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} component="form" onSubmit={(e) => (e.preventDefault(), login())} sx={{ alignItems: 'flex-start' }}>
          <TextField
            size="small"
            type="password"
            label={t(S.password)}
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            error={!!err}
            helperText={err || ' '}
            sx={{ flex: 1 }}
            slotProps={{ htmlInput: { autoComplete: 'current-password' } }}
          />
          <Button type="submit" variant="contained" color="secondary" disabled={!pw} sx={{ mt: 0.25 }}>
            {t(S.logIn)}
          </Button>
        </Stack>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------- vocal removal

const MODEL_TEXT: Record<string, StringId> = { HP5: S.modelHP5, HP2: S.modelHP2, HP3: S.modelHP3, baseline: S.modelBaseline, LR: S.useLR };

function VocalCard({ s, reload }: { s: Settings; reload: () => void }) {
  const { t, notify, refreshStatus } = useApp();
  const run = (url: string) =>
    getText(url)
      .catch((e) => notify({ message: errorText(e, t(S.adminOnly)), severity: 'error' }))
      .finally(() => setTimeout(() => (reload(), refreshStatus()), 800));
  const unavailable = s.splitter === 'unavailable';
  return (
    <Section title={t(S.vocalRemoval)} action={<HelpButton title={t(S.vocalRemoval)} text={t(S.helpVocalRemoval)} />}>
      {unavailable && (
        <Alert severity="info" sx={{ mb: 1 }}>
          {t(S.splitUnavailable)}
          {s.splitter_missing ? ` (${s.splitter_missing})` : ''}
        </Alert>
      )}
      <Toggle label={t(S.vocalSplitter)} checked={!!s.vocal_split && !unavailable} onChange={(b) => run('/vocal_split/' + b)} />
      {s.vocal_split && !unavailable && (
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
          <Typography variant="body2" color={s.splitter === 'stopped' ? 'error' : 'text.secondary'} sx={{ flex: 1 }}>
            {s.splitter === 'stopped' ? t(S.splitStopped) : t(S.splitterWorking)}
            {s.splitter_device ? ` · ${t(S.splitterDevice)}: ${s.splitter_device}` : ''}
          </Typography>
          {s.splitter === 'stopped' ? (
            <Button size="small" color="secondary" startIcon={<RestartAltRounded />} onClick={() => run('/bg-process/vocal-restart')}>
              {t(S.restart)}
            </Button>
          ) : null}
        </Stack>
      )}
      <Divider sx={{ my: 1 }} />
      <Stack direction="row" sx={{ alignItems: 'center' }}>
        <Typography variant="subtitle2" sx={{ flex: 1 }}>
          {t(S.model)}
        </Typography>
        <HelpButton title={t(S.model)} text={[t(S.helpModel1), t(S.helpModel2), t(S.helpModel3)].join('\n\n')} />
      </Stack>
      <RadioGroup value={s.vocal_model ?? ''} onChange={(e) => run('/set_vocal_model/' + e.target.value)}>
        {(s.models ?? []).map((m) => (
          <FormControlLabel
            key={m.id}
            value={m.id}
            control={<Radio color="secondary" />}
            label={
              <Box sx={{ py: 0.5 }}>
                <Typography variant="body2">{MODEL_TEXT[m.id] ? t(MODEL_TEXT[m.id]) : m.id}</Typography>
                {m.status === 'missing' && (
                  <Typography variant="caption" color="text.secondary">
                    {t(S.modelMissing)}
                  </Typography>
                )}
                {m.status === 'downloading' && (
                  <>
                    <Typography variant="caption" color="text.secondary">
                      {t(S.modelDownloading)}
                    </Typography>
                    <LinearProgress color="secondary" sx={{ mt: 0.5 }} />
                  </>
                )}
              </Box>
            }
          />
        ))}
      </RadioGroup>
    </Section>
  );
}

// ---------------------------------------------------------------- playback

function PlaybackCard({ s, reload }: { s: Settings; reload: () => void }) {
  const { t } = useApp();
  const set = (url: string) => getText(url).finally(reload);
  return (
    <Section title={t(S.playback)}>
      <Toggle
        label={t(S.volumeNormalization)}
        help={t(S.helpVolumeNormalization)}
        checked={!!s.norm_vol}
        onChange={(b) => set('/norm_vol/' + b)}
      />
      <Toggle
        label={t(S.savePlaySettings)}
        help={t(S.helpSavePlaySettings)}
        checked={!!s.save_delays}
        onChange={(b) => set('/save_delays/' + b)}
      />
    </Section>
  );
}

function ServerLanguageCard({ s, reload }: { s: Settings; reload: () => void }) {
  const { t, config } = useApp();
  return (
    <Section title={t(S.tvLanguage)} action={<HelpButton title={t(S.tvLanguage)} text={t(S.helpServerLang)} />}>
      <TextField
        select
        fullWidth
        size="small"
        value={s.server_lang ?? ''}
        onChange={(e) => getText('/change_language/' + e.target.value).finally(reload)}
      >
        {config.langs.map(([code, name]) => (
          <MenuItem key={code} value={code}>
            {name}
          </MenuItem>
        ))}
      </TextField>
    </Section>
  );
}

function LibraryCard({ s, reload }: { s: Settings; reload: () => void }) {
  const { t, notify } = useApp();
  const [busy, setBusy] = useState(false);
  const rescan = () => {
    setBusy(true);
    getJson<{ count: number }>('/refresh')
      .then((r) => notify({ message: t(S.nSongs, r.count), severity: 'success' }))
      .finally(() => (setBusy(false), reload()));
  };
  return (
    <Section title={t(S.songLibrary)}>
      <Info label={t(S.libraryPath)} value={s.download_path} />
      <Info label={t(S.songCount)} value={String(s.num_songs)} />
      <Stack direction="row" sx={{ alignItems: 'center', mt: 1 }}>
        <Button startIcon={<RefreshRounded />} color="secondary" disabled={busy} onClick={rescan}>
          {t(S.rescanLibrary)}
        </Button>
        <HelpButton title={t(S.rescanLibrary)} text={t(S.helpRescan)} />
      </Stack>
    </Section>
  );
}

function Info({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Stack direction="row" spacing={2} sx={{ py: 0.5 }}>
      <Typography variant="body2" color="text.secondary" sx={{ width: '40%', flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
        {value}
      </Typography>
    </Stack>
  );
}

function AboutCard({ s, reload }: { s: Settings; reload: () => void }) {
  const { t, notify } = useApp();
  const confirm = useConfirm();
  const update = async () => {
    if (!(await confirm({ title: t(S.updateDownloadTool), text: t(S.confirmUpdateYtdl), confirm: t(S.updateDownloadTool) }))) return;
    getJson<OkResponse>('/update_ytdl')
      .then((r) => notify({ message: r.message || '', severity: 'info' }))
      .catch((e) => notify({ message: errorText(e, t(S.adminOnly)), severity: 'error' }));
  };
  return (
    <Section title={t(S.aboutTroubleshooting)}>
      <Info label={t(S.ohkVersion)} value={s.version} />
      <Info label={t(S.os)} value={`${s.os} (${s.platform})`} />
      <Info label="CPU" value={`${s.cpu}%`} />
      <Info label={t(S.memory)} value={t(S.freeOf, gb(s.memory.free), gb(s.memory.total))} />
      <Info label={t(S.diskUsage)} value={t(S.freeOf, gb(s.disk.free), gb(s.disk.total))} />
      <Info label={t(S.ytdlpVersion)} value={s.youtubedl_version} />
      {s.admin && (
        <>
          <Stack direction="row" sx={{ alignItems: 'center', mt: 1 }}>
            <Button startIcon={<SystemUpdateAltRounded />} color="secondary" onClick={update}>
              {t(S.updateDownloadTool)}
            </Button>
            <HelpButton title={t(S.updateDownloadTool)} text={`${t(S.helpUpdate)} ${s.youtubedl_version}\n${t(S.helpUpdateFail)}`} />
          </Stack>
          {s.streamer !== null && (
            <Stack direction="row" sx={{ alignItems: 'center' }}>
              <Button
                startIcon={<RestartAltRounded />}
                color="secondary"
                onClick={() => getText('/bg-process/streamer-restart').finally(reload)}
              >
                {t(S.restartStreamer)}
              </Button>
              <HelpButton title={t(S.screenCapture)} text={t(S.helpStreamer)} />
            </Stack>
          )}
        </>
      )}
    </Section>
  );
}

function DangerCard({ s }: { s: Settings }) {
  const { t, notify } = useApp();
  const confirm = useConfirm();
  const act = async (label: string, text: string, url: string) => {
    if (!(await confirm({ title: label, text, confirm: label, danger: true }))) return;
    getJson<OkResponse>(url)
      .then((r) => r.message && notify({ message: r.message, severity: 'warning' }))
      .catch((e) => notify({ message: errorText(e, t(S.adminOnly)), severity: 'error' }));
  };
  // each button says what it does and asks with the matching question (the old page swapped reboot/shutdown)
  return (
    <Section title={t(S.dangerZone)}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t(S.helpShutdown)}
      </Typography>
      <Stack spacing={1} sx={{ alignItems: 'flex-start' }}>
        <Button color="error" startIcon={<ExitToAppRounded />} onClick={() => act(t(S.quitOhk), t(S.confirmQuit), '/quit')}>
          {t(S.quitOhk)}
        </Button>
        {(s.platform === 'linux' || s.is_pi) && (
          <>
            <Button color="error" startIcon={<RestartAltRounded />} onClick={() => act(t(S.rebootSystem), t(S.confirmReboot), '/reboot')}>
              {t(S.rebootSystem)}
            </Button>
            <Button
              color="error"
              startIcon={<PowerSettingsNewRounded />}
              onClick={() => act(t(S.shutdownSystem), t(S.confirmShutdown), '/shutdown')}
            >
              {t(S.shutdownSystem)}
            </Button>
          </>
        )}
        {s.is_pi && (
          <Stack direction="row" sx={{ alignItems: 'center' }}>
            <Button color="error" startIcon={<SdCardRounded />} onClick={() => act(t(S.expandFs), t(S.confirmExpandFs), '/expand_fs')}>
              {t(S.expandFs)}
            </Button>
            <HelpButton title={t(S.expandFs)} text={t(S.helpExpandFs)} />
          </Stack>
        )}
      </Stack>
    </Section>
  );
}
