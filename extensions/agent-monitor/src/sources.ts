import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readdir, readFile, realpath, stat} from 'node:fs/promises';
import {basename, dirname, isAbsolute, join, relative, delimiter} from 'node:path';
import {AgentEvent, CODEX, Detail, Journal, REPO, event, redact, safeUrl} from './events';

const exec = promisify(execFile);
export type Run = (command: string, args: string[], cwd?: string) => Promise<string>;
export const run: Run = async (command, args, cwd) => {
  const p = await exec(command, args, {
    cwd,
    encoding: 'utf8',
    windowsHide: true,
    timeout: 30000,
    maxBuffer: 16 * 1024 * 1024,
    env: {...process.env, GIT_OPTIONAL_LOCKS: '0', GH_PROMPT_DISABLED: '1'},
  });
  return p.stdout;
};
export interface Batch {
  events: AgentEvent[];
  details: Record<string, Detail>;
  warnings: string[];
}
export interface ReviewState {
  status: string;
  sha: string | null;
  url?: string;
  p0: number;
  p1: number;
  p2: number;
}
export interface PullState {
  number: number;
  task: string | null;
  branch: string;
  sha: string;
  url: string;
  review: ReviewState;
  next: string;
}
const blank = (): Batch => ({events: [], details: {}, warnings: []});
function taskId(text: string): string | null {
  return /\bGA-0[1-5]\b/i.exec(text)?.[0].toUpperCase() ?? null;
}
function severity(text: string) {
  return /\bP[012]\b/.exec(text)?.[0] ?? 'info';
}
function summary(text: string) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/<[^>]*>/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[*#`>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function reviewState(sha: string, comments: any[], inline: any[]): ReviewState {
  const state: ReviewState = {status: 'Unknown', sha: null, p0: 0, p1: 0, p2: 0};
  const summary = comments
    .filter(c => c.user?.login === CODEX && String(c.body).includes('<!-- codex-review-state:v1 '))
    .sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)))[0];
  if (summary) {
    const match = /<!-- codex-review-state:v1 (\{[^\n]*\}) -->/.exec(summary.body);
    try {
      const r = JSON.parse(match?.[1] ?? '{}').code_review;
      state.sha = r?.commit_sha ?? null;
      state.url = safeUrl(summary.html_url);
      state.status = !r
        ? 'Unknown'
        : r.commit_sha !== sha
          ? 'Stale SHA'
          : r.status === 'running'
            ? 'Reviewing'
            : r.status !== 'completed'
              ? 'Unknown'
              : r.has_unresolved_findings === true
                ? 'Changes requested'
                : r.has_any_findings === false && r.has_unresolved_findings === false
                  ? 'Review clear'
                  : 'Unknown';
    } catch {
      state.status = 'Invalid review marker';
    }
  }
  for (const c of inline) {
    if (c.user?.login !== CODEX || c.commit_id !== sha) continue;
    const s = severity(c.body ?? '');
    if (s === 'P0') state.p0++;
    if (s === 'P1') state.p1++;
    if (s === 'P2') state.p2++;
  }
  return state;
}

