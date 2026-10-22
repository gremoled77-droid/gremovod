/** Чистые функции экрана «Выпуск». Допуск к утверждению решает только сервер (`/gate`): здесь его не выводим. */

export type GateState = 'IMPORTED' | 'TECHNICAL_PASS' | 'OWNER_APPROVED' | 'REJECTED';
export type Blocker = {code: string; message: string};
export type HistoryItem = {
  decision_id: string;
  decision: 'APPROVED' | 'REJECTED';
  master_sha256: string;
  owner_id: string;
  note: string;
  created_at: string;
};
export type Gate = {
  artifact_id: string;
  state: GateState;
  master_sha256: string;
  qc_verdict: string;
  qc_stale: boolean;
  qc_reason: string;
  version_id: string | null;
  project_revision: number;
  decision: string;
  decided_at: string | null;
  owner_id: string | null;
  decision_stale: boolean;
  decision_stale_reason: string;
  approve_blockers: Blocker[];
  can_approve: boolean;
  can_reject: boolean;
  blocked_reason: string | null;
  n35_evidence: {
    coverage: Record<string, {status: string; reason: string}>;
    coverage_status: string;
    reason: string;
    processing_rights_confirmed: boolean;
  };
  history: HistoryItem[];
};

const STATE_TEXT: Record<GateState, string> = {
  IMPORTED: 'Загружен, проверка не пройдена',
  TECHNICAL_PASS: 'Техническая проверка пройдена, ждёт решения владельца',
  OWNER_APPROVED: 'Утверждён владельцем',
  REJECTED: 'Отклонён владельцем',
};
export const stateText = (state: GateState | undefined) =>
  state ? STATE_TEXT[state] : 'Состояние неизвестно';

const VERDICT_TEXT: Record<string, string> = {
  PASS_TECHNICAL: 'Пройдена',
  FAIL: 'Не соответствует ожиданиям',
  BLOCKED: 'Измерить нельзя',
};
export const verdictText = (verdict: string | undefined) =>
  !verdict ? 'Не проводилась' : (VERDICT_TEXT[verdict] ?? verdict);

/** Финальными называются только утверждённые владельцем; остальные — «ждут приёмки», не загруженные в gate — «не проверены». */
export function releaseCounts(ids: string[], gates: Record<string, Gate | undefined>) {
  let final = 0;
  let pending = 0;
  let unknown = 0;
  for (const id of ids) {
    const gate = gates[id];
    if (!gate) unknown += 1;
    else if (gate.state === 'OWNER_APPROVED') final += 1;
    else pending += 1;
  }
  return {final, pending, unknown};
}

/** Манифест N34 — ожидания к мастеру; сервер сам выводит вердикт. */
export const qcManifest = (requireAudio: boolean) => ({container: 'mp4', require_audio: requireAudio});

export type ApproveInput = {ownerId: string; rights: boolean; busy: boolean};

/** Почему «Утвердить» недоступно (пусто — можно отправлять). Допуск сервера главный, здесь только локальные поля. */
export function approveBlockReason(gate: Gate | undefined, input: ApproveInput): string {
  if (!gate) return 'Состояние выпуска ещё не загружено.';
  if (input.busy) return 'Выполняется действие, подождите.';
  const server = gate.approve_blockers[0];
  if (server) return server.message;
  if (!gate.can_approve) {
    return gate.state === 'OWNER_APPROVED'
      ? 'Эта версия уже утверждена.'
      : 'Сервер не разрешает утверждение.';
  }
  if (!input.ownerId.trim()) return 'Укажите идентификатор владельца.';
  if (!input.rights) return 'Подтвердите право на обработку контента.';
  return '';
}

export function approveBody(gate: Gate, input: ApproveInput) {
  if (approveBlockReason(gate, input)) return null;
  return {
    decision: 'APPROVED',
    owner_id: input.ownerId.trim(),
    expected_master_sha256: gate.master_sha256, // тот хеш, что показан на экране
    processing_rights_confirmed: true,
    required_modalities: ['VIDEO'],
    note: '',
  };
}

export function rejectBlockReason(
  gate: Gate | undefined,
  input: {ownerId: string; note: string; busy: boolean}
): string {
  if (!gate) return 'Состояние выпуска ещё не загружено.';
  if (input.busy) return 'Выполняется действие, подождите.';
  if (!gate.can_reject) return 'Эта версия уже отклонена.';
  if (!input.ownerId.trim()) return 'Укажите идентификатор владельца.';
  if (!input.note.trim()) return 'Укажите причину отклонения.';
  return '';
}

export function rejectBody(gate: Gate, input: {ownerId: string; note: string; busy: boolean}) {
  if (rejectBlockReason(gate, input)) return null;
  return {
    decision: 'REJECTED',
    owner_id: input.ownerId.trim(),
    expected_master_sha256: gate.master_sha256,
    note: input.note.trim(),
  };
}

const UPLOAD_STATUS_TEXT: Record<number, string> = {
  409: 'Проект изменился после подготовки выпуска. Нажмите «Загрузить» ещё раз — возьмётся актуальная ревизия.',
  413: 'Файл слишком большой: максимум 1 ГБ.',
  415: 'Нужен файл в контейнере MP4.',
  422: 'Студия не смогла прочитать видео: файл повреждён или без видеопотока.',
};

/** Русский текст ошибки ответа. Сообщение сервера важнее общей подписи по статусу. */
export function errorText(status: number, body: unknown, upload = false): string {
  const detail = (body as {detail?: unknown} | null)?.detail;
  const message =
    typeof detail === 'string'
      ? detail
      : detail && typeof detail === 'object' && typeof (detail as {message?: unknown}).message === 'string'
        ? ((detail as {message: string}).message as string)
        : '';
  if (upload && UPLOAD_STATUS_TEXT[status])
    return message ? `${UPLOAD_STATUS_TEXT[status]} (${message})` : UPLOAD_STATUS_TEXT[status];
  if (status === 404 && (!message || message === 'Not Found'))
    return 'Проект или MP4 не найден на сервере. Сохраните проект и обновите страницу.';
  if (status === 401) return 'Сессия студии не принята. Обновите страницу.';
  if (status === 403) return message || 'Действие запрещено для этой сессии.';
  if (message) return message;
  return `Ошибка сервера (${status}).`;
}

export const shortSha = (sha: string) => (sha ? sha.slice(0, 12) + '…' : '—');
