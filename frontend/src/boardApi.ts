import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

export type EntityPatch = Partial<{
  character_node_ids: string[];
  location_node_id: string | null;
  selected_image_file_id: string | null;
  selected_video_file_id: string | null;
}>;

const json = (method: string, body: unknown) => ({
  method,
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/**
 * Меняет часть карточки (состав, локацию, главный дубль), сохраняя остальное: читает актуальную карточку
 * с ревизией и отправляет её целиком с правкой. Конфликт версий вернёт ошибку 409 с понятным текстом.
 */
export async function patchEntity(pid: string, nid: string, patch: EntityPatch) {
  const url = `/api/productions/${pid}/nodes/${nid}/editor`;
  const editor = await responseJson(await apiFetch(url));
  const d = editor.data;
  return responseJson(
    await apiFetch(
      url,
      json('PUT', {
        base_revision: editor.revision,
        notes: editor.node.notes,
        character_node_ids: d.character_node_ids,
        location_node_id: d.location_node_id,
        selected_image_file_id: d.selected_image_file_id,
        selected_video_file_id: d.selected_video_file_id,
        ...patch,
      })
    )
  );
}

/** Новый порядок сцен серии (parentId = id серии) или кадров сцены (parentId = id сцены). */
export async function putOrder(boardPath: string, revision: string, parentId: string, nodeIds: string[]) {
  return responseJson(
    await apiFetch(
      boardPath + '/order',
      json('PUT', {base_revision: revision, parent_id: parentId, node_ids: nodeIds})
    )
  );
}
