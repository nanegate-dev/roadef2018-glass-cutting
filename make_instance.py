"""Write the fifteen dataset-B instances of the ROADEF/EURO 2018 challenge, and prove what they are.

    python make_instance.py                     # writes instances.json from the official CSVs (all fifteen)
    python make_instance.py DIR                 # ... reading the official files from DIR instead
    python make_instance.py --only B1,B7        # a subset, in the order given
    python make_instance.py --check             # rebuild in memory, compare byte for byte
    python make_instance.py --self-test         # the data, the rivals and the round trip, asserted

THE DATA IS THE CHALLENGE'S, UNCHANGED. Saint-Gobain Glass France published, for
the ROADEF/EURO 2018 challenge, a batch file (ITEM_ID;LENGTH_ITEM;WIDTH_ITEM;
STACK;SEQUENCE) and a defect file (DEFECT_ID;PLATE_ID;X;Y;WIDTH;HEIGHT) per
instance, and one global_param.csv (nPlates 100, widthPlates 6000, heightPlates
3210, min1Cut 100, max1Cut 3500, min2Cut 100, minWaste 20). DIR is the folder
holding `dataset_B/` and the checker's `checker/instances_checker/global_param.csv`
(default: $ROADEF2018_DIR, else `data/` next to this file). Nothing is
downloaded here.

HOW THE OFFICIAL CHECKER READS THEM, AND WHY THE INSTANCE CARRIES WHAT IT CARRIES.
The checker (main.cpp, 23/05/2018) reads LENGTH_ITEM as an item's height and
WIDTH_ITEM as its width, so `item_h` and `item_w` are those two columns (an item
may be rotated, so the pair is what matters). It builds each stack from the batch
rows IN FILE ORDER, which is the SEQUENCE order only if the rows are sorted; the
self-test asserts they are, so `stacks` -- each stack as its list of item ids, in
the order they must be cut -- is exactly the checker's stack. It reads defect
coordinates with atoi, which truncates "428.0" to 428; every B coordinate is a
whole number, asserted. It stops reading defects at the first row whose plate is
not used, which loses nothing only when the file is sorted by plate; asserted.
The defects of all 100 plates are carried (at most 441 per instance), so no bound
on the plates an answer may use is assumed beyond the challenge's own nPlates.

THE RIVALS ARE LABELS NO RULE READS. `best_180s` and `best_3600s` are the best
objective over all teams in the challenge's final phase (final_results.xlsx,
sheets RESULT_180 and RESULT_3600, re-derived here from their TSV exports when
present); `best_known` is Libralesso and Fontan, EJOR 291(3) 2021, Table 4, as
transcribed. Each of the 45 numbers is checked to be an objective an answer can
have: v + (the items' area) is a whole multiple of the plate height, giving a
whole number of plates and a residual width inside the plate.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "instances.json"
DEFAULT_DIR = Path(os.environ.get("ROADEF2018_DIR", str(HERE / "data")))
NAMES = tuple(f"B{k}" for k in range(1, 16))

#: (best over all teams, 180 s runs; best over all teams, 3600 s runs; best known,
#: Libralesso & Fontan 2021, Table 4), mm^2 of geometrical loss.
RIVALS = {
    "B1": (3_232_698, 2_661_318, 2_661_318),
    "B2": (15_635_435, 13_674_125, 11_931_095),
    "B3": (20_540_813, 18_191_093, 15_786_803),
    "B4": (8_269_045, 8_269_045, 7_315_675),
    "B5": (72_155_615, 72_155_615, 72_155_615),
    "B6": (12_116_527, 11_195_257, 10_800_427),
    "B7": (9_601_299, 8_355_819, 6_628_839),
    "B8": (17_865_559, 16_067_959, 14_398_759),
    "B9": (18_502_147, 17_484_577, 16_495_897),
    "B10": (26_012_183, 21_951_533, 21_951_533),
    "B11": (25_251_890, 22_584_380, 20_626_280),
    "B12": (15_868_657, 13_958_707, 12_514_207),
    "B13": (28_349_055, 24_471_375, 22_657_725),
    "B14": (9_346_480, 8_656_330, 8_023_960),
    "B15": (27_794_441, 24_517_031, 22_619_921),
}

#: The global parameters, in the order global_param.csv lists them, and the keys the
#: instance carries them under.
PARAMS = (("nPlates", "n_plates_max"), ("widthPlates", "plate_w"), ("heightPlates", "plate_h"),
          ("min1Cut", "min1cut"), ("max1Cut", "max1cut"), ("min2Cut", "min2cut"), ("minWaste", "min_waste"))
PARAM_KEYS = tuple(key for _, key in PARAMS)
ITEM_KEYS = ("item_w", "item_h")
DEFECT_KEYS = ("defect_plate", "defect_x", "defect_y", "defect_w", "defect_h")
LABEL_KEYS = ("name", "source", "best_180s", "best_3600s", "best_known")


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.reader(handle, delimiter=";")]
    return [row for row in rows[1:] if row and row[0].strip()]


def _atoi(text: str) -> int:
    """C's atoi on the leading digits, which is what the checker does: "428.0" is 428."""
    text = text.strip()
    sign, digits = 1, ""
    if text[:1] in "+-":
        sign, text = (-1 if text[0] == "-" else 1), text[1:]
    for ch in text:
        if not ch.isdigit():
            break
        digits += ch
    return sign * int(digits or "0")


