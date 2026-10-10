from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import csv
import json
import re


PASS_STATUSES = {"success", "pass"}
ROUND_RE = re.compile(
    r"(?:^|/)steps/round-(\d+)/verifier/test-stdout\.txt$"
)
FIELD_RE = re.compile(r"\b([A-Za-z0-9_-]+)=([^\s]+)")
SCENARIO_RE = re.compile(r'\bscenario="([^"]*)"')


@dataclass(frozen=True)
class Case:
    case_id: str
    status: str
    origin: str | None = None
    requirement: str | None = None
    case_type: str | None = None
    scenario: str | None = None

    @property
    def passed(self) -> bool:
        return self.status in PASS_STATUSES

    @property
    def stable_key(self) -> str:
        """Cross-round identity for one semantic verifier case.

        EvoCode case_id values such as c001 are ordinal positions generated anew
        by each round verifier. They are valid for same-round joins (for example
        against the released panel) but are not stable trajectory identities when
        cases are inserted, retired, or reordered. The canonical scenario/name is
        stable across retained cases in the released tasks.
        """

        if self.scenario:
            return f"scenario:{self.scenario}"
        # Synthetic/legacy logs may not expose scenario. Preserve compatibility,
        # but callers should not infer semantic continuity from this fallback.
        return f"case_id:{self.case_id}"


def index_cases_by_stable_key(cases: dict[str, "Case"]) -> dict[str, "Case"]:
    """Index one round by semantic identity, rejecting ambiguous identities."""

    indexed: dict[str, Case] = {}
    for case in cases.values():
        key = case.stable_key
        if key in indexed:
            raise ValueError(f"duplicate stable verifier case identity: {key}")
        indexed[key] = case
    return indexed


@dataclass
class RoundMetrics:
    round: int
    reward: float
    cases_total: int
    cases_success: int
    cases_fail: int
    success_rate: float
    stable_success: int | None = None
    regressions: int | None = None
    recoveries: int | None = None
    stable_fail: int | None = None
    new_cases: int | None = None
    new_success: int | None = None
    new_fail: int | None = None
    new_success_rate: float | None = None
    retired_cases: int | None = None
    retained_cases: int | None = None
    case_churn_rate: float | None = None


def parse_case_line(line: str) -> Case | None:
    """Parse one EvoCode CASE_RESULT line."""

    if not line.startswith("CASE_RESULT "):
        return None

    fields = dict(FIELD_RE.findall(line))
    scenario_match = SCENARIO_RE.search(line)
    if not fields.get("case_id") or not fields.get("status"):
        return None

    return Case(
        case_id=fields["case_id"],
        status=fields["status"],
        origin=fields.get("origin_step"),
        requirement=fields.get("requirement_ref"),
        case_type=fields.get("case_type"),
        scenario=scenario_match.group(1) if scenario_match else None,
    )


def parse_verifier_stdout(path: Path) -> dict[str, Case]:
    """Return the final observed state for every case ID in a verifier output."""

    cases: dict[str, Case] = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        case = parse_case_line(line)
        if case is not None:
            cases[case.case_id] = case
    return cases


def discover_round_files(run_dir: Path) -> dict[int, Path]:
    """Find exactly one verifier stdout for each discovered round."""

    found: dict[int, list[Path]] = defaultdict(list)
    for path in Path(run_dir).rglob("test-stdout.txt"):
        match = ROUND_RE.search(path.as_posix())
        if match:
            found[int(match.group(1))].append(path)

    duplicates = {
        round_: paths
        for round_, paths in found.items()
        if len(paths) != 1
    }
    if duplicates:
        details = ", ".join(
            f"r{round_}={len(paths)}"
            for round_, paths in sorted(duplicates.items())
        )
        raise ValueError(
            "expected exactly one verifier stdout per round: " + details
        )

    return {round_: paths[0] for round_, paths in found.items()}


def _transition_metrics(
    previous: dict[str, Case],
    current: dict[str, Case],
    row: RoundMetrics,
) -> None:
    previous_stable = index_cases_by_stable_key(previous)
    current_stable = index_cases_by_stable_key(current)
    previous_ids = set(previous_stable)
    current_ids = set(current_stable)

    retained = previous_ids & current_ids
    introduced = current_ids - previous_ids
    retired = previous_ids - current_ids
    union = previous_ids | current_ids

    row.stable_success = sum(
        previous_stable[case_id].passed and current_stable[case_id].passed
        for case_id in retained
    )
    row.regressions = sum(
        previous_stable[case_id].passed and not current_stable[case_id].passed
        for case_id in retained
    )
    row.recoveries = sum(
        not previous_stable[case_id].passed and current_stable[case_id].passed
        for case_id in retained
    )
    row.stable_fail = sum(
        not previous_stable[case_id].passed and not current_stable[case_id].passed
        for case_id in retained
    )

    row.new_cases = len(introduced)
    row.new_success = sum(
        current_stable[case_id].passed
        for case_id in introduced
    )
    row.new_fail = row.new_cases - row.new_success
    row.new_success_rate = (
        row.new_success / row.new_cases
        if row.new_cases
        else None
    )

    row.retired_cases = len(retired)
    row.retained_cases = len(retained)
    row.case_churn_rate = (
        (len(introduced) + len(retired)) / len(union)
        if union
        else 0.0
    )


