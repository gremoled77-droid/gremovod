/** Вложения ролика («Идея» → «Мир» → «Персонажи»): лежат в scene.assets, роль задаёт, как их читать дальше. */
export type Attachment = {asset_id: string; role: string; note: string};

export const ATTACHMENT_ROLES: {id: string; label: string}[] = [
  {id: 'character', label: 'Герой'},
  {id: 'location', label: 'Локация'},
  {id: 'reference', label: 'Референс'},
  {id: 'object', label: 'Предмет'},
  {id: 'style', label: 'Стиль / свет'},
];

export const roleLabel = (role: string) => ATTACHMENT_ROLES.find(r => r.id === role)?.label || role;

/** Добавляет вложение без дублей: тот же файл второй раз не ставится, даже с другой ролью. */
export function addAttachment(list: Attachment[], asset_id: string, role: string): Attachment[] {
  return list.some(a => a.asset_id === asset_id) ? list : [...list, {asset_id, role, note: ''}];
}

export const setAttachmentRole = (list: Attachment[], asset_id: string, role: string): Attachment[] =>
  list.map(a => (a.asset_id === asset_id ? {...a, role} : a));

export const removeAttachment = (list: Attachment[], asset_id: string): Attachment[] =>
  list.filter(a => a.asset_id !== asset_id);
