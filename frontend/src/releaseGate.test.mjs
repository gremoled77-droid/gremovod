import test from 'node:test';
import assert from 'node:assert/strict';
import {
  approveBlockReason,
  approveBody,
  audioRequirementText,
  errorText,
  ownerNotConfigured,
  qcManifest,
  qcOutcome,
  rejectBlockReason,
  rejectBody,
  releaseCounts,
  requirementMismatch,
  requiredModalities,
  shortSha,
  stateText,
  verdictText,
} from './releaseGate.ts';

const SHA = 'a'.repeat(64);
const gate = (over = {}) => ({
  artifact_id: 'a1',
  project_id: 'p1',
  state: 'TECHNICAL_PASS',
  master_sha256: SHA,
  qc_verdict: 'PASS_TECHNICAL',
  qc_stale: false,
  qc_reason: '',
  version_id: null,
  project_revision: 3,
  content_sha256: 'b'.repeat(64),
  decision: '',
  decided_at: null,
  owner_id: null,
  decision_stale: false,
  decision_stale_code: '',
  decision_stale_reason: '',
  approve_blockers: [],
  can_approve: true,
  can_reject: true,
  blocked_reason: null,
  n35_evidence: {
    master: {},
    qc: {},
    coverage: {VIDEO: {status: 'CONFIRMED', reason: ''}},
    coverage_status: 'CONFIRMED',
    reason: '',
    processing_rights_confirmed: false,
  },
  history: [],
  ...over,
});
const ready = {ownerId: 'owner', rights: true, busy: false, requireAudio: false};

test('финальными считаются только утверждённые владельцем, импорты — отдельно', () => {
  const gates = {
    a: gate({state: 'OWNER_APPROVED'}),
    b: gate({state: 'IMPORTED'}),
    c: gate({state: 'REJECTED'}),
    d: gate({state: 'TECHNICAL_PASS'}),
  };
  assert.deepEqual(releaseCounts(['a', 'b', 'c', 'd', 'e'], gates), {final: 1, pending: 4, unknown: 1});
  assert.deepEqual(releaseCounts(['x', 'y'], {}), {final: 0, pending: 2, unknown: 2});
});

test('загруженные MP4 без решения не называются финальными', () => {
  const gates = {a: gate({state: 'IMPORTED'}), b: gate({state: 'TECHNICAL_PASS'})};
  const counts = releaseCounts(['a', 'b'], gates);
  assert.equal(counts.final, 0);
  assert.equal(counts.pending, 2);
});

test('счётчик ожидающих приёмки включает всё, что сервер не утвердил', () => {
  const ids = ['a', 'b', 'c'];
  const gates = {
    a: gate({state: 'OWNER_APPROVED'}),
    b: gate({state: 'REJECTED'}),
  };
  const counts = releaseCounts(ids, gates);
  assert.equal(counts.final, 1);
  assert.equal(counts.pending, 2);
  assert.equal(counts.unknown, 1);
  assert.equal(counts.pending, ids.length - counts.final);
});

test('утверждение отправляет тот хеш, что показан в gate, и не несёт клиентских флагов состояния', () => {
  const body = approveBody(gate(), {...ready, ownerId: '  owner  '});
  assert.deepEqual(body, {
    decision: 'APPROVED',
    owner_id: 'owner',
    expected_master_sha256: SHA,
    processing_rights_confirmed: true,
    required_modalities: ['VIDEO'],
    note: '',
  });
  for (const key of Object.keys(body)) assert.ok(!/state|verdict|qc|approved|can_/i.test(key));
});

test('хеш в теле утверждения берётся из gate, а не из ответа сервера', () => {
  const other = 'c'.repeat(64);
  const body = approveBody(gate({master_sha256: other}), ready);
  assert.equal(body.expected_master_sha256, other);
  assert.notEqual(body.expected_master_sha256, SHA);
});

test('утверждение заблокировано: серверные блокеры, can_approve, поля, занятость', () => {
  const server = gate({
    approve_blockers: [{code: 'QC_STALE', message: 'Файл изменён после проверки'}],
    can_approve: false,
  });
  assert.equal(approveBlockReason(server, ready), 'Файл изменён после проверки');
  assert.equal(approveBody(server, ready), null);
  assert.match(
    approveBlockReason(gate({can_approve: false, state: 'OWNER_APPROVED'}), ready),
    /уже утверждена/
  );
  assert.match(approveBlockReason(gate({can_approve: false}), ready), /Сервер не разрешает/);
  assert.match(approveBlockReason(gate(), {...ready, ownerId: ' '}), /владельца/);
  assert.match(approveBlockReason(gate(), {...ready, rights: false}), /право на обработку/);
  assert.match(approveBlockReason(gate(), {...ready, busy: true}), /подождите/);
  assert.match(approveBlockReason(undefined, ready), /не загружено/);
  assert.equal(approveBlockReason(gate(), ready), '');
});

