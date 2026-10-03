from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Optional


@dataclass(frozen=True)
class RoundMetric:
    round_index: int
    reward: float
    case_success: int
    case_total: int
    cumulative_tokens: Optional[int] = None

    @property
    def case_ratio(self) -> float:
        if self.case_total <= 0:
            return 0.0
        return self.case_success / self.case_total


@dataclass(frozen=True)
class TaskMetrics:
    rounds: int
    task_score: float
    case_score: float
    regression_count: int
    final_round_passed: bool
    perfect_task: bool
    progress_auc_tokens: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


def compute_task_metrics(rounds: Iterable[RoundMetric]) -> TaskMetrics:
    rs = sorted(rounds, key=lambda r: r.round_index)
    if not rs:
        raise ValueError("at least one round is required")

    task_score = sum(1.0 if r.reward >= 1.0 else 0.0 for r in rs) / len(rs)
    case_score = sum(r.case_ratio for r in rs) / len(rs)
    regression_count = sum(
        1 for prev, cur in zip(rs, rs[1:]) if cur.case_ratio + 1e-12 < prev.case_ratio
    )

    auc = _normalized_progress_auc_tokens(rs)
    return TaskMetrics(
        rounds=len(rs),
        task_score=task_score,
        case_score=case_score,
        regression_count=regression_count,
        final_round_passed=rs[-1].reward >= 1.0,
        perfect_task=all(r.reward >= 1.0 for r in rs),
        progress_auc_tokens=auc,
    )


def _normalized_progress_auc_tokens(rs: list[RoundMetric]) -> Optional[float]:
    """Area under case-ratio vs cumulative-token curve, normalized to [0,1].

    This is a proposed Amplio diagnostic, not an EvoCode official metric.
    Returns None when complete monotonic cumulative token snapshots are unavailable.
    """
    if any(r.cumulative_tokens is None for r in rs):
        return None
    xs = [int(r.cumulative_tokens or 0) for r in rs]
    if xs[-1] <= 0 or any(b < a for a, b in zip(xs, xs[1:])):
        return None

    # Anchor at zero tokens with zero externally verified progress.
    points = [(0, 0.0)] + [(x, r.case_ratio) for x, r in zip(xs, rs)]
    area = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        area += (x1 - x0) * (y0 + y1) / 2.0
    return area / xs[-1]


def recovery_tokens(rounds: Iterable[RoundMetric]) -> list[dict]:
    """Token cost from each non-passing round to next fully-passing round.

    Only computed when cumulative token snapshots exist. Multiple failures before the
    same recovery are retained because they represent different starting points.
    """
    rs = sorted(rounds, key=lambda r: r.round_index)
    out: list[dict] = []
    for i, r in enumerate(rs):
        if r.reward >= 1.0 or r.cumulative_tokens is None:
            continue
        for nxt in rs[i + 1 :]:
            if nxt.reward >= 1.0 and nxt.cumulative_tokens is not None:
                out.append(
                    {
                        "failed_round": r.round_index,
                        "recovered_round": nxt.round_index,
                        "recovery_tokens": nxt.cumulative_tokens - r.cumulative_tokens,
                    }
                )
                break
    return out
