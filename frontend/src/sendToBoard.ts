import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {readLocal, writeLocal} from './localDrafts';

export type BoardScene = {id: string; title: string; number: number; frames: {id: string; title: string}[]};
export type BoardTarget = {
  pid: string;
  sid: string;
  seriesTitle: string;
  revision: string;
  scenes: BoardScene[];
  characterNodes: {id: string; title: string; character_id: string | null}[];
  locationNodes: {id: string; title: string}[];
};

/** Куда отправлять кадры: общий проект и серия проекта из «Раскадровки», затем доска с ревизией и составом. */
export async function loadTarget(projectId: string): Promise<BoardTarget | null> {
  const where = await responseJson(
    await apiFetch(`/api/projects/${encodeURIComponent(projectId)}/workspace-location`)
  );
  const stored = readLocal<{pid: string; sid: string}>('studio:board-location', {pid: '', sid: ''});
  let pid: string = where?.production_id || '';
  if (!pid) {
    const all = await responseJson(await apiFetch('/api/productions'));
    pid = all.find((p: {id: string}) => p.id === stored.pid)?.id || (all.length === 1 ? all[0].id : '');
  }
  if (!pid) return null;
  const tree = await responseJson(await apiFetch('/api/productions/' + pid));
  const series = tree.nodes.filter((n: {kind: string}) => n.kind === 'series');
  const sid: string =
    where?.series?.id ||
    series.find((n: {id: string}) => n.id === stored.sid)?.id ||
    (series.length ? series[0].id : '');
  if (!sid) return null;
  const board = await responseJson(await apiFetch(`/api/productions/${pid}/series/${sid}/storyboard`));
  return {
    pid,
    sid,
    seriesTitle: board.series.title,
    revision: board.revision,
    scenes: board.scenes,
    characterNodes: tree.nodes.filter((n: {kind: string}) => n.kind === 'character'),
    locationNodes: tree.nodes.filter((n: {kind: string}) => n.kind === 'location'),
  };
}

export type SendBody = {
  scene_id?: string;
  scene_title?: string;
  frames: {asset_id: string; title: string}[];
  character_node_ids: string[];
  location_node_id: string | null;
};

/** «Отправить в раскадровку»: один запрос. request_id создаётся на попытку, повтор безопасен. */
export async function sendFrames(target: BoardTarget, body: SendBody, requestId: string) {
  const result = await responseJson(
    await apiFetch(`/api/productions/${target.pid}/series/${target.sid}/storyboard/frames`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...body, base_revision: target.revision, request_id: requestId}),
    })
  );
  writeLocal('studio:board-location', {pid: target.pid, sid: target.sid});
  return result as {scene_id: string; frame_ids: string[]; revision: string; replayed: boolean};
}
