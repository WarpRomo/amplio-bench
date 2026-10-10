from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import csv
import json

from .case_metrics import (
    Case,
    discover_round_files,
    index_cases_by_stable_key,
    parse_verifier_stdout,
)


def _round_cases(run_dir: Path) -> dict[int, dict[str, Case]]:
    files = discover_round_files(Path(run_dir))
    if not files:
        raise ValueError("no EvoCode verifier rounds found")

    rounds = sorted(files)
    expected = list(range(rounds[0], rounds[-1] + 1))
    if rounds != expected:
        raise ValueError(f"non-contiguous rounds: {rounds}")

    return {
        round_number: parse_verifier_stdout(files[round_number])
        for round_number in rounds
    }


def _round_failure_rows(
    cases_by_round: dict[int, dict[str, Case]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous: dict[str, Case] | None = None

    for round_number, current in sorted(cases_by_round.items()):
        current_stable = index_cases_by_stable_key(current)
        current_ids = set(current_stable)
        failures = sum(not case.passed for case in current.values())
        successes = len(current) - failures

        if previous is None:
            rows.append(
                {
                    "round": round_number,
                    "cases_success": successes,
                    "cases_fail": failures,
                    "initial_failures": failures,
                    "inherited_failures": None,
                    "regressions": None,
                    "adaptation_misses": None,
                    "recoveries": None,
                    "introduced_cases": None,
                    "introduced_successes": None,
                    "new_case_capture_rate": None,
                    "retired_cases": None,
                    "case_churn_rate": None,
                }
            )
            previous = current
            continue

        previous_stable = index_cases_by_stable_key(previous)
        previous_ids = set(previous_stable)
        retained = previous_ids & current_ids
        introduced = current_ids - previous_ids
        retired = previous_ids - current_ids
        union = previous_ids | current_ids

        inherited = sum(
            (not previous_stable[case_id].passed)
            and (not current_stable[case_id].passed)
            for case_id in retained
        )
        regressions = sum(
            previous_stable[case_id].passed
            and (not current_stable[case_id].passed)
            for case_id in retained
        )
        recoveries = sum(
            (not previous_stable[case_id].passed)
            and current_stable[case_id].passed
            for case_id in retained
        )
        adaptation_misses = sum(
            not current_stable[case_id].passed
            for case_id in introduced
        )

        # Every active failing case is exactly one of these three categories.
        if failures != inherited + regressions + adaptation_misses:
            raise AssertionError(
                "failure decomposition invariant violated: "
                f"round={round_number} total={failures} "
                f"inherited={inherited} regressions={regressions} "
                f"adaptation_misses={adaptation_misses}"
            )

        rows.append(
            {
                "round": round_number,
                "cases_success": successes,
                "cases_fail": failures,
                "initial_failures": None,
                "inherited_failures": inherited,
                "regressions": regressions,
                "adaptation_misses": adaptation_misses,
                "recoveries": recoveries,
                "introduced_cases": len(introduced),
                "introduced_successes": len(introduced) - adaptation_misses,
                "new_case_capture_rate": (
                    (len(introduced) - adaptation_misses) / len(introduced)
                    if introduced else None
                ),
                "retired_cases": len(retired),
                "case_churn_rate": (
                    (len(introduced) + len(retired)) / len(union)
                    if union
                    else 0.0
                ),
            }
        )
        previous = current

    return rows


def _case_lifecycles(
    cases_by_round: dict[int, dict[str, Case]],
) -> list[dict[str, Any]]:
    observed: dict[str, list[tuple[int, Case]]] = defaultdict(list)
    for round_number, cases in sorted(cases_by_round.items()):
        for case_key, case in index_cases_by_stable_key(cases).items():
            observed[case_key].append((round_number, case))

    final_round = max(cases_by_round)
    rows: list[dict[str, Any]] = []
    for case_key, history in sorted(observed.items()):
        regressions = 0
        recoveries = 0
        longest_failure_streak = 0
        failure_streak = 0
        previous_round: int | None = None
        previous_case: Case | None = None

        for round_number, case in history:
            if (
                previous_round is not None
                and round_number == previous_round + 1
                and previous_case is not None
            ):
                regressions += int(previous_case.passed and not case.passed)
                recoveries += int((not previous_case.passed) and case.passed)
            else:
                failure_streak = 0

            if case.passed:
                failure_streak = 0
            else:
                failure_streak += 1
                longest_failure_streak = max(longest_failure_streak, failure_streak)

            previous_round = round_number
            previous_case = case

        first_round, first_case = history[0]
        last_round, last_case = history[-1]
        pass_rounds = [r for r, case in history if case.passed]
        fail_rounds = [r for r, case in history if not case.passed]
        rows.append(
            {
                "case_key": case_key,
                "scenario": first_case.scenario or "",
                "first_case_id": first_case.case_id,
                "final_case_id": last_case.case_id if last_round == final_round else "",
                "requirement": first_case.requirement or "?",
                "origin": first_case.origin or "",
                "case_type": first_case.case_type or "",
                "introduced_round": first_round,
                "last_active_round": last_round,
                "active_rounds": len(history),
                "pass_rounds": len(pass_rounds),
                "fail_rounds": len(fail_rounds),
                "first_pass_round": pass_rounds[0] if pass_rounds else None,
                "first_fail_round": fail_rounds[0] if fail_rounds else None,
                "regressions": regressions,
                "recoveries": recoveries,
                "longest_failure_streak": longest_failure_streak,
                "active_final_round": last_round == final_round,
                "final_status": (
                    "pass" if last_case.passed else "fail"
                ) if last_round == final_round else "retired",
            }
        )
    return rows


def _panel_case_failures(panel: dict[str, Any]) -> dict[str, Any]:
    models = panel.get("models")
    if not isinstance(models, dict) or not models:
        raise ValueError("panel JSON has no model results")

    reached: Counter[int] = Counter()
    totals: dict[int, Counter[int]] = defaultdict(Counter)
    failed_by: dict[tuple[int, str], set[str]] = defaultdict(set)
    metadata: dict[tuple[int, str], dict[str, str]] = {}

    for model_name, model_rounds in models.items():
        if not isinstance(model_rounds, dict):
            continue
        for round_key, round_result in model_rounds.items():
            try:
                round_number = int(round_key)
            except (TypeError, ValueError):
                continue
            if not isinstance(round_result, dict):
                continue

            reached[round_number] += 1
            total = round_result.get("total")
            if isinstance(total, int):
                totals[round_number][total] += 1

            seen_for_model: set[str] = set()
            for group in round_result.get("fails") or []:
                if not isinstance(group, dict):
                    continue
                requirement = str(group.get("req") or "?")
                case_type = str(group.get("type") or "")
                for case in group.get("cases") or []:
                    if not isinstance(case, dict):
                        continue
                    case_id = str(case.get("id") or "")
                    if not case_id or case_id in seen_for_model:
                        continue
                    seen_for_model.add(case_id)
                    key = (round_number, case_id)
                    failed_by[key].add(str(model_name))
                    if key not in metadata:
                        metadata[key] = {
                            "requirement": requirement,
                            "case_type": case_type,
                            "intent": str(case.get("intent") or ""),
                            "scenario": str(case.get("scenario") or ""),
                            "expected": str(case.get("expected") or ""),
                        }

    modal_totals: dict[int, int] = {}
    for round_number, counts in totals.items():
        if counts:
            modal_totals[round_number] = counts.most_common(1)[0][0]

    return {
        "model_count": len(models),
        "reached": dict(reached),
        "modal_totals": modal_totals,
        "failed_by": failed_by,
        "metadata": metadata,
    }


def _target_panel_rows(
    cases_by_round: dict[int, dict[str, Case]],
    panel_stats: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    compatibility: list[dict[str, Any]] = []

    reached: dict[int, int] = panel_stats["reached"]
    modal_totals: dict[int, int] = panel_stats["modal_totals"]
    failed_by: dict[tuple[int, str], set[str]] = panel_stats["failed_by"]
    metadata: dict[tuple[int, str], dict[str, str]] = panel_stats["metadata"]

    for round_number, cases in sorted(cases_by_round.items()):
        panel_reached = int(reached.get(round_number, 0))
        panel_total = modal_totals.get(round_number)
        compatible = panel_total is None or panel_total == len(cases)
        compatibility.append(
            {
                "round": round_number,
                "target_cases": len(cases),
                "panel_modal_cases": panel_total,
                "panel_models_reached": panel_reached,
                "case_count_matches": compatible,
            }
        )

        for case_id, case in sorted(cases.items()):
            key = (round_number, case_id)
            fail_models = len(failed_by.get(key, set()))
            meta = metadata.get(key, {})
            fail_rate = (
                fail_models / panel_reached
                if panel_reached and compatible
                else None
            )
            rows.append(
                {
                    "round": round_number,
                    "case_id": case_id,
                    "requirement": case.requirement or meta.get("requirement", "?"),
                    "case_type": case.case_type or meta.get("case_type", ""),
                    "target_status": "pass" if case.passed else "fail",
                    "panel_models_reached": panel_reached,
                    "panel_fail_models": fail_models if compatible else None,
                    "panel_fail_rate": fail_rate,
                    "intent": meta.get("intent", ""),
                    "scenario": meta.get("scenario", ""),
                    "expected": meta.get("expected", ""),
                }
            )

    return rows, compatibility


def analyze_failures(
    run_dir: Path,
    panel_json: Path | None = None,
) -> dict[str, Any]:
    """Decompose target failures and optionally compare them with EvoCode's panel.

    The decomposition is exact rather than a weighted score. For round r > 1,
    every active target failure is one of:
      * inherited unresolved failure (failed in r-1 and r),
      * regression (passed in r-1, failed in r), or
      * adaptation miss (introduced in r and currently failing).
    """

    cases_by_round = _round_cases(Path(run_dir))
    rounds = _round_failure_rows(cases_by_round)
    lifecycles = _case_lifecycles(cases_by_round)

    final_active_failures = [
        row
        for row in lifecycles
        if row["active_final_round"] and row["final_status"] == "fail"
    ]
    final_never_solved = sum(
        row.get("first_pass_round") is None for row in final_active_failures
    )
    final_lost_after_pass = len(final_active_failures) - final_never_solved

    introduced_total = sum(row.get("introduced_cases") or 0 for row in rounds)
    introduced_success_total = sum(
        row.get("introduced_successes") or 0 for row in rounds
    )

    result: dict[str, Any] = {
        "run_dir": str(Path(run_dir)),
        "summary": {
            "rounds": len(rounds),
            "final_round": rounds[-1]["round"],
            "final_failures": rounds[-1]["cases_fail"],
            "final_never_solved_failures": final_never_solved,
            "final_lost_after_pass_failures": final_lost_after_pass,
            "regression_events": sum(row.get("regressions") or 0 for row in rounds),
            "recovery_events": sum(row.get("recoveries") or 0 for row in rounds),
            "adaptation_miss_events": sum(
                row.get("adaptation_misses") or 0 for row in rounds
            ),
            "introduced_cases": introduced_total,
            "introduced_successes": introduced_success_total,
            "new_case_capture_rate": (
                introduced_success_total / introduced_total
                if introduced_total else None
            ),
        },
        "rounds": rounds,
        "case_lifecycles": lifecycles,
    }

    if panel_json is not None:
        panel = json.loads(Path(panel_json).read_text())
        panel_stats = _panel_case_failures(panel)
        target_panel, compatibility = _target_panel_rows(cases_by_round, panel_stats)
        result["panel"] = {
            "source": str(Path(panel_json)),
            "model_count": panel_stats["model_count"],
            "round_compatibility": compatibility,
            "common_fail": panel.get("common_fail") or [],
        }
        result["target_panel_cases"] = target_panel
        panel_zero_by_round: Counter[int] = Counter()
        for row in target_panel:
            if (
                row["target_status"] == "fail"
                and row.get("panel_fail_models") == 0
                and row.get("panel_fail_rate") is not None
            ):
                panel_zero_by_round[int(row["round"])] += 1
        for round_row in rounds:
            round_row["panel_zero_target_failures"] = panel_zero_by_round.get(
                int(round_row["round"]), 0
            )
        result["summary"]["final_panel_zero_target_failures"] = (
            panel_zero_by_round.get(int(rounds[-1]["round"]), 0)
        )

    return result


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def _fmt_int(value: Any) -> str:
    return "-" if value is None else str(value)


def _fmt_rate(value: Any) -> str:
    return "-" if value is None else f"{100 * float(value):.1f}%"


def write_failure_analysis(result: dict[str, Any], out_dir: Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "failure_signals.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )

    round_fields = [
        "round",
        "cases_success",
        "cases_fail",
        "initial_failures",
        "inherited_failures",
        "regressions",
        "adaptation_misses",
        "recoveries",
        "introduced_cases",
        "introduced_successes",
        "new_case_capture_rate",
        "retired_cases",
        "case_churn_rate",
        "panel_zero_target_failures",
    ]
    _write_csv(out / "round_failure_signals.csv", result["rounds"], round_fields)

    lifecycle_fields = [
        "case_key",
        "scenario",
        "first_case_id",
        "final_case_id",
        "requirement",
        "origin",
        "case_type",
        "introduced_round",
        "last_active_round",
        "active_rounds",
        "pass_rounds",
        "fail_rounds",
        "first_pass_round",
        "first_fail_round",
        "regressions",
        "recoveries",
        "longest_failure_streak",
        "active_final_round",
        "final_status",
    ]
    _write_csv(out / "case_lifecycles.csv", result["case_lifecycles"], lifecycle_fields)

    if "target_panel_cases" in result:
        panel_fields = [
            "round",
            "case_id",
            "requirement",
            "case_type",
            "target_status",
            "panel_models_reached",
            "panel_fail_models",
            "panel_fail_rate",
            "intent",
            "scenario",
            "expected",
        ]
        _write_csv(
            out / "target_panel_cases.csv",
            result["target_panel_cases"],
            panel_fields,
        )

    summary = result.get("summary", {})
    lines = [
        "# Failure diagnostics",
        "",
        "Final failure debt: "
        f"**{summary.get('final_never_solved_failures', '-')} never solved**, "
        f"**{summary.get('final_lost_after_pass_failures', '-')} lost after pass**; "
        f"panel-zero target failures: "
        f"**{summary.get('final_panel_zero_target_failures', '-')}**.",
        "",
        "For rounds after the initial build, every active failure is decomposed "
        "exactly into unresolved inherited failures, regressions, or misses on "
        "newly introduced cases. No weighted failure score is used.",
        "",
        "## Round-level failure sources",
        "",
        "| Round | Failing | Inherited | Regressions | New misses | Recoveries | Churn |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["rounds"]:
        lines.append(
            f"| {row['round']} | {row['cases_fail']} | "
            f"{_fmt_int(row['inherited_failures'])} | "
            f"{_fmt_int(row['regressions'])} | "
            f"{_fmt_int(row['adaptation_misses'])} | "
            f"{_fmt_int(row['recoveries'])} | "
            f"{_fmt_rate(row['case_churn_rate'])} |"
        )

    if "target_panel_cases" in result:
        final_round = result["summary"]["final_round"]
        final_failures = [
            row
            for row in result["target_panel_cases"]
            if row["round"] == final_round
            and row["target_status"] == "fail"
            and row["panel_fail_rate"] is not None
        ]
        rare = sorted(
            final_failures,
            key=lambda row: (row["panel_fail_rate"], row["case_id"]),
        )[:10]
        common = sorted(
            final_failures,
            key=lambda row: (-row["panel_fail_rate"], row["case_id"]),
        )[:10]

        lines.extend(
            [
                "",
                "## Released-panel comparison",
                "",
                "The panel comparison asks how often released EvoCode models fail "
                "the same verifier case. Low panel failure rates can surface "
                "target/scaffold/trajectory-specific candidates; high rates point "
                "toward benchmark-wide weaknesses. This ranking is diagnostic, not causal.",
            ]
        )

        def add_case_table(title: str, rows: list[dict[str, Any]]) -> None:
            lines.extend(
                [
                    "",
                    f"### {title}",
                    "",
                    "| Case | Requirement | Panel fail rate | Intent |",
                    "|---|---|---:|---|",
                ]
            )
            if not rows:
                lines.append("| - | - | - | No compatible panel cases |")
                return
            for row in rows:
                intent = str(row.get("intent") or "").replace("|", "\\|")
                requirement = str(row.get("requirement") or "?").replace("|", "\\|")
                lines.append(
                    f"| {row['case_id']} | {requirement} | "
                    f"{_fmt_rate(row['panel_fail_rate'])} | {intent} |"
                )

        add_case_table("Target failures least common in the panel", rare)
        add_case_table("Target failures most common in the panel", common)

    (out / "summary.md").write_text("\n".join(lines) + "\n")
