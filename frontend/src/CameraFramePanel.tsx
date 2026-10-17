import {useState} from 'react';
import {X} from 'lucide-react';
import CameraFramePreview from './CameraFramePreview';
import {
  FRAME_CATS,
  FRAME_ITEMS,
  removeFrameItem,
  selectedFrameItems,
  toggleFrameItem,
  type FrameCat,
} from './cameraFrameCatalog';

/** Панель «Камера и кадр»: карточки с мини-превью, клик добавляет фразу в строки FRAME / CAMERA / LIGHT промпта, выбранное видно чипами. */
export default function CameraFramePanel({
  prompt,
  onPrompt,
  extra,
  categories = ['size', 'angle', 'comp', 'light'],
  defaultOpen = false,
  hint = 'план, ракурс, композиция, свет',
  title = 'Камера и кадр',
}: {
  prompt: string;
  onPrompt: (update: (current: string) => string) => void;
  extra?: React.ReactNode;
  /** Движение камеры подключается в разделе «Видео», в «Кадрах» его нет. */
  categories?: FrameCat[];
  defaultOpen?: boolean;
  hint?: string;
  title?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [cat, setCat] = useState<FrameCat>(categories[0] ?? 'size');
  const cats = FRAME_CATS.filter(c => categories.includes(c.id));
  const chosen = selectedFrameItems(prompt).filter(i => categories.includes(i.cat));
  const chosenIds = new Set(chosen.map(i => i.id));
  const catLabel = (c: FrameCat) => FRAME_CATS.find(x => x.id === c)!.label;

  return (
    <div className="cf">
      <div className="cf-bar">
        <button
          type="button"
          className={'cf-toggle' + (open ? ' on' : '')}
          aria-expanded={open}
          onClick={() => setOpen(v => !v)}
        >
          {title} <span aria-hidden="true">{open ? '▴' : '▾'}</span>
        </button>
        <div className="cf-chips" aria-label="Выбрано">
          {chosen.map(i => (
            <span key={i.id} className="cf-chip" title={i.en}>
              <small>{catLabel(i.cat)}</small>
              {i.ru}
              <button
                type="button"
                aria-label={`Убрать: ${i.ru}`}
                onClick={() => onPrompt(cur => removeFrameItem(cur, i))}
              >
                <X size={12} />
              </button>
            </span>
          ))}
          {!chosen.length && <span className="cf-hint">{hint}</span>}
        </div>
        {extra}
      </div>
      {open && (
        <div className="cf-drawer">
          <div className="cf-tabs" role="tablist">
            {cats.map(c => {
              const count = chosen.filter(i => i.cat === c.id).length;
              return (
                <button
                  key={c.id}
                  type="button"
                  role="tab"
                  aria-selected={cat === c.id}
                  className={cat === c.id ? 'on' : ''}
                  onClick={() => setCat(c.id)}
                >
                  {c.label}
                  {count > 0 && <em>●</em>}
                </button>
              );
            })}
          </div>
          <div className="cf-grid">
            {FRAME_ITEMS.filter(i => i.cat === cat).map(i => (
              <button
                key={i.id}
                type="button"
                className={'cf-card' + (chosenIds.has(i.id) ? ' on' : '')}
                aria-pressed={chosenIds.has(i.id)}
                title={i.en}
                onClick={() => onPrompt(cur => toggleFrameItem(cur, i))}
              >
                <CameraFramePreview cat={i.cat} id={i.id} />
                <span>{i.ru}</span>
              </button>
            ))}
          </div>
          <small className="muted">
            Фраза уходит в строки {[...new Set(cats.map(c => c.line))].join(', ')} промпта; в каждой группе
            выбирается один вариант.
          </small>
        </div>
      )}
    </div>
  );
}
