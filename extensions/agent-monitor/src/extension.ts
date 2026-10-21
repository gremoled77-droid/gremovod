import * as vscode from 'vscode';
import {createHash, randomBytes} from 'node:crypto';
import {join} from 'node:path';
import {homedir, tmpdir} from 'node:os';
import {Detail, Filter, Journal, filterEvents, redact, safeUrl} from './events';
import {PullState, allowedReport, cliPresence, gitSource, github, localSources} from './sources';

export function html(webview: vscode.Webview, uri: vscode.Uri) {
  const nonce = randomBytes(24).toString('hex');
  const resource = (name: string) => webview.asWebviewUri(vscode.Uri.joinPath(uri, 'media', name));
  return `<!doctype html><html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; script-src 'nonce-${nonce}'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none';">
  <link rel="stylesheet" href="${resource('monitor.css')}"><title>GremoVOD Agent Monitor</title></head><body>
  <header><div><p class="eyebrow">GREMOVOD / OBSERVABILITY</p><h1>Agent Monitor <span>v1 · read-only</span></h1></div><button id="refresh">↻ Refresh</button></header>
  <p id="freshness" role="status" aria-live="polite">Подключение источников…</p><div id="warnings" role="status"></div>
  <section id="overview" class="overview" aria-label="Состояние конвейера"></section>
  <section class="agents"><article><p class="eyebrow">DEVELOPER</p><h2>MiniMax</h2><dl id="minimax"></dl></article><article><p class="eyebrow">REVIEWER</p><h2>Codex</h2><dl id="codex"></dl></article></section>
  <section class="history"><div class="section-title"><h2>Временная шкала</h2><span id="count"></span></div>
  <form id="filters"><label>Агент<select id="agent"><option value="">Все</option></select></label><label>Задача<select id="task"><option value="">Все</option></select></label><label>PR<select id="pr"><option value="">Все</option></select></label><label>Статус<select id="status"><option value="">Все</option></select></label><label>От<input id="from" type="datetime-local"></label><label>До<input id="to" type="datetime-local"></label><label class="search">Поиск<input id="search" type="search" placeholder="Текст, тип события или SHA"></label><button type="reset">Сбросить</button></form>
  <div class="table-wrap"><table><thead><tr><th>Время / источник</th><th>Агент / задача</th><th>Событие</th><th>PR / SHA</th></tr></thead><tbody id="timeline"></tbody></table></div><button id="more">Показать ещё</button></section>
  <section class="handoff"><div class="section-title"><h2>Handoff Log</h2><div><button id="copy" disabled>Копировать текст</button> <button id="open" disabled>Открыть источник</button></div></div><p id="detail-meta">Выберите событие в шкале.</p><pre id="detail">Задание, ответ, замечания и причина остановки отображаются только при наличии источника.</pre></section>
  <footer>Наблюдения из источников ≠ подтверждение работы процесса. Модели и команды исполнения здесь не запускаются.</footer>
  <script nonce="${nonce}" src="${resource('monitor.js')}"></script></body></html>`;
}

