import {useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {useSharedActivity} from './ActivityContext';
import {allowedWhileTyping, ALT_DIGIT_MODES, comboOf, HOTKEY_HELP, isTyping} from './hotkeyRules';
import {attachExternalResult, openQueue} from './imageRoutes';
import {SCREENS, type Mode} from './screens';
import {
  onToast,
  PASTE_REFERENCE,
  restoreLastTrashed,
  libraryChanged,
  toast,
  type Toast,
} from './studioEvents';

const visible = (el: HTMLElement) => el.offsetParent !== null || el.getClientRects().length > 0;
const modalOpen = () => !!document.querySelector('[aria-modal="true"]');

/** Кнопка генерации для Ctrl+Enter: та, что в одном блоке с курсором; без курсора — единственная на экране. */
function generateTarget(): HTMLButtonElement | null | 'many' {
  const all = [...document.querySelectorAll<HTMLButtonElement>('.gen-main')].filter(
    b => visible(b) && !b.disabled
  );
  let el = document.activeElement as HTMLElement | null;
  while (el && el !== document.body) {
    const inside = all.find(b => el!.contains(b));
    if (inside) return inside;
    el = el.parentElement;
  }
  if (all.length > 1) return 'many';
  return all[0] || null;
}

function focusPrompt() {
  const fields = [...document.querySelectorAll<HTMLTextAreaElement>('[data-prompt]')].filter(visible);
  const target =
    fields[0] || [...document.querySelectorAll<HTMLTextAreaElement>('main textarea')].find(visible);
  if (!target) return false;
  target.focus();
  target.setSelectionRange(target.value.length, target.value.length);
  return true;
}

/** Esc для окон без своего обработчика (подтверждение цены и др.): жмём их «Закрыть»/«Отмена». */
function closeTopModal(): boolean {
  const modals = document.querySelectorAll<HTMLElement>('[aria-modal="true"]');
  const top = modals[modals.length - 1];
  const button = top
    ? [...top.querySelectorAll<HTMLButtonElement>('button')].find(
        b =>
          b.getAttribute('aria-label') === 'Закрыть' ||
          ['Закрыть', 'Отмена'].includes((b.textContent || '').trim())
      )
    : undefined;
  if (!button || button.disabled) return false;
  button.click();
  return true;
}

type Command = {id: string; group: string; label: string; run: () => void};

/**
 * Горячие клавиши студии (список — `hotkeyRules.ts`, подсказка по «?»), быстрый переход Ctrl+K,
 * уведомления внизу экрана и Ctrl+V для картинок.
 */
export default function Hotkeys({
  mode,
  onMode,
  projects,
  onOpenProject,
  heroes,
  onHero,
  dockOpen,
  onCloseDock,
  onSave,
}: {
  mode: Mode;
  onMode: (m: Mode) => void;
  projects: {id: string; title: string}[];
  onOpenProject: (id: string) => void;
  heroes: {id: string; name: string}[];
  onHero: (id: string) => void;
  dockOpen: boolean;
  onCloseDock: () => void;
  onSave: () => void;
}) {
  const [help, setHelp] = useState(false);
  const [palette, setPalette] = useState(false);
  const [toasts, setToasts] = useState<(Toast & {id: number})[]>([]);
  const {items, reset} = useSharedActivity();
  const waiting = items.filter(i => i.source === 'external' && i.status === 'waiting_external');
  const live = useRef({mode, waiting, dockOpen, help, palette, onMode, onCloseDock, onSave});
  live.current = {mode, waiting, dockOpen, help, palette, onMode, onCloseDock, onSave};

  useEffect(
    () =>
      onToast(t => {
        const id = Date.now() + Math.random();
        setToasts(list => [...list.slice(-2), {...t, id}]);
        window.setTimeout(() => setToasts(list => list.filter(x => x.id !== id)), t.ms || 4000);
      }),
    []
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const combo = comboOf(e);
      if (!combo || e.defaultPrevented) return;
      if (isTyping(e.target as HTMLElement) && !allowedWhileTyping(combo)) return;
      const s = live.current;
      if (combo === 'escape') {
        if (s.help || s.palette) {
          setHelp(false);
          setPalette(false);
        } else if (modalOpen()) {
          if (!closeTopModal()) return;
        } else if (s.dockOpen) s.onCloseDock();
        else return;
      } else if (combo === 'mod+s') {
        s.onSave(); // и не даём браузеру «Сохранить страницу»
      } else if (modalOpen() || s.help || s.palette) {
        return; // окна (просмотр, подтверждение цены) обрабатывают свои клавиши сами
      } else if (combo === 'mod+k') setPalette(true);
      else if (combo === '?') setHelp(true);
      else if (combo === '/') {
        if (!focusPrompt()) return;
      } else if (combo === 'mod+enter') {
        const target = generateTarget();
        if (target === 'many')
          toast({text: 'Здесь несколько кнопок генерации: поставь курсор в нужный блок'});
        else if (target) target.click();
        else return;
      } else if (combo === 'mod+z') void restoreLastTrashed();
      else if (combo.startsWith('alt+')) {
        const next = ALT_DIGIT_MODES[Number(combo.slice(4))];
        if (!next) return;
        s.onMode(next);
      } else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Ctrl+V с картинкой: сначала ответ ChatGPT, которого ждём; иначе в «Кадрах» — новый референс.
  useEffect(() => {
    const onPaste = (ev: ClipboardEvent) => {
      if (isTyping(ev.target as HTMLElement)) return;
      const file = Array.from(ev.clipboardData?.files || []).find(f => f.type.startsWith('image/'));
      if (!file) return;
      window.setTimeout(() => {
        if (ev.defaultPrevented) return; // лоток в «Очереди» уже принял картинку по «Вставить»
        const s = live.current;
        if (s.waiting.length === 1) {
          void attachExternalResult(s.waiting[0].id, file)
            .then(() => {
              reset();
              libraryChanged();
              toast({text: 'Картинка из ChatGPT сохранена в библиотеку'});
            })
            .catch(e => toast({text: e instanceof Error ? e.message : String(e)}));
        } else if (s.waiting.length > 1) {
          openQueue();
          toast({text: 'Ждём несколько картинок: нажми «Вставить» у нужного задания в «Очереди»'});
        } else if (s.mode === 'create') {
          window.dispatchEvent(new CustomEvent<File>(PASTE_REFERENCE, {detail: file}));
        }
      });
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [reset]);

  const commands = useMemo<Command[]>(
    () => [
      ...SCREENS.filter(s => s.group !== 'hidden' && s.mode !== 'characters').map(s => ({
        id: 'screen:' + s.mode,
        group: 'Экран',
        label: s.title,
        run: () => onMode(s.mode),
      })),
      {id: 'screen:characters', group: 'Экран', label: 'Мир → Персонажи', run: () => onMode('characters')},
      ...heroes.map(h => ({id: 'hero:' + h.id, group: 'Герой', label: h.name, run: () => onHero(h.id)})),
      ...projects.map(p => ({
        id: 'project:' + p.id,
        group: 'Проект',
        label: p.title,
        run: () => onOpenProject(p.id),
      })),
    ],
    [heroes, projects, onMode, onHero, onOpenProject]
  );

  return (
    <>
      {palette && <Palette commands={commands} onClose={() => setPalette(false)} />}
      {help &&
        createPortal(
          <div className="hk-backdrop" onClick={() => setHelp(false)}>
            <section
              className="hk-help"
              role="dialog"
              aria-label="Горячие клавиши"
              onClick={e => e.stopPropagation()}
            >
              <div className="hk-head">
                <b>Горячие клавиши</b>
                <button aria-label="Закрыть" onClick={() => setHelp(false)}>
                  ×
                </button>
              </div>
              <dl>
                {HOTKEY_HELP.map(h => (
                  <div key={h.keys}>
                    <dt>
                      <kbd>{h.keys}</kbd>
                    </dt>
                    <dd>{h.text}</dd>
                  </div>
                ))}
              </dl>
              <small className="muted">Одиночные клавиши не срабатывают, пока курсор в поле ввода.</small>
            </section>
          </div>,
          document.body
        )}
      {toasts.length > 0 &&
        createPortal(
          <div className="hk-toasts" role="status" aria-live="polite">
            {toasts.map(t => (
              <div key={t.id} className="hk-toast">
                <span>{t.text}</span>
                {t.action && (
                  <button
                    onClick={() => {
                      t.action!.run();
                      setToasts(list => list.filter(x => x.id !== t.id));
                    }}
                  >
                    {t.action.label}
                  </button>
                )}
              </div>
            ))}
          </div>,
          document.body
        )}
    </>
  );
}

function Palette({commands, onClose}: {commands: Command[]; onClose: () => void}) {
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const q = query.trim().toLowerCase();
  const found = (
    q ? commands.filter(c => (c.label + ' ' + c.group).toLowerCase().includes(q)) : commands
  ).slice(0, 12);
  useEffect(() => setActive(0), [q]);
  const run = (c?: Command) => {
    if (!c) return;
    onClose();
    c.run();
  };
  return createPortal(
    <div className="hk-backdrop" onClick={onClose}>
      <section
        className="hk-palette"
        role="dialog"
        aria-label="Быстрый переход"
        onClick={e => e.stopPropagation()}
      >
        <input
          autoFocus
          placeholder="Экран, проект или герой…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'ArrowDown') setActive(i => Math.min(found.length - 1, i + 1));
            else if (e.key === 'ArrowUp') setActive(i => Math.max(0, i - 1));
            else if (e.key === 'Enter') run(found[active]);
            else return;
            e.preventDefault();
          }}
        />
        <ul role="listbox">
          {found.map((c, i) => (
            <li key={c.id} role="option" aria-selected={i === active}>
              <button
                className={i === active ? 'on' : ''}
                onMouseEnter={() => setActive(i)}
                onClick={() => run(c)}
              >
                <span>{c.label}</span>
                <small>{c.group}</small>
              </button>
            </li>
          ))}
          {!found.length && <li className="muted">Ничего не нашлось</li>}
        </ul>
      </section>
    </div>,
    document.body
  );
}
