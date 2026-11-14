import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import useMediaQuery from '@mui/material/useMediaQuery';
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import CheckRounded from '@mui/icons-material/CheckRounded';
import { getText, setCookie } from '../api';
import { useApp } from '../state';
import { S } from '../strings';

// ---------------------------------------------------------------- your name

export function NameDialog({ open, onClose, required }: { open: boolean; onClose: () => void; required: boolean }) {
  const { t, user, setUser } = useApp();
  const [name, setName] = useState(user);
  useEffect(() => {
    if (!open) return;
    if (user) setName(user);
    else getText('/auto_username').then((s) => setName(s)).catch(() => setName(''));
  }, [open, user]);
  const ok = () => {
    if (!name.trim()) return;
    setUser(name);
    onClose();
  };
  return (
    <Dialog open={open} onClose={required ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>{t(S.yourName)}</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ mb: 2 }}>{t(S.helpYourName)}</DialogContentText>
        <TextField
          autoFocus
          fullWidth
          label={t(S.yourName)}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ok()}
          slotProps={{ htmlInput: { maxLength: 40, autoComplete: 'nickname' } }}
          error={!name.trim()}
          helperText={!name.trim() ? t(S.nameRequired) : ' '}
        />
      </DialogContent>
      <DialogActions>
        {!required && <Button onClick={onClose}>{t(S.cancel)}</Button>}
        <Button onClick={ok} disabled={!name.trim()} variant="contained" color="secondary">
          {t(S.save)}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------- language of this device

export function LanguageDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, config } = useApp();
  const phone = useMediaQuery((th) => th.breakpoints.down('sm'));
  const choose = (lang: string) => {
    setCookie('lang', lang);
    location.reload();
  };
  return (
    <Dialog open={open} onClose={onClose} fullScreen={phone} fullWidth maxWidth="xs" scroll="paper">
      <DialogTitle>{t(S.changeLanguage)}</DialogTitle>
      <DialogContent dividers sx={{ p: 0 }}>
        <List dense>
          {config.langs.map(([code, name]) => (
            <ListItemButton key={code} selected={code === config.lang} onClick={() => choose(code)} sx={{ minHeight: 48 }}>
              <ListItemText primary={name} secondary={code} />
              {code === config.lang && <CheckRounded fontSize="small" />}
            </ListItemButton>
          ))}
        </List>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t(S.close)}</Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------- confirmation (MD2 dialog, not window.confirm)

interface ConfirmOptions {
  title: string;
  text?: string;
  confirm: string;
  danger?: boolean;
}
type ConfirmFn = (o: ConfirmOptions) => Promise<boolean>;
const ConfirmCtx = createContext<ConfirmFn>(() => Promise.resolve(false));
export const useConfirm = () => useContext(ConfirmCtx);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useApp();
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<(v: boolean) => void>(undefined);
  const confirm = useCallback<ConfirmFn>(
    (o) =>
      new Promise<boolean>((resolve) => {
        resolver.current = resolve;
        setOpts(o);
      }),
    [],
  );
  const done = (v: boolean) => {
    resolver.current?.(v);
    setOpts(null);
  };
  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      <Dialog open={!!opts} onClose={() => done(false)} maxWidth="xs" fullWidth>
        {opts && (
          <>
            <DialogTitle>{opts.title}</DialogTitle>
            {opts.text && (
              <DialogContent>
                <DialogContentText>{opts.text}</DialogContentText>
              </DialogContent>
            )}
            <DialogActions>
              <Button onClick={() => done(false)}>{t(S.cancel)}</Button>
              <Button onClick={() => done(true)} color={opts.danger ? 'error' : 'secondary'} autoFocus>
                {opts.confirm}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </ConfirmCtx.Provider>
  );
}

// ---------------------------------------------------------------- ⓘ help that stays until closed

export function HelpButton({ title, text }: { title: string; text: string }) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Tooltip title={title}>
        <IconButton size="small" aria-label={title} onClick={() => setOpen(true)} sx={{ color: 'text.secondary' }}>
          <InfoOutlined fontSize="small" />
        </IconButton>
      </Tooltip>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="xs">
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
          <DialogContentText>{text}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t(S.close)}</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
