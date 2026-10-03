from __future__ import annotations
import csv
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: check_reference_metrics.py ROUND_METRICS.csv")

path = Path(sys.argv[1])
rows = list(csv.DictReader(path.open()))

expected = [
    (1, 34, 115, None, None, None, None),
    (2, 54, 151, 24, 36, 4, 0),
    (3, 52, 168, 2, 17, 4, 0),
    (4, 59, 204, 6, 36, 1, 2),
    (5, 60, 233, 1, 29, 0, 0),
    (6, 64, 251, 4, 18, 1, 1),
    (7, 64, 268, 1, 17, 2, 1),
    (8, 64, 278, 0, 10, 0, 0),
]

got = []
for row in rows:
    def opt_int(name):
        value = row.get(name)
        if value in (None, ""):
            return None
        return int(value)

    got.append((
        int(row["round"]),
        int(row["cases_success"]),
        int(row["cases_total"]),
        opt_int("new_success"),
        opt_int("new_cases"),
        opt_int("regressions"),
        opt_int("recoveries"),
    ))

if got != expected:
    raise SystemExit(
        "REFERENCE_METRICS=FAIL\n"
        f"expected={expected}\n"
        f"got={got}"
    )

print("REFERENCE_METRICS=PASS")
