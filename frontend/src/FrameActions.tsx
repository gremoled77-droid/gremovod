import {Clapperboard, Download, Heart, ImagePlus, Pencil, Trash2} from 'lucide-react';

/** Действия над кадром. Любое действие, которого нет, просто не показывается. */
export type FrameActionSet = {
  favorite?: boolean;
  onFavorite?: () => void;
  /** Править в GPT Image: кадр становится референсом правки. */
  onEdit?: () => void;
  onRef?: () => void;
  refActive?: boolean;
  onAnimate?: () => void;
  downloadUrl?: string;
  downloadName?: string;
  onTrash?: () => void;
};

/** Один набор кнопок для просмотра во весь экран, плиток и карточек результатов. */
export default function FrameActions({
  className = '',
  small,
  ...a
}: FrameActionSet & {className?: string; small?: boolean}) {
  const size = small ? 13 : 16;
  const stop = (fn?: () => void) => (e: {stopPropagation: () => void}) => {
    e.stopPropagation();
    fn?.();
  };
  return (
    <div className={'frame-actions' + (small ? ' sm' : '') + (className ? ' ' + className : '')}>
      {a.onFavorite && (
        <button
          type="button"
          className={'fa-fav' + (a.favorite ? ' on' : '')}
          aria-label={a.favorite ? 'Убрать из избранного' : 'В избранное'}
          aria-pressed={!!a.favorite}
          title={a.favorite ? 'Убрать из избранного' : 'В избранное'}
          onClick={stop(a.onFavorite)}
        >
          <Heart size={size} fill={a.favorite ? 'currentColor' : 'none'} />
        </button>
      )}
      {a.onEdit && (
        <button
          type="button"
          aria-label="Править в GPT Image"
          title="Править в GPT Image"
          onClick={stop(a.onEdit)}
        >
          <Pencil size={size} />
        </button>
      )}
      {a.onRef && (
        <button
          type="button"
          className={a.refActive ? 'on' : ''}
          aria-label={a.refActive ? 'Убрать из референсов' : 'В референсы'}
          aria-pressed={!!a.refActive}
          title={a.refActive ? 'Убрать из референсов' : 'В референсы'}
          onClick={stop(a.onRef)}
        >
          <ImagePlus size={size} />
        </button>
      )}
      {a.onAnimate && (
        <button type="button" aria-label="Оживить" title="Оживить" onClick={stop(a.onAnimate)}>
          <Clapperboard size={size} />
        </button>
      )}
      {a.downloadUrl && (
        <a
          className="fa-link"
          href={a.downloadUrl}
          download={a.downloadName || ''}
          aria-label="Скачать"
          title="Скачать"
          onClick={e => e.stopPropagation()}
        >
          <Download size={size} />
        </a>
      )}
      {a.onTrash && (
        <button
          type="button"
          className="fa-trash"
          aria-label="В корзину"
          title="В корзину"
          onClick={stop(a.onTrash)}
        >
          <Trash2 size={size} />
        </button>
      )}
    </div>
  );
}