def read_params(path: Path) -> dict[str, int]:
    rows = _rows(path)
    values = {row[0]: _atoi(row[1]) for row in rows}
    return {key: values[name] for name, key in PARAMS}


def read_batch(path: Path) -> dict:
    """Items and stacks, as the checker builds them."""
    rows = _rows(path)
    ids = [_atoi(r[0]) for r in rows]
    if ids != list(range(len(rows))):
        raise SystemExit(f"{path.name}: item ids are not 0..n-1 in file order")
    item_h = [_atoi(r[1]) for r in rows]   # LENGTH_ITEM: the checker's height
    item_w = [_atoi(r[2]) for r in rows]   # WIDTH_ITEM: the checker's width
    stack = [_atoi(r[3]) for r in rows]
    seq = [_atoi(r[4]) for r in rows]
    stacks: list[list[int]] = []
    for item, (s, q) in enumerate(zip(stack, seq)):
        if s == len(stacks):
            stacks.append([])
        if s != len(stacks) - 1 or q != len(stacks[s]) + 1:
            raise SystemExit(f"{path.name}: row {item} is not in stack-then-sequence order "
                             f"(stack {s}, sequence {q}); the checker would read another stack")
        stacks[s].append(item)
    return {"item_w": item_w, "item_h": item_h, "stacks": stacks}


def read_defects(path: Path, params: dict[str, int]) -> dict:
    rows = _rows(path)
    out = {key: [] for key in DEFECT_KEYS}
    last_plate = -1
    for position, r in enumerate(rows):
        if _atoi(r[0]) != position:
            raise SystemExit(f"{path.name}: defect ids are not 0..D-1 in file order")
        plate = _atoi(r[1])
        numbers = [float(v) for v in r[2:6]]
        if any(v != int(v) for v in numbers):
            raise SystemExit(f"{path.name}: defect {position} has a coordinate that is not whole: {r}")
        x, y, w, h = (_atoi(v) for v in r[2:6])
        if plate < last_plate:
            raise SystemExit(f"{path.name}: defects are not sorted by plate; the checker would drop some")
        if not (0 <= plate < params["n_plates_max"] and w >= 1 and h >= 1 and x >= 0 and y >= 0
                and x + w <= params["plate_w"] and y + h <= params["plate_h"]):
            raise SystemExit(f"{path.name}: defect {position} is not a positive rectangle inside its plate: {r}")
        last_plate = plate
        for key, value in zip(DEFECT_KEYS, (plate, x, y, w, h)):
            out[key].append(value)
    return out


