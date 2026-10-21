'use strict';
const core = require('./core.cjs');
const f = require('./fixtures.cjs');

function runTests(core, f) {
  const results = [];
  function equal(actual, expected) {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`Expected ${JSON.stringify(expected)}; got ${JSON.stringify(actual)}`);
  }
  function check(name, fn) {
    try { fn(); results.push({ name, status: 'PASS' }); }
    catch (error) { results.push({ name, status: 'FAIL', error: error.message }); }
  }
  function rejected(input) {
    let threw = false;
    try { core.verify(input); } catch { threw = true; }
    equal(threw, true);
  }
  const now = '2026-10-21T10:00:00.000Z';
  const ms = Date.parse(now);
  const normalize = (input, snapshot = f.pr) => core.normalize(input, snapshot, now);
  const row = (event, id = 1, status = 'PENDING') => ({ ...core.journal(event), id, status });
  const review = (commit = f.head, body = '') => f.fixture('pull_request_review', 'submitted', { review: { id: 12, user: f.bot, commit_id: commit, body, state: 'commented' } });
  check('new PR produces one notification plan', () => equal(core.plan([row(normalize(f.fixture()))], ms).length, 1));
  check('delivery duplicate suppressed within batch', () => equal(core.plan([row(normalize(f.fixture())), row(normalize(f.fixture()), 2)], ms)[0].count, 1));
  check('semantic duplicate with different delivery suppressed', () => {
    const event = normalize(f.fixture());
    const second = { ...event, github_delivery_id: 'fixture-delivery-2' };
    equal(core.plan([row(event), row(second, 2)], ms)[0].count, 1);
  });
  check('sent semantic status suppresses redelivery across executions', () => equal(core.plan([row(normalize(f.fixture()), 1, 'SENT'), row(normalize(f.fixture()), 2)], ms), []));
  check('new PR commit updates SHA', () => equal(normalize(f.fixture('pull_request', 'synchronize')).head_sha, f.head));
  check('late PR event retains event SHA', () => equal(normalize(f.fixture('pull_request', 'synchronize', {pull_request: {...f.pr, head: {sha: f.old}}})).head_sha, f.old));
  check('update does not claim MiniMax fixed findings', () => equal(normalize(f.fixture('pull_request', 'synchronize')).kind, 'PR_UPDATED'));
  check('old Codex review is stale', () => equal(normalize(review(f.old)).review_status, 'STALE'));
  check('current completed review has one plan', () => equal(core.plan([row(normalize(review()))], ms)[0].count, 1));
  check('same SHA review status with new review id deduplicates', () => {
    const first = normalize(review());
    const input = review(); input.body.review.id = 100; input.headers['x-github-delivery'] = 'another-review';
    equal(core.plan([row(first, 1, 'SENT'), row(normalize(input), 2)], ms), []);
  });
  check('P1 finding is urgent', () => equal(normalize(review(f.head, '[P1] fix this')).route, 'immediate'));
  check('P2 finding retained', () => equal(normalize(review(f.head, '[P2] issue')).severity, 'P2'));
  check('CI failed urgent', () => equal(normalize(f.fixture('check_run', 'completed', { check_run: { id: 99, head_sha: f.head, status: 'completed', conclusion: 'failure' } })).severity, 'P1'));
  check('CI success recorded', () => equal(normalize(f.fixture('status', '', { sha: f.head, state: 'success', context: 'tests' })).kind, 'CI_PASSED'));
  check('merged requires merged true', () => equal(normalize(f.fixture('pull_request', 'closed', { pull_request: { ...f.pr, merged: true } })).kind, 'PR_MERGED'));
  check('closed without merge stays closed', () => equal(normalize(f.fixture('pull_request', 'closed')).kind, 'PR_CLOSED'));
  check('wrong repository rejected', () => rejected(f.fixture('push', '', { repository: { full_name: 'evil/repo' } })));
  check('missing delivery rejected', () => rejected({ ...f.fixture(), headers: { 'x-github-event': 'push' } }));
  check('spoofed bot rejected', () => equal(normalize(f.fixture('pull_request_review', 'submitted', { review: { user: { login: 'attacker', type: 'Bot' }, commit_id: f.head, body: 'P0' } })), null));
  check('edited Codex comment without commit remains unknown', () => equal(normalize(f.fixture('issue_comment', 'edited', { pull_request: undefined, issue: { number: 58, pull_request: {} }, comment: { id: 1, user: f.bot, body: `Review completed ${f.head}` } })).review_status, 'UNKNOWN'));
  check('edited inline finding supported', () => equal(normalize(f.fixture('pull_request_review_comment', 'edited', { comment: { id: 5, user: f.bot, commit_id: f.head, body: 'P1' } })).severity, 'P1'));
  check('GitHub outage cannot mark review complete', () => equal(normalize(review(), { error: 'unavailable' }).review_status, 'UNKNOWN'));
  check('ready does not mean accepted', () => equal(normalize(f.fixture('pull_request', 'ready_for_review')), null));
  check('requesting review does not prove started', () => equal(normalize(f.fixture('pull_request', 'review_requested')), null));
  check('native Codex check start requires current SHA', () => equal(normalize(f.fixture('check_run', 'created', { check_run: { id: 2, head_sha: f.head, status: 'in_progress', app: { slug: 'chatgpt-codex-connector' } } })).review_status, 'STARTED'));
  check('unrelated check not Codex', () => equal(normalize(f.fixture('check_run', 'created', { check_run: { id: 2, head_sha: f.head, status: 'in_progress', app: { slug: 'github-actions' } } })), null));
  check('GA transition never inferred from prose', () => equal(normalize(f.fixture('issue_comment', 'created', { comment: { id: 5, user: f.bot, body: 'GREMOVOD_NEXT_TASK GA-02' } })).kind, 'CODEX_COMMENT_UNCORRELATED'));
  check('body and titles cannot leak to notification', () => {
    const e = normalize(f.fixture('pull_request', 'opened', { pull_request: { ...f.pr, title: '<b>private password</b>' } }));
    equal(core.plan([row(e)], ms)[0].text.includes('password'), false);
  });
  check('HTML escaping', () => equal(core.escapeHtml('<a>&'), '&lt;a&gt;&amp;'));
  check('info waits for digest interval', () => equal(core.plan([row(normalize(f.fixture('push', '', { after: f.head })))], ms), []));
  check('info grouped after five minutes', () => {
    const e = normalize(f.fixture('push', '', { after: f.head }));
    const other = { ...e, semantic_key: 'another', github_delivery_id: 'another' };
    equal(core.plan([row(e), row(other, 2)], ms + 300001)[0].count, 2);
  });
  check('urgent precedes pending info', () => {
    const e = normalize(f.fixture('push', '', { after: f.head }));
    const urgentInput = review(f.head, 'P0');
    urgentInput.headers['x-github-delivery'] = 'urgent-delivery';
    const urgent = normalize(urgentInput);
    equal(core.plan([row(e), row(urgent, 2)], ms + 300001)[0].row_ids, [2]);
  });
  check('timeout outcome blocks auto retry', () => equal(core.telegramOutcome({ error: 'timeout' }).status, 'UNKNOWN'));
  check('unknown sends never automatically replayed', () => equal(core.plan([row(normalize(f.fixture()), 1, 'UNKNOWN'), row(normalize(f.fixture()), 2)], ms), []));
  check('sending crash remains blocked', () => equal(core.plan([row(normalize(f.fixture()), 1, 'SENDING'), row(normalize(f.fixture()), 2)], ms), []));
  check('Telegram confirmed success persists message id', () => equal(core.telegramOutcome({ message_id: 123 }).message_id, '123'));
  check('Telegram confirmed 429 requires controlled reconciliation', () => equal(core.telegramOutcome({ error_code: 429 }).status, 'FAILED'));
  check('raw error never enters journal error code', () => equal(core.telegramOutcome({ error: 'token=secret' }).error_code.includes('secret'), false));
  return results;
}

if (require.main === module) {
  const results = runTests(core, f);
  const report = { results, pass: results.filter(r => r.status === 'PASS').length, fail: results.filter(r => r.status === 'FAIL').length };
  require('node:fs').writeFileSync(require('node:path').join(__dirname, 'local-test-results.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  if (results.some(r => r.status === 'FAIL')) process.exitCode = 1;
}
module.exports = { runTests };