export async function github(numbers: number[], command: Run = run): Promise<Batch & {pulls: PullState[]}> {
  const result = {...blank(), pulls: [] as PullState[]};
  const api = async (endpoint: string) =>
    JSON.parse(await command('gh', ['api', '--hostname', 'github.com', endpoint]));
  const pages = async (endpoint: string) => {
    const value = JSON.parse(
      await command('gh', [
        'api',
        '--hostname',
        'github.com',
        '--paginate',
        '--slurp',
        endpoint + '?per_page=100',
      ])
    );
    if (!Array.isArray(value) || !value.every(Array.isArray))
      throw Error('Unexpected paginated GitHub response');
    return value.flat();
  };
  /**
   * Read one optional source of a PR. A failure is reported as a warning and never turns the
   * already collected data of that PR into missing data.
   */
  const optional = async <T>(
    number: number,
    label: string,
    read: () => Promise<T>,
    fallback: T
  ): Promise<T> => {
    try {
      return await read();
    } catch (error: any) {
      result.warnings.push(
        `PR #${number}: ${label} unavailable (${redact(error?.message ?? 'Unknown error').slice(0, 200)}).`
      );
      return fallback;
    }
  };
  /** Collect one PR. Events of a PR that fails stay out of the batch: only the warning remains. */
  const collect = async (number: number): Promise<Batch & {pulls: PullState[]}> => {
    const local = {...blank(), pulls: [] as PullState[]};
    const base = `repos/${REPO}`;
    const pr = await api(`${base}/pulls/${number}`);
    if (!/^[a-f0-9]{40}$/i.test(pr.head?.sha ?? '')) throw Error('Invalid GitHub head SHA');
    const comments = await optional(number, 'comments', () => pages(`${base}/issues/${number}/comments`), [] as any[]);
    const reviews = await optional(number, 'reviews', () => pages(`${base}/pulls/${number}/reviews`), [] as any[]);
    const inline = await optional(number, 'inline comments', () => pages(`${base}/pulls/${number}/comments`), [] as any[]);
    const commits = await optional(number, 'commits', () => pages(`${base}/pulls/${number}/commits`), [] as any[]);
    const files = await optional(number, 'files', () => pages(`${base}/pulls/${number}/files`), [] as any[]);
    if ((pr.changed_files ?? 0) > files.length)
      result.warnings.push(
        `PR #${number}: GitHub files response is incomplete (${files.length}/${pr.changed_files}).`
      );
    const task = taskId(`${pr.title} ${pr.head.ref}`);
    const pull: PullState = {
      number,
      task,
      branch: pr.head.ref,
      sha: pr.head.sha,
      url: safeUrl(pr.html_url) ?? '',
      review: reviewState(pr.head.sha, comments, inline),
      next: 'Waiting for owner merge + Codex marker',
    };
    // This is a displayed observation of the dispatcher's documented gate, never an execution permit.
    const next = task && Number(task.slice(-2)) < 5 ? `GA-0${Number(task.slice(-2)) + 1}` : null;
    const marker = comments.find(
      c => c.user?.login === CODEX && next && String(c.body).includes(`GREMOVOD_NEXT_TASK: ${next}`)
    );
    if (pr.merged && marker)
      pull.next = `${next}: GitHub merge + Codex marker observed; dispatcher acceptance Unknown`;
    local.pulls.push(pull);
    const add = (
      type: string,
      id: string,
      timestamp: string,
      agent: string,
      status: string,
      summary: string,
      url: string,
      sha: string | null,
      text = summary
    ) => {
      const e = event(
        {
          timestamp,
          source: 'github',
          agent,
          task_id: task,
          pr_number: number,
          commit_sha: sha,
          event_type: type,
          severity: severity(type === 'finding' ? text : summary),
          status,
          summary,
          payload_ref: safeUrl(url) ?? null,
        },
        id
      );
      local.events.push(e);
      local.details[e.event_id] = {text: redact(text).slice(0, 64000), url: safeUrl(url)};
    };
    add(
      'pr_created',
      `pr:${number}:created`,
      pr.created_at,
      'GitHub',
      pr.draft ? 'Draft' : 'Open',
      pr.title,
      pr.html_url,
      null,
      pr.body ?? ''
    );
    add(
      'pr_observed',
      `pr:${number}:${pr.updated_at}:${pr.head.sha}:${pr.state}:${pr.draft}`,
      pr.updated_at,
      'GitHub',
      pr.merged ? 'Merged' : pr.state,
      `#${number} ${pr.title}`,
      pr.html_url,
      pr.head.sha,
      `${pr.body ?? ''}\n\nFiles at observed head:\n${files.map((f: any) => `${f.status}: ${redact(f.filename)}`).join('\n')}`
    );
    for (const c of commits)
      add(
        'commit',
        `commit:${number}:${c.sha}`,
        c.commit.committer?.date ?? c.commit.author.date,
        'Git',
        'Committed',
        c.commit.message,
        c.html_url,
        c.sha
      );
    for (const [kind, items] of [
      ['discussion', comments],
      ['review', reviews],
      ['finding', inline],
    ] as const) {
      for (const c of items) {
        const agent = c.user?.login === CODEX ? 'Codex GitHub' : `GitHub: ${c.user?.login ?? 'Unknown'}`;
        const marker =
          c.user?.login === CODEX && String(c.body).includes('<!-- codex-review-state:v1 ')
            ? reviewState(pr.head.sha, [c], [])
            : undefined;
        const sha = c.commit_id ?? marker?.sha ?? null;
        const timestamp = c.updated_at ?? c.submitted_at ?? c.created_at;
        if (!timestamp) continue;
        add(
          marker ? 'review_state' : kind,
          `${kind}:${c.id}:${timestamp}`,
          timestamp,
          agent,
          sha && sha !== pr.head.sha ? 'Stale SHA' : (marker?.status ?? c.state ?? 'Observed'),
          marker ? `Codex Review Summary: ${marker.status}` : summary(c.body ?? ''),
          c.html_url,
          sha,
          c.body ?? ''
        );
      }
    }
    const actions = await optional(
      number,
      'GitHub Actions',
      () => api(`${base}/actions/runs?head_sha=${pr.head.sha}&per_page=100`),
      {total_count: 0, workflow_runs: []} as any
    );
    if ((actions.total_count ?? 0) > 100)
      result.warnings.push(`PR #${number}: Actions view limited to 100 runs at current SHA.`);
    for (const a of actions.workflow_runs ?? [])
      add(
        'github_actions',
        `action:${a.id}:${a.run_attempt}:${a.updated_at}`,
        a.updated_at,
        'GitHub Actions',
        a.conclusion ?? a.status,
        `${a.name}: ${a.conclusion ?? a.status} (GitHub Actions)`,
        a.html_url,
        a.head_sha
      );
    // A moving head invalidates the collected view; retry on the next poll rather than declaring a stale review clear.
    const latest = await optional(number, 'head re-check', () => api(`${base}/pulls/${number}`), undefined as any);
    if (latest && latest.head?.sha !== pull.sha) {
      pull.review.status = 'Stale SHA';
      result.warnings.push(`PR #${number}: head changed during refresh; next poll required.`);
    }
    return local;
  };
  const unique = [...new Set(numbers)];
  let failed = 0;
  for (const number of unique) {
    if (!Number.isSafeInteger(number) || number < 1) throw Error('Invalid PR number');
    try {
      const local = await collect(number);
      result.events.push(...local.events);
      Object.assign(result.details, local.details);
      result.pulls.push(...local.pulls);
    } catch (error: any) {
      // One unavailable PR must not discard the data of the PRs that were read successfully.
      failed++;
      result.warnings.push(
        `PR #${number}: unavailable (${redact(error?.message ?? 'Unknown error').slice(0, 200)}).`
      );
    }
  }
  if (unique.length && failed === unique.length)
    throw Error('GitHub refresh failed: no configured PR could be read.');
  return result;
}

