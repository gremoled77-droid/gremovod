const SHA = 'a'.repeat(40),
  NEW_SHA = 'b'.repeat(40);
function fixture() {
  const url = 'https://github.com/gremoled77-droid/gremovod/pull/58';
  return {
    pr: {
      number: 58,
      title: 'GA-01 settlement',
      body: 'Task assigned. <script>globalThis.INJECTED=true</script> token=mocksecret',
      head: {sha: SHA, ref: 'minimax/ga-01-llm-settlement'},
      created_at: '2026-10-21T07:00:00Z',
      updated_at: '2026-10-21T08:00:00Z',
      html_url: url,
      state: 'open',
      draft: true,
      merged: false,
    },
    comments: [
      {
        id: 1,
        body: `<!-- codex-review-state:v1 ${JSON.stringify({code_review: {commit_sha: SHA, status: 'completed', has_any_findings: true, has_unresolved_findings: true}})} -->`,
        user: {login: 'chatgpt-codex-connector[bot]'},
        html_url: url + '#issuecomment-1',
        created_at: '2026-10-21T08:00:00Z',
        updated_at: '2026-10-21T08:00:00Z',
      },
    ],
    reviews: [
      {
        id: 2,
        body: 'Review complete',
        state: 'COMMENTED',
        user: {login: 'chatgpt-codex-connector[bot]'},
        commit_id: SHA,
        submitted_at: '2026-10-21T08:01:00Z',
        html_url: url + '#pullrequestreview-2',
      },
    ],
    inline: [
      {
        id: 3,
        body: '<sub>![P1 Badge](https://img.shields.io/badge/P1-orange)</sub> Confirmed cost must survive reconciliation. <img src=x onerror="globalThis.INJECTED=true">',
        user: {login: 'chatgpt-codex-connector[bot]'},
        commit_id: SHA,
        created_at: '2026-10-21T08:02:00Z',
        updated_at: '2026-10-21T08:02:00Z',
        html_url: url + '#discussion_r3',
      },
    ],
    commits: [
      {
        sha: SHA,
        commit: {message: 'fix: settlement', committer: {date: '2026-10-21T07:30:00Z'}},
        html_url: 'https://github.com/gremoled77-droid/gremovod/commit/' + SHA,
      },
    ],
    files: [{filename: 'backend/llm_guard.py', status: 'modified'}],
    actions: {
      workflow_runs: [
        {
          id: 4,
          run_attempt: 1,
          name: 'Offline tests',
          head_sha: SHA,
          status: 'completed',
          conclusion: 'success',
          updated_at: '2026-10-21T08:03:00Z',
          html_url: 'https://github.com/gremoled77-droid/gremovod/actions/runs/4',
        },
      ],
    },
  };
}
function mockGitHub(f, calls) {
  return async (command, args) => {
    if (command !== 'gh') throw Error('unexpected command');
    calls.push(args);
    const endpoint = args.at(-1);
    if (endpoint.endsWith('/pulls/58')) return JSON.stringify(f.pr);
    let value = endpoint.includes('/actions/runs?')
      ? f.actions
      : endpoint.includes('/issues/58/comments')
        ? f.comments
        : endpoint.includes('/pulls/58/comments')
          ? f.inline
          : endpoint.includes('/reviews')
            ? f.reviews
            : endpoint.includes('/commits')
              ? f.commits
              : endpoint.includes('/files')
                ? f.files
                : undefined;
    if (!value) throw Error('unexpected endpoint ' + endpoint);
    return JSON.stringify(args.includes('--paginate') ? [value] : value);
  };
}
module.exports = {fixture, mockGitHub, SHA, NEW_SHA};
