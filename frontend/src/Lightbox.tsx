import {useEffect, useRef} from 'react';
import {createPortal} from 'react-dom';
import FrameActions, {type FrameActionSet} from './FrameActions';
import MediaAssetActions from './MediaAssetActions';
import {assetIdFromUrl, type MediaChange} from './mediaAsset';

export type LightboxItem = FrameActionSet & {
  url: string;
  title?: string;
  kind?: string;
  assetId?: string;
  /** Подпись сверху: модель, разрешение, цена. */
  caption?: string;
};

/** Полноэкранный просмотр: стрелки ← → листают, Esc закрывает, клик по фону закрывает. */
export default function Lightbox({
  items,
  index,
  onIndex,
  onClose,
  onAssetChanged,
  onReference,
  onAnimate,
}: {
  items: LightboxItem[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
  onAssetChanged?: (id: string, change: MediaChange) => void;
  onReference?: (id: string) => void;
  onAnimate?: (id: string) => void;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const n = items.length;
  const item = items[index];
  const go = (d: number) => onIndex((index + d + n) % n);
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    const root = document.getElementById('root');
    const inert = root?.inert;
    document.body.style.overflow = 'hidden';
    if (root) root.inert = true;
    const frame = requestAnimationFrame(() => closeButton.current?.focus());
    return () => {
      cancelAnimationFrame(frame);
      document.body.style.overflow = overflow;
      if (root) root.inert = inert ?? false;
      if (previous?.isConnected) previous.focus({preventScroll: true});
    };
  }, []);
  useEffect(() => {
    if (!dialog.current?.contains(document.activeElement)) closeButton.current?.focus();
  }, [index, item?.url]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        const controls = Array.from(
          dialog.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]),a[href],textarea,input,select,[tabindex="0"]'
          ) || []
        ).filter(el => el.getClientRects().length > 0);
        const first = controls[0],
          last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
        return;
      }
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const target = e.target instanceof HTMLElement ? e.target : null;
      const editing =
        target?.matches('input,textarea,select') || target?.isContentEditable || target?.closest('video');
      if (e.key === 'Escape') onClose();
      else if (!editing && e.key === 'ArrowLeft' && n > 1) go(-1);
      else if (!editing && e.key === 'ArrowRight' && n > 1) go(1);
      else return;
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  if (!item) return null;
  return createPortal(
    <div
      ref={dialog}
      className="lb"
      role="dialog"
      aria-modal="true"
      aria-label="Просмотр кадра"
      onClick={e => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <button ref={closeButton} className="lb-x" aria-label="Закрыть" onClick={onClose}>
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
        <div className="lb-media">
          {item.kind === 'video' ? (
            <video src={item.url} controls autoPlay />
          ) : (
            <img src={item.url} alt={item.title || ''} />
          )}
          <div className="lb-top">
            <span>{item.caption}</span>
            <FrameActions
              favorite={item.favorite}
              onFavorite={item.onFavorite}
              onEdit={item.onEdit}
              onRef={item.onRef}
              refActive={item.refActive}
              onAnimate={item.onAnimate}
              downloadUrl={item.downloadUrl ?? item.url}
              downloadName={item.downloadName}
              onTrash={item.onTrash}
            />
          </div>
        </div>
        <figcaption>
          <span>{item.title}</span>
          <span>
            {index + 1} / {n} · ← → листать · Esc закрыть
          </span>
        </figcaption>
        {!item.onFavorite && (item.assetId || assetIdFromUrl(item.url)) && (
          <MediaAssetActions
            key={item.assetId || assetIdFromUrl(item.url)}
            assetId={(item.assetId || assetIdFromUrl(item.url))!}
            onChanged={onAssetChanged}
            onReference={onReference}
            onAnimate={onAnimate}
          />
        )}
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
