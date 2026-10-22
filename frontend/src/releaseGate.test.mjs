import test from 'node:test';
import assert from 'node:assert/strict';
import {
  approveBlockReason,
  approveBody,
  errorText,
  qcManifest,
  rejectBlockReason,
  rejectBody,
  releaseCounts,
  stateText,
  verdictText,
} from './releaseGate.ts';

const SHA = 'a'.repeat(64);
const gate = (over = {}) => ({
  artifact_id: 'a1',
  state: 'TECHNICAL_PASS',
  master_sha256: SHA,
  qc_verdict: 'PASS_TECHNICAL',
  qc_stale: false,
  qc_reason: '',
  version_id: null,
  project_revision: 3,
  decision: '',
  decided_at: null,
  owner_id: null,
  decision_stale: false,
  decision_stale_reason: '',
  approve_blockers: [],
  can_approve: true,
  can_reject: true,
  blocked_reason: null,
  n35_evidence: {coverage: {}, coverage_status: 'CONFIRMED', reason: '', processing_rights_confirmed: false},
  history: [],
  ...over,
});
const ready = {ownerId: 'owner', rights: true, busy: false};

test('финальными считаются только утверждённые владельцем, импорты — отдельно', () => {
  const gates = {
    a: gate({state: 'OWNER_APPROVED'}),
    b: gate({state: 'IMPORTED'}),
    c: gate({state: 'REJECTED'}),
    d: gate({state: 'TECHNICAL_PASS'}),
  };
  assert.deepEqual(releaseCounts(['a', 'b', 'c', 'd', 'e'], gates), {final: 1, pending: 3, unknown: 1});
  assert.deepEqual(releaseCounts(['x', 'y'], {}), {final: 0, pending: 0, unknown: 2});
});

test('загруженные MP4 без решения не называются финальными', () => {
  const gates = {a: gate({state: 'IMPORTED'}), b: gate({state: 'TECHNICAL_PASS'})};
  assert.equal(releaseCounts(['a', 'b'], gates).final, 0);
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
  assert.match(rejectBlockReason(gate({can_reject: false}), input), /уже отклонена/);
  assert.match(rejectBlockReason(gate(), {...input, busy: true}), /подождите/);
  // отклонение не зависит от технической проверки
  assert.equal(
    rejectBlockReason(
      gate({approve_blockers: [{code: 'QC_NOT_RUN', message: 'x'}], can_approve: false}),
      input
    ),
    ''
  );
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

test('подписи состояний и вердиктов, манифест N34', () => {
  assert.match(stateText('OWNER_APPROVED'), /Утверждён/);
  assert.match(stateText('IMPORTED'), /не пройдена/);
  assert.equal(stateText(undefined), 'Состояние неизвестно');
  assert.equal(verdictText(''), 'Не проводилась');
  assert.equal(verdictText('PASS_TECHNICAL'), 'Пройдена');
  assert.deepEqual(qcManifest(true), {container: 'mp4', require_audio: true});
  assert.deepEqual(qcManifest(false), {container: 'mp4', require_audio: false});
});
