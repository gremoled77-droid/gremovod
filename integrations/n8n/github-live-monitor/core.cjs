'use strict';

const REPOSITORY = 'gremoled77-droid/gremovod';
const BOT = 'chatgpt-codex-connector[bot]';
const SHA = /^[a-f0-9]{40}$/;
const login = value => typeof value === 'string' && /^[a-zA-Z0-9[\]_-]{1,100}$/.test(value) ? value : 'UNKNOWN';
const sha = value => typeof value === 'string' && SHA.test(value) ? value : null;
const escapeHtml = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function verify(input) {
  const h = input.headers || {};
  const body = input.body;
  if (!body || body.repository?.full_name !== REPOSITORY) throw new Error('REPOSITORY_REJECTED');
  if (!/^[a-z_]+$/.test(h['x-github-event'] || '')) throw new Error('EVENT_REJECTED');
  if (!/^[a-zA-Z0-9-]{1,100}$/.test(h['x-github-delivery'] || '')) throw new Error('DELIVERY_REJECTED');
  const number = body.pull_request?.number || (body.issue?.pull_request && body.issue.number) || body.check_run?.pull_requests?.[0]?.number || body.check_suite?.pull_requests?.[0]?.number;
  if (number && (!Number.isSafeInteger(number) || number <= 0)) throw new Error('PR_REJECTED');
  return { ...input, snapshot_url: `https://api.github.com/repos/${REPOSITORY}${number ? `/pulls/${number}` : ''}` };
}

function normalize(input, snapshot, now = new Date().toISOString()) {
  verify(input);
  const b = input.body;
  const type = input.headers['x-github-event'];
  const action = b.action || '';
  const pr = b.pull_request || (b.issue?.pull_request ? b.issue : null) || b.check_run?.pull_requests?.[0] || b.check_suite?.pull_requests?.[0] || null;
  const number = pr?.number || null;
  const current = snapshot?.number === number && snapshot?.base?.repo?.full_name === REPOSITORY && sha(snapshot?.head?.sha);
  const head = sha(b.pull_request?.head?.sha) || current;
  const item = b.review || b.comment;
  const actor = login(item?.user?.login || b.sender?.login);
  const event = {
    event_id: `github:${input.headers['x-github-delivery']}`,
    received_at: now,
    github_delivery_id: input.headers['x-github-delivery'],
    event_type: type,
    action,
    repository: REPOSITORY,
    actor,
    pr_number: number,
    task_id: (String(snapshot?.title || pr?.title || '').match(/\bGA-\d{2}\b/) || [null])[0],
    head_sha: head || null,
    review_status: 'UNKNOWN',
    severity: 'INFO',
    summary: '',
    source_url: `https://github.com/${REPOSITORY}${number ? `/pull/${number}` : ''}`,
    kind: '',
    route: 'digest',
    evidence_id: '',
  };
  if (type === 'push' && !b.deleted && sha(b.after)) {
    event.kind = 'COMMIT'; event.head_sha = b.after;
    event.source_url = `https://github.com/${REPOSITORY}/commit/${b.after}`;
  } else if (type === 'pull_request' && ['opened', 'reopened', 'synchronize', 'ready_for_review', 'closed', 'labeled'].includes(action)) {
    event.kind = { opened: 'PR_OPENED', reopened: 'PR_REOPENED', synchronize: 'PR_UPDATED', ready_for_review: 'PR_READY', closed: b.pull_request.merged === true ? 'PR_MERGED' : 'PR_CLOSED', labeled: '' }[action];
    if (event.kind === 'PR_READY' && (b.pull_request.draft || !current || snapshot.draft)) event.kind = '';
    const block = ['security-blocked', 'financial-blocked', 'dispatcher-stopped'];
    if (action === 'labeled' && b.sender?.login === 'gremoled77-droid' && block.includes(b.label?.name)) {
      event.kind = b.label.name.toUpperCase().replace(/-/g, '_'); event.severity = 'P1';
    }
    if (event.kind && action !== 'labeled') event.severity = 'NORMAL';
    // A new commit is evidence of an update, never evidence that findings were fixed.
  } else if (['pull_request_review', 'pull_request_review_comment', 'issue_comment'].includes(type) && item?.user?.login === BOT && item.user.type === 'Bot' && number && ['submitted', 'created', 'edited'].includes(action)) {
    const reviewed = sha(item.commit_id);
    const text = String(item.body || '');
    event.evidence_id = String(item.id || '');
    if (Number.isSafeInteger(item.id) && item.id > 0) {
      const anchor = type === 'pull_request_review' ? 'pullrequestreview-' : type === 'issue_comment' ? 'issuecomment-' : 'discussion_r';
      event.source_url += `#${anchor}${item.id}`;
    }
    if (reviewed && current && reviewed !== current) {
      event.kind = 'STALE_REVIEW'; event.review_status = 'STALE'; event.head_sha = reviewed;
    } else if (reviewed && current && reviewed === current) {
      event.head_sha = reviewed;
      const severity = (text.match(/\bP[012]\b/g) || []).sort()[0];
      if (severity) {
        event.kind = 'CODEX_FINDING'; event.severity = severity; event.review_status = 'FINDINGS';
      } else if (type === 'pull_request_review' && action === 'submitted' && ['approved', 'changes_requested', 'commented'].includes(item.state?.toLowerCase())) {
        event.kind = 'CODEX_REVIEW_COMPLETED'; event.severity = 'NORMAL'; event.review_status = item.state.toUpperCase();
      }
    } else {
      // Issue comments have no authoritative commit_id, including edited comments.
      event.kind = 'CODEX_COMMENT_UNCORRELATED';
    }
    if (!event.kind) event.kind = 'CODEX_STATUS_UNKNOWN';
  } else if (type === 'check_run' || type === 'check_suite' || type === 'status') {
    const check = b.check_run || b.check_suite || b;
    event.head_sha = sha(check.head_sha || b.sha);
    event.evidence_id = String(check.id || check.context || '');
    const status = type === 'status' ? b.state : check.status === 'completed' ? check.conclusion : check.status;
    if (['failure', 'timed_out', 'action_required', 'cancelled', 'startup_failure', 'error'].includes(status)) {
      event.kind = 'CI_FAILED'; event.severity = 'P1';
    } else if (status === 'success') event.kind = 'CI_PASSED';
    const codex = type === 'check_run' && check.app?.slug === 'chatgpt-codex-connector';
    if (codex) {
      const correlated = current && current === event.head_sha;
      event.kind = !correlated ? 'CODEX_STATUS_UNKNOWN' : status === 'in_progress' ? 'CODEX_REVIEW_STARTED' : check.status === 'completed' ? 'CODEX_REVIEW_COMPLETED' : 'CODEX_STATUS_UNKNOWN';
      event.review_status = !correlated ? 'UNKNOWN' : status === 'in_progress' ? 'STARTED' : check.status === 'completed' ? 'COMPLETED' : 'UNKNOWN';
      event.severity = 'NORMAL';
    }
  }
  if (!event.kind) return null;
  if (event.kind !== 'CODEX_COMMENT_UNCORRELATED' && event.kind !== 'CODEX_STATUS_UNKNOWN' && !event.head_sha) return null;
  event.route = ['P0', 'P1', 'NORMAL'].includes(event.severity) ? 'immediate' : 'digest';
  event.summary = `${event.kind}${number ? ` PR #${number}` : ''}${event.head_sha ? ` @${event.head_sha.slice(0, 12)}` : ''}${event.review_status !== 'UNKNOWN' ? ` ${event.review_status}` : ''}`;
  const identity = ['CODEX_FINDING', 'CI_FAILED', 'CI_PASSED', 'CODEX_COMMENT_UNCORRELATED'].includes(event.kind) ? event.evidence_id : '';
  event.semantic_key = JSON.stringify([REPOSITORY, number, event.head_sha, event.kind, event.review_status, event.severity, identity]);
  return event;
}

