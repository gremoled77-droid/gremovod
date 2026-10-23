type Take = {id: string; asset_id: string | null; kind: string; filename: string; url: string};

/** Дубли кадра: фото и видео по одному плиточному ряду, клик назначает или снимает «главный». В инспекторе открыты всегда. */
export default function FrameTakes({
  open = false,
  files,
  imageId,
  videoId,
  busy,
  onPick,
}: {
  open?: boolean;
  files: Take[];
  imageId: string | null;
  videoId: string | null;
  busy: boolean;
  onPick: (kind: 'image' | 'video', id: string | null) => void;
}) {
  if (!files.length || (!open && files.length < 2 && !imageId && !videoId)) return null;
  return (
    <details className="ps-takes" open={open}>
      <summary>Дубли ({files.length}) · выбрать главный</summary>
      <div className="ps-take-row">
        {files.map(f => {
          const kind = f.kind === 'video' ? 'video' : 'image';
          const current = kind === 'image' ? imageId : videoId;
          const on = current === f.id;
          return (
            <button
              key={f.id}
              type="button"
              className={'ps-take' + (on ? ' on' : '')}
              disabled={busy}
              aria-pressed={on}
              title={
                on
                  ? 'Главный дубль. Нажми, чтобы снять выбор'
                  : kind === 'image'
                    ? 'Сделать главным фото'
                    : 'Сделать главным видео'
              }
              onClick={() => onPick(kind, on ? null : f.id)}
            >
              {kind === 'image' ? (
                <img
                  src={f.asset_id ? `/api/library/${f.asset_id}/thumbnail` : f.url}
                  alt={f.filename}
                  loading="lazy"
                />
              ) : (
                <span className="ps-take-video" aria-hidden="true">
                  ▶
                </span>
              )}
              <span>
                {on
                  ? kind === 'image'
                    ? 'главное фото'
                    : 'главное видео'
                  : kind === 'image'
                    ? 'фото'
                    : 'видео'}
              </span>
            </button>
          );
        })}
      </div>
    </details>
  );
}