export function activate(context: vscode.ExtensionContext) {
  let panel: vscode.WebviewPanel | undefined;
  let opening: Promise<vscode.WebviewPanel> | undefined;
  let latest: any;
  let details: Record<string, Detail> = {};
  let disposed = false;
  let journal: Journal;
  let localBusy = false,
    localPending = false,
    remoteBusy = false,
    remotePending = false;
  let nextGitHub = 0,
    failures = 0;
  let generation = 0,
    lastAttempt = 0;
  let pulls: PullState[] = [];
  let githubStatus = 'Not connected';
  let lastGitHub: string | null = null;
  let localWarnings: string[] = [];
  let remoteWarnings: string[] = [];
  let localView = {rounds: {} as Record<string, number>, lastRun: 'Unknown', connected: false};
  let gitView = {branch: 'Unknown', changed: [] as string[]};
  let cliCache: Record<string, string> = {};
  let filter: Filter = {};
  let visible = 200;
  const send = () => {
    if (!panel || !latest || !journal) return;
    const all = journal.events;
    const matches = filterEvents(all, filter);
    panel.webview.postMessage({
      ...latest,
      type: 'snapshot',
      events: matches.slice(-visible).reverse(),
      count: matches.length,
      shown: Math.min(matches.length, visible),
      observed: journal.ids.size,
      retained: all.length,
      choices: {
        agent: [...new Set(all.map(e => e.agent))],
        task: [...new Set(all.map(e => e.task_id).filter(Boolean))],
        pr: [...new Set(all.map(e => e.pr_number).filter(Boolean))],
        status: [...new Set(all.map(e => e.status))],
      },
    });
  };
  let root = '',
    dispatcher = '';
  /** Build the snapshot from the state collected so far and hand it to the panel. */
  const publish = () => {
    if (!panel || !journal) return;
    const ids = new Set(journal.events.map(e => e.event_id));
    for (const id of Object.keys(details)) if (!ids.has(id)) delete details[id];
    latest = {
      updated: new Date().toISOString(),
      githubStatus,
      lastGitHub,
      nextGitHub: new Date(nextGitHub).toISOString(),
      pulls,
      warnings: [...localWarnings, ...remoteWarnings],
      local: localView,
      git: {branch: redact(gitView.branch), worktree: root, changed: gitView.changed},
      cli: cliCache,
      journal: journal.path,
      lastEvent: journal.events.at(-1)?.timestamp ?? null,
    };
    send();
  };
  /**
   * Local sources only: the dispatcher state, the worktree and the journal. This path never waits
   * for GitHub, so a local change is published even while the network poll is still running.
   */
  async function refreshLocal(): Promise<void> {
    if (disposed || !journal) return;
    if (localBusy) {
      localPending = true;
      return;
    }
    localBusy = true;
    const activeGeneration = generation;
    try {
      const local = await localSources(dispatcher);
      const git = await gitSource(root);
      if (disposed || generation !== activeGeneration) return;
      localView = {rounds: local.rounds, lastRun: local.lastRun, connected: local.connected};
      gitView = {branch: git.branch, changed: git.changed};
      details = {...details, ...local.details};
      localWarnings = [...local.warnings, ...git.warnings, ...journal.warnings];
      const localEvents = local.events.map(e => {
        const task = e.task_id ?? pulls.find(p => p.number === e.pr_number)?.task;
        return task
          ? {
              ...e,
              task_id: task,
              correlation_id: `${task}:PR-${e.pr_number ?? 'unknown'}:${e.commit_sha ?? 'unknown'}`,
            }
          : e;
      });
      await journal.add([...localEvents, ...git.events]);
      if (disposed || generation !== activeGeneration) return;
      cliCache = await cliPresence();
      if (disposed || generation !== activeGeneration) return;
      publish();
    } catch {
      panel?.webview.postMessage({
        type: 'error',
        message:
          'Не удалось обновить монитор. Проверьте доступ к локальному журналу; исходники и state.json не изменялись.',
      });
    } finally {
      localBusy = false;
      if (localPending && !disposed) {
        localPending = false;
        void refreshLocal();
      }
    }
  }
  /** GitHub poll. It is the only path that waits for the network and it holds its own lock. */
  async function refreshRemote(): Promise<void> {
    if (disposed || !journal) return;
    if (remoteBusy) {
      remotePending = true;
      return;
    }
    if (Date.now() < nextGitHub) return;
    remoteBusy = true;
    const activeGeneration = generation;
    try {
      const cfg = vscode.workspace.getConfiguration('gremovodAgentMonitor', vscode.Uri.file(root));
      const seconds = Math.max(60, Math.min(3600, Number(cfg.get('pollSeconds', 120)) || 120));
      lastAttempt = Date.now();
      try {
        const numbers = cfg.get<number[]>('pullRequests', [58, 59]);
        if (!Array.isArray(numbers) || numbers.length > 10) throw Error('Invalid PR configuration');
        const remote = await github(numbers);
        if (disposed || generation !== activeGeneration) return;
        pulls = remote.pulls;
        details = {...details, ...remote.details};
        remoteWarnings = remote.warnings;
        failures = 0;
        lastGitHub = new Date().toISOString();
        githubStatus = 'Connected';
        try {
          await context.workspaceState.update('agentMonitor.lastPulls', {pulls, at: lastGitHub});
        } catch {
          remoteWarnings = [
            ...remoteWarnings,
            'VS Code snapshot cache could not be saved; event journal remains independent.',
          ];
        }
        await journal.add(remote.events);
        if (disposed || generation !== activeGeneration) return;
      } catch (error: any) {
        failures++;
        githubStatus = 'Not connected / cached observations';
        const detail = redact(error?.stderr || error?.message || 'Unknown error').slice(0, 300);
        remoteWarnings = [
          `GitHub refresh failed: ${detail}. Check gh authentication/network/rate limits. Cached events remain visible.`,
        ];
      }
      nextGitHub = Date.now() + Math.min(3600000, seconds * 1000 * 2 ** Math.min(failures, 5));
      if (disposed || generation !== activeGeneration) return;
      publish();
    } finally {
      remoteBusy = false;
      if (remotePending && !disposed) {
        remotePending = false;
        void refreshRemote();
      }
    }
  }
  async function refresh(): Promise<void> {
    await refreshLocal();
    await refreshRemote();
  }
  const openPanel = async (): Promise<vscode.WebviewPanel> => {
    generation++;
    root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
    if (!root) {
      vscode.window.showInformationMessage('Откройте локальную папку проекта для Agent Monitor.');
      throw Error('No workspace folder');
    }
    disposed = false;
    filter = {};
    visible = 200;
    nextGitHub = 0;
    failures = 0;
    details = {};
    localWarnings = [];
    remoteWarnings = [];
    localView = {rounds: {}, lastRun: 'Unknown', connected: false};
    gitView = {branch: 'Unknown', changed: []};
    const saved = context.workspaceState.get<{pulls: PullState[]; at: string}>('agentMonitor.lastPulls');
    pulls = saved?.pulls ?? [];
    lastGitHub = saved?.at ?? null;
    githubStatus = 'Not connected / cached observations';
    dispatcher =
      vscode.workspace.getConfiguration('gremovodAgentMonitor').get<string>('dispatcherDirectory', '') ||
      join(
        process.env.LOCALAPPDATA ||
          (process.platform === 'win32' ? tmpdir() : join(homedir(), '.local', 'share')),
        'GremoVOD',
        'agent-dispatcher'
      );
    const key = createHash('sha256').update(root).digest('hex').slice(0, 16);
    journal = new Journal(join(context.globalStorageUri.fsPath, key, 'events.jsonl'));
    await journal.load();
    // Resources of this panel only: closing it must not touch the resources of another one.
    const own: vscode.Disposable[] = [];
    const created = vscode.window.createWebviewPanel(
      'gremovodAgentMonitor',
      'GremoVOD Agent Monitor',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')],
        retainContextWhenHidden: true,
        enableCommandUris: false,
      }
    );
    panel = created;
    created.webview.html = html(created.webview, context.extensionUri);
    created.webview.onDidReceiveMessage(
      async (m: any) => {
        if (!m || typeof m !== 'object' || typeof m.type !== 'string') return;
        if (m.type === 'ready') {
          send();
          return;
        }
        if (m.type === 'refresh') {
          if (!failures && Date.now() - lastAttempt > 15000) nextGitHub = 0;
          void refresh();
          return;
        }
        if (m.type === 'filter') {
          const f: Filter = {};
          for (const k of ['agent', 'task', 'pr', 'status', 'from', 'to', 'search'] as const)
            if (typeof m.filter?.[k] === 'string') f[k] = m.filter[k].slice(0, 200);
          filter = f;
          visible = 200;
          send();
          return;
        }
        if (m.type === 'more') {
          visible = Math.min(5000, visible + 200);
          send();
          return;
        }
        if (typeof m.id !== 'string') return;
        const e = journal.events.find(e => e.event_id === m.id);
        if (!e) return;
        const d = details[e.event_id];
        if (m.type === 'detail')
          created.webview.postMessage({
            type: 'detail',
            id: e.event_id,
            text: d?.text ?? `${e.summary}\n\nПолный текст недоступен в этом снимке. Откройте источник.`,
            meta: `${e.source} · ${e.timestamp} · ${e.correlation_id}`,
            canOpen: !!(safeUrl(d?.url ?? e.payload_ref) || d?.file),
          });
        else if (m.type === 'copy') await vscode.env.clipboard.writeText(redact(d?.text ?? e.summary));
        else if (m.type === 'open') {
          const url = safeUrl(d?.url ?? e.payload_ref);
          if (url) await vscode.env.openExternal(vscode.Uri.parse(url));
          else if (d?.file && (await allowedReport(dispatcher, d.file))) {
            // Open the redacted snapshot, never the raw report containing arbitrary secrets.
            const doc = await vscode.workspace.openTextDocument({content: d.text, language: 'plaintext'});
            await vscode.window.showTextDocument(doc, {preview: true, viewColumn: vscode.ViewColumn.Beside});
          }
        }
      },
      undefined,
      own
    );
    const watcher = vscode.workspace.createFileSystemWatcher(
        new vscode.RelativePattern(vscode.Uri.file(dispatcher), '{state.json,events.jsonl,STOP,PR-*.md,PR-*.json}')
    );
    let debounce: ReturnType<typeof setTimeout> | undefined;
    const changed = () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => void refresh(), 200);
    };
    watcher.onDidChange(changed);
    watcher.onDidCreate(changed);
    watcher.onDidDelete(changed);
    const timer = setInterval(() => void refresh(), 30000);
    own.push(watcher, {
      dispose: () => {
        clearInterval(timer);
        clearTimeout(debounce);
      },
    });
    created.onDidDispose(() => {
      // Only the owner of the panel clears the shared state.
      if (panel === created) {
        panel = undefined;
        disposed = true;
      }
      for (const d of own.splice(0)) d.dispose();
    });
    await refresh();
    return created;
  };
  const command = vscode.commands.registerCommand('gremovodAgentMonitor.open', async () => {
    if (!vscode.workspace.isTrusted) {
      vscode.window.showWarningMessage('Agent Monitor requires a trusted workspace.');
      return;
    }
    if (panel) {
      panel.reveal();
      return;
    }
    // A second open while the first one is still starting must join it, not start a rival panel.
    if (!opening) opening = openPanel().finally(() => (opening = undefined));
    const created = await opening.catch(() => undefined);
    created?.reveal();
  });
  context.subscriptions.push(command, {
    dispose: () => {
      disposed = true;
      panel?.dispose();
    },
  });
  return {getSnapshot: () => latest, getEvents: () => journal?.events ?? [], close: () => panel?.dispose()};
}
