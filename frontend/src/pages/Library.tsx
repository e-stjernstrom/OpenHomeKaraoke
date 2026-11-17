import { useMemo, useState } from 'react';
import Card from '@mui/material/Card';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';
import Divider from '@mui/material/Divider';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import IconButton from '@mui/material/IconButton';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Skeleton from '@mui/material/Skeleton';
import FilterListRounded from '@mui/icons-material/FilterListRounded';
import ClearRounded from '@mui/icons-material/ClearRounded';
import AddRounded from '@mui/icons-material/AddRounded';
import CheckRounded from '@mui/icons-material/CheckRounded';
import MoreVertRounded from '@mui/icons-material/MoreVertRounded';
import EditRounded from '@mui/icons-material/EditRounded';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import { postJson, type OkResponse, type Song } from '../api';
import { useApp } from '../state';
import { S } from '../strings';
import { errorText, useEnqueue, useLibrary } from '../library';
import { useConfirm } from '../components/Dialogs';

const PAGE = 100;

export default function LibraryPage() {
  const { t, config } = useApp();
  const [sort, setSort] = useState<'name' | 'date'>('name');
  const { songs, reload } = useLibrary(sort);
  const enqueue = useEnqueue();
  const [filter, setFilter] = useState('');
  const [shown, setShown] = useState(PAGE);
  const [menu, setMenu] = useState<{ el: HTMLElement; song: Song } | null>(null);
  const [renaming, setRenaming] = useState<Song | null>(null);
  const confirm = useConfirm();
  const { notify } = useApp();

  const list = useMemo(() => {
    const w = filter.toLowerCase().split(/\s+/).filter(Boolean);
    return (songs ?? []).filter((s) => w.every((x) => s.title.toLowerCase().includes(x)));
  }, [songs, filter]);

  const del = async (song: Song) => {
    setMenu(null);
    if (!(await confirm({ title: song.title, text: t(S.confirmDeleteSong), confirm: t(S.remove), danger: true }))) return;
    postJson<OkResponse>('/files/delete', { song: song.file })
      .then((r) => notify({ message: r.message || t(S.removed, song.title), severity: 'success' }))
      .catch((e) => notify({ message: errorText(e, t(S.adminOnly)), severity: 'error' }))
      .finally(reload);
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <TextField
          size="small"
          sx={{ flex: 1 }}
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setShown(PAGE);
          }}
          placeholder={t(S.filter)}
          slotProps={{
            htmlInput: { 'aria-label': t(S.filter) },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <FilterListRounded />
                </InputAdornment>
              ),
              endAdornment: filter ? (
                <InputAdornment position="end">
                  <IconButton size="small" aria-label={t(S.clear)} onClick={() => setFilter('')}>
                    <ClearRounded fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ) : undefined,
            },
          }}
        />
        <ToggleButtonGroup size="small" exclusive value={sort} onChange={(_, v) => v && setSort(v)}>
          <ToggleButton value="name">{t(S.sortName)}</ToggleButton>
          <ToggleButton value="date">{t(S.sortDate)}</ToggleButton>
        </ToggleButtonGroup>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ px: 1 }}>
        {songs ? t(S.nSongs, list.length) : ' '}
      </Typography>

      {songs === null ? (
        <Skeleton variant="rounded" height={300} />
      ) : (
        list.length > 0 && (
          <Card>
            <List disablePadding>
              {list.slice(0, shown).map((s, i) => (
                <div key={s.file}>
                  {i > 0 && <Divider component="div" />}
                  <ListItem
                    disablePadding
                    secondaryAction={
                      <Stack direction="row" sx={{ alignItems: 'center' }}>
                        {s.queued ? (
                          <CheckRounded sx={{ color: 'text.secondary', mx: 1 }} aria-label={t(S.alreadyQueued)} />
                        ) : (
                          <IconButton color="secondary" aria-label={t(S.addToQueue)} onClick={() => enqueue(s)}>
                            <AddRounded />
                          </IconButton>
                        )}
                        {config.admin && (
                          <IconButton edge="end" aria-label={t(S.more)} onClick={(e) => setMenu({ el: e.currentTarget, song: s })}>
                            <MoreVertRounded />
                          </IconButton>
                        )}
                      </Stack>
                    }
                  >
                    <ListItemButton onClick={() => !s.queued && enqueue(s)} sx={{ pr: config.admin ? 12 : 7 }}>
                      <ListItemText
                        primary={s.title}
                        secondary={s.queued ? t(S.alreadyQueued) : undefined}
                        slotProps={{ primary: { sx: { wordBreak: 'break-word' } } }}
                      />
                    </ListItemButton>
                  </ListItem>
                </div>
              ))}
            </List>
            {list.length > shown && (
              <Button fullWidth onClick={() => setShown(shown + PAGE)} sx={{ py: 1.5 }}>
                {t(S.showMore)} ({list.length - shown})
              </Button>
            )}
          </Card>
        )
      )}

      <Menu anchorEl={menu?.el} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem
          onClick={() => {
            setRenaming(menu!.song);
            setMenu(null);
          }}
        >
          <ListItemIcon>
            <EditRounded fontSize="small" />
          </ListItemIcon>
          {t(S.rename)}
        </MenuItem>
        <MenuItem onClick={() => menu && del(menu.song)} sx={{ color: 'error.main' }}>
          <ListItemIcon sx={{ color: 'inherit' }}>
            <DeleteOutlineRounded fontSize="small" />
          </ListItemIcon>
          {t(S.remove)}
        </MenuItem>
      </Menu>
      {renaming && <RenameDialog song={renaming} onClose={() => setRenaming(null)} onDone={reload} />}
    </Stack>
  );
}

function RenameDialog({ song, onClose, onDone }: { song: Song; onClose: () => void; onDone: () => void }) {
  const { t, notify } = useApp();
  const [name, setName] = useState(song.title);
  const save = () =>
    postJson<OkResponse>('/edit_song', { old_file_name: song.file, new_file_name: name.trim() })
      .then((r) => {
        notify({ message: r.message || t(S.save), severity: 'success' });
        onDone();
        onClose();
      })
      .catch((e) => notify({ message: errorText(e, t(S.adminOnly)), severity: 'error' }));
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{t(S.rename)}</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          fullWidth
          multiline
          label={t(S.songName)}
          value={name}
          onChange={(e) => setName(e.target.value.replace(/[\n/\\]/g, ''))}
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t(S.cancel)}</Button>
        <Button variant="contained" color="secondary" disabled={!name.trim() || name.trim() === song.title} onClick={save}>
          {t(S.save)}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
