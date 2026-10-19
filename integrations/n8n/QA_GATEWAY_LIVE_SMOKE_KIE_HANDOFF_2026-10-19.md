# GremoVOD — n8n Gateway QA experiment and KIE migration
Date: 2026-10-19

## What was ACTUALLY tested (n8n Cloud)

Project: `jG7gkyrK2hH0rEBj`
Manual-only draft workflow: `2DllTVkrO6imk2IR`
Editor URL: https://gremovod.app.n8n.cloud/workflow/2DllTVkrO6imk2IR

- Two independent, short, SYNTHETIC TEXT review prompts, conceptually REVIEW-REQ / REVIEW-SYSTEM.
- Both nodes use `@n8n/n8n-nodes-langchain.googleGemini`, `models/gemini-3-flash-preview` and n8n **Gateway credits** automatically assigned by n8n (`source=aiGateway`, `googlePalmApi`).
- They do NOT invoke the separate saved n8n Agent drafts A6/A7 (those still reference a user's Anthropic credential).
- No tools, memory, schedules, publication, media inspection, canon mutation, or communication with local Studio FastAPI.
- Total initial experiment budget authorized by owner: no more than USD $0.50 worth of n8n promotional Gateway credits. Actual dollar balance/charges are only visible in n8n Cloud Gateway credits dashboard; metadata is not a billing statement.

### Real model executions

- Execution `19`: one model request; node success, but truncated response, `finishReason=MAX_TOKENS`. Token metadata: input 157, output 9. Diagnosed and revised low output cap.
- Execution `20`: two real n8n Gateway model requests; BOTH nodes completed successfully. A6 correctly rejected revealing the stretched limo in shot 1; A7 correctly rejected yellow vehicle conflicting with **synthetic test-only** aubergine lock. Both returned JSON `verdict=FAIL` with actual matching TEXT quotes; `source_scope=TEXT`.
- Execution `20` token metadata: REVIEW-REQ input 105 / output 77; REVIEW-SYSTEM input 121 / output 85; total input 226 + output 162 = **388 tokens** reported by n8n. Models can additionally account for reasoning/billing differences; do not infer exact USD cost from this alone.

### Mocked/free workflow tests (no provider calls)

- Execution `21`: pinned reviewer JSON, Code aggregation ran, `qa_transport_smoke_passed=true`.
- Execution `22`: A6 with fabricated evidence quote, A7 valid; aggregator returned `qa_transport_smoke_passed=false`.
- Aggregator always sets `source_is_approved=false`, `backend_evidence_verified=false`, `quality_claim=false`, `text_precheck_passed=false`, `all_passed=false`, `final_release_approved=false`, `auto_publish=false`.
- This is a **provider transport experiment**, not real creative canon approval or media verification. The main GremoVOD QA Orchestrator `nh3ARcl4XPW6RHqs` was not published or altered by these tests.

## KIE API transition: separate provider adapter

Official docs:
- https://docs.kie.ai/getting-started
- https://docs.kie.ai/ai-agent/overview
- https://docs.kie.ai/ai-agent/claude-code
- https://docs.kie.ai/market/gemini/gemini-3-flash

KIE supports multiple families over **different protocols/endpoints**. Do not assume a single universal URL or shared model ID:
- Claude Messages protocol: discover using authenticated `GET https://api.kie.ai/anthropic/v1/models` then requests to `POST https://api.kie.ai/anthropic/v1/messages`, only for the returned model IDs.
- Gemini 3 Flash OpenAI-compatible path: `POST https://api.kie.ai/gemini-3-flash/v1/chat/completions` (model availability and exact schema must be verified at integration time).
- All KIE requests require `Authorization: Bearer <KIE_API_KEY>`; credentials belong in a local secret store or n8n credential, **never in GitHub**.
- Some KIE APIs return an error envelope in a nominally HTTP 200 response. Parse provider error code/body, not HTTP status alone. Parse and persist actual `usage` and `credits_consumed` when available. Unknown billing state => BLOCKED; no blind retry.

Recommended implementation:
1. In FastAPI/GremoVOD define an interface `TextReviewerProvider` with a **server-frozen QA packet** input and a normalized provider result: `role, verdict, evidence, model, provider, request_id, token_usage, actual_cost_usd, error, source_revision`.
2. Keep A6 and A7 as separate isolated TEXT messages. Never provide one the other's answer or builder notes. Canon must come from the server-approved version, not arbitrary n8n JSON.
3. Implement two distinct adapters: `n8n_gateway_test` (only for the current cloud sandbox) and `kie_api` (future real provider). The normalized verdict validation, approval hashes, quote offset checks, cost cap, idempotency and release gates remain wholly on FastAPI.
4. KIE adapter requires a user-provisioned, verified KIE key and model listing before enabling real calls. Budget reservations and hard caps must be enforced server-side, and use only explicit opt-in for payment. Avoid double-charge retry after uncertain response.
5. Cloud n8n still cannot call loopback-only Windows FastAPI. Implement a separately security-reviewed **outbound local dispatcher** rather than opening the computer to the public internet.
6. Unpublishable until signed callbacks, exact source ID/version, provider cost checks, artifact evidence validation and owner approval work end to end.
7. A8 (Sonnet) remains disabled from real automatic invocation. Image/video/audio scopes remain BLOCKED without actual media inspection.

This document is a test report/design note, NOT authorization to spend more credits, publish n8n workflows, or merge into main.
