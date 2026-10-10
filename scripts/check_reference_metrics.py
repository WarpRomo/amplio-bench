from __future__ import annotations
import csv
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: check_reference_metrics.py ROUND_METRICS.csv")

path = Path(sys.argv[1])
rows = list(csv.DictReader(path.open()))

expected_totals = [
    (1, 34, 115),
    (2, 54, 151),
    (3, 52, 168),
    (4, 59, 204),
    (5, 60, 233),
    (6, 64, 251),
    (7, 64, 268),
    (8, 64, 278),
]

got_totals = [
    (int(r["round"]), int(r["cases_success"]), int(r["cases_total"]))
    for r in rows
]

if got_totals != expected_totals:
    raise SystemExit(
        "REFERENCE_METRICS=FAIL totals changed\n"
        f"expected={expected_totals}\n"
        f"got={got_totals}"
    )

# Cross-round transition values are no longer pinned to the old cNNN-ordinal
# interpretation. Semantic-identity correctness is covered by unit tests.
for row in rows[1:]:
    for field in ("new_cases", "regressions", "recoveries"):
        if row.get(field) in (None, ""):
            raise SystemExit(
                f"REFERENCE_METRICS=FAIL missing {field} in round {row['round']}"
            )

print("REFERENCE_METRICS=PASS")
