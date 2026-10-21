'use strict';
const repo = { full_name: 'gremoled77-droid/gremovod' };
const head = 'a'.repeat(40);
const old = 'b'.repeat(40);
const pr = { number: 58, title: '[GA-01] settlement', head: { sha: head }, base: { repo }, draft: true, merged: false };
const bot = { login: 'chatgpt-codex-connector[bot]', type: 'Bot' };
function fixture(type = 'pull_request', action = 'opened', changes = {}) {
  return { headers: { 'x-github-event': type, 'x-github-delivery': 'fixture-delivery-1' }, body: { repository: repo, sender: { login: 'gremoled77-droid' }, action, pull_request: pr, ...changes } };
}
module.exports = { repo, head, old, pr, bot, fixture };