test('причины блокировки берутся из approve_blockers[].message', () => {
  const blocked = gate({
    approve_blockers: [
      {code: 'QC_NOT_RUN', message: 'Техническая проверка N34 ещё не проводилась.'},
      {
        code: 'OWNER_ID_NOT_CONFIGURED',
        message: 'Владелец студии не настроен на сервере: решение невозможно.',
      },
    ],
    can_approve: false,
  });
  assert.equal(approveBlockReason(blocked, ready), 'Техническая проверка N34 ещё не проводилась.');
  assert.equal(ownerNotConfigured(blocked), true);
  assert.equal(ownerNotConfigured(gate()), false);
  assert.equal(approveBody(blocked, ready), null);
});

test('отклонение требует причину и владельца, недоступно для уже отклонённого и при занятости', () => {
  const input = {ownerId: 'owner', note: '  плохой звук ', busy: false};
  assert.deepEqual(rejectBody(gate(), input), {
    decision: 'REJECTED',
    owner_id: 'owner',
    expected_master_sha256: SHA,
    note: 'плохой звук',
  });
  assert.match(rejectBlockReason(gate(), {...input, note: '   '}), /причину/);
  assert.equal(rejectBody(gate(), {...input, note: ''}), null);
  assert.equal(rejectBody(gate(), {...input, note: '   '}), null);
  assert.match(rejectBlockReason(gate({can_reject: false}), input), /уже отклонена/);
  assert.match(rejectBlockReason(gate(), {...input, busy: true}), /подождите/);
  assert.match(rejectBlockReason(gate(), {...input, ownerId: ' '}), /владельца/);
});

test('отклонение доступно без технического PASS: технические блокеры его не закрывают', () => {
  const input = {ownerId: 'owner', note: 'плохой звук', busy: false};
  const technical = gate({
    approve_blockers: [{code: 'QC_NOT_RUN', message: 'Техническая проверка N34 ещё не проводилась.'}],
    can_approve: false,
  });
  assert.equal(rejectBlockReason(technical, input), '');
  assert.equal(rejectBody(technical, input).decision, 'REJECTED');
});

test('без владельца на сервере отклонить тоже нельзя', () => {
  const input = {ownerId: 'owner', note: 'плохой звук', busy: false};
  const noOwner = gate({
    approve_blockers: [
      {
        code: 'OWNER_ID_NOT_CONFIGURED',
        message: 'Владелец студии не настроен на сервере: решение невозможно.',
      },
    ],
    can_approve: false,
  });
  assert.match(rejectBlockReason(noOwner, input), /не настроен/);
  assert.equal(rejectBody(noOwner, input), null);
});

test('тексты ошибок: сообщение сервера, коды загрузки 409/413/415/422, 401/403', () => {
  assert.match(
    errorText(409, {detail: {code: 'PROJECT_REVISION_CONFLICT', message: 'Проект изменился'}}, true),
    /ещё раз/
  );
  assert.match(errorText(413, {}, true), /1 ГБ/);
  assert.match(errorText(415, null, true), /MP4/);
  assert.match(errorText(422, {detail: 'FFmpeg не смог'}, true), /FFmpeg не смог/);
  assert.equal(
    errorText(409, {detail: {code: 'QC_STALE', message: 'Файл изменён после технической проверки'}}),
    'Файл изменён после технической проверки'
  );
  assert.match(
    errorText(403, {
      detail: {
        code: 'MACHINE_TOKEN_FORBIDDEN',
        message: 'Машинный токен не может принимать решение о выпуске.',
      },
    }),
    /Машинный токен/
  );
  assert.match(errorText(404, {detail: 'Not Found'}), /Сохраните проект/);
  assert.equal(errorText(404, {detail: 'Проект не найден'}), 'Проект не найден');
  assert.match(errorText(401, {}), /Сессия/);
  assert.equal(errorText(500, null), 'Ошибка сервера (500).');
});

test('ответ сервера важнее подписи по статусу, но код загрузки не теряется', () => {
  const text = errorText(422, {detail: 'В итоговом MP4 отсутствует видеопоток'}, true);
  assert.match(text, /видеопоток/);
  assert.match(text, /повреждён/);
});

