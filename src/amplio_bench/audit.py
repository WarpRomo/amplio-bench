from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re


ERROR_PATTERNS = {
    "provider_429": re.compile(r"429 Too Many|rate limit", re.I),
    "retry_exhausted": re.compile(
        r"openai request failed after",
        re.I,
    ),
    "runtime_error": re.compile(r"\bRuntimeError\b"),
    "crashed": re.compile(r"\bcrashed\b", re.I),
    "error_log": re.compile(r"level=ERROR"),
}

REWARD_RE = re.compile(
    r"(?:^|/)steps/round-(\d+)/verifier/reward\.txt$"
)


def verifier_rounds(run_dir: Path) -> list[int]:
    """Return sorted round numbers with verifier reward artifacts."""

    rounds: set[int] = set()
    for path in Path(run_dir).rglob("reward.txt"):
        match = REWARD_RE.search(path.as_posix())
        if match:
            rounds.add(int(match.group(1)))
    return sorted(rounds)


def check_harbor_verifier_isolation(
    harbor_root: Path,
) -> dict[str, Any]:
    """Check that Harbor clears shared verifier artifacts before a new step."""

    source = (
        Path(harbor_root)
        / "src/harbor/trial/multi_step.py"
    )
    if not source.exists():
        return {
            "status": "FAIL",
            "reason": f"missing {source}",
        }

    text = source.read_text(errors="replace")
    start = text.find("def _prepare_step")
    if start < 0:
        start = text.find("async def _prepare_step")
    if start < 0:
        return {
            "status": "FAIL",
            "reason": "_prepare_step not found",
        }

    candidates = [
        pos
        for pos in (
            text.find("\n    async def ", start + 1),
            text.find("\n    def ", start + 1),
        )
        if pos >= 0
    ]
    end = (
        min(candidates)
        if candidates
        else min(len(text), start + 8000)
    )
    body = text[start:end]

    calls_reset = "_reset_shared_step_verifier_dirs" in body
    return {
        "status": "PASS" if calls_reset else "FAIL",
        "prepare_step_calls_helper": calls_reset,
        "source": str(source),
    }


def audit_run(
    run_dir: Path,
    expected_rounds: int | None = None,
    harbor_root: Path | None = None,
) -> dict[str, Any]:
    """Validate round completeness and common runtime integrity signals."""

    run = Path(run_dir)
    found = verifier_rounds(run)
    expected = (
        list(range(1, expected_rounds + 1))
        if expected_rounds is not None
        else None
    )

    checks: dict[str, Any] = {
        "rounds": {
            "found": found,
            "expected": expected,
            "pass": (
                bool(found)
                if expected is None
                else found == expected
            ),
        }
    }

    exit_code_path = run / "harbor_rc.txt"
    checks["harbor_exit_code"] = {
        "value": None,
        "pass": None,
    }
    if exit_code_path.exists():
        value = int(exit_code_path.read_text().strip())
        checks["harbor_exit_code"] = {
            "value": value,
            "pass": value == 0,
        }

    hits: dict[str, list[str]] = {}
    log_path = run / "run.log"
    if log_path.exists():
        log_text = log_path.read_text(errors="replace")
        for name, pattern in ERROR_PATTERNS.items():
            matches = pattern.findall(log_text)
            if matches:
                hits[name] = [
                    str(value)
                    for value in matches[:10]
                ]
    checks["known_runtime_errors"] = {
        "hits": hits,
        "pass": not hits,
    }

    postflight = run / "audit/daytona-postflight.txt"
    checks["sandbox_cleanup"] = {"pass": None}
    if postflight.exists():
        cleaned = (
            "COUNT_AFTER_CLEANUP = 0"
            in postflight.read_text(errors="replace")
        )
        checks["sandbox_cleanup"] = {"pass": cleaned}

    if harbor_root is not None:
        checks["verifier_isolation"] = (
            check_harbor_verifier_isolation(harbor_root)
        )

    gates: list[bool] = []
    for check in checks.values():
        if not isinstance(check, dict):
            continue
        if check.get("pass") is not None:
            gates.append(bool(check["pass"]))
        elif check.get("status") in {"PASS", "FAIL"}:
            gates.append(check["status"] == "PASS")

    return {
        "run_dir": str(run),
        "checks": checks,
        "validation_status": (
            "PASS"
            if gates and all(gates)
            else "FAIL"
        ),
    }


def write_audit(
    result: dict[str, Any],
    out: Path,
) -> None:
    Path(out).write_text(
        json.dumps(result, indent=2) + "\n"
    )
