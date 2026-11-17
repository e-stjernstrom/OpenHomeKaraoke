import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import CloseRounded from '@mui/icons-material/CloseRounded';
import { useApp } from '../state';
import { S } from '../strings';

/** One MD2 snackbar at a time; errors use a filled red alert and stay a little longer. */
export default function Snackbars({ bottomOffset }: { bottomOffset: number }) {
  const { snacks, dismissSnack, t } = useApp();
  const s = snacks[0];
  if (!s) return null;
  const close = () => dismissSnack(s.id);
  const timeout = s.timeout ?? (s.severity === 'error' ? 8000 : s.action ? 6000 : 4000);
  const action = (
    <>
      {s.action && (
        <Button
          color={s.severity === 'error' ? 'inherit' : 'secondary'}
          size="small"
          onClick={() => {
            s.action!.onClick();
            close();
          }}
        >
          {s.action.label}
        </Button>
      )}
      <IconButton size="small" color="inherit" aria-label={t(S.close)} onClick={close}>
        <CloseRounded fontSize="small" />
      </IconButton>
    </>
  );
  return (
    <Snackbar
      key={s.id}
      open
      autoHideDuration={timeout}
      onClose={(_, reason) => reason !== 'clickaway' && close()}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      sx={{ bottom: { xs: `${bottomOffset + 8}px`, md: '24px' } }}
      message={s.severity && s.severity !== 'info' ? undefined : s.message}
      action={s.severity && s.severity !== 'info' ? undefined : action}
    >
      {s.severity && s.severity !== 'info' ? (
        <Alert severity={s.severity} variant="filled" action={action} sx={{ width: '100%', alignItems: 'center' }}>
          {s.message}
        </Alert>
      ) : undefined}
    </Snackbar>
  );
}