export async function allowedReport(root: string, candidate: string): Promise<string | undefined> {
  if (
    !/^PR-\d+(?:-[a-f0-9]{12})?-(?:feedback(?:-result)?|codex-review)\.(?:md|json)$/.test(basename(candidate))
  )
    return;
  try {
    const [r, p] = await Promise.all([realpath(root), realpath(candidate)]);
    const rel = relative(r, p);
    if (rel.startsWith('..') || isAbsolute(rel) || dirname(p).toLowerCase() !== r.toLowerCase()) return;
    return p;
  } catch {
    return;
  }
}
export async function localSources(
  root: string
): Promise<Batch & {rounds: Record<string, number>; lastRun: string; connected: boolean}> {
  const result = {...blank(), rounds: {} as Record<string, number>, lastRun: 'Unknown', connected: false};
  try {
    const statePath = join(root, 'state.json');
    const resolved = await realpath(statePath);
    if (dirname(resolved).toLowerCase() !== (await realpath(root)).toLowerCase())
      throw Error('State symlink leaves dispatcher directory');
    if ((await stat(resolved)).size > 4 * 1024 * 1024) throw Error('State exceeds 4 MiB');
    const state = JSON.parse(await readFile(resolved, 'utf8'));
    if (!state || typeof state !== 'object' || Array.isArray(state)) throw Error('Invalid dispatcher state');
    result.connected = true;
    for (const [task, record] of Object.entries(state.tasks ?? {}) as [string, any][]) {
      if (!/^GA-0[1-5]$/.test(task)) continue;
      if (/^GA-0[1-5]$/.test(task) && Number.isSafeInteger(record?.rounds) && record.rounds >= 0)
        result.rounds[task] = record.rounds;
      if (record?.accepted?.at && /^[a-f0-9]{40}$/i.test(record.accepted.merge_sha ?? '')) {
        const e = event(
          {
            timestamp: record.accepted.at,
            source: 'dispatcher',
            agent: 'Owner record',
            task_id: task,
            pr_number: null,
            commit_sha: record.accepted.merge_sha,
            event_type: 'owner_accept_record',
            severity: 'info',
            status: 'Observed',
            summary: `${task}: dispatcher acceptance record (not a new authorization)`,
            payload_ref: null,
          },
          `accept:${task}:${record.accepted.at}`
        );
        if (Number.isFinite(Date.parse(e.timestamp))) result.events.push(e);
      }
    }
    const runs = state.runs ?? state;
    for (const [key, value] of Object.entries(runs) as [string, any][]) {
      const m = /^(\d+):([a-f0-9]{40}):([A-Z_]+)$/i.exec(key);
      if (!m || !value || !Number.isFinite(Date.parse(value.at))) continue;
      const status = ['LAUNCHED', 'FAILED', 'TIMEOUT', 'COMPLETED', 'DONE'].includes(value.status)
        ? value.status
        : 'Unknown';
      const e = event(
        {
          timestamp: value.at,
          source: 'dispatcher',
          agent: 'MiniMax',
          task_id: null,
          pr_number: Number(m[1]),
          commit_sha: m[2],
          event_type: 'dispatcher_run_observed',
          severity: status === 'FAILED' || status === 'TIMEOUT' ? 'warning' : 'info',
          status,
          summary: `Dispatcher recorded ${status}; current process activity Unknown`,
          payload_ref: null,
        },
        `${key}:${status}:${value.at}`
      );
      result.events.push(e);
    }
    const last = [...result.events]
      .filter(e => e.agent === 'MiniMax')
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0];
    if (last) result.lastRun = `${last.status} at ${last.timestamp}; live activity Unknown`;
  } catch (e: any) {
    result.warnings.push(
      e.code === 'ENOENT'
        ? 'Dispatcher: Not connected (state.json missing)'
        : 'Dispatcher: unreadable/invalid state.json'
    );
  }
  try {
    const journalPath = join(root, 'events.jsonl');
    const actual = await realpath(journalPath);
    if (actual.toLowerCase() !== journalPath.toLowerCase()) throw Error('Unsafe dispatcher journal path');
    const journal = new Journal(journalPath);
    await journal.load();
    result.events.push(...journal.events);
    result.warnings.push(...journal.warnings.map(w => `Dispatcher journal: ${w}`));
  } catch (e: any) {
    if (e.code !== 'ENOENT') result.warnings.push('Dispatcher journal: unreadable/unsafe events.jsonl');
  }
  try {
    if ((await stat(join(root, 'STOP'))).isFile()) result.warnings.push('Automation stopped by owner (STOP marker).');
  } catch { /* No owner stop marker. */ }
  try {
    const names = (await readdir(root)).filter(n => /^PR-/.test(n));
    for (const name of names.slice(0, 200)) {
      const file = await allowedReport(root, join(root, name));
      if (!file) continue;
      const info = await stat(file);
      if (info.size > 256 * 1024) {
        result.warnings.push(`Report ${name}: exceeds 256 KiB; skipped`);
        continue;
      }
      const text = redact(await readFile(file, 'utf8'));
      const codex = name.includes('codex-review');
      const sha = /PR-\d+-([a-f0-9]{12})-/.exec(name)?.[1];
      const fullSha = /HEAD SHA:\s*([a-f0-9]{40})/i.exec(text)?.[1] ?? null;
      const e = event(
        {
          timestamp: info.mtime.toISOString(),
          source: codex ? 'codex-cli-report' : name.endsWith('-result.json') ? 'minimax-report' : 'dispatcher',
          agent: codex ? 'Codex CLI' : name.endsWith('-result.json') ? 'MiniMax' : 'Dispatcher',
          task_id: taskId(text),
          pr_number: Number(/^PR-(\d+)/.exec(name)![1]),
          commit_sha: fullSha,
          event_type: 'report_observed',
          severity: 'info',
          status: 'Report available',
          summary: `${name} (file observation; execution/test outcome Unknown${sha ? `; SHA prefix ${sha}` : ''})`,
          payload_ref: null,
        },
        `${name}:${info.mtimeMs}:${info.size}`
      );
      result.events.push(e);
      result.details[e.event_id] = {text, file};
    }
    if (names.length > 200) result.warnings.push('Report scan limited to 200 files.');
  } catch (e: any) {
    if (e.code !== 'ENOENT') result.warnings.push('Reports: directory unreadable');
  }
  return result;
}

