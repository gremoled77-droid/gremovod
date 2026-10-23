import FrameActions from './FrameActions';
import FrameCast from './FrameCast';
import FrameTakes from './FrameTakes';
import UpscaleButton from './UpscaleButton';
import type {EntityPatch} from './boardApi';
import {frameStatus, photoLabel, videoLabel} from './frameStatus';
import {kindLabel, soundLabel, type Cue} from './soundCues';

type Media = {id: string; asset_id: string | null; kind: string; filename: string; url: string};
type Cast = {
  character_node_ids: string[];
  location_node_id: string | null;
  location_angle_file_id?: string | null;
};
type Selection = Cast & {selected_image_file_id: string | null; selected_video_file_id: string | null};
type Frame = {id: string; title: string; number: number; files: Media[]; selection: Selection};

const fileUrl = (f: Media) => (f.asset_id ? `/api/library/${f.asset_id}/file` : f.url);

/** Свойства кадра в фокусе: состав, дубли, звук и следующий шаг, без ухода с доски. */
export default function FrameInspector({
  pid,
  sceneNumber,
  sceneSelection,
  frame,
  catalogue,
  cues,
  generating,
  busy,
  onPatch,
  onAnimate,
  onStudio,
  onFiles,
  onSound,
  onClose,
}: {
  pid: string;
  sceneNumber: number;
  sceneSelection: Cast;
  frame: Frame;
  catalogue: {id: string; kind: string; title: string}[];
  cues: Cue[];
  generating: boolean;
  busy: boolean;
  onPatch: (patch: EntityPatch, message: string) => void;
  onAnimate: () => void;
  onStudio: () => void;
  onFiles: () => void;
  onSound?: () => void;
  onClose: () => void;
}) {
  const sel = frame.selection;
  const image =
    frame.files.find(f => f.id === sel.selected_image_file_id) || frame.files.find(f => f.kind === 'image');
  const video = frame.files.find(f => f.id === sel.selected_video_file_id);
  const st = frameStatus(frame.files, sel, generating);
  return (
    <aside className="ps-inspector" aria-label={`Свойства кадра ${sceneNumber}.${frame.number}`}>
      <header>
        <h3>
          Кадр {sceneNumber}.{frame.number} · {frame.title}
        </h3>
        <button type="button" aria-label="Закрыть свойства кадра" title="Закрыть" onClick={onClose}>
          ✕
        </button>
      </header>
      <div className="ps-insp-shot">
        {image ? (
          <img
            src={image.asset_id ? `/api/library/${image.asset_id}/thumbnail` : image.url}
            alt={frame.title}
          />
        ) : (
          <div className="ps-empty">нет изображения</div>
        )}
        {image && (
          <FrameActions
            small
            downloadUrl={fileUrl(image)}
            downloadName={image.filename}
            className="ps-insp-fa"
          />
        )}
      </div>
      <div className="ps-badges" aria-label="Статус кадра">
        <span className={'ps-badge ' + st.photo}>{photoLabel(st)}</span>
        <span className={'ps-badge v-' + st.video}>{videoLabel(st)}</span>
        <span className={'ps-badge s-' + (cues.length ? 'on' : 'off')}>{soundLabel(cues)}</span>
      </div>
      <div className="ps-acts">
        <button
          className="primary"
          disabled={busy || !sel.selected_image_file_id}
          title={
            sel.selected_image_file_id
              ? 'Оживить главное фото кадра'
              : 'Сначала утверди главное фото в дублях'
          }
          onClick={onAnimate}
        >
          Оживить
        </button>
        <button disabled={busy} onClick={onStudio}>
          В студию
        </button>
        <button onClick={onFiles}>Файлы ↗</button>
      </div>
      {!sel.selected_image_file_id && (
        <p className="muted">
          {image ? 'Выбери главное фото в дублях: оживить можно только его.' : 'Сделай фото кадра в студии.'}
        </p>
      )}
      <section>
        <h4>Состав</h4>
        <FrameCast
          id={frame.id}
          pid={pid}
          catalogue={catalogue}
          own={sel}
          scene={sceneSelection}
          busy={busy}
          onChange={onPatch}
        />
      </section>
      <section>
        <h4>Дубли</h4>
        {frame.files.length ? (
          <FrameTakes
            open
            files={frame.files}
            imageId={sel.selected_image_file_id}
            videoId={sel.selected_video_file_id}
            busy={busy}
            onPick={(kind, id) =>
              onPatch(
                kind === 'image' ? {selected_image_file_id: id} : {selected_video_file_id: id},
                id ? (kind === 'image' ? 'Главное фото выбрано.' : 'Главное видео выбрано.') : 'Выбор снят.'
              )
            }
          />
        ) : (
          <p className="muted">Файлов пока нет.</p>
        )}
        {sel.selected_image_file_id && <UpscaleButton fileId={sel.selected_image_file_id} />}
        {video && (
          <a href={fileUrl(video)} download={video.filename}>
            Скачать главное видео
          </a>
        )}
      </section>
      <section>
        <h4>Звук</h4>
        {cues.length ? (
          <ul className="ps-insp-cues">
            {cues.map(c => (
              <li key={c.id}>
                <b>{kindLabel(c.kind)}</b> {c.text || '—'}{' '}
                <small>
                  {c.level_db} дБ · с {c.start_s} с ·{' '}
                  {c.status === 'file' ? c.filename || 'файл' : 'без файла'}
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Звуковых заметок нет.</p>
        )}
        {onSound && (
          <button type="button" onClick={onSound}>
            Звук кадра →
          </button>
        )}
      </section>
    </aside>
  );
}
