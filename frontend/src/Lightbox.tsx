import {useEffect} from 'react';
import {createPortal} from 'react-dom';

export type LightboxItem = {url: string; title?: string; kind?: string};

/** Полноэкранный просмотр: стрелки ← → листают, Esc закрывает, клик по фону закрывает. */
export default function Lightbox({
  items,
  index,
  onIndex,
  onClose,
}: {
  items: LightboxItem[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
}) {
  const n = items.length;
  const go = (d: number) => onIndex((index + d + n) % n);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') go(-1);
      else if (e.key === 'ArrowRight') go(1);
      else return;
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  const item = items[index];
  if (!item) return null;
  return createPortal(
    <div className="lb" role="dialog" aria-modal="true" aria-label="Просмотр кадра" onClick={onClose}>
      <button className="lb-x" aria-label="Закрыть" onClick={onClose}>
        ×
      </button>
      {n > 1 && (
        <button
          className="lb-nav lb-prev"
          aria-label="Предыдущий"
          onClick={e => {
            e.stopPropagation();
            go(-1);
          }}
        >
          ‹
        </button>
      )}
      <figure onClick={e => e.stopPropagation()}>
        {item.kind === 'video' ? (
          <video src={item.url} controls autoPlay />
        ) : (
          <img src={item.url} alt={item.title || ''} />
        )}
        <figcaption>
          <span>{item.title}</span>
          <span>
            {index + 1} / {n} · ← → листать · Esc закрыть
          </span>
        </figcaption>
      </figure>
      {n > 1 && (
        <button
          className="lb-nav lb-next"
          aria-label="Следующий"
          onClick={e => {
            e.stopPropagation();
            go(1);
          }}
        >
          ›
        </button>
      )}
    </div>,
    document.body
  );
}