def build_one(folder: Path, name: str) -> dict:
    params = read_params(folder / "checker" / "instances_checker" / "global_param.csv")
    batch = read_batch(folder / "dataset_B" / f"{name}_batch.csv")
    defects = read_defects(folder / "dataset_B" / f"{name}_defects.csv", params)
    best_180, best_3600, best_known = RIVALS[name]
    return {
        "name": name,
        "source": (f"ROADEF/EURO 2018 challenge (Saint-Gobain Glass France), dataset B, instance {name}: "
                   f"{name}_batch.csv, {name}_defects.csv and global_param.csv as published by the challenge"),
        "best_180s": best_180,
        "best_3600s": best_3600,
        "best_known": best_known,
        **params,
        **batch,
        **defects,
    }


def build(folder: Path, names: tuple[str, ...] = NAMES) -> list[dict]:
    return [build_one(folder, name) for name in names]


def render(instances: list[dict]) -> str:
    """One instance per line, compact."""
    return "[\n" + ",\n".join(json.dumps(i, separators=(",", ":")) for i in instances) + "\n]\n"


# --- the worked instance problem.txt uses ----------------------------------------

#: A 1000 x 500 plate, three plates at most, the challenge's cut rules with max1cut
#: 600 so that a stripe too wide can be exhibited inside one plate. Six items in
#: three stacks; four defects, one on each of plates 0 (two), 1 and 2.
FIXTURE = {
    "name": "worked",
    "source": "the worked instance of problem.txt: six items, three stacks, four defects, 1000 x 500 plates",
    "best_180s": 0,
    "best_3600s": 0,
    "best_known": 0,
    "n_plates_max": 3,
    "plate_w": 1000,
    "plate_h": 500,
    "min1cut": 100,
    "max1cut": 600,
    "min2cut": 100,
    "min_waste": 20,
    "item_w": [300, 300, 450, 200, 250, 450],
    "item_h": [200, 200, 200, 300, 150, 350],
    "stacks": [[0, 1, 2], [3, 4], [5]],
    "defect_plate": [0, 0, 1, 2],
    "defect_x": [150, 900, 600, 500],
    "defect_y": [450, 100, 200, 250],
    "defect_w": [4, 5, 3, 4],
    "defect_h": [4, 3, 3, 4],
}


def fixture() -> dict:
    return json.loads(json.dumps(FIXTURE))


def item_area(instance: dict) -> int:
    return sum(w * h for w, h in zip(instance["item_w"], instance["item_h"]))


