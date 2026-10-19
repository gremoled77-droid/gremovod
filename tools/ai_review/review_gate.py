#!/usr/bin/env python3
"""Budget gate between a Git diff and the KIE Gemini 4 Argon chat route.

Everything that costs money is decided here, in code, not in a prompt:

  * OFFLINE is the default. Without an explicit mode, key, budget policy and
    owner approval no socket is ever opened.
  * One Argon call per PR/head_sha/payload, 2 per day, 5 per week, 1 at a time.
  * The reservation is written to a locked ledger BEFORE the HTTP call, so a
    hang or a crash still holds the limit instead of releasing it.
  * Retries are not configurable. A 429, a 5xx or a timeout ends the run with
    HALTED_UNKNOWN and spends nothing extra.
  * Credits are accounted, never converted to money: the tariff is unknown, so
    usd_amount stays null and the owner sets the credit ceilings.

The provider and the balance reader are injectable, which is what keeps the
whole test-suite offline.
"""
import argparse
import contextlib
import datetime as dt
import json
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import argon_review  # noqa: E402
import build_review_packet as packets  # noqa: E402

STATUS_OFFLINE = "OFFLINE"
STATUS_PENDING_APPROVAL = "PENDING_APPROVAL"
STATUS_PASS = "PASS"
STATUS_FINDINGS = "FINDINGS"
STATUS_BLOCKED = "BLOCKED"
STATUS_HALTED_UNKNOWN = "HALTED_UNKNOWN"

ALL_STATUSES = (STATUS_OFFLINE, STATUS_PENDING_APPROVAL, STATUS_PASS, STATUS_FINDINGS,
                STATUS_BLOCKED, STATUS_HALTED_UNKNOWN)

VERDICT_MAP = {
    "PASS": STATUS_PASS,
    "FINDINGS": STATUS_FINDINGS,
    "NEED_CONTEXT": STATUS_BLOCKED,
    "UNSURE": STATUS_HALTED_UNKNOWN,
}
VERDICTS = tuple(VERDICT_MAP)
MAX_FINDINGS = 20
BEARER = re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.I)

LEDGER_SCHEMA = "gremovod/argon-ledger/1"
_PROCESS_LOCK = threading.RLock()


class GateError(Exception):
    """The gate refused to continue. Always ends in a named status."""

    def __init__(self, message: str, status: str = STATUS_BLOCKED, reason: str = "blocked"):
        super().__init__(message)
        self.status = status
        self.reason = reason


@dataclass
class Policy:
    """Hard limits. The credit ceilings have no default on purpose."""

    max_calls_per_pr: int = 1
    max_calls_per_day: int = 2
    max_calls_per_week: int = 5
    max_concurrent: int = 1
    max_packet_bytes: int = 6144
    max_packet_files: int = 4
    retry_count: int = 0
    max_kie_credits_per_day: float | None = None
    max_kie_credits_per_call: float | None = None
    min_kie_balance: float | None = None
    credit_delta_tolerance: float = 1.0
    stale_call_seconds: int = 900
    env_source: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, env=None) -> "Policy":
        env = os.environ if env is None else env
        source: dict = {}

        def as_int(name, default):
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                source[name] = default
                return default
            try:
                value = int(raw)
            except ValueError:
                raise GateError(f"{name} is not an integer", reason="bad_policy")
            source[name] = value
            return value

        def as_float(name):
            raw = env.get(name)
            if raw is None or raw.strip() == "":
                source[name] = None
                return None
            try:
                value = float(raw)
            except ValueError:
                raise GateError(f"{name} is not a number", reason="bad_policy")
            source[name] = value
            return value

        retry = as_int("ARGON_RETRY_COUNT", 0)
        if retry != 0:
            raise GateError("Retries are not allowed: ARGON_RETRY_COUNT must stay 0", reason="retry_not_allowed")
        tolerance = as_float("ARGON_CREDIT_DELTA_TOLERANCE")
        return cls(
            max_calls_per_pr=as_int("ARGON_MAX_CALLS_PER_PR", 1),
            max_calls_per_day=as_int("ARGON_MAX_CALLS_PER_DAY", 2),
            max_calls_per_week=as_int("ARGON_MAX_CALLS_PER_WEEK", 5),
            max_concurrent=as_int("ARGON_MAX_CONCURRENT", 1),
            max_packet_bytes=as_int("ARGON_MAX_PACKET_BYTES", 6144),
            max_packet_files=as_int("ARGON_MAX_PACKET_FILES", 4),
            retry_count=0,
            max_kie_credits_per_day=as_float("ARGON_MAX_KIE_CREDITS_PER_DAY"),
            max_kie_credits_per_call=as_float("ARGON_MAX_KIE_CREDITS_PER_CALL"),
            min_kie_balance=as_float("ARGON_MIN_KIE_BALANCE"),
            credit_delta_tolerance=1.0 if tolerance is None else tolerance,
            env_source=source,
        )