function journal(event) {
  return { event_id: event.event_id, delivery_id: event.github_delivery_id, semantic_key: event.semantic_key, event_json: JSON.stringify(event), status: 'PENDING', message_id: '', error_code: '' };
}

function plan(rows, now = Date.now()) {
  // shortcut: Data Table lacks semantic uniqueness; enable only with a verified single sender.
  const sent = new Set(rows.filter(r => ['SENDING', 'SENT', 'UNKNOWN', 'FAILED'].includes(r.status)).map(r => r.semantic_key));
  const deliveries = new Set(rows.filter(r => ['SENDING', 'SENT', 'UNKNOWN', 'FAILED'].includes(r.status)).map(r => r.delivery_id));
  const pending = [];
  for (const row of [...rows].sort((a, b) => a.id - b.id)) {
    if (row.status !== 'PENDING' || sent.has(row.semantic_key) || deliveries.has(row.delivery_id)) continue;
    const e = JSON.parse(row.event_json);
    if (e.repository !== REPOSITORY || e.semantic_key !== row.semantic_key) throw new Error('JOURNAL_REJECTED');
    sent.add(row.semantic_key); deliveries.add(row.delivery_id);
    pending.push({ row, e });
  }
  const urgent = pending.find(p => ['P0', 'P1'].includes(p.e.severity));
  const immediate = urgent || pending.find(p => p.e.route === 'immediate');
  const selected = immediate ? [immediate] : pending.filter(p => now - Date.parse(p.e.received_at) >= 300000).slice(0, 15);
  if (!selected.length) return [];
  const text = selected.map(p => `${p.e.severity} | ${p.e.summary}\n${p.e.source_url}`).join('\n\n');
  return [{ row_ids: selected.map(p => p.row.id), semantic_keys: selected.map(p => p.row.semantic_key), text: escapeHtml(text), count: selected.length }];
}

function telegramOutcome(response) {
  const id = response?.result?.message_id ?? response?.message_id;
  if (Number.isSafeInteger(id) && id > 0 && response?.ok !== false) return { status: 'SENT', message_id: String(id), error_code: '' };
  const code = response?.error_code;
  if (code === 429) return { status: 'FAILED', message_id: '', error_code: 'RATE_LIMIT_CONFIRMED_RETRY_AFTER_OWNER_RECONCILIATION' };
  if ([400, 401, 403].includes(code)) return { status: 'FAILED', message_id: '', error_code: `TELEGRAM_${code}` };
  return { status: 'UNKNOWN', message_id: '', error_code: 'DELIVERY_UNKNOWN_NO_AUTO_RETRY' };
}

module.exports = { REPOSITORY, BOT, verify, normalize, journal, plan, telegramOutcome, escapeHtml };
