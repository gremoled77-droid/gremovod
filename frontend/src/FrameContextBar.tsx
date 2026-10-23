import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {frameStatus, generatingFrames, photoLabel, videoLabel} from './frameStatus';

type Ref = {id: string; title: string; number: number};
export type FrameWorkspace = {
  production_id: string;
  project_id: string;
  frame: Ref;
  scene: Ref;
  series: Ref;
  files: {id: string; kind: string}[];
  selection: {selected_image_file_id: string | null; selected_video_file_id: string | null};
  cues: {id: string}[];
  jobs: {kind: string; status: string; node_id?: string | null}[];
};

/** Рабочее место кадра; проект кадра открывается на сервере (идемпотентно), приложение не переключается. */
export async function openFrameWorkspace(pid: string, nid: string): Promise<FrameWorkspace> {
  const base = `/api/productions/${encodeURIComponent(pid)}/nodes/${encodeURIComponent(nid)}`;
  const data = await responseJson(await apiFetch(base + '/workspace'));
  if (data.project_id) return data;
  const opened = await responseJson(await apiFetch(base + '/open-project', {method: 'POST'}));
  return {...data, project_id: opened.project_id};
}

/** Над «Кадрами», «Видео» и «Звуком»: для какого кадра работает инструмент и его состояние. */
export default function FrameContextBar({
  work,
  onBoard,
  onClear,
}: {
  work: FrameWorkspace;
  onBoard: () => void;
  onClear: () => void;
}) {
  const st = frameStatus(work.files, work.selection, generatingFrames(work.jobs).has(work.frame.id));
  return (
    <div className="frame-context" role="region" aria-label="Кадр в работе">
      <span>
        Кадр {work.scene.number}.{work.frame.number} · <b>{work.frame.title}</b>
        <small>
          {' '}
          · {work.series.title} · {work.scene.title}
        </small>
      </span>
      <span className={'ps-badge ' + st.photo}>{photoLabel(st)}</span>
      <span className={'ps-badge v-' + st.video}>{videoLabel(st)}</span>
      <span className="ps-badge">звук: {work.cues.length}</span>
      <button type="button" onClick={onBoard}>
        ← К доске
      </button>
      <button type="button" onClick={onClear} title="Работать без привязки к кадру">
        Без кадра
      </button>
    </div>
  );
}
