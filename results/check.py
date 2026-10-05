"""Check the fifteen best-single answers, on their own.

    python make_instance.py                 # once: instances.json from the official files in data/
    python results/check.py                 # every answer, by the plain-Python reading
    python results/check.py --checker       # ... and by the challenge's official checker
    python results/check.py --ranking FILE  # ... and the places they would take in the 2018 final

Each answer in `best-single/` is judged against `instances.json` by
`verify.validity_reasons` (the rules of problem.txt, written out in loops) and
`verify.objective`, and the objective is compared with the one `provenance.json`
records. `--checker` also converts each answer to the challenge's CSV and runs the
official checker (built from its source in data/checker, see make_instance.py),
reading back validSolution and the objective it prints.

`--ranking FILE` takes the 2018 final's weighted results (one row per instance
B1..B15, then X1..X15; one column per team; the cell is the team's
0.1 x 180 s + 0.9 x 3600 s objective, empty or a penalty value when the team had
no valid answer) as a tab-separated export of final_results.xlsx, and gives each
answer its place on its instance and the points that place earns (rank r earns
max(0, 11 - r)), with the teams' own totals beside ours.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("verify", ROOT / "verify.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def ranking(path: Path, ours: list[int]) -> None:
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter="\t"))
    teams = [t for t in rows[0][1:] if t]
    table = {t: [float(r[j]) if j < len(r) and r[j].strip() else float("inf") for r in rows[1:16]]
             for j, t in enumerate(teams, start=1)}
    table["US"] = [float(v) for v in ours]
    points = dict.fromkeys(table, 0)
    for i in range(15):
        column = {t: v[i] for t, v in table.items()}
        for t, v in column.items():
            points[t] += max(0, 11 - (1 + sum(1 for y in column.values() if y < v)))
    order = sorted(points.items(), key=lambda kv: -kv[1])
    place = 1 + sum(1 for t, q in points.items() if t != "US" and q > points["US"])
    print(f"\ndataset B, the 2018 final's {len(teams)} teams and these answers: {points['US']} points, place {place}")
    for t, q in order[:8]:
        print(f"  {'these answers' if t == 'US' else t:14s} {q}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checker", action="store_true", help="also run the official checker")
    parser.add_argument("--ranking", type=Path, help="the 2018 final's weighted results, tab-separated")
    args = parser.parse_args()
    instances_file = ROOT / "instances.json"
    if not instances_file.exists():
        raise SystemExit("no instances.json: run make_instance.py first (it reads the official files from data/)")
    instances = {i["name"]: i for i in json.loads(instances_file.read_text(encoding="utf-8"))}
    recorded = {r["instance"]: r for r in json.loads((HERE / "best-single" / "provenance.json").read_text(encoding="utf-8"))}
    total, values, failures = 0, [], 0
    for k in range(1, 16):
        name = f"B{k}"
        answer = json.loads((HERE / "best-single" / f"{name}.json").read_text(encoding="utf-8"))
        reasons = V.validity_reasons(instances[name], answer)
        of = V.objective(instances[name], answer)
        line = f"{name:4s} {of:>13,}  {'valid' if not reasons else 'REFUSED ' + '; '.join(reasons[:2])}"
        ok = not reasons and of == recorded[name]["objective"]
        if args.checker:
            verdict = V.run_checker(instances[name], answer, tag="results")
            line += f"  | checker: valid={verdict.get('valid')} OF={verdict.get('of')}"
            ok = ok and verdict.get("valid") and int(verdict.get("of")) == of
        print(line + ("" if ok else "   <-- DIFFERS FROM THE RECORD"))
        failures += not ok
        total += of
        values.append(of)
    print(f"\nmean loss over B1-B15: {total / 15:,.1f} mm^2 ({total / 15e6:.4f} M); "
          f"{'all fifteen agree with the record' if not failures else f'{failures} disagree'}")
    if args.ranking:
        ranking(args.ranking, values)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
