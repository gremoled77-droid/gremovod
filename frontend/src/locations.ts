import {apiFetch, responseJson} from './api';

export type LocationNode = {id: string; title: string; notes: string};
export type LocationFile = {id: string; asset_id: string | null; kind: string; filename: string};
export type LocationCard = LocationNode & {files: LocationFile[]};

const json = (method: string, body: unknown) => ({
  method,
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/** Общий проект только по явной связи: чужая открытая доска не меняет владельца данных. */
export async function findProduction(projectId: string): Promise<string> {
  const where = await responseJson(
    await apiFetch(`/api/projects/${encodeURIComponent(projectId)}/workspace-location`)
  );
  if (where?.production_id) return where.production_id;
  return '';
}

/** Локации общего проекта вместе с файлами-картинками. */
export async function loadLocations(pid: string): Promise<LocationCard[]> {
  const tree = await responseJson(await apiFetch('/api/productions/' + pid));
  const nodes: LocationNode[] = tree.nodes.filter((n: {kind: string}) => n.kind === 'location');
  return Promise.all(
    nodes.map(async n => {
      const full = await responseJson(await apiFetch(`/api/productions/${pid}/nodes/${n.id}`));
      return {
        id: n.id,
        title: n.title,
        notes: n.notes || '',
        files: (full.files || []).filter((f: LocationFile) => f.kind === 'image'),
      };
    })
  );
}

export async function createLocation(pid: string, title: string) {
  return responseJson(
    await apiFetch(`/api/productions/${pid}/nodes`, json('POST', {kind: 'location', title, parent_id: null}))
  );
}

export async function saveLocationNotes(pid: string, nid: string, notes: string) {
  return responseJson(await apiFetch(`/api/productions/${pid}/nodes/${nid}/notes`, json('PUT', {notes})));
}

/** Кладёт картинки из библиотеки в папку локации (раздел «Изображения»). */
export async function attachToLocation(pid: string, nid: string, assetIds: string[]) {
  for (const asset_id of assetIds)
    await responseJson(
      await apiFetch(
        `/api/productions/${pid}/nodes/${nid}/assets`,
        json('POST', {asset_id, category: '02_Изображения'})
      )
    );
}

export async function uploadToLocation(pid: string, nid: string, file: File) {
  const form = new FormData();
  form.append('category', '02_Изображения');
  form.append('file', file);
  return responseJson(
    await apiFetch(`/api/productions/${pid}/nodes/${nid}/upload`, {method: 'POST', body: form})
  );
}