def _verdict_text(parsed: dict, content: str) -> str:
    """Short human-readable verdict line. The raw answer never goes into a report."""
    verdict = parsed.get("verdict")
    if verdict:
        findings = parsed.get("findings") or []
        requested = parsed.get("requested_context") or []
        return (f"verdict: {verdict}; findings: {len(findings)}; "
                f"requested_context: {len(requested)}")
    return redact_free_text((content or "")[:300]) or "(no usable answer)"


def redact(text: str) -> str:
    """Never let a credential-shaped string reach a committable report."""
    if not text:
        return ""
    return BEARER.sub("Bearer [REDACTED]", argon_review.SECRET.sub("[REDACTED]", text))


TOKENISH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9_]{20,}(?![A-Za-z0-9_])")


def redact_free_text(text: str) -> str:
    """Redact provider-authored prose: secrets plus long opaque token shapes.

    Pure hex strings are kept: they are git SHAs and digests, not credentials.
    """
    if not text:
        return ""
    cleaned = redact(text)

    def _mask(match: re.Match) -> str:
        token = match.group(0)
        if re.fullmatch(r"[0-9a-f]{32,}", token):
            return token
        if not any(ch.isdigit() for ch in token):
            return token
        if not any(ch.isupper() for ch in token):
            return token
        return "[REDACTED]"

    return TOKENISH.sub(_mask, cleaned)


# --------------------------------------------------------------------------- ledger


@contextlib.contextmanager
def _file_lock(path: Path):
    """Cross-process exclusive lock. Windows uses msvcrt, POSIX uses fcntl."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            except OSError as ex:
                raise GateError(f"Cannot acquire ledger lock: {ex}", reason="ledger_locked") from None
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


class Ledger:
    """Append-only JSON ledger guarded by a file lock.

    Reservations are written before the HTTP call. An entry that never gets
    finalized still holds its slot, so a hang cannot be turned into a retry.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _read(self) -> dict:
        if not self.path.exists():
            return {"schema": LEDGER_SCHEMA, "entries": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as ex:
            # Fail closed: a broken ledger must never look like an empty one,
            # otherwise a corrupted file would silently reset the limits.
            raise GateError(f"Ledger is unreadable: {ex}", reason="ledger_corrupted") from None
        if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
            raise GateError("Ledger has an unexpected shape", reason="ledger_corrupted")
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, self.path)

    @contextlib.contextmanager
    def _locked(self):
        with _PROCESS_LOCK:
            with _file_lock(self.lock_path):
                yield

    def entries(self) -> list[dict]:
        with self._locked():
            return list(self._read()["entries"])

    def reserve(self, record: dict, policy: Policy, now: dt.datetime) -> tuple[bool, str]:
        """Atomically decide whether one more paid call is allowed."""
        with self._locked():
            data = self._read()
            entries = data["entries"]
            repo, pr = record["repo"], record["pr"]

            per_pr = [e for e in entries if e.get("repo") == repo and e.get("pr") == pr]
            if len(per_pr) >= policy.max_calls_per_pr:
                return False, f"no_new_call: PR limit {policy.max_calls_per_pr} reached"

            today = now.date()
            per_day = [e for e in entries if _entry_day(e) == today]
            if len(per_day) >= policy.max_calls_per_day:
                return False, f"no_new_call: daily limit {policy.max_calls_per_day} reached"

            week_ago = now - dt.timedelta(days=7)
            per_week = [e for e in entries if _entry_time(e) is not None and _entry_time(e) >= week_ago]
            if len(per_week) >= policy.max_calls_per_week:
                return False, f"no_new_call: weekly limit {policy.max_calls_per_week} reached"

            if policy.max_kie_credits_per_day is not None and policy.max_kie_credits_per_call is not None:
                spent = sum(float(e.get("credits_consumed") or 0.0) for e in per_day)
                if spent + policy.max_kie_credits_per_call > policy.max_kie_credits_per_day:
                    return False, (f"no_new_call: daily credit ceiling "
                                   f"{policy.max_kie_credits_per_day} would be exceeded")

            key = (repo, pr, record["head_sha"], record["payload_sha256"])
            for entry in entries:
                if (entry.get("repo"), entry.get("pr"), entry.get("head_sha"),
                        entry.get("payload_sha256")) == key:
                    return False, "no_new_call: this PR/SHA/payload was already submitted"

            data["entries"].append(record)
            self._write(data)
            return True, "reserved"

    def finalize(self, entry_id: str, updates: dict) -> None:
        with self._locked():
            data = self._read()
            for entry in data["entries"]:
                if entry.get("id") == entry_id:
                    entry.update(updates)
                    break
            self._write(data)

    def credits_spent_today(self, now: dt.datetime) -> float:
        today = now.date()
        return sum(float(e.get("credits_consumed") or 0.0) for e in self.entries()
                   if _entry_day(e) == today)