def decompose(instance: dict, value: int) -> tuple[int, int] | None:
    """(plates, residual width) of an objective value, or None if no answer has it."""
    q, r = divmod(value + item_area(instance), instance["plate_h"])
    if r:
        return None
    plates = -(-q // instance["plate_w"])
    residual = plates * instance["plate_w"] - q
    if not (1 <= plates <= instance["n_plates_max"] and 0 <= residual < instance["plate_w"]):
        return None
    return plates, residual


# --- the self-test -----------------------------------------------------------------


def _sheet_minima(path: Path) -> dict[str, int]:
    """The best raw objective per B instance in one results sheet's first block."""
    lines = [line.rstrip("\n").split("\t") for line in path.read_text(encoding="utf-8").splitlines()]
    out: dict[str, int] = {}
    for row in lines[1:]:
        if row and row[0] in RIVALS and row[0] not in out:
            values = [float(v) for v in row[1:] if v.strip()]
            out[row[0]] = int(min(values))
        if row and not row[0].strip():
            break
    return out


def self_test(folder: Path) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    problems: list[str] = []
    instances = build(folder)
    params = read_params(folder / "checker" / "instances_checker" / "global_param.csv")
    print(f"global_param.csv: {params}")
    if params != {"n_plates_max": 100, "plate_w": 6000, "plate_h": 3210, "min1cut": 100, "max1cut": 3500,
                  "min2cut": 100, "min_waste": 20}:
        problems.append("the global parameters are not the challenge's")

    for sheet, column in (("sheet1.tsv", 0), ("sheet2.tsv", 1)):
        path = folder / sheet
        if not path.is_file():
            print(f"{sheet} not present: the {('180 s', '3600 s')[column]} column is taken as transcribed")
            continue
        minima = _sheet_minima(path)
        wrong = [n for n in NAMES if minima.get(n) != RIVALS[n][column]]
        print(f"{sheet} ({('RESULT_180', 'RESULT_3600')[column]}): the best over all teams re-derived for "
              f"{len(minima)} instances; {'all equal the transcribed column' if not wrong else f'DIFFERENT: {wrong}'}")
        if wrong:
            problems.append(f"{sheet}: {wrong}")

    print(f"\n{'':<4} {'items':>5} {'stacks':>6} {'longest':>7} {'defects':>7} {'dims':>11} {'item area':>13} "
          f"{'plates>=':>8}  rivals (plates, residual)")
    for inst in instances:
        name = inst["name"]
        n, stacks = len(inst["item_w"]), inst["stacks"]
        if sorted(i for s in stacks for i in s) != list(range(n)):
            problems.append(f"{name}: the stacks do not partition the items")
        dims = inst["item_w"] + inst["item_h"]
        area = item_area(inst)
        # the batch round-trips: the rows the instance implies are the file's rows
        rows = _rows(folder / "dataset_B" / f"{name}_batch.csv")
        rebuilt = []
        for s, members in enumerate(stacks):
            for q, item in enumerate(members, start=1):
                rebuilt.append((item, inst["item_h"][item], inst["item_w"][item], s, q))
        rebuilt.sort()
        if rebuilt != [tuple(_atoi(v) for v in r[:5]) for r in rows]:
            problems.append(f"{name}: the batch does not round-trip")
        drows = _rows(folder / "dataset_B" / f"{name}_defects.csv")
        dback = [(d, *(inst[k][d] for k in DEFECT_KEYS)) for d in range(len(inst["defect_x"]))]
        if dback != [tuple(_atoi(v) for v in r[:6]) for r in drows]:
            problems.append(f"{name}: the defects do not round-trip")
        cells = []
        for value in RIVALS[name]:
            parts = decompose(inst, value)
            if parts is None:
                problems.append(f"{name}: rival {value} is not an objective any answer can have")
            cells.append(f"{parts}")
        b180, b3600, known = RIVALS[name]
        if not known <= b3600 <= b180:
            problems.append(f"{name}: the rival columns are not ordered")
        print(f"{name:<4} {n:>5} {len(stacks):>6} {max(len(s) for s in stacks):>7} {len(inst['defect_x']):>7} "
              f"{min(dims):>5}..{max(dims):<5} {area:>13,} {area / (inst['plate_w'] * inst['plate_h']):>8.2f}  "
              + "  ".join(cells))
        if max(dims) >= inst["plate_h"] or min(dims) < inst["min2cut"]:
            problems.append(f"{name}: an item side reaches the plate height or is under min2cut")

    fix = fixture()
    if decompose(fix, 210_000) != (2, 650):
        problems.append("the worked instance's worked answer does not decompose")
    text = render(instances)
    held = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
    print(f"\ninstances.json: {'byte-identical to a rebuild' if held == text else 'DIFFERS from a rebuild'}")
    if held != text:
        problems.append("instances.json is not the rebuild")
    if problems:
        print("\nFAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nOK: 15 instances, every item id, stack, sequence and defect as the checker reads it; all 45 rival "
          "numbers are objectives an answer can have")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_DIR,
                        help="the folder holding dataset_B/ and checker/")
    parser.add_argument("--only", help="a comma-separated subset, e.g. B1,B7")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if args.self_test:
        return self_test(args.folder)
    names = tuple(n.strip() for n in args.only.split(",")) if args.only else NAMES
    unknown = [n for n in names if n not in RIVALS]
    if unknown:
        raise SystemExit(f"not a dataset-B instance: {unknown}")
    text = render(build(args.folder, names)).encode("utf-8")
    if args.check:
        held = args.out.read_bytes() if args.out.is_file() else b""
        print(f"{args.out.name}: {'byte-identical' if held == text else 'DIFFERS'} "
              f"({len(held):,} bytes held, {len(text):,} rebuilt)")
        return 0 if held == text else 1
    args.out.write_bytes(text)
    print(f"wrote {args.out.name} ({args.out.stat().st_size:,} bytes): {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
