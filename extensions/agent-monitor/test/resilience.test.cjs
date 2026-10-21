/**
 * Регрессии панели: локальное состояние не зависит от сети, а двойное открытие не создаёт
 * вторую панель. Тесты гоняют настоящий собранный entry point расширения против поддельного
 * API VS Code — так же, как это делает Extension Host, но без запуска Electron.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const events = require('../dist/events');
const sources = require('../dist/sources');

const tick = () => new Promise(r => setImmediate(r));
const empty = () => ({events: [], details: {}, warnings: []});

async function fakeEnvironment(t, name, remote, local) {
  const panels = [],
    watchers = [],
    timers = [];
  let command;
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'agent-monitor-resilience-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  const uri = p => ({fsPath: p, toString: () => p});
  const vscode = {
    Uri: {
      file: uri,
      joinPath: (base, ...parts) => uri(path.join(base.fsPath, ...parts)),
      parse: uri,
    },
    ViewColumn: {One: 1, Beside: 2},
    commands: {
      registerCommand: (_name, cb) => {
        command = cb;
        return {dispose() {}};
      },
    },
    window: {
      showWarningMessage() {},
      showInformationMessage() {},
      createWebviewPanel() {
        const panel = {
          closed: false,
          disposeHandlers: [],
          messages: [],
          reveal() {},
          webview: {
            asWebviewUri: x => x,
            postMessage: m => {
              panel.messages.push(m);
              return Promise.resolve(true);
            },
            onDidReceiveMessage: cb => {
              panel.receive = cb;
              return {dispose() {}};
            },
          },
          onDidDispose: cb => panel.disposeHandlers.push(cb),
          dispose() {
            if (!this.closed) {
              this.closed = true;
              for (const cb of this.disposeHandlers) cb();
            }
          },
        };
        panels.push(panel);
        return panel;
      },
    },
    workspace: {
      isTrusted: true,
      workspaceFolders: [{uri: uri(root)}],
      getConfiguration: () => ({
        get: (key, fallback) => (key === 'dispatcherDirectory' ? path.join(root, 'dispatcher') : fallback),
      }),
      createFileSystemWatcher: () => {
        const watcher = {
          dispose() {},
          onDidChange: cb => (watcher.change = cb),
          onDidCreate() {},
          onDidDelete() {},
        };
        watchers.push(watcher);
        return watcher;
      },
    },
    RelativePattern: class {},
    env: {clipboard: {writeText: async () => {}}, openExternal: async () => {}},
  };
  const state = {};
  const context = {
    subscriptions: [],
    extensionUri: uri(path.join(__dirname, '..')),
    globalStorageUri: uri(path.join(root, 'global')),
    workspaceState: {
      get: k => state[k],
      update: async (k, v) => {
        state[k] = v;
      },
    },
  };
  const sourceMocks = {
    ...sources,
    github: remote,
    localSources: local,
    gitSource: async () => ({...empty(), branch: 'fixture', changed: [], worktree: 'fixture'}),
    cliPresence: async () => ({}),
  };
  const module = {exports: {}};
  const requireMock = id =>
    id === 'vscode' ? vscode : id === './sources' ? sourceMocks : id === './events' ? events : require(id);
  const compiled = await fs.readFile(path.join(__dirname, '..', 'dist', 'extension.js'), 'utf8');
  vm.runInNewContext(
    '(function(require,module,exports){' + compiled + '\n})',
    {
      setTimeout,
      clearTimeout,
      setInterval: fn => {
        timers.push(fn);
        return fn;
      },
      clearInterval() {},
      process,
      URL,
      console,
      Date,
    }
  )(requireMock, module, module.exports);
  const api = module.exports.activate(context);
  return {
    api,
    panels,
    watchers,
    open: () => command(),
    close: () => context.subscriptions.forEach(d => d.dispose()),
  };
}

test('local state is published while the GitHub poll is still pending', async t => {
  let release,
    calls = 0;
  const gate = new Promise(r => (release = r));
  let connected = false;
  const env = await fakeEnvironment(
    t,
    'slow-github',
    async () => {
      calls++;
      await gate;
      return {...empty(), pulls: []};
    },
    async () => ({...empty(), rounds: {}, lastRun: 'Unknown', connected})
  );
  const opening = env.open();
  for (let i = 0; i < 200 && !calls; i++) await tick();
  assert.equal(calls, 1, 'the GitHub poll started');
  connected = true;
  await env.panels[0].receive({type: 'refresh'});
  for (let i = 0; i < 200 && !env.api.getSnapshot()?.local.connected; i++) await tick();
  assert.equal(
    env.api.getSnapshot().local.connected,
    true,
    'a local change must be published without waiting for GitHub'
  );
  release();
  await opening;
  env.close();
});

test('a second open joins the running one instead of creating a rival panel', async t => {
  const env = await fakeEnvironment(t, 'double-open', async () => ({...empty(), pulls: []}));
  await Promise.all([env.open(), env.open()]);
  for (let i = 0; i < 200 && !env.api.getSnapshot(); i++) await tick();
  assert.equal(env.panels.length, 1, 'a double open must not create a second panel');
  assert.ok(env.api.getSnapshot(), 'the panel publishes');
  // The surviving panel must still react to a refresh.
  const before = env.panels[0].messages.length;
  await env.panels[0].receive({type: 'refresh'});
  for (let i = 0; i < 200 && env.panels[0].messages.length === before; i++) await tick();
  assert.ok(env.panels[0].messages.length > before, 'the panel keeps publishing after a double open');
  env.close();
});

test('closing the panel releases its resources and a new open gets a working panel', async t => {
  const env = await fakeEnvironment(t, 'reopen', async () => ({...empty(), pulls: []}));
  await env.open();
  for (let i = 0; i < 200 && !env.api.getSnapshot(); i++) await tick();
  assert.ok(env.api.getSnapshot(), 'the first panel publishes');
  env.panels[0].dispose();
  await env.open();
  for (let i = 0; i < 200 && !env.api.getSnapshot(); i++) await tick();
  assert.equal(env.panels.length, 2, 'reopening creates a new panel');
  assert.ok(env.api.getSnapshot(), 'the reopened panel publishes');
  env.close();
});
