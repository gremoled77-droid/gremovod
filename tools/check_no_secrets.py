"""Fail-closed check that a change does not carry secrets.

Offline. Never contacts GitHub, n8n, a paid provider or the running Studio.
Only the ADDED lines of the change are inspected, so a key that already lives in the
repository is reported once by the audit, not on every unrelated pull request.

Path level reuses ``scripts/check_git_files.py`` so the pre-commit rule and this check
cannot drift apart.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_git_files import blocked  # noqa: E402  (needs ROOT on sys.path)

# Provider key formats. A match here is always a finding.
PROVIDER_PATTERNS = (
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("github_token", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

# A literal assigned to a credential-looking name.
ASSIGNMENT_PATTERN = re.compile(
    r"['\"]?[A-Za-z0-9_\-]*(?:api[_-]?key|secret|token|password|credential)['\"]?"
    r"\s*[:=]\s*['\"]([^'\"\s]{12,})['\"]",
    re.IGNORECASE,
)

# Offline test fixtures that look like credentials but are not. Exact values only.
ALLOWED_LITERAL_VALUES = {
    "qa-service-token": "offline test fixture in backend/test_qa_reviews.py",
    "correct-horse-battery": "offline test fixture in backend/test_remote_access.py",
    "environment-test-key": "offline test fixture in backend/test_smoke.py",
}


def _is_placeholder(value):
    upper = value.upper()
    if "<" in value and ">" in value:
        return True
    if upper in {"REDACTED", "CHANGEME", "PLACEHOLDER", "NONE", "NULL"}:
        return True
    if upper.startswith("REPLACE_") or upper.startswith("YOUR_"):
        return True
    return False


def scan_text(text, path="<text>"):
    """Return findings for one chunk of text. Never returns the secret itself."""
    findings = []
    for rule, pattern in PROVIDER_PATTERNS:
        if pattern.search(text):
            findings.append(f"{path}: looks like a {rule}")
    for match in ASSIGNMENT_PATTERN.finditer(text):
        value = match.group(1)
        if value.lower() in ALLOWED_LITERAL_VALUES:
            continue
        if _is_placeholder(value):
            continue
        findings.append(f"{path}: literal value assigned to a credential-like name")
        break
    return findings


def added_lines(base, root=ROOT):
    """Return the added lines of a change as ``(path, line)`` pairs."""
    result = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", f"origin/{base}...HEAD"],
        capture_output=True, cwd=str(root),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cannot diff against origin/{base}: {result.stderr.decode('utf8', 'replace').strip()}")
    current = None
    pairs = []
    for line in result.stdout.decode("utf8", "replace").splitlines():
        if line.startswith("+++ "):
            candidate = line[4:].strip()
            if candidate.startswith("b/"):
                candidate = candidate[2:]
            current = None if candidate == "/dev/null" else candidate
        elif line.startswith("+") and not line.startswith("+++") and current:
            pairs.append((current, line[1:]))
    return pairs


def changed_paths(base, root=ROOT):
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", f"origin/{base}...HEAD"],
        capture_output=True, cwd=str(root),
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot list changes against origin/{base}")
    return [p.decode("utf8", "replace") for p in result.stdout.split(b"\0") if p]


def check_change(base, root=ROOT):
    """Return findings for a whole change: forbidden paths plus secret-looking lines."""
    findings = []
    paths = changed_paths(base, root)
    for path in paths:
        if blocked(path):
            findings.append(f"{path}: blocked local data/credential path")
    for path, line in added_lines(base, root):
        findings.extend(scan_text(line, path))
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="mavis/work")
    args = parser.parse_args()
    try:
        findings = check_change(args.base)
    except RuntimeError as exc:
        print(f"SECRET_SCAN_ERROR: {exc}", file=sys.stderr)
        return 2
    if findings:
        print(f"SECRET_SCAN: FAILED ({len(findings)} finding(s))")
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        print("Remove the credential from the change; keep it out of the repository.",
              file=sys.stderr)
        return 1
    print("SECRET_SCAN: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