test('результат N34: сначала свежая проверка, при устаревании — серверный BLOCKED', () => {
  const measured = {verdict: 'PASS_TECHNICAL', reason: '', checks: []};
  assert.deepEqual(qcOutcome(gate(), measured), {
    verdict: 'PASS_TECHNICAL',
    reason: '',
    stale: false,
  });
  assert.deepEqual(qcOutcome(gate(), {verdict: 'BLOCKED', reason: 'в файле нет аудиодорожки', checks: []}), {
    verdict: 'BLOCKED',
    reason: 'в файле нет аудиодорожки',
    stale: false,
  });
  const stale = gate({qc_verdict: 'BLOCKED', qc_stale: true, qc_reason: 'Файл изменён после проверки'});
  assert.deepEqual(qcOutcome(stale, measured), {
    verdict: 'BLOCKED',
    reason: 'Файл изменён после проверки',
    stale: true,
  });
  assert.deepEqual(qcOutcome(undefined, undefined), {verdict: '', reason: '', stale: false});
});

test('подписи состояний и вердиктов, манифест N34, короткий хеш', () => {
  assert.match(stateText('OWNER_APPROVED'), /Утверждён/);
  assert.match(stateText('IMPORTED'), /не пройдена/);
  assert.match(stateText('REJECTED'), /Отклонён/);
  assert.equal(stateText(undefined), 'Состояние неизвестно');
  assert.equal(verdictText(''), 'Не проводилась');
  assert.equal(verdictText('PASS_TECHNICAL'), 'Пройдена');
  assert.equal(verdictText('FAIL'), 'Не соответствует ожиданиям');
  assert.equal(verdictText('BLOCKED'), 'Измерить нельзя');
  assert.deepEqual(qcManifest(true), {container: 'mp4', require_audio: true});
  assert.deepEqual(qcManifest(false), {container: 'mp4', require_audio: false});
  assert.equal(shortSha(SHA), 'aaaaaaaaaaaa…');
  assert.equal(shortSha(''), '—');
});

test('требование аудио задаёт модальности, которые сервер проверит при утверждении', () => {
  assert.deepEqual(requiredModalities(false), ['VIDEO']);
  assert.deepEqual(requiredModalities(true), ['VIDEO', 'AUDIO']);
  assert.match(audioRequirementText(true), /с требованием аудиодорожки/);
  assert.match(audioRequirementText(false), /без требования аудиодорожки/);
});

test('утверждение требует звук на сервере, когда владелец его запросил', () => {
  const withAudio = approveBody(gate(), {...ready, requireAudio: true});
  assert.deepEqual(withAudio.required_modalities, ['VIDEO', 'AUDIO']);
  const withoutAudio = approveBody(gate(), {...ready, requireAudio: false});
  assert.deepEqual(withoutAudio.required_modalities, ['VIDEO']);
});

test('расхождение требований видно: вердикт измерен с другим требованием', () => {
  assert.equal(requirementMismatch(undefined, true), false);
  assert.equal(requirementMismatch({requireAudio: true}, true), false);
  assert.equal(requirementMismatch({requireAudio: false}, false), false);
  assert.equal(requirementMismatch({requireAudio: false}, true), true);
  assert.equal(requirementMismatch({requireAudio: true}, false), true);
  assert.equal(requirementMismatch({}, true), false); // манифест неизвестен — расхождения не выдумываем
});

test('причина сервера из вложенного detail не теряется', () => {
  const text = errorText(409, {
    detail: {
      code: 'MEDIA_NOT_CONFIRMED',
      message: 'Мастер не покрывает требуемые модальности.',
      detail: 'AUDIO: в мастере нет аудиодорожки',
    },
  });
  assert.match(text, /не покрывает требуемые модальности/);
  assert.match(text, /AUDIO: в мастере нет аудиодорожки/);
  // пустая или нестроковая причина ничего не меняет
  assert.equal(errorText(409, {detail: {code: 'X', message: 'Текст'}}), 'Текст');
  assert.equal(errorText(409, {detail: {code: 'X', message: 'Текст', detail: 7}}), 'Текст');
  // без сообщения сервера сырой вывод FFmpeg в текст не попадает
  const raw = errorText(422, {detail: {error: 'FFmpeg', detail: 'moov atom not found'}}, true);
  assert.doesNotMatch(raw, /moov atom/);
  assert.match(raw, /повреждён/);
});
