import { useCallback, useEffect, useState } from 'react';
import { getJson, HttpError, postJson, type OkResponse, type Song } from './api';
import { useApp } from './state';
import { S } from './strings';

/** The song library, re-read when the queue changes (queued flags) or after a download. */
export function useLibrary(sort: 'name' | 'date' = 'name') {
  const { queue, onServerEvent } = useApp();
  const [songs, setSongs] = useState<Song[] | null>(null);
  const load = useCallback(() => {
    getJson<Song[]>('/api/library' + (sort === 'date' ? '?sort=date' : ''))
      .then(setSongs)
      .catch(() => setSongs((s) => s ?? []));
  }, [sort]);
  useEffect(load, [load, queue]);
  useEffect(() => onServerEvent((e) => e.type === 'download' && load()), [onServerEvent, load]);
  return { songs, reload: load };
}

/** Add a library song to the queue, with a snackbar. */
export function useEnqueue() {
  const { t, user, notify, refreshQueue } = useApp();
  return useCallback(
    (song: { file: string; title: string }) =>
      postJson<{ success: boolean }>('/enqueue', { song: song.file, user })
        .then((r) =>
          notify({
            message: r.success ? t(S.songAdded, song.title) : t(S.songAlreadyQueued, song.title),
            severity: r.success ? 'success' : 'warning',
          }),
        )
        .catch(() => notify({ message: t(S.cannotPlay), severity: 'error' }))
        .finally(refreshQueue),
    [t, user, notify, refreshQueue],
  );
}

export function errorText(e: unknown, fallback: string) {
  return (e instanceof HttpError && e.serverMessage) || fallback;
}

export type { OkResponse };
