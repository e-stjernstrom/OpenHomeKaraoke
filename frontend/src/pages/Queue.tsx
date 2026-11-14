import { useEffect, useState } from 'react';
import Card from '@mui/material/Card';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import Divider from '@mui/material/Divider';
import ShuffleRounded from '@mui/icons-material/ShuffleRounded';
import ClearAllRounded from '@mui/icons-material/ClearAllRounded';
import MoreVertRounded from '@mui/icons-material/MoreVertRounded';
import DragIndicatorRounded from '@mui/icons-material/DragIndicatorRounded';
import VerticalAlignTopRounded from '@mui/icons-material/VerticalAlignTopRounded';
import ArrowUpwardRounded from '@mui/icons-material/ArrowUpwardRounded';
import ArrowDownwardRounded from '@mui/icons-material/ArrowDownwardRounded';
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded';
import QueueMusicRounded from '@mui/icons-material/QueueMusicRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { restrictToVerticalAxis } from '../dnd';
import { getJson, HttpError, postJson, type OkResponse, type QueueItem } from '../api';
import { useApp } from '../state';
import { S } from '../strings';
import { SplitLine } from '../components/VocalSwitch';
import { useConfirm } from '../components/Dialogs';

export default function QueuePage() {
  const { t, queue, config, notify, go, refreshQueue, user } = useApp();
  const confirm = useConfirm();
  const admin = config.admin;
  // local order while a drag is being sent, so the row does not jump back
  const [items, setItems] = useState(queue);
  useEffect(() => setItems(queue), [queue]);

  const fail = (e: unknown) =>
    notify({ message: (e instanceof HttpError && e.serverMessage) || t(S.adminOnly), severity: 'error' });

  const edit = (body: Record<string, unknown>) => postJson<OkResponse>('/queue/edit', body).catch(fail).finally(refreshQueue);

  const remove = (item: QueueItem, index: number) => {
    edit({ action: 'delete', song: item.file, user });
    notify({
      message: t(S.removed, item.title),
      action: { label: t(S.undo), onClick: () => edit({ action: 'insert', song: item.file, index, user: item.user }) },
      timeout: 6000,
    });
  };

  const clear = async () => {
    if (!(await confirm({ title: t(S.clearAll), text: t(S.confirmClearQueue), confirm: t(S.clear), danger: true }))) return;
    edit({ action: 'clear' });
  };

  const addRandom = () =>
    getJson<OkResponse>('/queue/addrandom?amount=3')
      .then((r) => r.message && notify({ message: r.message, severity: r.ok ? 'success' : 'warning' }))
      .catch(fail);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const title = (id: string | number) => items.find((i) => i.file === id)?.title ?? '';
  const pos = (id: string | number) => items.findIndex((i) => i.file === id) + 1;
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    const from = items.findIndex((i) => i.file === active.id);
    const to = items.findIndex((i) => i.file === over.id);
    if (from < 0 || to < 0) return;
    setItems(arrayMove(items, from, to));
    edit({ action: 'move', from, to, size: items.length });
  };

  return (
    <Stack spacing={2}>
      <Box>
        <Button variant="outlined" color="secondary" startIcon={<ShuffleRounded />} onClick={addRandom}>
          {t(S.addRandom)}
        </Button>
      </Box>

      {items.length === 0 ? (
        <Card>
          <Box sx={{ textAlign: 'center', py: 5, px: 2 }}>
            <QueueMusicRounded sx={{ fontSize: 48, color: 'text.secondary' }} />
            <Typography variant="h6" sx={{ mt: 1 }}>
              {t(S.queueEmpty)}
            </Typography>
            <Button variant="contained" color="secondary" startIcon={<SearchRounded />} sx={{ mt: 2 }} onClick={() => go('search')}>
              {t(S.findASong)}
            </Button>
          </Box>
        </Card>
      ) : (
        <Card>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis]}
            onDragEnd={onDragEnd}
            accessibility={{
              // read song titles and positions, not file paths
              announcements: {
                onDragStart: ({ active }) => t(S.dndPicked, title(active.id)),
                onDragOver: ({ active, over }) => (over ? t(S.dndMoved, title(active.id), pos(over.id)) : undefined),
                onDragEnd: ({ active, over }) => (over ? t(S.dndMoved, title(active.id), pos(over.id)) : t(S.dndCancelled)),
                onDragCancel: () => t(S.dndCancelled),
              },
            }}
          >
            <SortableContext items={items.map((i) => i.file)} strategy={verticalListSortingStrategy}>
              <List disablePadding>
                {items.map((item, i) => (
                  <Row
                    key={item.file}
                    item={item}
                    index={i}
                    last={i === items.length - 1}
                    admin={admin}
                    onAction={(a) => (a === 'delete' ? remove(item, i) : edit({ action: a, song: item.file }))}
                  />
                ))}
              </List>
            </SortableContext>
          </DndContext>
        </Card>
      )}
      {admin && items.length > 0 && (
        <Box sx={{ textAlign: 'end' }}>
          <Button color="error" startIcon={<ClearAllRounded />} onClick={clear}>
            {t(S.clearAll)}
          </Button>
        </Box>
      )}
    </Stack>
  );
}

