const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const {event, Journal, filterEvents, redact, safeUrl, validateEvent, CODEX} = require('../dist/events');
const {github, reviewState, localSources, allowedReport, gitSource} = require('../dist/sources');
const {fixture, mockGitHub, SHA, NEW_SHA} = require('./fixtures.cjs');
const make = (id = 'a', patch = {}) =>
  event(
    {
      timestamp: '2026-10-21T08:00:00Z',
      source: 'github',
      agent: 'Codex GitHub',
      task_id: 'GA-01',
      pr_number: 58,
      commit_sha: SHA,
      event_type: 'finding',
      severity: 'P1',
      status: 'Observed',
      summary: 'Finding',
      payload_ref: null,
      ...patch,
    },
    id
  );
test('chronology compares instants across Git timezone offsets and retains the newest events', async (t) => {
  const root = await temp(t);
  const file = path.join(root, 'events.jsonl');
  const j = new Journal(file, 2);
  await j.add([
    make('newest', {timestamp: '2026-10-21T10:00:00Z'}),
    make('old', {timestamp: '2026-10-21T12:00:00+03:00'}),
    make('middle', {timestamp: '2026-10-21T09:30:00Z'}),
  ]);
  assert.deepEqual(j.events.map((e) => e.event_id), [make('middle').event_id, make('newest').event_id]);
  const reopened = new Journal(file, 2);
  await reopened.load();
  assert.deepEqual(reopened.events.map((e) => e.event_id), j.events.map((e) => e.event_id));
});
async function temp(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-monitor-test-'));
  t.after(() => fs.rm(dir, {recursive: true, force: true}));
  return dir;
}

