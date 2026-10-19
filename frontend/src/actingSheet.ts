export const beatFields = [
  ['objective', 'Цель'],
  ['tactic', 'Тактика'],
  ['obstacle', 'Препятствие'],
  ['trigger', 'Повод перемены'],
  ['reaction', 'Реакция'],
  ['next_tactic', 'Следующая тактика'],
  ['visible_action', 'Видимое действие'],
  ['timing', 'Тайминг и пауза'],
  ['contact', 'Опора и контакт'],
  ['sound', 'Звук и синхроточка'],
  ['camera', 'Камера — отдельно'],
] as const;
export type BeatField = (typeof beatFields)[number][0];
export type Beat = Record<BeatField, string> & {
  id: string;
  actor_id: string;
  partner_id: string | null;
  shot_ids: string[];
};
export type ActingDraft = {
  base_revision: number;
  source_revision: string;
  status: 'draft' | 'interpretation' | 'approved';
  beats: Beat[];
};
export type ActingSnapshot = Omit<ActingDraft, 'base_revision'> & {
  revision: number;
  stale: boolean;
  scene: {id: string; title: string; notes: string};
  actors: {id: string; title: string}[];
  shots: {id: string; title: string}[];
};
export function fromSnapshot(saved: ActingSnapshot): ActingDraft {
  return {
    base_revision: saved.revision,
    source_revision: saved.source_revision,
    status: saved.status,
    beats: saved.beats,
  };
}
export function newBeat(actorId: string): Beat {
  return {
    id: crypto.randomUUID(),
    actor_id: actorId,
    partner_id: null,
    shot_ids: [],
    objective: '',
    tactic: '',
    obstacle: '',
    trigger: '',
    reaction: '',
    next_tactic: '',
    visible_action: '',
    timing: '',
    contact: '',
    sound: '',
    camera: '',
  };
}
export function validDraft(value: unknown): value is ActingDraft {
  if (!value || typeof value !== 'object') return false;
  const d = value as ActingDraft;
  return (
    Number.isInteger(d.base_revision) &&
    d.base_revision >= 0 &&
    typeof d.source_revision === 'string' &&
    /^[a-f0-9]{64}$/.test(d.source_revision) &&
    ['draft', 'interpretation', 'approved'].includes(d.status) &&
    Array.isArray(d.beats) &&
    d.beats.length <= 50 &&
    d.beats.every(
      b =>
        b &&
        typeof b.id === 'string' &&
        typeof b.actor_id === 'string' &&
        (b.partner_id === null || typeof b.partner_id === 'string') &&
        Array.isArray(b.shot_ids) &&
        b.shot_ids.every(id => typeof id === 'string') &&
        beatFields.every(([key]) => typeof b[key] === 'string')
    )
  );
}
export function versionsMatch(draft: ActingDraft, saved: ActingSnapshot) {
  return draft.base_revision === saved.revision && draft.source_revision === saved.source_revision;
}
/** Called only after the user compares versions and explicitly keeps their draft. */
export function keepDraft(draft: ActingDraft, saved: ActingSnapshot): ActingDraft {
  return {...draft, base_revision: saved.revision, source_revision: saved.source_revision, status: 'draft'};
}