def _entry_time(entry: dict) -> dt.datetime | None:
    raw = entry.get("ts_utc")
    if not isinstance(raw, str):
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _entry_day(entry: dict) -> dt.date | None:
    moment = _entry_time(entry)
    return moment.date() if moment else None


# --------------------------------------------------------------------------- concurrency


class ConcurrencyGuard:
    """At most `max_concurrent` live calls. Slots are created with O_EXCL."""

    def __init__(self, directory: Path, max_concurrent: int = 1, stale_seconds: int = 900):
        self.directory = Path(directory)
        self.max_concurrent = max_concurrent
        self.stale_seconds = stale_seconds

    def _prune(self, now: float) -> None:
        if not self.directory.exists():
            return
        for slot in self.directory.glob("slot-*.json"):
            try:
                age = now - slot.stat().st_mtime
            except OSError:
                continue
            if age > self.stale_seconds:
                with contextlib.suppress(OSError):
                    slot.unlink()

    def acquire(self, now: float | None = None) -> tuple[str | None, str]:
        """Take a free slot. Returns (token, reason); token is None when full."""
        now = time.time() if now is None else now
        self.directory.mkdir(parents=True, exist_ok=True)
        self._prune(now)
        for index in range(self.max_concurrent):
            slot = self.directory / f"slot-{index}.json"
            try:
                fd = os.open(str(slot), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                continue
            except OSError:
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps({"pid": os.getpid(), "started": now}))
            return f"slot-{index}", "acquired"
        return None, f"no_new_call: concurrency limit {self.max_concurrent} reached"

    def release(self, token: str | None) -> None:
        if not token or not isinstance(token, str):
            return
        with contextlib.suppress(OSError):
            (self.directory / f"{token}.json").unlink()


# --------------------------------------------------------------------------- approval


def load_approval(path: Path | None) -> dict | None:
    if not path:
        return None
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def canonical_pr(pr_url: str) -> str:
    """One spelling per PR. The ledger key must not depend on a trailing slash."""
    return (pr_url or "").strip().rstrip("/")


def approval_matches(approval: dict, pr_url: str, head_sha: str) -> tuple[bool, str]:
    """One-time approval bound to a PR and a SHA. A new commit invalidates it."""
    if not approval:
        return False, "approval_missing"
    if approval.get("approved") is not True:
        return False, "approval_missing"
    approved_pr = canonical_pr(str(approval.get("pr", "")))
    if approved_pr != canonical_pr(pr_url):
        return False, "approval_stale: approval is for another PR"
    approved_sha = str(approval.get("head_sha", "")).strip()
    if not approved_sha:
        return False, "approval_stale: approval does not name a head_sha"
    if approved_sha != head_sha:
        return False, "approval_stale: approval is for another head_sha"
    return True, "approved"


# --------------------------------------------------------------------------- verdict