test('AgentEvent schema, stable IDs, distinct sources and strict validation', () => {
  assert.equal(make().event_id, make().event_id);
  assert.ok(validateEvent(make()));
  assert.notEqual(make().event_id, make('a', {source: 'codex-cli-report'}).event_id);
  assert.ok(!validateEvent({...make(), pr_number: -1}));
  assert.ok(!validateEvent({...make(), timestamp: 'never'}));
  assert.ok(!validateEvent({...make(), commit_sha: 'HEAD'}));
  assert.ok(!validateEvent({...make(), source: 'chat-history'}));
});
test('filters combine agent/task/PR/status/search and inclusive period', () => {
  const list = [
    make(),
    make('b', {agent: 'MiniMax', status: 'FAILED'}),
    make('c', {pr_number: 59, task_id: null}),
  ];
  assert.equal(
    filterEvents(list, {
      agent: 'Codex GitHub',
      task: 'GA-01',
      pr: '58',
      status: 'Observed',
      search: 'find',
      from: '2026-10-21T08:00:00Z',
      to: '2026-10-21T08:00:00Z',
    }).length,
    1
  );
  assert.equal(filterEvents(list, {from: '2027-01-01'}).length, 0);
});
test('append journal deduplicates across refresh and restart; interrupted/corrupt lines recover', async t => {
  const root = await temp(t),
    file = path.join(root, 'events.jsonl');
  const j = new Journal(file);
  await j.load();
  await j.add([make(), make()]);
  await j.add([make()]);
  assert.equal(j.events.length, 1);
  await fs.appendFile(file, 'bad json\n{"incomplete":');
  const k = new Journal(file);
  await k.load();
  assert.equal(k.events.length, 1);
  assert.ok(k.warnings.length);
  await k.add([make('b')]);
  const reopened = new Journal(file);
  await reopened.load();
  assert.equal(reopened.events.length, 2);
});
test('large journal bounds view, rejects oversized lines, retains full dedupe index and never truncates', async t => {
  const root = await temp(t),
    file = path.join(root, 'events.jsonl');
  const lines = Array.from({length: 12000}, (_, i) => JSON.stringify(make(String(i))));
  await fs.writeFile(file, 'x'.repeat(200000) + '\n' + lines.join('\n') + '\n');
  const size = (await fs.stat(file)).size;
  const j = new Journal(file, 100);
  await j.load();
  assert.equal(j.events.length, 100);
  assert.equal(j.ids.size, 12000);
  await j.add([make('0')]);
  assert.equal((await fs.stat(file)).size, size);
  assert.ok(j.warnings.some(w => w.includes('oversized')));
});
test('journal does not store report bodies or credential-shaped summaries', async t => {
  const root = await temp(t),
    file = path.join(root, 'events.jsonl');
  const j = new Journal(file);
  await j.add([make('secret', {summary: 'token=supersecret ghp_testtesttest sk-testtesttest'})]);
  const content = await fs.readFile(file, 'utf8');
  assert.ok(!content.includes('supersecret'));
  assert.ok(!content.includes('ghp_test'));
  assert.ok(!content.includes('sk-test'));
});
test('redaction handles assignments, auth headers, URL userinfo, signed query and private keys', () => {
  const value = redact(
    'password="hidden value" API_KEY: abc Bearer abc.def https://user:pass@example.com/file?sig=hidden\n-----BEGIN RSA PRIVATE KEY-----\nabcdef\n-----END RSA PRIVATE KEY-----'
  );
  for (const secret of ['hidden value', 'abc.def', 'user:pass', 'sig=hidden', 'abcdef'])
    assert.ok(!value.includes(secret));
});
test('link allowlist blocks command/javascript/file/external host/lookalike/query credentials', () => {
  assert.ok(safeUrl('https://github.com/gremoled77-droid/gremovod/pull/58#discussion_r1'));
  for (const url of [
    'command:workbench.action.terminal.new',
    'javascript:alert(1)',
    'file:///C:/secret',
    'https://evil.com/',
    'https://github.com/gremoled77-droid/gremovod-evil/pull/58',
    'https://user:pass@github.com/gremoled77-droid/gremovod/pull/58',
    'https://github.com/gremoled77-droid/gremovod/pull/58?token=secret',
  ])
    assert.equal(safeUrl(url), undefined);
});
test('Codex marker exact SHA, trusted bot, missing/malformed/running and stale SHA', () => {
  const f = fixture();
  assert.equal(reviewState(SHA, f.comments, f.inline).status, 'Changes requested');
  assert.equal(reviewState(NEW_SHA, f.comments, f.inline).status, 'Stale SHA');
  assert.equal(reviewState(SHA, [{...f.comments[0], user: {login: 'impostor'}}], []).status, 'Unknown');
  assert.equal(
    reviewState(SHA, [{...f.comments[0], body: '<!-- codex-review-state:v1 {bad} -->'}], []).status,
    'Invalid review marker'
  );
  const clear = JSON.parse(JSON.stringify(f.comments));
  clear[0].body = clear[0].body.replace('true', 'false').replace('true', 'false');
  assert.equal(reviewState(SHA, clear, []).status, 'Review clear');
  clear[0].body = clear[0].body.replace('completed', 'running');
  assert.equal(reviewState(SHA, clear, []).status, 'Reviewing');
});
test('current-head findings exclude stale comments and distinguish GitHub from local CLI', async () => {
  const f = fixture();
  f.inline.push({...f.inline[0], id: 999, commit_id: NEW_SHA});
  const calls = [];
  const batch = await github([58, 58], mockGitHub(f, calls));
  assert.equal(batch.pulls.length, 1);
  assert.equal(batch.pulls[0].review.p1, 1);
  assert.ok(batch.events.some(e => e.agent === 'Codex GitHub'));
  assert.ok(!batch.events.some(e => e.agent === 'Codex CLI'));
  assert.equal(batch.events.find(e => e.event_type === 'finding').severity, 'P1');
  assert.ok(batch.events.some(e => e.status === 'Stale SHA'));
  assert.ok(calls.some(args => args.includes('--paginate') && args.includes('--slurp')));
  assert.ok(calls.every(args => args[0] === 'api'));
  assert.ok(batch.events.some(e => e.event_type === 'github_actions'));
});
test('PR head moves during polling: never label review clear for the new head', async () => {
  const f = fixture();
  const base = mockGitHub(f, []);
  let heads = 0;
  const r = await github([58], async (cmd, args) => {
    const text = await base(cmd, args);
    if (args.at(-1).endsWith('/pulls/58') && ++heads === 2)
      return JSON.stringify({...f.pr, head: {...f.pr.head, sha: NEW_SHA}});
    return text;
  });
  assert.equal(r.pulls[0].review.status, 'Stale SHA');
  assert.ok(r.warnings.length);
});
test('offline/rate-limit rejection preserves a previously collected durable journal', async t => {
  const root = await temp(t),
    j = new Journal(path.join(root, 'events.jsonl'));
  await j.add([make()]);
  await assert.rejects(
    github([58], async () => {
      throw Error('network offline / rate limit');
    })
  );
  const reopened = new Journal(j.path);
  await reopened.load();
  assert.equal(reopened.events.length, 1);
});
test('one unavailable PR does not discard the PRs that were read', async () => {
  const f = fixture(),
    calls = [];
  const success = mockGitHub(f, calls);
  const batch = await github([58, 999], async (cmd, args) => {
    if (args.at(-1).endsWith('/pulls/999')) throw Error('404 Not Found');
    return success(cmd, args);
  });
  assert.equal(batch.pulls.length, 1, 'the readable PR must survive');
  assert.equal(batch.pulls[0].number, 58);
  assert.ok(batch.events.some(e => e.agent === 'Codex GitHub'));
  assert.ok(batch.events.some(e => e.event_type === 'finding'));
  assert.ok(batch.warnings.some(w => w.includes('#999')), 'the unavailable PR is reported');
});
test('unavailable optional Actions does not discard PR, review or findings', async () => {
  const f = fixture(),
    calls = [];
  const success = mockGitHub(f, calls);
  const batch = await github([58], async (cmd, args) => {
    if (args.at(-1).includes('/actions/runs?')) throw Error('403 Actions scope unavailable');
    return success(cmd, args);
  });
  assert.equal(batch.pulls.length, 1);
  assert.equal(batch.pulls[0].review.p1, 1);
  assert.ok(batch.events.some(e => e.event_type === 'finding'));
  assert.ok(!batch.events.some(e => e.event_type === 'github_actions'));
  assert.ok(batch.warnings.some(w => w.includes('Actions')), 'the missing optional source is reported');
});
test('a PR that cannot be read at all still rejects the batch', async () => {
  await assert.rejects(
    github([58], async () => {
      throw Error('network offline');
    })
  );
});
test('two writers of one journal never append the same upstream event twice', async t => {
  const root = await temp(t),
    file = path.join(root, 'events.jsonl');
  const a = new Journal(file),
    b = new Journal(file);
  await Promise.all([a.load(), b.load()]);
  await Promise.all([a.add([make()]), b.add([make()])]);
  const rows = (await fs.readFile(file, 'utf8')).split('\n').filter(Boolean);
  assert.equal(rows.length, 1, 'the shared event must be written once');
  assert.equal(new Set(rows.map(r => JSON.parse(r).event_id)).size, 1);
  const reopened = new Journal(file);
  await reopened.load();
  assert.equal(reopened.events.length, 1);
});
test('the first append creates the journal directory', async t => {
  const root = await temp(t),
    file = path.join(root, 'nested', 'deeper', 'events.jsonl');
  const j = new Journal(file);
  await j.load();
  await j.add([make()]);
  const reopened = new Journal(file);
  await reopened.load();
  assert.equal(reopened.events.length, 1);
});
test('next task requires observed merge and real Codex marker, no owner permission fabricated', async () => {
  const f = fixture();
  f.comments.push({
    id: 99,
    user: {login: CODEX},
    body: 'GREMOVOD_NEXT_TASK: GA-02',
    updated_at: '2026-10-21T10:00:00Z',
  });
  let r = await github([58], mockGitHub(f, []));
  assert.match(r.pulls[0].next, /Waiting/);
  f.pr.merged = true;
  r = await github([58], mockGitHub(f, []));
  assert.match(r.pulls[0].next, /acceptance Unknown/);
});
test('missing/corrupt MiniMax state is Not connected; LAUNCHED never means live Running', async t => {
  const root = await temp(t);
  let r = await localSources(root);
  assert.equal(r.connected, false);
  assert.equal(r.lastRun, 'Unknown');
  await fs.writeFile(path.join(root, 'state.json'), '{bad');
  r = await localSources(root);
  assert.equal(r.connected, false);
  await fs.writeFile(
    path.join(root, 'state.json'),
    JSON.stringify({
      version: 2,
      tasks: {'GA-01': {rounds: 1}},
      runs: {[`58:${SHA}:CHANGES_REQUESTED`]: {status: 'LAUNCHED', at: '2026-10-21T08:00:00Z'}},
    })
  );
  r = await localSources(root);
  assert.equal(r.rounds['GA-01'], 1);
  assert.match(r.lastRun, /activity Unknown/);
  assert.ok(!r.events.some(e => e.status === 'Running'));
});
test('dispatcher v1 flat state, reports, report symlink/traversal and secret filename boundaries', async t => {
  const root = await temp(t),
    outside = await temp(t);
  await fs.writeFile(
    path.join(root, 'state.json'),
    JSON.stringify({[`58:${SHA}:CHANGES_REQUESTED`]: {status: 'FAILED', at: '2026-10-21T08:00:00Z'}})
  );
  const report = path.join(root, 'PR-58-codex-review.md');
  await fs.writeFile(report, `GA-01\nHEAD SHA: ${SHA}\ntoken=supersecret\n<script>alert(1)</script>`);
  await fs.writeFile(path.join(root, '.env'), 'API_KEY=never-read');
  let r = await localSources(root);
  assert.ok(r.events.some(e => e.source === 'codex-cli-report'));
  assert.ok(r.events.some(e => e.status === 'FAILED'));
  assert.ok(!JSON.stringify(r).includes('supersecret'));
  assert.ok(!JSON.stringify(r).includes('never-read'));
  assert.equal(await allowedReport(root, path.join(root, '.env')), undefined);
  await fs.writeFile(path.join(outside, 'PR-58-feedback.md'), 'private');
  assert.equal(await allowedReport(root, path.join(outside, 'PR-58-feedback.md')), undefined);
});
test('git adapter reads branch/head/status only; handles rename, no content or model commands', async () => {
  const calls = [];
  const r = await gitSource('C:/fixture', async (cmd, args) => {
    calls.push([cmd, args]);
    const a = args.slice(4);
    if (a[0] === 'branch') return 'minimax/ga-01-llm-settlement\n';
    if (a[0] === 'rev-parse') return SHA;
    if (a[0] === 'log') return JSON.stringify({sha: SHA, at: '2026-10-21T08:00:00Z'});
    return ' M backend/main.py\0R  docs/new.md\0docs/old.md\0?? .env\0?? API_KEY.txt\0';
  });
  assert.deepEqual(r.changed, ['backend/main.py', 'docs/new.md']);
  assert.ok(calls.every(([c]) => c === 'git'));
  assert.equal(r.events.length, 1);
});
