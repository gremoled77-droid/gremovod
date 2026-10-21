const vscode = require('vscode');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {execFile} = require('node:child_process');
const {promisify} = require('node:util');
const delay = ms => new Promise(r => setTimeout(r, ms));
async function suite() {
  const root = process.env.MONITOR_TEST_ROOT;
  const dispatcher = path.join(root, '.test-host', 'dispatcher');
  await fs.mkdir(dispatcher, {recursive: true});
  await fs.rm(path.join(dispatcher, 'state.json'), {force: true});
  const config = vscode.workspace.getConfiguration('gremovodAgentMonitor');
  await config.update('dispatcherDirectory', dispatcher, vscode.ConfigurationTarget.Global);
  await config.update('pullRequests', [58], vscode.ConfigurationTarget.Global);
  const ext = vscode.extensions.getExtension('gremovod.gremovod-agent-monitor');
  assert.ok(ext, 'extension discovered');
  const api = await ext.activate();
  await vscode.commands.executeCommand('gremovodAgentMonitor.open');
  let snapshot = api.getSnapshot();
  assert.ok(snapshot, 'panel snapshot created');
  await fs.writeFile(path.join(root, '.test-host', 'debug-snapshot.json'), JSON.stringify(snapshot, null, 2));
  assert.equal(snapshot.githubStatus, 'Connected', 'live GitHub read via gh');
  assert.ok(
    snapshot.pulls.some(p => p.number === 58),
    'real PR 58'
  );
  assert.equal(snapshot.local.connected, false, 'missing MiniMax explicitly disconnected');
  assert.ok(
    api.getEvents().some(e => e.agent === 'Codex GitHub' && e.event_type === 'finding'),
    'real Codex finding received'
  );
  assert.ok(
    api.getEvents().some(e => e.event_type === 'finding' && e.severity === 'P1'),
    'real Markdown badge severity'
  );
  await vscode.commands.executeCommand('workbench.action.closeSidebar');
  await vscode.commands.executeCommand('workbench.action.closeAuxiliaryBar');
  await fs.mkdir(path.join(root, 'evidence'), {recursive: true});
  await fs.writeFile(path.join(root, '.test-host', 'snapshot.json'), JSON.stringify(api.getSnapshot()));
  const ui = await promisify(execFile)('node', [path.join(root, 'test', 'ui-suite.cjs')], {
    cwd: root,
    windowsHide: true,
    timeout: 90000,
    env: {...process.env, MONITOR_TEST_ROOT: root},
  });
  console.log(ui.stdout);
  // Local watcher must update without triggering a model or waiting for the GitHub interval.
  const state = {
    version: 2,
    tasks: {'GA-01': {rounds: 1}},
    runs: {['58:' + 'a'.repeat(40) + ':CHANGES_REQUESTED']: {status: 'LAUNCHED', at: '2026-10-21T10:30:00Z'}},
  };
  await fs.writeFile(path.join(dispatcher, 'state.json'), JSON.stringify(state));
  for (let i = 0; i < 60 && !api.getSnapshot()?.local.connected; i++) await delay(250);
  assert.equal(api.getSnapshot().local.connected, true, 'file watcher refresh');
  assert.match(api.getSnapshot().local.lastRun, /activity Unknown/);
  await fs.unlink(path.join(dispatcher, 'state.json'));
  await delay(1000);
  const idsBefore = new Set(api.getEvents().map(e => e.event_id));
  api.close();
  await vscode.commands.executeCommand('gremovodAgentMonitor.open');
  const idsAfter = new Set(api.getEvents().map(e => e.event_id));
  for (const id of idsBefore) assert.ok(idsAfter.has(id), 'history survives panel recreation');
  assert.equal(idsAfter.size, api.getEvents().length, 'no duplicate events after reopening');
  const report = {
    at: new Date().toISOString(),
    host: vscode.version,
    githubInitial: snapshot.githubStatus,
    githubAfterReopen: api.getSnapshot().githubStatus,
    pr: 58,
    warningsAfterReopen: api.getSnapshot().warnings,
    review: api.getSnapshot().pulls[0].review,
    events: idsAfter.size,
    fixtureEvents: 1,
    screenshotsContain: 'Live GitHub observations only; local watcher fixture added after screenshots',
    passed: [
      'extension activation',
      'open real VS Code Webview',
      'read-only live GitHub PR 58',
      'Codex GitHub findings',
      'missing MiniMax',
      'filtering',
      'Handoff detail',
      'HTML injection inert',
      'local file watcher',
      'history after close/reopen',
      'no duplicate IDs',
    ],
    screenshot: 'vscode-live-pr58.png',
  };
  await fs.writeFile(
    path.join(root, 'evidence', 'host-results.json'),
    JSON.stringify(report, null, 2) + '\n'
  );
  console.log('AGENT MONITOR HOST PASS', JSON.stringify(report));
  api.close();
}
exports.run = async () => {
  try {
    await suite();
  } catch (error) {
    await fs.writeFile(
      path.join(process.env.MONITOR_TEST_ROOT, '.test-host', 'failure.txt'),
      String(error.stack || error) + '\n' + String(error.stderr || '')
    );
    throw error;
  }
};
