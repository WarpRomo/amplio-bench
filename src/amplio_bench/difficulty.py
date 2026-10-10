from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any, Iterable
import csv
import difflib
import json
import math
import re
import tomllib

from .case_metrics import (
    discover_round_files,
    index_cases_by_stable_key,
    parse_verifier_stdout,
)


@dataclass(frozen=True)
class StructuralRound:
    round: int
    change_types: tuple[str, ...]
    instruction_words: int
    instruction_lines: int
    solution_lines: int
    verifier_lines_added: int | None
    verifier_lines_removed: int | None
    active_cases: int | None
    introduced_cases: int | None
    retired_cases: int | None
    retained_cases: int | None
    case_churn_rate: float | None
    active_requirements: int | None
    introduced_requirements: int | None
    retired_requirements: int | None


@dataclass(frozen=True)
class PanelRound:
    round: int
    panel_models_total: int
    panel_models_reached: int
    panel_reach_rate: float
    panel_round_pass_rate_reached: float | None
    panel_round_pass_wilson_low_reached: float | None
    panel_round_pass_wilson_high_reached: float | None
    panel_case_mean_reached: float | None
    panel_case_median_reached: float | None
    panel_case_std_reached: float | None
    panel_binary_1pl_beta: float | None
    panel_binary_1pl_percentile: float | None
    panel_case_1pl_beta: float | None
    panel_case_1pl_percentile: float | None
    panel_calibration_items_total: int | None


def _round_num(name: str) -> int | None:
    m = re.fullmatch(r"(?:round[-_])?(\d+)", str(name))
    return int(m.group(1)) if m else None


def _task_rounds(task_dir: Path) -> list[dict[str, Any]]:
    cfg = tomllib.loads((task_dir / "task.toml").read_text())
    meta = cfg.get("metadata", {})
    chain = meta.get("requirement_chain", {})
    chain_steps = {
        str(x.get("step")): tuple(str(t) for t in x.get("change_types", []))
        for x in chain.get("steps", [])
    }
    steps = cfg.get("steps", [])
    out: list[dict[str, Any]] = []
    for i, step in enumerate(steps, 1):
        name = str(step.get("name", f"round-{i}"))
        n = _round_num(name) or i
        out.append({"round": n, "name": name, "change_types": chain_steps.get(name, ())})
    if not out:
        n = int(chain.get("num_steps", 0))
        out = [
            {"round": i, "name": f"round-{i}", "change_types": chain_steps.get(f"round-{i}", ())}
            for i in range(1, n + 1)
        ]
    return sorted(out, key=lambda x: x["round"])