def parse_verdict(content: str) -> tuple[str, dict]:
    """Map the Argon answer to a status. Invalid JSON is never PASS."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return STATUS_HALTED_UNKNOWN, {"reason": "response_not_json", "raw": text[:400]}
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return STATUS_HALTED_UNKNOWN, {"reason": "response_not_json", "raw": text[:400]}
    if not isinstance(data, dict):
        return STATUS_HALTED_UNKNOWN, {"reason": "response_not_json"}

    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in VERDICTS:
        return STATUS_HALTED_UNKNOWN, {"reason": "unknown_verdict", "raw": text[:400]}

    findings = []
    raw_findings = data.get("findings")
    if raw_findings is not None and not isinstance(raw_findings, list):
        return STATUS_HALTED_UNKNOWN, {"reason": "response_not_json", "raw": text[:400]}
    for item in (raw_findings or [])[:MAX_FINDINGS]:
        if not isinstance(item, dict):
            continue
        findings.append({
            "severity": str(item.get("severity", ""))[:8],
            "path": str(item.get("path", ""))[:200],
            "line": item.get("line") if isinstance(item.get("line"), int) else None,
            "evidence": str(item.get("evidence", ""))[:400],
            "fix": str(item.get("fix", ""))[:400],
            "test": str(item.get("test", ""))[:200],
        })
    requested = []
    raw_requested = data.get("requested_context")
    if raw_requested is not None and not isinstance(raw_requested, list):
        return STATUS_HALTED_UNKNOWN, {"reason": "response_not_json", "raw": text[:400]}
    for item in (raw_requested or [])[:MAX_FINDINGS]:
        if not isinstance(item, dict):
            continue
        requested.append({
            "path": str(item.get("path", ""))[:200],
            "lines": str(item.get("lines", ""))[:80],
            "reason": str(item.get("reason", ""))[:300],
        })
    if verdict == "PASS" and findings:
        # A clean verdict next to a list of findings is not a conclusion we can verify.
        return STATUS_HALTED_UNKNOWN, {"reason": "contradictory_verdict", "verdict": verdict,
                                       "findings": findings, "requested_context": requested,
                                       "raw": text[:400]}
    return VERDICT_MAP[verdict], {"verdict": verdict, "findings": findings, "requested_context": requested}


# --------------------------------------------------------------------------- report


def render_report(outcome: dict) -> str:
    """Sanitized report. Contains no diff text, no credentials, no key."""
    status = outcome.get("status", STATUS_HALTED_UNKNOWN)
    lines = [
        "# GremoVOD — Argon (KIE) review report",
        "",
        f"- Status: **{status}**",
        f"- Reason: `{outcome.get('reason', '-')}`",
        f"- Mode: {outcome.get('mode', '-')}",
        f"- Date UTC: {outcome.get('now_utc', '-')}",
        f"- Repo: {outcome.get('repo', '-')}",
        f"- PR: {outcome.get('pr_url', '-') or '-'}",
        f"- base_sha: `{outcome.get('base_sha', '-')}`",
        f"- head_sha: `{outcome.get('head_sha', '-')}`",
        f"- diff_sha256: `{outcome.get('diff_sha256', '-')}`",
        f"- payload_sha256: `{outcome.get('payload_sha256', '-')}`",
        f"- payload bytes: {outcome.get('payload_bytes', '-')} / {outcome.get('max_payload_bytes', '-')}",
        f"- Network calls: {outcome.get('network_calls', 0)}",
        f"- Ledger entry: `{outcome.get('ledger_id') or '-'}`",
        "",
    ]
    selection = outcome.get("selection") or {}
    if selection:
        lines += [
            "## Packet scope",
            "",
            f"- Changed files: {selection.get('changed_files_total', '-')}",
            f"- Files in packet: {', '.join(selection.get('files_included', [])) or '-'}",
            f"- Files omitted: {', '.join(selection.get('files_omitted', [])) or '-'}",
            f"- Hunks in packet: {selection.get('hunks_included', '-')}",
            "",
        ]
    tests = outcome.get("tests") or []
    if tests:
        lines += ["## Tests reported by the author (untrusted)", ""]
        for test in tests:
            lines.append(f"- `{test.get('command', '-')}` — status {test.get('status', '-')}, "
                         f"exit code {test.get('exit_code', '-')}")
        lines.append("")
    lines += ["## Verdict", "", str(outcome.get("verdict_text") or outcome.get("message") or "-"), ""]
    findings = outcome.get("findings") or []
    if findings:
        lines += ["## Findings", ""]
        for item in findings:
            where = f"{item.get('path', '?')}:{item.get('line')}" if item.get("line") else item.get("path", "?")
            lines.append(f"- **{item.get('severity', '-')}** `{where}`")
            if item.get("evidence"):
                lines.append(f"  - evidence: {redact_free_text(item['evidence'])}")
            if item.get("fix"):
                lines.append(f"  - fix: {redact_free_text(item['fix'])}")
            if item.get("test"):
                lines.append(f"  - test: {redact_free_text(item['test'])}")
        lines.append("")
    requested = outcome.get("requested_context") or []
    if requested:
        lines += ["## Requested context (Level B, needs a separate owner approval)", ""]
        for item in requested:
            lines.append(f"- `{redact_free_text(item.get('path', '?'))}` lines "
                         f"`{redact_free_text(item.get('lines', '?'))}` — "
                         f"{redact_free_text(item.get('reason', ''))}")
        lines.append("")
    credits = outcome.get("credits") or {}
    lines += [
        "## Spend accounting",
        "",
        f"- credits_before: `{credits.get('credits_before')}`",
        f"- credits_after: `{credits.get('credits_after')}`",
        f"- credits_consumed: `{credits.get('credits_consumed')}`",
        f"- credits_reported_by_provider: `{credits.get('credits_reported')}`",
        f"- usd_amount: `{credits.get('usd_amount')}` (credits are not USD; no confirmed tariff)",
        f"- accounting: `{credits.get('accounting')}`",
        "",
        "---",
        "",
        "Argon PASS is not a test PASS and is not a permission to merge. The owner decides.",
        "",
    ]
    return redact("\n".join(lines))


# --------------------------------------------------------------------------- gate


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _is_inside(inner: Path, outer: Path) -> bool:
    """True when `inner` lives inside `outer`."""
    try:
        inner = Path(inner).resolve()
        outer = Path(outer).resolve()
    except OSError:
        return False
    try:
        inner.relative_to(outer)
        return True
    except ValueError:
        return False


def _default_state_dir() -> Path:
    env = os.environ.get("ARGON_REVIEW_STATE_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".gremovod" / "argon-review"


def _stop_requested(state_dir: Path) -> bool:
    if os.environ.get("ARGON_EMERGENCY_STOP", "").strip() not in ("", "0", "false", "False"):
        return True
    return (state_dir / "STOP").exists()


def _new_outcome(repo: Path, pr_url: str, mode: str, now: dt.datetime, policy: Policy,
                 tests: list[dict] | None) -> dict:
    return {
        "status": STATUS_OFFLINE,
        "reason": "-",
        "message": "",
        "mode": "LIVE" if str(mode).lower() == "live" else "OFFLINE",
        "now_utc": now.isoformat(timespec="seconds"),
        "repo": packets.repo_slug(repo),
        "repo_path": str(repo),
        "pr_url": pr_url,
        "network_calls": 0,
        "ledger_id": None,
        "payload_bytes": 0,
        "max_payload_bytes": policy.max_packet_bytes,
        "findings": [],
        "requested_context": [],
        "verdict_text": "",
        "credits": {"credits_before": None, "credits_after": None, "credits_consumed": None,
                    "usd_amount": None, "accounting": "NOT_APPLICABLE"},
        "tests": tests or [],
    }


def run(*, repo: Path, base: str, head: str, pr_url: str, task_id: str, scope: str,
        summary: str = "", tests: list[dict] | None = None, links: list[str] | None = None,
        mode: str = "offline", policy: Policy | None = None, state_dir: Path | None = None,
        approval_path: Path | None = None, expected_head_sha: str | None = None,
        provider=None, credits_reader=None, api_key: str | None = None,
        now: dt.datetime | None = None) -> dict:
    """Run the gate. Returns an outcome dict; never raises for expected refusals.

    The raw packet snapshot is written to the local state directory on every
    path, including the offline one, so the owner can inspect exactly what
    would have been sent.
    """
    state_dir = Path(state_dir) if state_dir else _default_state_dir()
    now = now or _now()
    try:
        policy = policy or Policy.from_env()
        outcome = _run(repo=repo, base=base, head=head, pr_url=pr_url, task_id=task_id, scope=scope,
                       summary=summary, tests=tests, links=links, mode=mode, policy=policy,
                       state_dir=state_dir, approval_path=approval_path,
                       expected_head_sha=expected_head_sha, provider=provider,
                       credits_reader=credits_reader, api_key=api_key, now=now)
    except GateError as ex:
        outcome = _new_outcome(repo, pr_url, mode, now, policy or Policy(), tests)
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = ex.reason
        outcome["message"] = str(ex)
    _write_local_artifacts(state_dir, outcome)
    return outcome


def _run(*, repo: Path, base: str, head: str, pr_url: str, task_id: str, scope: str,
         summary: str = "", tests: list[dict] | None = None, links: list[str] | None = None,
         mode: str = "offline", policy: Policy | None = None, state_dir: Path | None = None,
         approval_path: Path | None = None, expected_head_sha: str | None = None,
         provider=None, credits_reader=None, api_key: str | None = None,
         now: dt.datetime | None = None) -> dict:
    now = now or _now()
    state_dir = Path(state_dir) if state_dir else _default_state_dir()
    policy = policy or Policy.from_env()
    provider = provider or argon_review.ask_argon_detailed
    credits_reader = credits_reader or argon_review.fetch_credits
    api_key = api_key if api_key is not None else os.environ.get("KIE_API_KEY", "").strip()
    pr_url = canonical_pr(pr_url)

    outcome: dict = _new_outcome(repo, pr_url, mode, now, policy, tests)

    ledger = Ledger(state_dir / "ledger.json")
    guard = ConcurrencyGuard(state_dir / "inflight", policy.max_concurrent, policy.stale_call_seconds)

    # The raw packet snapshot must never land inside the repository.
    if _is_inside(state_dir, repo):
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "state_dir_inside_repo"
        outcome["message"] = ("The state directory is inside the repository. Move it outside "
                              "(ARGON_REVIEW_STATE_DIR) so the raw packet is never committed.")
        return outcome

    # ---- packet (never networked) -------------------------------------------
    try:
        packet = packets.build_packet(
            repo, base, head, pr_url=pr_url, task_id=task_id, scope=scope, summary=summary,
            tests=tests or [], links=links or [],
            max_files=policy.max_packet_files, max_payload_bytes=policy.max_packet_bytes,
        )
    except packets.PacketError as ex:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = ex.reason
        outcome["message"] = str(ex)
        return outcome
    except argon_review.ReviewError as ex:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "unsafe_diff"
        outcome["message"] = str(ex)
        return outcome

    payload = packets.packet_user_payload(packet)
    payload_bytes = len(payload.encode("utf-8"))
    payload_sha = packets.packet_digest(packet)
    outcome.update({
        "base_sha": packet["base_sha"],
        "head_sha": packet["head_sha"],
        "diff_sha256": packet["diff_sha256"],
        "payload_bytes": payload_bytes,
        "payload_sha256": payload_sha,
        "selection": packet["selection"],
        "packet": packet,
        # The public repo slug goes into the report; the local path stays out of it.
        "repo": packet["repo"],
        "repo_path": str(repo),
    })

    if payload_bytes > policy.max_packet_bytes:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "packet_too_large"
        outcome["message"] = f"user payload {payload_bytes} > {policy.max_packet_bytes} bytes"
        return outcome

    if expected_head_sha and expected_head_sha.strip() and expected_head_sha.strip() != packet["head_sha"]:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "pr_head_drift"
        outcome["message"] = (f"head_sha moved to {packet['head_sha']} while the approval named "
                              f"{expected_head_sha.strip()}")
        return outcome

    if outcome["mode"] == "OFFLINE":
        outcome["status"] = STATUS_OFFLINE
        outcome["reason"] = "offline_mode"
        outcome["message"] = "Packet built locally. No provider request was made."
        outcome["verdict_text"] = "No Argon call was made. This is an offline preview, not a review."
        return outcome

    # ---- LIVE gates ---------------------------------------------------------
    if _stop_requested(state_dir):
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "emergency_stop"
        outcome["message"] = "Emergency stop is active; no provider request was made."
        return outcome

    if not api_key:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "no_api_key"
        outcome["message"] = "KIE_API_KEY is missing; no provider request was made."
        return outcome

    if (policy.max_kie_credits_per_day is None or policy.max_kie_credits_per_call is None
            or policy.min_kie_balance is None):
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "no_budget_policy"
        outcome["message"] = ("LIVE needs ARGON_MAX_KIE_CREDITS_PER_DAY, ARGON_MAX_KIE_CREDITS_PER_CALL "
                              "and ARGON_MIN_KIE_BALANCE set by the owner; no provider request was made.")
        return outcome

    approval = load_approval(approval_path)
    approved, approval_reason = approval_matches(approval, pr_url, packet["head_sha"])
    if not approved:
        outcome["status"] = STATUS_PENDING_APPROVAL
        outcome["reason"] = approval_reason
        outcome["message"] = "Owner approval for this PR/SHA is missing or stale; no provider request was made."
        return outcome

    if packet["worktree"]["dirty_tracked"]:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "dirty_worktree"
        outcome["message"] = "Tracked files are modified locally; the approved SHA is not what is on disk."
        return outcome

    # Balance before the call. This GET is not a paid generation.
    credits_before = credits_reader(api_key)
    outcome["credits"]["credits_before"] = credits_before
    if credits_before is None:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "balance_unknown"
        outcome["message"] = "KIE credit balance could not be read; refusing to spend blindly."
        return outcome
    if credits_before < policy.min_kie_balance:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "insufficient_balance"
        outcome["message"] = (f"balance {credits_before} is below the owner floor "
                              f"{policy.min_kie_balance}; no provider request was made.")
        return outcome
    if credits_before - policy.max_kie_credits_per_call < policy.min_kie_balance:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = "insufficient_balance"
        outcome["message"] = (f"balance {credits_before} minus the per-call ceiling "
                              f"{policy.max_kie_credits_per_call} is below the owner floor "
                              f"{policy.min_kie_balance}; no provider request was made.")
        return outcome

    # Concurrency slot first: a clean refusal must not consume a ledger slot.
    slot, slot_reason = guard.acquire()
    if not slot:
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = slot_reason
        outcome["message"] = "Another Argon call is already in flight; no provider request was made."
        return outcome

    # Reserve before the HTTP call. Everything above this line is free.
    entry_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    record = {
        "id": entry_id,
        "ts_utc": now.isoformat(timespec="seconds"),
        "repo": packet["repo"],
        "pr": pr_url,
        "base_sha": packet["base_sha"],
        "head_sha": packet["head_sha"],
        "payload_sha256": payload_sha,
        "diff_sha256": packet["diff_sha256"],
        "mode": "LIVE",
        "state": "RESERVED",
        "status": None,
        "reason": None,
        "credits_before": credits_before,
        "credits_after": None,
        "credits_consumed": None,
        "usd_amount": None,
        "http_status": None,
    }
    try:
        allowed, why = ledger.reserve(record, policy, now)
    except GateError:
        guard.release(slot)
        raise
    if not allowed:
        guard.release(slot)
        outcome["status"] = STATUS_BLOCKED
        outcome["reason"] = why
        outcome["message"] = "A limit or a duplicate stopped the call before any request was made."
        return outcome
    outcome["ledger_id"] = entry_id

    try:
        messages = packets.make_packet_prompt(packet)
        # The request is going out now: count it even if the provider fails.
        outcome["network_calls"] = 1
        try:
            result = provider(messages, api_key)
        except argon_review.ProviderError as ex:
            status, reason = _provider_failure(ex)
            outcome["status"] = status
            outcome["reason"] = reason
            outcome["message"] = f"{ex} (no automatic retry)"
            ledger.finalize(entry_id, {"state": "COMPLETED", "status": status, "reason": reason,
                                       "http_status": ex.status})
            return outcome
        except argon_review.ReviewError as ex:
            outcome["status"] = STATUS_HALTED_UNKNOWN
            outcome["reason"] = "provider_error"
            outcome["message"] = f"{ex} (no automatic retry)"
            ledger.finalize(entry_id, {"state": "COMPLETED", "status": STATUS_HALTED_UNKNOWN,
                                       "reason": "provider_error"})
            return outcome

        content = result.get("content") if isinstance(result, dict) else ""
        status, parsed = parse_verdict(content)
        outcome["findings"] = parsed.get("findings", [])
        outcome["requested_context"] = parsed.get("requested_context", [])
        outcome["verdict_text"] = _verdict_text(parsed, content)
        outcome["raw_answer"] = content
        if status == STATUS_HALTED_UNKNOWN:
            outcome["reason"] = parsed.get("reason") or (
                "model_unsure" if parsed.get("verdict") == "UNSURE" else "unverifiable_answer")
        elif status == STATUS_BLOCKED and parsed.get("verdict") == "NEED_CONTEXT":
            outcome["reason"] = "need_context"

        credits_after = credits_reader(api_key)
        reported = result.get("credits_consumed") if isinstance(result, dict) else None
        accounting, note, consumed = _account(credits_before, credits_after, reported, policy)
        outcome["credits"].update({
            "credits_after": credits_after,
            "credits_consumed": consumed,
            "credits_reported": reported,
            "usd_amount": None,
            "accounting": accounting,
        })
        if status in (STATUS_PASS, STATUS_FINDINGS) and accounting != "OK":
            status = STATUS_HALTED_UNKNOWN
            outcome["reason"] = "credit_accounting_mismatch"
            outcome["message"] = note
        elif status in (STATUS_PASS, STATUS_FINDINGS):
            outcome["reason"] = "-"

        ledger.finalize(entry_id, {
            "state": "COMPLETED",
            "status": status,
            "reason": outcome.get("reason"),
            "credits_after": credits_after,
            "credits_consumed": consumed,
            "credits_reported": reported,
            "usd_amount": None,
            "http_status": result.get("http_status") if isinstance(result, dict) else None,
        })
        outcome["status"] = status
        if status == STATUS_BLOCKED and parsed.get("verdict") == "NEED_CONTEXT":
            outcome["message"] = ("Argon asked for more context. A Level B packet needs a separate owner "
                                  "approval and a new frozen packet hash; no automatic follow-up call.")
        elif status == STATUS_HALTED_UNKNOWN and not outcome.get("message"):
            outcome["message"] = "The provider answer could not be verified; no automatic retry."
        return outcome
    finally:
        guard.release(slot)


def _provider_failure(ex: argon_review.ProviderError) -> tuple[str, str]:
    if ex.kind == "auth_failed":
        return STATUS_BLOCKED, "auth_failed"
    if ex.kind == "rate_limited":
        return STATUS_HALTED_UNKNOWN, "rate_limited"
    if ex.kind == "server_error":
        return STATUS_HALTED_UNKNOWN, "server_error"
    if ex.kind == "timeout":
        return STATUS_HALTED_UNKNOWN, "timeout"
    if ex.kind == "network":
        return STATUS_HALTED_UNKNOWN, "network_error"
    return STATUS_HALTED_UNKNOWN, "provider_error"


def _account(before, after, reported, policy: Policy) -> tuple[str, str, float | None]:
    """Compare the reported spend with the observed balance change.

    Returns (accounting, note, effective_consumed). The effective value is what
    the ledger records, so the daily credit ceiling keeps working even when the
    provider omits credits_consumed.
    """
    if before is None or after is None:
        return "UNKNOWN", "balance could not be read before/after the call", None
    delta = before - after
    if delta < 0:
        return "MISMATCH", f"balance went up by {abs(delta)} during the call", None
    ceiling = policy.max_kie_credits_per_call
    if reported is None:
        if delta > 0 and ceiling is not None and delta > ceiling:
            return ("MISMATCH",
                    f"the call spent {delta} credits, above the per-call ceiling {ceiling}", delta)
        return "OK", "", delta
    try:
        reported = float(reported)
    except (TypeError, ValueError):
        return "UNKNOWN", "credits_consumed in the response is not a number", None
    if abs(reported - delta) > policy.credit_delta_tolerance:
        return ("MISMATCH",
                f"provider reported {reported} credits but the balance moved by {delta}", reported)
    if ceiling is not None and reported > ceiling:
        return "MISMATCH", f"the call spent {reported} credits, above the per-call ceiling {ceiling}", reported
    return "OK", "", reported


def _write_local_artifacts(state_dir: Path, outcome: dict) -> None:
    """Keep the raw packet and the raw answer outside the repository."""
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        packet = outcome.get("packet")
        if packet:
            packets_dir = state_dir / "packets"
            packets_dir.mkdir(parents=True, exist_ok=True)
            target = packets_dir / f"{outcome.get('payload_sha256', 'unknown')}.json"
            with target.open("w", encoding="utf-8", newline="\n") as f:
                json.dump(packet, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.write("\n")
        raw = outcome.get("raw_answer")
        if raw:
            answers_dir = state_dir / "answers"
            answers_dir.mkdir(parents=True, exist_ok=True)
            target = answers_dir / f"{outcome.get('ledger_id') or 'unknown'}.txt"
            with target.open("w", encoding="utf-8", newline="\n") as f:
                f.write(str(raw))
    except OSError:
        pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Budget gate for KIE Argon review; offline unless --mode live")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--pr-url", default="")
    p.add_argument("--task-id", default="TASK")
    p.add_argument("--scope", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--test", action="append", default=[])
    p.add_argument("--link", action="append", default=[])
    p.add_argument("--mode", choices=("offline", "live"), default="offline")
    p.add_argument("--state-dir", type=Path, default=None)
    p.add_argument("--approval", type=Path, default=None)
    p.add_argument("--expected-head-sha", default=None)
    p.add_argument("--report", type=Path, default=None)
    args = p.parse_args(argv)

    tests = [{"command": cmd, "status": "NOT_RUN", "exit_code": None} for cmd in args.test]
    try:
        policy = Policy.from_env()
    except GateError as ex:
        print(f"STOP: {ex}", file=sys.stderr)
        return 2

    outcome = run(
        repo=args.repo, base=args.base, head=args.head, pr_url=args.pr_url, task_id=args.task_id,
        scope=args.scope, summary=args.summary, tests=tests, links=args.link, mode=args.mode,
        policy=policy, state_dir=args.state_dir, approval_path=args.approval,
        expected_head_sha=args.expected_head_sha,
    )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", encoding="utf-8", newline="\n") as f:
            f.write(render_report(outcome))

    print(f"status: {outcome['status']}")
    print(f"reason: {outcome['reason']}")
    print(f"network calls: {outcome['network_calls']}")
    if outcome.get("payload_bytes"):
        print(f"payload bytes: {outcome['payload_bytes']} / {outcome['max_payload_bytes']}")
    if outcome.get("message"):
        print(f"message: {outcome['message']}")
    if args.report:
        print(f"report: {args.report}")

    if outcome["status"] in (STATUS_OFFLINE, STATUS_PASS):
        return 0
    if outcome["status"] == STATUS_FINDINGS:
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
