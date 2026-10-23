import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {readLocal, writeLocal} from './localDrafts';

type Row = {id: string; metadata: {kind?: string; request?: {payload?: {input?: {prompt?: string}}}}};

/**
 * Портрет карточки без рабочего образа: случайный результат из листа (ракурсы не важны).
 * Выбор запоминается в браузере, чтобы карточка не мигала; если кадр ушёл, выбирается другой.
 */
export function usePortraits(
  projectId: string,
  revision: number,
  kind: 'hero' | 'location',
  names: string[]
) {
  const [picked, setPicked] = useState<Record<string, string>>({});
  const key = names.join('\u0000');
  useEffect(() => {
    if (!projectId || !names.length) return;
    let active = true;
    const storeKey = `studio:portrait:${projectId}:${kind}`;
    const load = () =>
      apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
        .then(responseJson)
        .then((rows: Row[]) => {
          if (!active) return;
          const saved = readLocal<Record<string, string>>(storeKey, {});
          const next: Record<string, string> = {};
          for (const name of names) {
            const head = kind === 'hero' ? `Лист персонажа «${name}»` : `Вариации локации «${name}»`;
            const ids = rows
              .filter(r => (r.metadata.kind || 'image') === 'image')
              .filter(r => (r.metadata.request?.payload?.input?.prompt || '').includes(head))
              .map(r => r.id);
            if (!ids.length) continue;
            next[name] = ids.includes(saved[name])
              ? saved[name]
              : ids[Math.floor(Math.random() * ids.length)];
          }
          writeLocal(storeKey, next);
          setPicked(next);
        })
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(() => !document.hidden && void load(), 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [projectId, revision, kind, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return picked;
}