export async function gitSource(
  root: string,
  command: Run = run
): Promise<Batch & {branch: string; worktree: string; changed: string[]}> {
  const result = {...blank(), branch: 'Unknown', worktree: root, changed: [] as string[]};
  try {
    const git = (args: string[]) =>
      command('git', ['-c', `safe.directory=${root.replace(/\\/g, '/')}`, '-C', root, ...args]);
    result.branch = (await git(['branch', '--show-current'])).trim() || 'Detached HEAD';
    const sha = (await git(['rev-parse', 'HEAD'])).trim();
    const last = JSON.parse(await git(['log', '-1', '--format={"sha":"%H","at":"%cI"}']));
    const raw = (await git(['status', '--porcelain=v1', '-z'])).split('\0');
    for (let i = 0; i < raw.length; i++) {
      const line = raw[i];
      if (!line) continue;
      const path = line.slice(3);
      if (
        !/(?:^|[\\/])(?:\.env[^\\/]*|\.git|.*(?:API_KEY|credentials|secret).*|id_rsa)(?:[\\/]|$)/i.test(path)
      )
        result.changed.push(redact(path));
      if (/[RC]/.test(line.slice(0, 2))) i++;
    }
    const e = event(
      {
        timestamp: last.at,
        source: 'git',
        agent: 'Git',
        task_id: taskId(result.branch),
        pr_number: null,
        commit_sha: sha,
        event_type: 'workspace_commit',
        severity: 'info',
        status: 'Observed',
        summary: `Workspace HEAD: ${result.branch}`,
        payload_ref: safeUrl(`https://github.com/${REPO}/commit/${sha}`) ?? null,
      },
      `${root}:${sha}`
    );
    result.events.push(e);
  } catch {
    result.warnings.push('Git: Not connected (workspace unavailable or not a repository)');
  }
  return result;
}
export async function cliPresence(): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  for (const name of ['gh', 'git', 'mcode', 'codex']) {
    let found = false;
    for (const dir of (process.env.PATH ?? '').split(delimiter)) {
      for (const suffix of process.platform === 'win32' ? ['.exe', '.cmd'] : ['']) {
        try {
          if ((await stat(join(dir, name + suffix))).isFile()) found = true;
        } catch {
          /* PATH entry absent. */
        }
      }
    }
    result[name] = found ? 'Installed on PATH; process activity Unknown' : 'Not connected (not on PATH)';
  }
  return result;
}
