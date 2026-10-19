"""Охранник квоты M Plan и отсечки доступа.

Задача (Issue #27, временное расширение от 19.10): использовать **только**
включённую квоту M Plan. Credit packs и pay-as-you-go баланс трогать нельзя.

По официальной документации MiniMax (регион Global):

* Subscription Key расходует включённую квоту M Plan, а после её исчерпания —
  credit packs, затем баланс аккаунта (pay-as-you-go). Ключи не взаимозаменяемы.
* Квота живёт в двух окнах: 5-часовом и недельном (для не-видео моделей нужны оба).
* Остаток проверяется через `mmx quota`, страницу консоли или
  `GET https://www.minimax.io/v1/token_plan/remains`.

Значит «остаток не подтверждён» — это не «остаток есть», а повод остановиться.
Все проверки закрыты по умолчанию (fail closed) и не делают сетевых вызовов:
transport для проверки квоты передаётся снаружи и подменяется в тестах.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable

#: Отсечка доступа: все новые LIVE-вызовы MiniMax запрещены не позднее этого момента.
#: Время московское (+03:00), как зафиксировано в Issue #27.
MINIMAX_SUBSCRIPTION_EXPIRES_AT = "2026-10-25T00:00:00+03:00"

#: Официальный endpoint остатка подписки (Subscription Key в заголовке Authorization).
MINIMAX_QUOTA_URL = "https://www.minimax.io/v1/token_plan/remains"

#: Провайдеры, которым вообще разрешено ходить в сеть из этого пайплайна.
ALLOWED_PROVIDERS = ("minimax", "argon")

#: Коды остановки.
STOP_EXPIRED = "SUBSCRIPTION_EXPIRED"
STOP_QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
STOP_QUOTA_UNKNOWN = "QUOTA_UNKNOWN"
STOP_NO_CONSENT = "CONSENT_REQUIRED"
STOP_WRONG_MODE = "LIVE_MODE_REQUIRED"
STOP_PROVIDER_NOT_ALLOWED = "PROVIDER_NOT_ALLOWED"
STOP_CREDENTIAL_MISSING = "CREDENTIAL_MISSING"
STOP_OK = "OK"

_FIVE_HOUR_TOKENS = ("5h", "5hour", "5_hour", "five_hour", "fivehour", "5hourly")
_WEEKLY_TOKENS = ("week", "weekly", "7d", "7day", "seven_day", "sevenday")


@dataclass
class QuotaSnapshot:
    """Снимок остатка квоты.

    `recognized` = False, если схема ответа не распознана: в этом случае запрос
    запрещён, потому что подтвердить остаток не удалось.
    """

    source: str
    checked_at: str
    window_5h_remaining: float | None = None
    window_5h_limit: float | None = None
    weekly_remaining: float | None = None
    weekly_limit: float | None = None
    recognized: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "checked_at": self.checked_at,
            "window_5h_remaining": self.window_5h_remaining,
            "window_5h_limit": self.window_5h_limit,
            "weekly_remaining": self.weekly_remaining,
            "weekly_limit": self.weekly_limit,
            "recognized": self.recognized,
        }


@dataclass
class GuardDecision:
    """Решение охранника: можно ли выполнять запрос."""

    allowed: bool
    code: str
    reason: str
    expires_at: str
    quota: QuotaSnapshot | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "reason": self.reason,
            "expires_at": self.expires_at,
            "quota": self.quota.as_dict() if self.quota else None,
        }


def _normalize(text: str) -> str:
    return text.lower().replace("-", "_").replace(" ", "_")


def _walk_numbers(payload: Any, path: str = "") -> list[tuple[str, float]]:
    """Собрать все числовые листья ответа с путями до них."""
    found: list[tuple[str, float]] = []
    if isinstance(payload, bool):
        return found
    if isinstance(payload, (int, float)):
        found.append((path, float(payload)))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{path}.{key}" if path else str(key)
            found.extend(_walk_numbers(value, child))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_walk_numbers(value, f"{path}[{index}]"))
    return found


def _match_key(path: str, tokens: tuple[str, ...]) -> bool:
    normalized = _normalize(path)
    return any(token in normalized for token in tokens)


def parse_quota_payload(payload: Any, source: str = MINIMAX_QUOTA_URL) -> QuotaSnapshot:
    """Разобрать ответ `/v1/token_plan/remains`.

    Схема ответа не опубликована как стабильный контракт, поэтому разбор
    tolerant: ищем числовые поля, относящиеся к 5-часовому и недельному окнам.
    Если схема не распознана — `recognized=False`, и живой запрос запрещён.
    """
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    snapshot = QuotaSnapshot(source=source, checked_at=now, raw=payload if isinstance(payload, dict) else {})

    if not isinstance(payload, dict):
        return snapshot

    numbers = _walk_numbers(payload)
    five_hour: list[tuple[str, float]] = []
    weekly: list[tuple[str, float]] = []
    for path, value in numbers:
        if _match_key(path, _FIVE_HOUR_TOKENS):
            five_hour.append((path, value))
        elif _match_key(path, _WEEKLY_TOKENS):
            weekly.append((path, value))

    def pick(items: list[tuple[str, float]], remaining_markers: tuple[str, ...], limit_markers: tuple[str, ...]):
        remaining = None
        limit = None
        for path, value in items:
            if any(marker in _normalize(path) for marker in remaining_markers):
                if remaining is None:
                    remaining = value
            elif any(marker in _normalize(path) for marker in limit_markers):
                if limit is None:
                    limit = value
        if remaining is None and items:
            remaining = items[0][1]
        return remaining, limit

    remaining_5h, limit_5h = pick(five_hour, ("remain", "left", "available", "free"), ("total", "limit", "quota", "max"))
    remaining_week, limit_week = pick(weekly, ("remain", "left", "available", "free"), ("total", "limit", "quota", "max"))

    snapshot.window_5h_remaining = remaining_5h
    snapshot.window_5h_limit = limit_5h
    snapshot.weekly_remaining = remaining_week
    snapshot.weekly_limit = limit_week
    snapshot.recognized = remaining_5h is not None and remaining_week is not None
    return snapshot


def check_expiry(
    now: dt.datetime | None = None,
    expires_at: str = MINIMAX_SUBSCRIPTION_EXPIRES_AT,
) -> GuardDecision:
    """Отсечка доступа. После срока любой новый вызов запрещён."""
    now = now or dt.datetime.now(dt.timezone.utc)
    deadline = dt.datetime.fromisoformat(expires_at)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=dt.timezone.utc)
    if now >= deadline:
        return GuardDecision(
            allowed=False,
            code=STOP_EXPIRED,
            reason=f"M Plan access window closed at {expires_at}; new LIVE calls require a separate owner approval",
            expires_at=expires_at,
        )
    return GuardDecision(
        allowed=True,
        code=STOP_OK,
        reason=f"within access window (until {expires_at})",
        expires_at=expires_at,
    )


def evaluate_quota(
    snapshot: QuotaSnapshot,
    min_remaining: float = 0.0,
    expires_at: str = MINIMAX_SUBSCRIPTION_EXPIRES_AT,
) -> GuardDecision:
    """Оценить остаток квоты.

    Требуется остаток > min_remaining в обоих окнах. Иначе запрос ушёл бы в
    credit packs — а это прямо запрещено владельцем.
    """
    if not snapshot.recognized:
        return GuardDecision(
            allowed=False,
            code=STOP_QUOTA_UNKNOWN,
            reason="M Plan quota response shape is not recognized; failing closed to avoid touching credit packs",
            expires_at=expires_at,
            quota=snapshot,
        )

    for label, value in (
        ("5-hour window", snapshot.window_5h_remaining),
        ("weekly window", snapshot.weekly_remaining),
    ):
        if value is None:
            return GuardDecision(
                allowed=False,
                code=STOP_QUOTA_UNKNOWN,
                reason=f"M Plan quota: {label} remaining is unknown; failing closed",
                expires_at=expires_at,
                quota=snapshot,
            )
        if value <= min_remaining:
            return GuardDecision(
                allowed=False,
                code=STOP_QUOTA_EXHAUSTED,
                reason=(
                    f"M Plan quota exhausted in {label} (remaining={value}); "
                    "refusing the request so it cannot spill into credit packs or pay-as-you-go"
                ),
                expires_at=expires_at,
                quota=snapshot,
            )

    return GuardDecision(
        allowed=True,
        code=STOP_OK,
        reason="M Plan quota confirmed in both windows",
        expires_at=expires_at,
        quota=snapshot,
    )


def preflight(
    *,
    mode: str,
    provider: str,
    consent: bool,
    credential_present: bool,
    now: dt.datetime | None = None,
    quota: QuotaSnapshot | None = None,
    expires_at: str = MINIMAX_SUBSCRIPTION_EXPIRES_AT,
    min_remaining: float = 0.0,
) -> GuardDecision:
    """Полная проверка перед любым сетевым запросом ревьюера.

    Порядок проверок соответствует «закрыт по умолчанию»: сначала дешёвые и
    однозначные запреты, затем квота.
    """
    expiry = check_expiry(now=now, expires_at=expires_at)
    if not expiry.allowed:
        return expiry

    if provider not in ALLOWED_PROVIDERS:
        return GuardDecision(
            allowed=False,
            code=STOP_PROVIDER_NOT_ALLOWED,
            reason=f"provider {provider!r} is not allowed to perform network review calls",
            expires_at=expires_at,
            quota=quota,
        )

    if mode != "LIVE":
        return GuardDecision(
            allowed=False,
            code=STOP_WRONG_MODE,
            reason=f"network review calls require mode=LIVE, got {mode!r}",
            expires_at=expires_at,
            quota=quota,
        )

    if not consent:
        return GuardDecision(
            allowed=False,
            code=STOP_NO_CONSENT,
            reason="explicit owner consent for this exact request was not given",
            expires_at=expires_at,
            quota=quota,
        )

    if not credential_present:
        return GuardDecision(
            allowed=False,
            code=STOP_CREDENTIAL_MISSING,
            reason="Subscription Key is missing; no request sent",
            expires_at=expires_at,
            quota=quota,
        )

    if quota is None:
        return GuardDecision(
            allowed=False,
            code=STOP_QUOTA_UNKNOWN,
            reason="M Plan quota was not checked; failing closed to avoid touching credit packs",
            expires_at=expires_at,
            quota=None,
        )

    return evaluate_quota(quota, min_remaining=min_remaining, expires_at=expires_at)


def fetch_quota(
    api_key: str,
    transport: Callable[[str, str], dict[str, Any]] | None = None,
    timeout: int = 30,
) -> QuotaSnapshot:
    """Запросить остаток квоты M Plan.

    Требует Subscription Key (не pay-as-you-go ключ). Транспорт внедряется, чтобы
    офлайн-тесты не ходили в сеть.
    """
    if transport is None:
        transport = _urllib_transport
    try:
        payload = transport(MINIMAX_QUOTA_URL, api_key)
    except Exception as ex:  # noqa: BLE001 — любая ошибка означает «остаток неизвестен»
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        return QuotaSnapshot(source=MINIMAX_QUOTA_URL, checked_at=now, recognized=False, raw={"error": type(ex).__name__})
    return parse_quota_payload(payload)


def _urllib_transport(url: str, api_key: str) -> dict[str, Any]:
    """Сетевой транспорт остатка квоты. Единственное место с обращением к MiniMax."""
    import json
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        method="GET",
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
    with opener.open(request, timeout=30) as response:
        return json.load(response)
