/**
 * Чистые функции экрана «Выпуск».
 *
 * Допуск к утверждению решает только сервер (`/gate`): здесь он не выводится и не
 * вычисляется. Клиент лишь собирает тело запроса из полей, которые ввёл человек, и
 * показывает то, что сервер уже посчитал (состояние, блокеры, хеш, вердикт N34).
 */

export type GateState = 'IMPORTED' | 'TECHNICAL_PASS' | 'OWNER_APPROVED' | 'REJECTED';
export type Blocker = {code: string; message: string};
export type HistoryItem = {
  decision_id: string;
  decision: 'APPROVED' | 'REJECTED';
  master_sha256: string;
  content_sha256: string;
  version_id: string | null;
  project_revision: number;
  owner_id: string;
  processing_rights_confirmed: number;
  qc_verdict: string;
  note: string;
  created_at: string;
};
export type Gate = {
  artifact_id: string;
  project_id: string;
  state: GateState;
  master_sha256: string;
  qc_verdict: string;
  qc_stale: boolean;
  qc_reason: string;
  version_id: string | null;
  project_revision: number;
  content_sha256: string;
  decision: string;
  decided_at: string | null;
  owner_id: string | null;
  decision_stale: boolean;
  decision_stale_code: string;
  decision_stale_reason: string;
  approve_blockers: Blocker[];
  can_approve: boolean;
  can_reject: boolean;
  blocked_reason: string | null;
  n35_evidence: {
    master: Record<string, unknown>;
    qc: Record<string, unknown>;
    coverage: Record<string, {status: string; reason: string}>;
    coverage_status: string;
    reason: string;
    processing_rights_confirmed: boolean;
  };
  history: HistoryItem[];
};

export type QcCheck = {name: string; expected: unknown; actual: unknown; ok: boolean};
export type QcResult = {verdict: string; reason: string; checks: QcCheck[]; requireAudio?: boolean};
export type QcOutcome = {verdict: string; reason: string; stale: boolean};

