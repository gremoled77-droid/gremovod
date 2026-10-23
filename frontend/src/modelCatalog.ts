import {useSyncExternalStore} from 'react';
import {apiFetch} from './api';

/** Поля каталога бэкенда (/api/model-specs), по которым строятся названия и порядок карточек. */
export type CatalogEntry = {
  kind?: string;
  label?: string;
  ui_order?: number;
  family?: string;
  variant_label?: string;
};
type Catalog = Record<string, CatalogEntry>;

let catalog: Catalog = {};
let requested = false;
const listeners = new Set<() => void>();

/** Каталог моделей из бэкенда для экранов, у которых своей копии спецификаций нет: один запрос на приложение. */
export function useModelCatalog(): Catalog {
  if (!requested) {
    requested = true;
    void apiFetch('/api/model-specs')
      .then(r => (r.ok ? r.json() : {}))
      .then(data => {
        catalog = data;
        listeners.forEach(notify => notify());
      })
      .catch(() => {
        requested = false;
      });
  }
  return useSyncExternalStore(
    notify => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    () => catalog
  );
}

export const modelLabel = (specs: Catalog, id: string) => specs[id]?.label || id;

const byOrder = ([, a]: [string, CatalogEntry], [, b]: [string, CatalogEntry]) =>
  (a.ui_order ?? 1e9) - (b.ui_order ?? 1e9);

/** Идентификаторы видеомоделей каталога в порядке показа. */
export const videoModelIds = (specs: Catalog) =>
  Object.entries(specs)
    .filter(([, s]) => s.kind === 'video' && s.label)
    .sort(byOrder)
    .map(([id]) => id);

/** Названия всех картиночных моделей каталога в порядке показа. */
export function imageLabels(specs: Catalog): Record<string, string> {
  return Object.fromEntries(
    Object.entries(specs)
      .filter(([, s]) => s.kind === 'image' && s.label)
      .sort(byOrder)
      .map(([id, s]) => [id, s.label as string])
  );
}

/** Порядок карточек и семейства вариантов: семейство — базовая модель и модели с family = её id. */
export function modelLayout(specs: Catalog) {
  const members = Object.entries(specs)
    .filter(([, s]) => s.family)
    .sort(byOrder);
  const families: Record<string, string[]> = {};
  for (const [id, s] of members) (families[s.family as string] ||= [s.family as string]).push(id);
  const memberIds = new Set(members.map(([id]) => id));
  const order = Object.entries(specs)
    .filter(([id, s]) => s.kind === 'image' && s.label && !memberIds.has(id))
    .sort(byOrder)
    .map(([id]) => id);
  return {order, families};
}