type RowAction = 'top' | 'up' | 'down' | 'delete';

function Row({
  item,
  index,
  last,
  admin,
  onAction,
}: {
  item: QueueItem;
  index: number;
  last: boolean;
  admin: boolean;
  onAction: (a: RowAction) => void;
}) {
  const { t, user } = useApp();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: item.file,
    disabled: !admin,
  });
  const [menuEl, setMenuEl] = useState<HTMLElement | null>(null);
  const act = (a: RowAction) => () => {
    setMenuEl(null);
    onAction(a);
  };
  const mine = item.user === user;
  return (
    <>
      {index > 0 && <Divider component="li" />}
      <ListItem
        ref={setNodeRef}
        style={{ transform: CSS.Translate.toString(transform), transition }}
        sx={{
          gap: 1,
          py: 1,
          pl: admin ? 0.5 : 2,
          bgcolor: isDragging ? 'action.selected' : 'background.paper',
          position: 'relative',
          zIndex: isDragging ? 1 : undefined,
          boxShadow: isDragging ? 6 : undefined,
        }}
        secondaryAction={
          admin ? (
            <IconButton edge="end" aria-label={t(S.more)} onClick={(e) => setMenuEl(e.currentTarget)}>
              <MoreVertRounded />
            </IconButton>
          ) : mine ? (
            // everyone may take back their own song
            <IconButton edge="end" aria-label={t(S.remove)} onClick={() => onAction('delete')}>
              <DeleteOutlineRounded />
            </IconButton>
          ) : undefined
        }
      >
        {admin && (
          <IconButton
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            aria-label={`${t(S.moveUp)} / ${t(S.moveDown)}`}
            sx={{ cursor: 'grab', touchAction: 'none', color: 'text.secondary' }}
          >
            <DragIndicatorRounded />
          </IconButton>
        )}
        <Typography variant="body2" color="text.secondary" sx={{ minWidth: 20, textAlign: 'center' }}>
          {index + 1}
        </Typography>
        <ListItemText
          sx={{ my: 0, minWidth: 0 }}
          primary={item.title}
          slotProps={{ primary: { sx: { wordBreak: 'break-word' } }, secondary: { component: 'span' } }}
          secondary={
            <Box component="span" sx={{ display: 'block' }}>
              <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {t(S.addedBy, item.user)}
              </Box>
              <Box component="span" sx={{ display: 'block' }}>
                <SplitLine split={item.split} dense />
              </Box>
            </Box>
          }
        />
      </ListItem>
      <Menu anchorEl={menuEl} open={!!menuEl} onClose={() => setMenuEl(null)}>
        <MenuItem onClick={act('top')} disabled={index === 0}>
          <ListItemIcon>
            <VerticalAlignTopRounded fontSize="small" />
          </ListItemIcon>
          {t(S.moveToTop)}
        </MenuItem>
        <MenuItem onClick={act('up')} disabled={index === 0}>
          <ListItemIcon>
            <ArrowUpwardRounded fontSize="small" />
          </ListItemIcon>
          {t(S.moveUp)}
        </MenuItem>
        <MenuItem onClick={act('down')} disabled={last}>
          <ListItemIcon>
            <ArrowDownwardRounded fontSize="small" />
          </ListItemIcon>
          {t(S.moveDown)}
        </MenuItem>
        <Divider />
        <MenuItem onClick={act('delete')} sx={{ color: 'error.main' }}>
          <ListItemIcon sx={{ color: 'inherit' }}>
            <DeleteOutlineRounded fontSize="small" />
          </ListItemIcon>
          {t(S.remove)}
        </MenuItem>
      </Menu>
    </>
  );
}