export type ApproveInput = {ownerId: string; rights: boolean; busy: boolean; requireAudio: boolean};
export type RejectInput = {ownerId: string; note: string; busy: boolean};
export type ApproveBody = {
  decision: 'APPROVED';
  owner_id: string;
  expected_master_sha256: string;
  processing_rights_confirmed: true;
  required_modalities: string[];
  note: string;
};
export type RejectBody = {
  decision: 'REJECTED';
  owner_id: string;
  expected_master_sha256: string;
  note: string;
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

/**
 * Счётчики выпуска. Финальным считается только OWNER_APPROVED — то, что сервер
 * зафиксировал как решение владельца. Всё остальное — «ожидает приёмки»;
 * `unknown` — подмножество `pending`: артефакты, состояние которых сервер ещё не отдавал.
 */
export function releaseCounts(ids: string[], gates: Record<string, Gate | undefined>) {
  let final = 0;
  let unknown = 0;
  for (const id of ids) {
    const gate = gates[id];
    if (!gate) {
      unknown += 1;
      continue;
    }
    if (gate.state === 'OWNER_APPROVED') final += 1;
  }
  return {final, pending: ids.length - final, unknown};
}

/** Манифест N34 — ожидания к мастеру; вердикт выводит сервер. */
export const qcManifest = (requireAudio: boolean) => ({container: 'mp4', require_audio: requireAudio});

/**
 * Требование аудио словами. Вердикт N34 относится к тому манифесту, которым мерили,
 * поэтому экран показывает, что именно проверялось — иначе «Пройдена» означала бы
 * неизвестно что.
 */
export const audioRequirementText = (requireAudio: boolean) =>
  requireAudio ? 'с требованием аудиодорожки' : 'без требования аудиодорожки';

/**
 * Требования изменились после проверки: показанный вердикт получен с другим
 * манифестом. Это предупреждение, а не запрет: допуск решает сервер.
 */
export function requirementMismatch(
  measured: {requireAudio?: boolean} | undefined,
  requireAudio: boolean
): boolean {
  if (!measured || measured.requireAudio === undefined) return false;
  return measured.requireAudio !== requireAudio;
}

/**
 * Модальности, которые сервер проверит при утверждении. Видеоблок нужен всегда,
 * звук — когда владелец его требует: без аудиодорожки утверждение не пройдёт
 * (сервер вернёт MEDIA_NOT_CONFIRMED по покрытию N35).
 */
export const requiredModalities = (requireAudio: boolean): string[] =>
  requireAudio ? ['VIDEO', 'AUDIO'] : ['VIDEO'];

/**
 * Что показать о проверке N34. Если файл менялся после проверки, сервер сам вернул
 * BLOCKED и qc_stale — тогда показываем серверную формулировку, а не старый вердикт.
 */
export function qcOutcome(gate: Gate | undefined, measured: QcResult | undefined): QcOutcome {
  if (!gate) return {verdict: '', reason: '', stale: false};
  if (gate.qc_stale)
    return {verdict: gate.qc_verdict || 'BLOCKED', reason: gate.qc_reason || '', stale: true};
  const verdict = measured?.verdict || gate.qc_verdict || '';
  const reason = measured?.reason || gate.qc_reason || '';
  return {verdict, reason, stale: false};
}

/** Владелец на сервере не настроен: ни утверждение, ни отклонение невозможны. */
export function ownerNotConfigured(gate: Gate | undefined): boolean {
  return !!gate?.approve_blockers.some(blocker => blocker.code === 'OWNER_ID_NOT_CONFIGURED');
}

/**
 * Почему «Утвердить» недоступно (пусто — можно отправлять). Первый серверный блокер
 * важнее локальных полей: сервер решает допуск.
 */
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

/** Тело утверждения: хеш берётся из `/gate` — тот, что показан на экране. Флагов состояния нет. */
export function approveBody(gate: Gate, input: ApproveInput): ApproveBody | null {
  if (approveBlockReason(gate, input)) return null;
  return {
    decision: 'APPROVED',
    owner_id: input.ownerId.trim(),
    expected_master_sha256: gate.master_sha256,
    processing_rights_confirmed: true,
    required_modalities: requiredModalities(input.requireAudio),
    note: '',
  };
}

/**
 * Почему «Отклонить» недоступно. Отклонение не зависит от технической проверки:
 * недоступно только при отсутствии владельца, уже вынесенном отказе и пустой причине.
 */
export function rejectBlockReason(gate: Gate | undefined, input: RejectInput): string {
  if (!gate) return 'Состояние выпуска ещё не загружено.';
  if (input.busy) return 'Выполняется действие, подождите.';
  if (ownerNotConfigured(gate)) return 'Владелец студии не настроен на сервере: решение невозможно.';
  if (!gate.can_reject) return 'Эта версия уже отклонена.';
  if (!input.ownerId.trim()) return 'Укажите идентификатор владельца.';
  if (!input.note.trim()) return 'Укажите причину отклонения.';
  return '';
}

/** Тело отклонения: причина обязательна, права на обработку не требуются. */
export function rejectBody(gate: Gate, input: RejectInput): RejectBody | null {
  if (rejectBlockReason(gate, input)) return null;
  return {
    decision: 'REJECTED',
    owner_id: input.ownerId.trim(),
    expected_master_sha256: gate.master_sha256,
    note: input.note.trim(),
  };
}

const UPLOAD_STATUS_TEXT: Record<number, string> = {
  409: 'Проект изменился после подготовки выпуска: нажмите «Загрузить» ещё раз — возьмётся актуальная ревизия. Автоматически не повторяем.',
  413: 'Файл слишком большой: максимум 1 ГБ.',
  415: 'Нужен файл в контейнере MP4.',
  422: 'Студия не смогла прочитать видео: файл повреждён или без видеопотока.',
};

/**
 * Причина от сервера. В ответах релиз-gate причина лежит во вложенном поле
 * `detail` объекта деталей (например, `AUDIO: в мастере нет аудиодорожки`) —
 * без неё владелец видел бы «не покрывает требуемые модальности» без объяснения.
 * Показываем её только вместе с сообщением сервера: иначе в текст попал бы сырой
 * вывод FFmpeg, а не объяснение по-русски.
 */
function serverReason(detail: unknown): string {
  if (!detail || typeof detail !== 'object') return '';
  const nested = (detail as {detail?: unknown}).detail;
  return typeof nested === 'string' ? nested : '';
}

/** Текст ошибки сервера по-русски. Сообщение сервера важнее общей подписи по статусу. */
export function errorText(status: number, body: unknown, upload = false): string {
  const detail = (body as {detail?: unknown} | null)?.detail;
  const message =
    typeof detail === 'string'
      ? detail
      : detail && typeof detail === 'object' && typeof (detail as {message?: unknown}).message === 'string'
        ? (detail as {message: string}).message
        : '';
  const reason = message ? serverReason(detail) : '';
  const withReason = (text: string) => (reason ? `${text} ${reason}` : text);
  if (upload && UPLOAD_STATUS_TEXT[status])
    return withReason(message ? `${UPLOAD_STATUS_TEXT[status]} (${message})` : UPLOAD_STATUS_TEXT[status]);
  if (status === 404 && (!message || message === 'Not Found'))
    return 'Проект или MP4 не найден на сервере. Сохраните проект и обновите страницу.';
  if (status === 401) return 'Сессия студии не принята. Обновите страницу.';
  if (status === 403) return withReason(message || 'Действие запрещено для этой сессии.');
  if (message) return withReason(message);
  return `Ошибка сервера (${status}).`;
}

export const shortSha = (sha: string) => (sha ? sha.slice(0, 12) + '…' : '—');
