/**
 * Правила горячих клавиш (без DOM и React). Клавиши определяются по физической кнопке (`code`),
 * поэтому работают и в русской раскладке: «/» — это кнопка с точкой, F — кнопка «А».
 */
export type KeyLike = {
  key: string;
  code?: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
};

/** Если браузер не дал `code` (синтетические события), угадываем кнопку по символу в обеих раскладках. */
const BY_KEY: Record<string, string> = {
  k: 'KeyK',
  л: 'KeyK',
  z: 'KeyZ',
  я: 'KeyZ',
  s: 'KeyS',
  ы: 'KeyS',
  f: 'KeyF',
  а: 'KeyF',
  '/': 'Slash',
};
function fallbackCode(key: string): string {
  const k = (key || '').toLowerCase();
  if (/^[0-9]$/.test(k)) return 'Digit' + k;
  return BY_KEY[k] || '';
}

/** Нормализованное сочетание: 'mod+enter', 'alt+3', '/', '?', 'escape', 'f', 'delete', 'mod+z'… */
export function comboOf(e: KeyLike): string | null {
  const mod = !!(e.ctrlKey || e.metaKey);
  const code = e.code || fallbackCode(e.key);
  if (e.key === 'Escape') return 'escape';
  if (e.key === 'Enter' && mod) return 'mod+enter';
  if (e.altKey && !mod && /^Digit[0-9]$/.test(code)) return 'alt+' + code.slice(5);
  if (mod && !e.altKey && code === 'KeyK') return 'mod+k';
  if (mod && !e.altKey && !e.shiftKey && code === 'KeyZ') return 'mod+z';
  if (mod && !e.altKey && !e.shiftKey && code === 'KeyS') return 'mod+s';
  if (mod || e.altKey) return null;
  if (code === 'Slash') return e.shiftKey ? '?' : '/';
  if (e.key === '?') return '?';
  if (code === 'KeyF' && !e.shiftKey) return 'f';
  if (e.key === 'Delete') return 'delete';
  return null;
}

type TargetLike = {tagName?: string; isContentEditable?: boolean; type?: string} | null | undefined;

/** Курсор в поле ввода: одиночные клавиши там пишут текст и не должны срабатывать как команды. */
export function isTyping(target: TargetLike): boolean {
  if (!target) return false;
  if (target.isContentEditable) return true;
  const tag = (target.tagName || '').toUpperCase();
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag !== 'INPUT') return false;
  return !['checkbox', 'radio', 'button', 'submit', 'range', 'color', 'file'].includes(
    (target.type || 'text').toLowerCase()
  );
}

/** Эти сочетания работают и во время набора текста (Ctrl+V обрабатывается отдельно, событием вставки). */
const WHILE_TYPING = new Set(['mod+enter', 'escape', 'mod+k', 'mod+s']);
export const allowedWhileTyping = (combo: string) => WHILE_TYPING.has(combo);

/** Alt+цифра → экран: 0 Старт, 1–5 этапы ролика, 6 Узлы, 7 Библиотека. */
export const ALT_DIGIT_MODES = [
  'home',
  'studio',
  'styles',
  'storyboard',
  'create',
  'video',
  'graph',
  'archive',
] as const;

/** Подсказка по «?». */
export const HOTKEY_HELP: {keys: string; text: string}[] = [
  {keys: 'Ctrl + Enter', text: 'Сгенерировать (для API сначала окно цены)'},
  {keys: 'Ctrl + K', text: 'Быстрый переход: экран, проект, герой'},
  {keys: 'Ctrl + S', text: 'Сохранить проект'},
  {keys: 'Alt + 0…7', text: 'Старт, Идея, Мир, Раскадровка, Кадры, Видео, Узлы, Библиотека'},
  {keys: '/', text: 'Курсор в строку промпта'},
  {keys: 'Ctrl + V', text: 'Картинка: ответ ChatGPT, а в «Кадрах» — новый референс'},
  {keys: '← →', text: 'Листать кадры в просмотре'},
  {keys: 'F', text: 'В избранное (в просмотре)'},
  {keys: 'Delete', text: 'В корзину (в просмотре), 10 секунд на «Отменить»'},
  {keys: 'Ctrl + Z', text: 'Вернуть последнее убранное в корзину'},
  {keys: 'Esc', text: 'Закрыть окно или панель'},
  {keys: '?', text: 'Эта подсказка'},
];
