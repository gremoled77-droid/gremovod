import {useEffect, useState} from 'react';
import {apiFetch, responseJson} from './api';
import {findProduction} from './locations';
import {readLocal, writeLocal} from './localDrafts';
import EditListPanel from './EditListPanel';
import type {Mode} from './screens';

type Series = {id: string; title: string};
type Frame = {
  id: string;
  title: string;
  files: {id: string; kind: string}[];
  selection: {selected_image_file_id: string | null; selected_video_file_id: string | null};
};

/** Одна и та же серия на этапах монтажа и выпуска; готовность только по выбранным дублям. */
export default function SeriesDelivery({
  projectId,
  onMode,
}: {
  projectId: string;
  onMode: (mode: Mode) => void;
}) {
  const [pid, setPid] = useState('');
  const [series, setSeries] = useState<Series[]>([]);
  const [sid, setSid] = useState('');
  const [frames, setFrames] = useState<Frame[] | null>(null);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    setLoaded(false);
    setFrames(null);
    setError('');
    void (async () => {
      const productionId = projectId ? await findProduction(projectId) : '';
      const tree = productionId
        ? await responseJson(await apiFetch('/api/productions/' + productionId))
        : null;
      if (!active) return;
      const items: Series[] = tree?.nodes.filter((node: {kind: string}) => node.kind === 'series') || [];
      const stored = readLocal<{pid: string; sid: string}>('studio:board-location', {pid: '', sid: ''});
      setPid(productionId);
      setSeries(items);
      setSid(items.find(s => stored.pid === productionId && s.id === stored.sid)?.id || items[0]?.id || '');
    })()
      .catch(e => active && setError(String(e)))
      .finally(() => active && setLoaded(true));
    return () => {
      active = false;
    };
  }, [projectId]);
  useEffect(() => {
    let active = true;
    setFrames(null);
    if (pid && sid) {
      writeLocal('studio:board-location', {pid, sid});
      void apiFetch(`/api/productions/${pid}/series/${sid}/storyboard`)
        .then(responseJson)
        .then(board => active && setFrames(board.scenes.flatMap((scene: {frames: Frame[]}) => scene.frames)))
        .catch(e => active && setError(String(e)));
    }
    return () => {
      active = false;
    };
  }, [pid, sid]);
  const chosen = (frame: Frame, kind: 'image' | 'video') =>
    frame.files.some(
      file =>
        file.kind === kind &&
        file.id === frame.selection[kind === 'image' ? 'selected_image_file_id' : 'selected_video_file_id']
    );
  const imageCount = frames?.filter(frame => chosen(frame, 'image')).length || 0;
  const videoCount = frames?.filter(frame => chosen(frame, 'video')).length || 0;
  return (
    <section className="panel series-delivery" aria-label="Подготовка серии к монтажу">
      <h2>Серия и готовность материалов</h2>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {!loaded ? (
        <p>Загружаем серии…</p>
      ) : !series.length ? (
        <p>
          Создай серию и кадры в раскадровке.{' '}
          <button onClick={() => onMode('storyboard')}>Открыть раскадровку →</button>
        </p>
      ) : (
        <>
          <label>
            Серия
            <select value={sid} onChange={e => setSid(e.target.value)}>
              {series.map(s => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
          </label>
          {frames && (
            <>
              <p>
                Кадров: <b>{frames.length}</b> · Главное фото:{' '}
                <b>
                  {imageCount}/{frames.length}
                </b>{' '}
                · Главный видеодубль:{' '}
                <b>
                  {videoCount}/{frames.length}
                </b>
              </p>
              {!frames.length ? (
                <p>В серии пока нет кадров.</p>
              ) : videoCount < frames.length ? (
                <p className="muted">
                  Выбери главные видеодубли в раскадровке. ZIP можно скачать и сейчас: пропуски будут
                  перечислены в инструкции.
                </p>
              ) : (
                <p role="status">
                  Для всех кадров выбраны видеодубли. Перед выпуском проверь звук, монтаж и финальный файл в
                  CapCut.
                </p>
              )}
              <div className="chips">
                <button onClick={() => onMode('storyboard')}>Проверить кадры и дубли</button>
                <button onClick={() => onMode('audio')}>Проверить звук</button>
              </div>
            </>
          )}
          <EditListPanel key={pid + sid} pid={pid} sid={sid} />
          <p className="muted">
            ZIP содержит материалы и CSV для ручного монтажа. Публикация ролика выполняется после проверки
            финального файла.
          </p>
        </>
      )}
    </section>
  );
}