def _read_text_tree(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    out: dict[str, list[str]] = {}
    for p in sorted(path.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(path).as_posix()
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        out[rel] = text.splitlines(keepends=True)
    return out


def _tree_line_delta(prev: dict[str, list[str]], cur: dict[str, list[str]]) -> tuple[int, int]:
    added = removed = 0
    for name in sorted(set(prev) | set(cur)):
        a = prev.get(name, [])
        b = cur.get(name, [])
        for line in difflib.ndiff(a, b):
            if line.startswith("+ "):
                added += 1
            elif line.startswith("- "):
                removed += 1
    return added, removed


def structural_rounds(task_dir: Path, run_dir: Path | None = None) -> list[StructuralRound]:
    task_dir = Path(task_dir)
    round_defs = _task_rounds(task_dir)

    run_cases: dict[int, dict] = {}
    if run_dir is not None:
        for n, p in discover_round_files(Path(run_dir)).items():
            run_cases[n] = parse_verifier_stdout(p)

    rows: list[StructuralRound] = []
    prev_tests: dict[str, list[str]] | None = None
    prev_cases: dict | None = None
    prev_requirements: set[str] | None = None

    for rd in round_defs:
        n = rd["round"]
        step_dir = task_dir / "steps" / rd["name"]
        if not step_dir.exists():
            # Some dataset layouts use round_N.
            alt = task_dir / rd["name"].replace("round-", "round_")
            if alt.exists():
                step_dir = alt

        instruction = (step_dir / "instruction.md").read_text(errors="replace") if (step_dir / "instruction.md").exists() else ""
        solution = (step_dir / "solution" / "solve.sh").read_text(errors="replace") if (step_dir / "solution" / "solve.sh").exists() else ""
        tests = _read_text_tree(step_dir / "tests")

        if prev_tests is None:
            verifier_added = sum(len(v) for v in tests.values()) if tests else None
            verifier_removed = 0 if tests else None
        else:
            verifier_added, verifier_removed = _tree_line_delta(prev_tests, tests)
        prev_tests = tests

        cases = run_cases.get(n)
        active_cases = introduced = retired = retained = None
        churn = None
        active_req = introduced_req = retired_req = None
        if cases is not None:
            cur_stable = index_cases_by_stable_key(cases)
            cur_ids = set(cur_stable)
            cur_req = {c.requirement for c in cases.values() if c.requirement}
            active_cases = len(cur_ids)
            active_req = len(cur_req)
            if prev_cases is None:
                introduced = len(cur_ids)
                retired = 0
                retained = 0
                introduced_req = len(cur_req)
                retired_req = 0
                churn = 1.0 if cur_ids else 0.0
            else:
                prev_ids = set(index_cases_by_stable_key(prev_cases))
                introduced_ids = cur_ids - prev_ids
                retired_ids = prev_ids - cur_ids
                retained_ids = cur_ids & prev_ids
                introduced = len(introduced_ids)
                retired = len(retired_ids)
                retained = len(retained_ids)
                union = cur_ids | prev_ids
                churn = (introduced + retired) / len(union) if union else 0.0
                introduced_req = len(cur_req - (prev_requirements or set()))
                retired_req = len((prev_requirements or set()) - cur_req)
            prev_cases = cases
            prev_requirements = cur_req

        rows.append(
            StructuralRound(
                round=n,
                change_types=tuple(rd["change_types"]),
                instruction_words=len(re.findall(r"\S+", instruction)),
                instruction_lines=len(instruction.splitlines()),
                solution_lines=len(solution.splitlines()),
                verifier_lines_added=verifier_added,
                verifier_lines_removed=verifier_removed,
                active_cases=active_cases,
                introduced_cases=introduced,
                retired_cases=retired,
                retained_cases=retained,
                case_churn_rate=churn,
                active_requirements=active_req,
                introduced_requirements=introduced_req,
                retired_requirements=retired_req,
            )
        )
    return rows


def _find_round_map(obj: Any) -> dict[int, dict[str, Any]]:
    """Find a mapping of round number -> result in one model's public result object."""
    if isinstance(obj, dict):
        direct: dict[int, dict[str, Any]] = {}
        for k, v in obj.items():
            n = _round_num(str(k))
            if n is not None and isinstance(v, dict) and any(x in v for x in ("pass", "total", "reward")):
                direct[n] = v
        if direct:
            return direct
        for key in ("rounds", "results", "per_round", "steps"):
            if key in obj:
                found = _find_round_map(obj[key])
                if found:
                    return found
        for v in obj.values():
            found = _find_round_map(v)
            if found:
                return found
    elif isinstance(obj, list):
        out = {}
        for item in obj:
            if isinstance(item, dict):
                n = item.get("n", item.get("round", item.get("round_index")))
                try:
                    n = int(n)
                except (TypeError, ValueError):
                    continue
                if any(x in item for x in ("pass", "total", "reward")):
                    out[n] = item
        if out:
            return out
        for v in obj:
            found = _find_round_map(v)
            if found:
                return found
    return {}


def load_panel_task(path: Path) -> dict[str, dict[int, dict[str, Any]]]:
    data = json.loads(Path(path).read_text())
    models = data.get("models")
    if not isinstance(models, dict):
        raise ValueError(f"panel task JSON has no models mapping: {path}")
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for model, obj in models.items():
        rounds = _find_round_map(obj)
        if rounds:
            out[str(model)] = rounds
    if not out:
        raise ValueError(f"no per-round model results found in panel task JSON: {path}")
    return out


def _round_case_ratio(r: dict[str, Any]) -> float | None:
    try:
        passed = float(r["pass"])
        total = float(r["total"])
    except (KeyError, TypeError, ValueError):
        return None
    return passed / total if total > 0 else None


def _round_reward(r: dict[str, Any]) -> float | None:
    try:
        return float(r["reward"])
    except (KeyError, TypeError, ValueError):
        ratio = _round_case_ratio(r)
        return 1.0 if ratio == 1.0 else (0.0 if ratio is not None else None)


def _fit_1pl(
    items: dict[str, dict[Any, dict[str, Any]]],
    response_fn,
    *,
    iterations: int = 300,
    reg: float = 1.0,
) -> dict[Any, float]:
    """Fit a regularized 1PL logistic calibration.

    ``response_fn`` may return either a binary response or a fractional response
    in [0, 1]. Fractional case-completion responses are treated as equal-weight
    soft observations per model-round. This avoids giving rounds with hundreds
    of verifier cases disproportionate influence over latent model ability.

    The resulting beta is a descriptive panel calibration, not an official
    EvoCode metric and not an intrinsic isolated-round difficulty estimate.
    """

    models = sorted(items)
    item_ids = sorted({r for m in models for r in items[m]}, key=str)
    theta = {m: 0.0 for m in models}
    beta = {r: 0.0 for r in item_ids}

    obs: list[tuple[str, Any, float]] = []
    for model in models:
        for item, result in items[model].items():
            y = response_fn(result)
            if y is None:
                continue
            y = min(1.0, max(0.0, float(y)))
            obs.append((model, item, y))

    if not obs:
        return {}

    def sigmoid(x: float) -> float:
        if x >= 0:
            z = math.exp(-x)
            return 1.0 / (1.0 + z)
        z = math.exp(x)
        return z / (1.0 + z)

    by_model: dict[str, list[tuple[Any, float]]] = {m: [] for m in models}
    by_item: dict[Any, list[tuple[str, float]]] = {r: [] for r in item_ids}
    for model, item, y in obs:
        by_model[model].append((item, y))
        by_item[item].append((model, y))

    for _ in range(iterations):
        max_delta = 0.0

        for model in models:
            g = -reg * theta[model]
            h = -reg
            for item, y in by_model[model]:
                p = sigmoid(theta[model] - beta[item])
                g += y - p
                h -= p * (1.0 - p)
            delta = g / (-h) if h < 0 else 0.0
            theta[model] += delta
            max_delta = max(max_delta, abs(delta))

        for item in item_ids:
            g = -reg * beta[item]
            h = -reg
            for model, y in by_item[item]:
                p = sigmoid(theta[model] - beta[item])
                g += p - y
                h -= p * (1.0 - p)
            delta = g / (-h) if h < 0 else 0.0
            beta[item] += delta
            max_delta = max(max_delta, abs(delta))

        if max_delta < 1e-9:
            break

    # Shift abilities and difficulties together for an interpretable zero mean.
    shift = mean(beta.values()) if beta else 0.0
    return {item: beta[item] - shift for item in beta}


def _binary_response(result: dict[str, Any]) -> float | None:
    reward = _round_reward(result)
    if reward is None:
        return None
    return 1.0 if reward >= 1.0 else 0.0


def _case_response(result: dict[str, Any]) -> float | None:
    return _round_case_ratio(result)


def load_panel_directory(panel_dir: Path) -> dict[str, dict[str, dict[int, dict[str, Any]]]]:
    """Load all public per-task panel JSON files in a directory."""
    panel_dir = Path(panel_dir)
    out: dict[str, dict[str, dict[int, dict[str, Any]]]] = {}
    for p in sorted(panel_dir.glob("*.json")):
        try:
            out[p.stem] = load_panel_task(p)
        except (ValueError, json.JSONDecodeError):
            continue
    if not out:
        raise ValueError(f"no usable panel task JSON files found in: {panel_dir}")
    return out


def _global_panel_calibration(
    panel_tasks: dict[str, dict[str, dict[int, dict[str, Any]]]],
    response_fn,
) -> dict[tuple[str, int], float]:
    by_model: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    for task, models in panel_tasks.items():
        for model, rounds in models.items():
            dst = by_model.setdefault(model, {})
            for n, result in rounds.items():
                dst[(task, n)] = result
    return _fit_1pl(by_model, response_fn)



def _wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    margin = (
        z
        * math.sqrt((p * (1.0 - p) / total) + (z2 / (4.0 * total * total)))
        / denom
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _midrank_percentile(value: float | None, population: Iterable[float]) -> float | None:
    if value is None:
        return None
    vals = [float(v) for v in population if v is not None and math.isfinite(float(v))]
    if not vals:
        return None
    less = sum(v < value for v in vals)
    equal = sum(v == value for v in vals)
    return (less + 0.5 * equal) / len(vals)


def panel_rounds(
    panel_json: Path | None = None,
    *,
    panel_dir: Path | None = None,
    task_key: str | None = None,
) -> list[PanelRound]:
    if panel_dir is not None:
        if not task_key:
            raise ValueError("task_key is required with panel_dir")
        panel_tasks = load_panel_directory(panel_dir)
        if task_key not in panel_tasks:
            raise ValueError(f"target task {task_key!r} not found in panel directory")

        models = panel_tasks[task_key]
        binary_global = _global_panel_calibration(panel_tasks, _binary_response)
        case_global = _global_panel_calibration(panel_tasks, _case_response)

        binary_beta = {
            n: binary_global.get((task_key, n))
            for n in {r for rounds in models.values() for r in rounds}
        }
        case_beta = {
            n: case_global.get((task_key, n))
            for n in {r for rounds in models.values() for r in rounds}
        }
        binary_population = list(binary_global.values())
        case_population = list(case_global.values())
        item_count = len(case_population)
    elif panel_json is not None:
        models = load_panel_task(panel_json)
        binary_beta = _fit_1pl(models, _binary_response)
        case_beta = _fit_1pl(models, _case_response)
        binary_population = list(binary_beta.values())
        case_population = list(case_beta.values())
        item_count = len(case_population)
    else:
        return []

    round_ids = sorted({r for rounds in models.values() for r in rounds})
    out: list[PanelRound] = []

    for n in round_ids:
        ratios: list[float] = []
        rewards: list[float] = []

        for rounds in models.values():
            if n not in rounds:
                continue
            ratio = _round_case_ratio(rounds[n])
            reward = _round_reward(rounds[n])
            if ratio is not None:
                ratios.append(ratio)
            if reward is not None:
                rewards.append(1.0 if reward >= 1.0 else 0.0)

        total_models = len(models)
        reached_models = sum(n in rounds for rounds in models.values())
        passed_models = int(sum(rewards))
        ci_low, ci_high = _wilson_interval(passed_models, len(rewards))

        binary_b = binary_beta.get(n)
        case_b = case_beta.get(n)

        out.append(
            PanelRound(
                round=n,
                panel_models_total=total_models,
                panel_models_reached=reached_models,
                panel_reach_rate=reached_models / total_models if total_models else 0.0,
                panel_round_pass_rate_reached=mean(rewards) if rewards else None,
                panel_round_pass_wilson_low_reached=ci_low,
                panel_round_pass_wilson_high_reached=ci_high,
                panel_case_mean_reached=mean(ratios) if ratios else None,
                panel_case_median_reached=median(ratios) if ratios else None,
                panel_case_std_reached=(
                    pstdev(ratios) if len(ratios) > 1 else (0.0 if ratios else None)
                ),
                panel_binary_1pl_beta=binary_b,
                panel_binary_1pl_percentile=_midrank_percentile(
                    binary_b, binary_population
                ),
                panel_case_1pl_beta=case_b,
                panel_case_1pl_percentile=_midrank_percentile(
                    case_b, case_population
                ),
                panel_calibration_items_total=item_count if item_count else None,
            )
        )
    return out

def _finite(values: Iterable[float | None]) -> list[float]:
    return [float(v) for v in values if v is not None and math.isfinite(float(v))]


def _range_summary(values: Iterable[float | None]) -> dict[str, float] | None:
    vals = _finite(values)
    if not vals:
        return None
    return {
        "min": min(vals),
        "max": max(vals),
        "spread": max(vals) - min(vals),
        "mean": mean(vals),
        "std": pstdev(vals) if len(vals) > 1 else 0.0,
    }


def _extreme_round(
    rows: list[dict[str, Any]],
    field: str,
    *,
    hardest: bool,
) -> dict[str, Any] | None:
    candidates = [
        r for r in rows
        if int(r["round"]) > 1 and r.get(field) is not None
    ]
    if not candidates:
        return None
    row = max(candidates, key=lambda r: float(r[field])) if hardest else min(
        candidates, key=lambda r: float(r[field])
    )
    return {
        "round": int(row["round"]),
        "change_types": row.get("change_types"),
        "value": float(row[field]),
    }


def _difficulty_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    adaptations = [r for r in rows if int(r["round"]) > 1]
    return {
        "scope": "adaptation rounds only (R2+); R1 is initial construction",
        "adaptation_rounds": len(adaptations),
        "case_churn": _range_summary(r.get("case_churn_rate") for r in adaptations),
        "panel_round_pass_reached": _range_summary(
            r.get("panel_round_pass_rate_reached") for r in adaptations
        ),
        "panel_case_mean_reached": _range_summary(
            r.get("panel_case_mean_reached") for r in adaptations
        ),
        "panel_binary_1pl_percentile": _range_summary(
            r.get("panel_binary_1pl_percentile") for r in adaptations
        ),
        "panel_case_1pl_beta": _range_summary(
            r.get("panel_case_1pl_beta") for r in adaptations
        ),
        "panel_case_1pl_percentile": _range_summary(
            r.get("panel_case_1pl_percentile") for r in adaptations
        ),
        "easiest_case_calibrated_round": _extreme_round(
            rows, "panel_case_1pl_beta", hardest=False
        ),
        "hardest_case_calibrated_round": _extreme_round(
            rows, "panel_case_1pl_beta", hardest=True
        ),
        "highest_churn_round": _extreme_round(
            rows, "case_churn_rate", hardest=True
        ),
    }



def adaptation_difficulty(
    task_dir: Path,
    run_dir: Path | None = None,
    panel_json: Path | None = None,
    panel_dir: Path | None = None,
) -> dict[str, Any]:
    from .case_metrics import analyze_run

    task_dir = Path(task_dir)
    structural = {r.round: asdict(r) for r in structural_rounds(task_dir, run_dir)}
    panel = {
        r.round: asdict(r)
        for r in panel_rounds(panel_json, panel_dir=panel_dir, task_key=task_dir.name)
    }
    target = {}
    if run_dir is not None:
        target = {int(r["round"]): r for r in analyze_run(run_dir)["rounds"]}

    rows = []
    for n in sorted(structural):
        row = dict(structural[n])
        row["change_types"] = "+".join(row["change_types"]) or "unspecified"
        if n in panel:
            row.update({k: v for k, v in panel[n].items() if k != "round"})
        if n in target:
            t = target[n]
            row.update({
                "target_round_reward": t.get("reward"),
                "target_case_success": t.get("cases_success"),
                "target_case_total": t.get("cases_total"),
                "target_case_ratio": t.get("success_rate"),
                "target_new_success_rate": t.get("new_success_rate"),
                "target_regressions": t.get("regressions"),
                "target_recoveries": t.get("recoveries"),
            })
        rows.append(row)

    return {
        "methodology": {
            "structural": "task/verifier descriptors; not a scalar difficulty claim",
            "panel": "released sequential cross-model outcomes; reports both round reach and conditional-on-reach performance, so survivorship is visible",
            "binary_1pl": "regularized 1PL over perfect-round rewards; useful for all-or-nothing success but may saturate when all models fail a round",
            "case_1pl": "regularized equal-weight fractional 1PL over per-model case-completion ratios; higher beta means harder for the released sequential panel",
            "target_outcome": "sequential target-agent performance, shown alongside but not used to estimate panel difficulty",
            "causal_warning": "sequential target-agent performance is an outcome, not an intrinsic difficulty estimate",
            "preferred_history_control": "oracle-prefix isolated-round evaluation",
        },
        "summary": _difficulty_summary(rows),
        "rounds": rows,
    }

def write_difficulty(result: dict[str, Any], out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adaptation_difficulty.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )

    rows = result["rounds"]
    fields = [
        "round",
        "change_types",
        "instruction_words",
        "instruction_lines",
        "solution_lines",
        "verifier_lines_added",
        "verifier_lines_removed",
        "active_cases",
        "introduced_cases",
        "retired_cases",
        "retained_cases",
        "case_churn_rate",
        "active_requirements",
        "introduced_requirements",
        "retired_requirements",
        "panel_models_total",
        "panel_models_reached",
        "panel_reach_rate",
        "panel_round_pass_rate_reached",
        "panel_round_pass_wilson_low_reached",
        "panel_round_pass_wilson_high_reached",
        "panel_case_mean_reached",
        "panel_case_median_reached",
        "panel_case_std_reached",
        "panel_binary_1pl_beta",
        "panel_binary_1pl_percentile",
        "panel_case_1pl_beta",
        "panel_case_1pl_percentile",
        "panel_calibration_items_total",
        "target_round_reward",
        "target_case_success",
        "target_case_total",
        "target_case_ratio",
        "target_new_success_rate",
        "target_regressions",
        "target_recoveries",
    ]

    with (out_dir / "adaptation_difficulty.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})

    def pct(value):
        return "—" if value is None else f"{100 * value:.1f}%"

    def beta(value):
        return "—" if value is None else f"{value:+.2f}"

    def number(value):
        return "—" if value is None else str(value)

    lines = [
        "# Adaptation difficulty",
        "",
        "Structural change, released-panel difficulty, and target-agent performance "
        "are reported as separate axes.",
        "",
        "## Difficulty calibration",
        "",
        "| R | Change | Churn | Panel case | Case β | Case diff pct | Perfect pass | "
        "Perfect diff pct | Target case | Reg | Rec |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in rows:
        lines.append(
            f"| {r['round']} | {r['change_types']} | "
            f"{pct(r.get('case_churn_rate'))} | "
            f"{pct(r.get('panel_case_mean_reached'))} | "
            f"{beta(r.get('panel_case_1pl_beta'))} | "
            f"{pct(r.get('panel_case_1pl_percentile'))} | "
            f"{pct(r.get('panel_round_pass_rate_reached'))} | "
            f"{pct(r.get('panel_binary_1pl_percentile'))} | "
            f"{pct(r.get('target_case_ratio'))} | "
            f"{number(r.get('target_regressions'))} | "
            f"{number(r.get('target_recoveries'))} |"
        )

    lines.extend(
        [
            "",
            "Case β is an equal-weight fractional 1PL calibration over each released "
            "model's case-completion ratio. Higher β / percentile means harder for "
            "the released sequential panel.",
            "",
            "Perfect-round difficulty uses binary reward and is retained as a secondary "
            "all-or-nothing view. It can saturate when every model misses at least one case.",
            "",
            "Neither panel calibration is an intrinsic isolated-round difficulty estimate.",
            "",
            "## Structural descriptors",
            "",
            "| R | Instr words | Ref-solution lines | Verifier + | Verifier - | "
            "Active cases | +cases | -cases | Active reqs | +reqs | -reqs |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for r in rows:
        lines.append(
            f"| {r['round']} | {r['instruction_words']} | {r['solution_lines']} | "
            f"{number(r.get('verifier_lines_added'))} | "
            f"{number(r.get('verifier_lines_removed'))} | "
            f"{number(r.get('active_cases'))} | "
            f"{number(r.get('introduced_cases'))} | "
            f"{number(r.get('retired_cases'))} | "
            f"{number(r.get('active_requirements'))} | "
            f"{number(r.get('introduced_requirements'))} | "
            f"{number(r.get('retired_requirements'))} |"
        )

    summary = result.get("summary", {})
    lines.extend(["", "## Adaptation heterogeneity (R2+)", ""])

    for key, label, scale in [
        ("case_churn", "Case-set churn", 100.0),
        ("panel_round_pass_reached", "Perfect-round panel pass", 100.0),
        ("panel_case_mean_reached", "Panel case completion", 100.0),
        ("panel_binary_1pl_percentile", "Perfect-round difficulty percentile", 100.0),
        ("panel_case_1pl_percentile", "Case-completion difficulty percentile", 100.0),
    ]:
        stats = summary.get(key)
        if stats:
            lines.append(
                f"- **{label}:** {scale * stats['min']:.1f}% to "
                f"{scale * stats['max']:.1f}% "
                f"(spread {scale * stats['spread']:.1f} pp)."
            )

    case_beta_stats = summary.get("panel_case_1pl_beta")
    if case_beta_stats:
        lines.append(
            f"- **Case-completion β:** {case_beta_stats['min']:+.2f} to "
            f"{case_beta_stats['max']:+.2f} "
            f"(span {case_beta_stats['spread']:.2f})."
        )

    hardest = summary.get("hardest_case_calibrated_round")
    easiest = summary.get("easiest_case_calibrated_round")
    churn = summary.get("highest_churn_round")
    if easiest and hardest:
        lines.append(
            f"- **Case-calibrated extremes:** easiest R{easiest['round']} "
            f"({easiest['change_types']}), hardest R{hardest['round']} "
            f"({hardest['change_types']})."
        )
    if churn:
        lines.append(
            f"- **Highest structural churn:** R{churn['round']} "
            f"({churn['change_types']}), {100 * churn['value']:.1f}%."
        )

    lines.extend(
        [
            "",
            "These are descriptive measures of non-uniformity under the released "
            "sequential evaluation. The preferred causal control for history effects "
            "is an oracle-prefix isolated-round run with the same target agent.",
        ]
    )

    (out_dir / "adaptation_difficulty.md").write_text("\n".join(lines) + "\n")
