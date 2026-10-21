import {createHash} from 'node:crypto';
import {createReadStream} from 'node:fs';
import {appendFile, mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';

export const REPO = 'gremoled77-droid/gremovod';
export const CODEX = 'chatgpt-codex-connector[bot]';
export type Source = 'github' | 'dispatcher' | 'codex-cli-report' | 'minimax-report' | 'git';
export interface AgentEvent {
  event_id: string;
  timestamp: string;
  source: Source;
  agent: string;
  task_id: string | null;
  pr_number: number | null;
  commit_sha: string | null;
  event_type: string;
  severity: string;
  status: string;
  summary: string;
  payload_ref: string | null;
  correlation_id: string;
}
export interface Detail {
  text: string;
  url?: string;
  file?: string;
}
export function redact(value: unknown): string {
  return String(value ?? '')
    .replace(
      /-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)/g,
      '[REDACTED PRIVATE KEY]'
    )
    .replace(
      /\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{8,}|AKIA[A-Z0-9]{16})\b/g,
      '[REDACTED]'
    )
    .replace(/\b(Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+/gi, '$1 [REDACTED]')
    .replace(
      /(["']?(?:[\w-]*(?:token|password|passwd|secret|api[_-]?key|authorization))["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;<>]+)/gi,
      '$1[REDACTED]'
    )
    .replace(/(https?:\/\/)[^\s/@]+:[^\s/@]+@/gi, '$1[REDACTED]@')
    .replace(/(https?:\/\/[^\s?#]+)\?[^\s#]*/gi, '$1?[REDACTED QUERY]');
}
export function safeUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return;
  try {
    const u = new URL(value);
    if (
      u.protocol === 'https:' &&
      u.hostname === 'github.com' &&
      !u.port &&
      !u.username &&
      !u.password &&
      !u.search &&
      u.pathname.startsWith(`/${REPO}/`) &&
      !/%|\\/.test(u.pathname)
    )
      return u.href;
  } catch {
    /* Untrusted links are displayed as text only. */
  }
}
export function event(input: Omit<AgentEvent, 'event_id' | 'correlation_id'>, identity: string): AgentEvent {
  return {
    ...input,
    summary: redact(input.summary).slice(0, 500),
    event_id: createHash('sha256').update(`${input.source}:${identity}`).digest('hex'),
    correlation_id: `${input.task_id ?? 'unknown'}:PR-${input.pr_number ?? 'unknown'}:${input.commit_sha ?? 'unknown'}`,
  };
}
const sources = new Set(['github', 'dispatcher', 'codex-cli-report', 'minimax-report', 'git']);
export function validateEvent(x: unknown): x is AgentEvent {
  if (!x || typeof x !== 'object') return false;
  const e = x as AgentEvent;
  return (
    typeof e.event_id === 'string' &&
    /^[a-f0-9]{64}$/.test(e.event_id) &&
    typeof e.timestamp === 'string' &&
    Number.isFinite(Date.parse(e.timestamp)) &&
    sources.has(e.source) &&
    ['agent', 'event_type', 'severity', 'status', 'summary', 'correlation_id'].every(
      k => typeof (e as any)[k] === 'string'
    ) &&
    (e.task_id === null || typeof e.task_id === 'string') &&
    (e.pr_number === null || (Number.isSafeInteger(e.pr_number) && e.pr_number > 0)) &&
    (e.commit_sha === null || /^[a-f0-9]{40}$/i.test(e.commit_sha)) &&
    (e.payload_ref === null || typeof e.payload_ref === 'string')
  );
}
export interface Filter {
  agent?: string;
  task?: string;
  pr?: string;
  status?: string;
  from?: string;
  to?: string;
  search?: string;
}
export function filterEvents(events: AgentEvent[], f: Filter): AgentEvent[] {
  return events.filter(
    e =>
      (!f.agent || e.agent === f.agent) &&
      (!f.task || e.task_id === f.task) &&
      (!f.pr || String(e.pr_number) === f.pr) &&
      (!f.status || e.status === f.status) &&
      (!f.from || Date.parse(e.timestamp) >= Date.parse(f.from)) &&
      (!f.to || Date.parse(e.timestamp) <= Date.parse(f.to)) &&
      (!f.search ||
        `${e.summary} ${e.event_type} ${e.commit_sha}`.toLowerCase().includes(f.search.toLowerCase()))
  );
}

export class Journal {
  readonly ids = new Set<string>();
  events: AgentEvent[] = [];
  warnings: string[] = [];
  constructor(
    readonly path: string,
    readonly limit = 5000
  ) {}
  private remember(e: AgentEvent) {
    this.ids.add(e.event_id);
    let low = 0,
      high = this.events.length;
    while (low < high) {
      const mid = (low + high) >>> 1;
      const current = this.events[mid];
      if (
        Date.parse(current.timestamp) < Date.parse(e.timestamp) ||
        (Date.parse(current.timestamp) === Date.parse(e.timestamp) && current.event_id < e.event_id)
      )
        low = mid + 1;
      else high = mid;
    }
    this.events.splice(low, 0, e);
    if (this.events.length > this.limit) this.events.shift();
  }
  async load() {
    this.ids.clear();
    this.events = [];
    this.warnings = [];
    let buffer = '',
      dropping = false,
      invalid = 0;
    const consume = (line: string) => {
      try {
        const e = JSON.parse(line);
        if (!validateEvent(e)) {
          invalid++;
          return;
        }
        if (!this.ids.has(e.event_id))
          this.remember({
            ...e,
            summary: redact(e.summary).slice(0, 500),
            payload_ref: safeUrl(e.payload_ref) ?? null,
          });
      } catch {
        if (line.trim()) invalid++;
      }
    };
    try {
      for await (const chunk of createReadStream(this.path, {encoding: 'utf8', highWaterMark: 65536})) {
        for (const part of String(chunk).split(/(?<=\n)/)) {
          if (!dropping) buffer += part;
          if (buffer.length > 65536) {
            buffer = '';
            dropping = true;
            invalid++;
          }
          if (part.endsWith('\n')) {
            if (!dropping) consume(buffer);
            buffer = '';
            dropping = false;
          }
        }
      }
      // An interrupted append must not turn the following append into one corrupt line.
      if (buffer.trim() || dropping)
        this.warnings.push('Journal has an incomplete final line; it is ignored.');
    } catch (e: any) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (invalid) this.warnings.push(`${invalid} invalid/oversized journal lines ignored.`);
  }
  async add(incoming: AgentEvent[]) {
    const fresh = incoming.filter(e => {
      if (!validateEvent(e) || this.ids.has(e.event_id)) return false;
      this.ids.add(e.event_id);
      return true;
    });
    // IDs become durable only after a successful append. Roll back on IO failure.
    try {
      if (fresh.length) {
        await mkdir(dirname(this.path), {recursive: true});
        await appendFile(
          this.path,
          '\n' +
            fresh
              .map(e =>
                JSON.stringify({
                  ...e,
                  summary: redact(e.summary),
                  payload_ref: safeUrl(e.payload_ref) ?? null,
                })
              )
              .join('\n') +
            '\n',
          {mode: 0o600}
        );
      }
    } catch (error) {
      for (const e of fresh) this.ids.delete(e.event_id);
      throw error;
    }
    for (const e of fresh) this.remember(e);
  }
}