def analyze_run(run_dir: Path) -> dict[str, Any]:
    """Analyze case-level progress across an EvoCode-style multi-round run."""

    round_files = discover_round_files(Path(run_dir))
    if not round_files:
        raise ValueError("no EvoCode verifier rounds found")

    round_numbers = sorted(round_files)
    expected = list(range(round_numbers[0], round_numbers[-1] + 1))
    if round_numbers != expected:
        raise ValueError(f"non-contiguous rounds: {round_numbers}")

    previous: dict[str, Case] | None = None
    cases_by_round: dict[int, dict[str, Case]] = {}
    rows: list[RoundMetrics] = []

    for round_number in round_numbers:
        stdout = round_files[round_number]
        cases = parse_verifier_stdout(stdout)
        reward = float(
            (stdout.parent / "reward.txt").read_text().strip()
        )

        success = sum(case.passed for case in cases.values())
        total = len(cases)
        row = RoundMetrics(
            round=round_number,
            reward=reward,
            cases_total=total,
            cases_success=success,
            cases_fail=total - success,
            success_rate=success / total if total else 0.0,
        )

        if previous is not None:
            _transition_metrics(previous, cases, row)

        rows.append(row)
        cases_by_round[round_number] = cases
        previous = cases

    requirements: dict[str, Counter[str]] = defaultdict(Counter)
    for case in cases_by_round[round_numbers[-1]].values():
        bucket = "success" if case.passed else "fail"
        requirements[case.requirement or "?"][bucket] += 1

    final_requirements: list[dict[str, Any]] = []
    for name, counts in sorted(requirements.items()):
        total = counts["success"] + counts["fail"]
        final_requirements.append(
            {
                "requirement": name,
                "success": counts["success"],
                "fail": counts["fail"],
                "total": total,
                "success_rate": (
                    counts["success"] / total if total else 0.0
                ),
            }
        )

    return {
        "rounds": [asdict(row) for row in rows],
        "final_round_requirements": final_requirements,
    }


def write_analysis(result: dict[str, Any], out_dir: Path) -> None:
    """Write machine-readable and Markdown trajectory summaries."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "metrics.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )

    round_fields = [
        "round",
        "reward",
        "cases_success",
        "cases_total",
        "cases_fail",
        "success_rate",
        "stable_success",
        "regressions",
        "recoveries",
        "stable_fail",
        "new_cases",
        "new_success",
        "new_fail",
        "new_success_rate",
        "retired_cases",
        "retained_cases",
        "case_churn_rate",
    ]
    with (out / "round_metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=round_fields)
        writer.writeheader()
        for row in result["rounds"]:
            writer.writerow(
                {field: row.get(field) for field in round_fields}
            )

    requirement_fields = [
        "requirement",
        "success",
        "fail",
        "total",
        "success_rate",
    ]
    with (out / "final_requirements.csv").open(
        "w",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=requirement_fields,
        )
        writer.writeheader()
        writer.writerows(result["final_round_requirements"])

    lines = [
        "# Run summary",
        "",
        (
            "| Round | Passing | Rate | New solved | Retired | Churn | "
            "Regressions | Recoveries |"
        ),
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for index, row in enumerate(result["rounds"]):
        if index == 0:
            new_solved = retired = churn = regressions = recoveries = "—"
        else:
            new_solved = f"{row['new_success']}/{row['new_cases']}"
            retired = str(row["retired_cases"])
            churn = f"{100 * row['case_churn_rate']:.1f}%"
            regressions = str(row["regressions"])
            recoveries = str(row["recoveries"])

        lines.append(
            f"| {row['round']} | "
            f"{row['cases_success']}/{row['cases_total']} | "
            f"{100 * row['success_rate']:.1f}% | "
            f"{new_solved} | {retired} | {churn} | "
            f"{regressions} | {recoveries} |"
        )

    (out / "summary.md").write_text("\n".join(lines) + "\n")
