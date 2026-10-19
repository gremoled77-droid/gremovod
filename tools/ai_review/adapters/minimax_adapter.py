"""Адаптер MiniMax-M3.1-Flash через официальный OpenAI-совместимый API.

Endpoint: `POST https://api.minimax.io/v1/chat/completions`
Модель:   `MiniMax-M3.1-Flash`

Документированные коды ответа `base_resp.status_code`:
`1001` — таймаут, `1002` — частотный лимит, `1004` — ошибка авторизации,
`1008` — недостаточно баланса.

Правила, зафиксированные владельцем:

* используется **только** включённая квота M Plan (Subscription Key);
* credit packs и pay-as-you-go баланс не трогаются — запрос не уходит, если
  остаток не подтверждён или исчерпан;
* автоматических повторов нет;
* «M3.1-Flash всегда размышляет»: `thinking` должен быть `adaptive`
  (`disabled` для этой модели даёт ошибку 400), поэтому `reasoning_effort`
  ограничен `low`, а `max_completion_tokens` — небольшим значением.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Callable

from .. import quota as quota_guard
from ..payload import parse_review_response
from ..reviewer import ReviewOutcome, ReviewRequest

API_BASE_URL = "https://api.minimax.io"
CHAT_PATH = "/v1/chat/completions"
CHAT_URL = f"{API_BASE_URL}{CHAT_PATH}"
MODEL = "MiniMax-M3.1-Flash"

#: Окно подписки M Plan для этого ревьюера — до 25.10.2026 00:00 (+03:00).
EXPIRES_AT = quota_guard.MINIMAX_SUBSCRIPTION_EXPIRES_AT

#: Лимиты одного запроса: ревью — это короткий разбор, а не генерация проекта.
DEFAULT_MAX_COMPLETION_TOKENS = 2_000
DEFAULT_REASONING_EFFORT = "low"

#: `base_resp.status_code` → статус контракта.
_BASE_RESP_STATUS = {
    1001: "API_ERROR",  # таймаут
    1002: "API_ERROR",  # частотный лимит
    1004: "API_ERROR",  # ошибка авторизации
    1008: "QUOTA_EXHAUSTED",  # недостаточно баланса
}

#: Имя переменной окружения с Subscription Key (M Plan).
API_KEY_ENV = "MINIMAX_SUBSCRIPTION_KEY"


class MiniMaxReviewer:
    """Ревьюер на MiniMax-M3.1-Flash.

    Живой вызов возможен только при `mode=LIVE`, явном согласии владельца,
    действующем окне подписки и подтверждённом остатке квоты.
    """

    name = "minimax"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        consent: bool = False,
        quota_snapshot: quota_guard.QuotaSnapshot | None = None,
        transport: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        now: dt.datetime | None = None,
        model: str = MODEL,
        expires_at: str = EXPIRES_AT,
    ):
        self.api_key = api_key or os.environ.get(API_KEY_ENV, "")
        self.consent = consent
        self.quota_snapshot = quota_snapshot
        self.transport = transport or _http_transport
        self.max_completion_tokens = max_completion_tokens
        self.reasoning_effort = reasoning_effort
        self.now = now
        self.model = model
        self.expires_at = expires_at

    # -- публичный контракт -------------------------------------------------

    def review(self, request: ReviewRequest) -> ReviewOutcome:
        if request.mode != "LIVE":
            return ReviewOutcome(
                provider=self.name,
                reviewer_model=self.model,
                status="NOT_RUN",
                findings=[],
                usage=None,
                raw=None,
                error=None,
                blocked_reason=f"LIVE provider requires mode=LIVE, got {request.mode!r}",
            )

        decision = quota_guard.preflight(
            mode=request.mode,
            provider=self.name,
            consent=self.consent,
            credential_present=bool(self.api_key),
            now=self.now,
            quota=self.quota_snapshot,
            expires_at=self.expires_at,
        )
        if not decision.allowed:
            status = "QUOTA_EXHAUSTED" if decision.code == quota_guard.STOP_QUOTA_EXHAUSTED else "NOT_RUN"
            return ReviewOutcome(
                provider=self.name,
                reviewer_model=self.model,
                status=status,
                findings=[],
                usage=None,
                raw=None,
                error=None,
                blocked_reason=f"{decision.code}: {decision.reason}",
            )

        body = {
            "model": self.model,
            "messages": request.payload.get("messages") or [],
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning_effort": self.reasoning_effort,
            "thinking": {"type": "adaptive"},
            "stream": False,
        }

        try:
            payload = self.transport(CHAT_URL, body, self.api_key)
        except Exception as ex:  # noqa: BLE001 — ошибка транспорта = API_ERROR, без повторов
            return ReviewOutcome(
                provider=self.name,
                reviewer_model=self.model,
                status="API_ERROR",
                findings=[],
                usage=None,
                raw=None,
                error=f"transport failure ({type(ex).__name__}); no automatic retry",
                blocked_reason=None,
            )

        return self._interpret(payload)

    # -- разбор ответа ------------------------------------------------------

    def _interpret(self, payload: Any) -> ReviewOutcome:
        if not isinstance(payload, dict):
            return ReviewOutcome(
                provider=self.name,
                reviewer_model=self.model,
                status="API_ERROR",
                findings=[],
                usage=None,
                raw=None,
                error="provider response is not a JSON object",
            )

        base_resp = payload.get("base_resp")
        if isinstance(base_resp, dict):
            code = base_resp.get("status_code")
            if isinstance(code, int) and code != 0:
                status = _BASE_RESP_STATUS.get(code, "API_ERROR")
                return ReviewOutcome(
                    provider=self.name,
                    reviewer_model=self.model,
                    status=status,
                    findings=[],
                    usage=None,
                    raw=None,
                    error=f"base_resp.status_code={code} ({base_resp.get('status_msg', 'no message')})",
                )

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ReviewOutcome(
                provider=self.name,
                reviewer_model=self.model,
                status="API_ERROR",
                findings=[],
                usage=None,
                raw=None,
                error="provider response has no choices",
            )

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return ReviewOutcome(
                provider=self.name,
                reviewer_model=self.model,
                status="UNCERTAIN",
                findings=[],
                usage=None,
                raw=None,
                error="provider returned empty/non-text review",
            )

        status, findings, error = parse_review_response(content)
        usage = payload.get("usage")
        usage_norm = None
        if isinstance(usage, dict):
            usage_norm = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }

        return ReviewOutcome(
            provider=self.name,
            reviewer_model=self.model,
            status=status,
            findings=findings,
            usage=usage_norm,
            raw=content[:8000],
            error=error,
            blocked_reason=None,
        )


def _http_transport(url: str, body: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Единственное сетевое обращение к MiniMax в этом модуле."""
    import urllib.error
    import urllib.request

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=90) as response:
        return json.load(response)
