/** Общие события интерфейса: короткие уведомления, корзина с «Отменить», обновление библиотеки. */
import {apiFetch} from './api';

export type Toast = {text: string; action?: {label: string; run: () => void}; ms?: number};

const TOAST = 'studio:toast';
const LIBRARY = 'studio:library-changed';
export const PASTE_REFERENCE = 'studio:paste-reference';

export function toast(t: Toast) {
  window.dispatchEvent(new CustomEvent<Toast>(TOAST, {detail: t}));
}
export function onToast(fn: (t: Toast) => void) {
  const h = (e: Event) => fn((e as CustomEvent<Toast>).detail);
  window.addEventListener(TOAST, h);
  return () => window.removeEventListener(TOAST, h);
}

/** Библиотека изменилась (корзина, восстановление, вставка): экраны перечитывают список. */
export const libraryChanged = () => window.dispatchEvent(new Event(LIBRARY));
export function onLibraryChanged(fn: () => void) {
  window.addEventListener(LIBRARY, fn);
  return () => window.removeEventListener(LIBRARY, fn);
}

/** Последние убранные в корзину за эту сессию: Ctrl+Z возвращает по одному. */
const undoStack: number[] = [];

async function errorText(r: Response) {
  const d = await r.json().catch(() => ({}));
  return typeof d.detail === 'string' ? d.detail : 'Сервер отклонил запрос';
}

async function restore(id: number): Promise<boolean> {
  const i = undoStack.lastIndexOf(id);
  if (i >= 0) undoStack.splice(i, 1);
  const r = await apiFetch(`/api/library/cleanup/restore/${id}`, {method: 'POST'});
  if (!r.ok) {
    toast({text: 'Не удалось вернуть: ' + (await errorText(r))});
    return false;
  }
  libraryChanged();
  toast({text: 'Файл возвращён из корзины'});
  return true;
}

export async function restoreLastTrashed(): Promise<boolean> {
  const id = undoStack[undoStack.length - 1];
  if (id === undefined) {
    toast({text: 'Нечего возвращать из корзины'});
    return false;
  }
  return restore(id);
}

/** «Удалить» без лишних вопросов: мягко в корзину (30 дней) и 10 секунд на «Отменить». */
export async function trashAsset(assetId: string): Promise<boolean> {
  const r = await apiFetch(`/api/library/${assetId}/trash`, {method: 'POST'});
  if (!r.ok) {
    toast({text: 'Не удалось убрать: ' + (await errorText(r))});
    return false;
  }
  const d = await r.json().catch(() => ({}));
  const id = typeof d.restore_id === 'number' ? d.restore_id : null;
  if (id !== null) undoStack.push(id);
  libraryChanged();
  toast({
    text: 'Убрано в корзину (30 дней)',
    action: id !== null ? {label: 'Отменить', run: () => void restore(id)} : undefined,
    ms: 10000,
  });
  return true;
}
