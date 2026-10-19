# GremoVOD — secure connection gate A6/A7 (TEXT_PRECHECK)
19.10.2026 · implementation notes · **NOT a live AI integration**

## Verified starting point

- Branch `feature/qa-text-audit-fixes-20261019`, forked from `feature/qa-text-precheck-sandbox-20261019`.
- Sandbox QA uses real `backend.main.app` and real SQLite schemas in temporary test fixtures; mock reviewers only, models `mock-a6-v1` and `mock-a7-v1`; all cost and release flags remain false.
- Audit issues: current editor notes replace historical storyboard import; real `story_plan.Card` fields (`id`, `title`, `summary`, `change`, `stage`, `scene_id`, `character_ids`, `location_id`) are retained; stale source status and callback/bearer validation hardened.
- Never infer approved artistic canon from `canon_revision` alone: a hash binds a *snapshot*, not editorial approval. This sandbox uses an explicit owner approval to freeze project identity text; a future canon-specific approval version is still required.
- n8n Agent drafts: A6 `nkmWNxBdJcFEXSMF` (Haiku), A7 `NRWXr5AY2MXAFhcH` (Sonnet), A8 `s7IIGiioapxre90t` (Opus) all unpublished; A8 must remain disconnected.
- Existing workflow `nh3ARcl4XPW6RHqs` remains inactive / BLOCKED. `n8n-nodes-base.messageAnAgent` and its Tool counterpart are marked **deprecated/retired** by the connected n8n node schema; do not build a production dependency on either.

## Hard blocker: network topology

Cloud n8n cannot access GremoVOD's *loopback-only* sandbox service route.
Do not open the Windows FastAPI port on the internet, do not put bearer secrets
in GitHub, and do not claim the existing n8n Cloud QA workflow is connected.

Safe next transport options (pick one and test separately):
1. **Outbound local dispatch worker (preferred for Windows local-first).**
   A local FastAPI-adjacent process claims one authorized task over loopback and
   delivers only the role-scoped signed packet to a trusted n8n HTTPS endpoint.
   It keeps token and callback credentials on the local host, verifies endpoint
   TLS, binds requests to task/execution/revision/nonce, and sends checked results
   back to FastAPI via loopback; never lets n8n write SQLite or approve canon.
   This still needs a verified supported n8n *saved Agent invocation mechanism*.
2. **Trusted HTTPS reverse-proxy to a cloud-deployed backend.**
   Requires scoped authentication, correctly configured Host/Origin/TLS, per-project
   rate limits, short-lived session credentials, replay protection, and a dedicated
   external review of the service gate before moving past loopback. Not supported
   by the current sandbox.

## Required fail-closed server-side contract before LIVE models

- Reviewer task is tied to immutable `approval_id`, source/reviewer role,
  artifact/brief/canon revision, text SHA, model ID and pinned skill SHA.
- Every reviewer receives an isolated fresh conversation: A6 only requirements
  and the finished text; A7 only owner-approved canon rules and the same finished
  text. No builder transcript or other critic's result.
- `A6` and `A7` each need an explicit **server-stored** cost authorization,
  unique reservation/callback idempotency key, actual usage/billing record, hard
  caps, and treatment of ambiguous provider failure as BLOCKED (no auto-retry).
  Client-supplied or LLM-supplied `approved=true` or `verified=true` is ignored.
- Verify that an approved canonical ruleset version exists before live A7.
  The current editable `projects.state.characters[].identity` data alone
  does not prove that rules have been artistically approved.
- Machine-check JSON schema and exact quote spans against frozen server text.
  A TEXT receipt cannot confer IMAGE/VIDEO/AUDIO PASS; A8 cannot run until
  reviewed actual media, coverage evidence, and independent server cost approval.
- On stale inputs, return 409 and create new review round; historical verdicts
  are preserved, but never shown as current. An A6 Haiku provider error should
  return BLOCKED/ERROR and must never be retried without explicit cost policy.
- Independent owner acceptance after reviewer success is mandatory. No automatic
  changes to Character Vault, media generations, or publication.

## Testing order (no paid AI)

1. Keep existing `qa_text_precheck` mock-only, test complete FastAPI/SQLite path
   on temporary data with provider functions patched to error on any outbound call.
2. Prototype the transport on a local fake HTTPS webhook, with signed packets,
   unique execution IDs, role isolation, invalid input, out-of-order callbacks,
   replay attempts and stale source failures. Never enable live provider node.
3. Validate the supported n8n Agents invocation path without calling any paid
   model; if none exists, stop and explicitly plan an alternative (dedicated
   LangChain workflow agents do **not** inherit the saved n8n Agent skills).
4. Check actual A6/A7 provider billing, model availability and retry semantics.
   Obtain the owner's separate consent for specific cost caps before any live call.
5. After green tests, connect `TEXT_PRECHECK` only and retain `FINAL_MEDIA`
   and all release approvals as BLOCKED.

## Acceptance gate

A successful GitHub CI run proves code compatibility in sandbox. It does not
prove real saved Agents can be invoked or guarantee provider billing stops.
A8/Opus, paid calls, public webhook publication, and main merge are OUT OF SCOPE
until separate explicit authorization.
