"""What the rules allow on the real instances, measured rather than asserted.

    python tricks.py              # the calibration, the bounds, the cheats and the checker's leniencies

A bound nobody has pushed on is a bound nobody knows binds, and a pointer nobody
has forged is a pointer nobody knows is checked. Every row below is a whole answer
on a dataset-B instance, judged three ways: this folder's Python reading of the
rules, the locked IR (`verify.judge_both`: the whole verdict and each of the
eleven conditions read alone, which is how the platform's verifier explains a
refusal), and the OFFICIAL CHECKER built from its own source, fed the answer as
its CSV. A row whose readings differ is a failure of this script.

THE CALIBRATION: the starting program on all fifteen instances, its geo_loss
against the three rival columns (the challenge's best 180 s and 3600 s results
and the best published), three ways.

THE BOUNDS BIND, BOTH SIDES: a stripe of 100 and of 3500, a strip of 100 and a
waste of 20 are accepted by all three readings; 99, 3501, 99 and 19 are refused by
all three.

THE CHEATS: each is the starting program's answer with one thing changed and its
certificate derived again (`verify.certify`), unless the row says a number is
forged; each breaks exactly one condition in both readings, and the checker
refuses every one whose geometry is wrong. A forged claim leaves the geometry
valid: the checker accepts it, and the objective it prints is the true one.

THE CHECKER'S LENIENCIES: what it accepts that the subject does not, measured.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import verify  # noqa: E402

nd = verify.node
BRANCH, WASTE, RESIDUAL = verify.BRANCH, verify.WASTE, verify.RESIDUAL


# --- trees ------------------------------------------------------------------------


def walk(root: dict, depth: int = 0, parent: dict | None = None):
    """Every node of a plate: (node, its parent, its cut, its position among its siblings)."""
    yield root, parent, depth, (next(i for i, m in enumerate(parent["c"]) if m is root) if parent else 0)
    for child in root["c"]:
        yield from walk(child, depth + 1, root)


def twin(root: dict, target: dict, other_root: dict) -> dict:
    """The node of `other_root` (a copy of `root`) at the place `target` holds in `root`."""
    at = next(i for i, (m, _, _, _) in enumerate(walk(root)) if m is target)
    return list(walk(other_root))[at][0]


def edited(trees: list, position: int, root: dict, *targets: dict) -> tuple[list, list[dict]]:
    """A copy of the plates and, in it, the nodes standing where `targets` stand."""
    changed = copy.deepcopy(trees)
    return changed, [twin(root, t, changed[position][1]) for t in targets]


def shift(n: dict, dx: int, dy: int) -> None:
    n["x"] += dx
    n["y"] += dy
    for child in n["c"]:
        shift(child, dx, dy)


def axis(depth: int) -> tuple[str, str]:
    """The coordinate and the size a node of this cut runs along among its siblings."""
    return ("x", "w") if depth % 2 == 1 else ("y", "h")


def swap(parent: dict, k: int, depth: int) -> None:
    """Children k and k + 1 of `parent` (both of cut `depth`) change places."""
    a, b = parent["c"][k], parent["c"][k + 1]
    pos, size = axis(depth)
    start = a[pos]
    move_b, move_a = start - b[pos], start + b[size] - a[pos]
    shift(b, *((move_b, 0) if pos == "x" else (0, move_b)))
    shift(a, *((move_a, 0) if pos == "x" else (0, move_a)))
    parent["c"][k], parent["c"][k + 1] = b, a


def defects(instance: dict, plate: int) -> list[tuple[int, int, int, int, int]]:
    keys = ("defect_x", "defect_y", "defect_w", "defect_h")
    return [(d, *(instance[k][d] for k in keys)) for d in range(len(instance["defect_x"]))
            if instance["defect_plate"][d] == plate]


def crosses(line: int, lo: int, size: int) -> bool:
    return lo < line < lo + size


def seed_trees(instance: dict) -> tuple[dict, list[tuple[int, dict]]]:
    answer, _, _ = verify.seed_answer(instance)
    return answer, verify.trees_of(answer)


def carve(instance: dict, trees: list, stripe: dict, width: int) -> list | None:
    """The last plate's residual with a stripe carved from its left, behind a waste gap
    when a defect is in the way: [waste gap][stripe][residual]. `stripe` is built at
    x 0 and moved; no new line may cross a defect and no item may cover one."""
    trees = copy.deepcopy(trees)
    plate, root = trees[-1]
    residual = root["c"][-1]
    if residual["t"] != RESIDUAL:
        return None
    x0, right = residual["x"], residual["x"] + residual["w"]
    marks = defects(instance, plate)
    starts = [x0, *sorted({x0 + 20} | {dx + dw for _, dx, _, dw, _ in marks if dx + dw >= x0 + 20})]
    for start in starts:
        if start + width > right or 0 < right - start - width < instance["min_waste"]:
            continue
        piece = copy.deepcopy(stripe)
        shift(piece, start, 0)
        lines = {start, start + width} - {x0, right}
        if any(crosses(line, dx, dw) for line in lines for _, dx, _, dw, _ in marks):
            continue
        bad = False
        for n, _, _, _ in walk(piece):
            for _, dx, dy, dw, dh in marks:
                meets = n["x"] < dx + dw and dx < n["x"] + n["w"] and n["y"] < dy + dh and dy < n["y"] + n["h"]
                holds = n["x"] <= dx and dx + dw <= n["x"] + n["w"] and n["y"] <= dy and dy + dh <= n["y"] + n["h"]
                if meets and (n["t"] >= 0 or (n["c"] and not holds)):
                    bad = True
        if bad:
            continue
        children = root["c"][:-1]
        if start > x0:
            children.append(nd(WASTE, x0, 0, start - x0, instance["plate_h"]))
        children.append(piece)
        if right > start + width:
            children.append(nd(RESIDUAL, start + width, 0, right - start - width, instance["plate_h"]))
        root["c"] = children
        return trees
    return None


def _item_overlaps(instance: dict, answer: dict) -> list[int]:
    """Defects of used plates that overlap an item node."""
    out = []
    for d in range(len(instance["defect_x"])):
        dp = instance["defect_plate"][d]
        if dp >= answer["n_plates"]:
            continue
        dx, dy, dw, dh = (instance[k][d] for k in ("defect_x", "defect_y", "defect_w", "defect_h"))
        for i in range(len(answer["type"])):
            if answer["plate"][i] == dp and answer["type"][i] >= 0:
                x, y, w, h = answer["x"][i], answer["y"][i], answer["w"][i], answer["h"][i]
                if x < dx + dw and dx < x + w and y < dy + dh and dy < y + h:
                    out.append(d)
                    break
    return out


# --- the rows -----------------------------------------------------------------------


def judged_row(instance: dict, label: str, solution: dict, expected: list[int] | None) -> dict:
    row = verify.three_way(instance, solution, "tricks")
    j, c = row["judged"], row["checker"]
    refused = j["refused_by"]
    ok = row["agree"] and (refused == expected if expected is not None else True)
    checker = (f"valid, OF {c['of']:,}" if c["valid"] else
               f"{c['stage']}: {', '.join(c['violated']) or (c['errors'][0][:60] if c['errors'] else '-')}")
    return {"label": label, "instance": instance["name"], "refused": refused, "ir": j["ir_clauses"],
            "checker": checker, "checker_valid": c["valid"], "ok": ok, "lenient": row["lenient"]}


def not_built(label: str, name: str) -> dict:
    return {"label": label, "instance": name, "refused": None, "ir": None, "checker": "NOT BUILT",
            "checker_valid": None, "ok": False, "lenient": []}


def show(row: dict) -> None:
    verdict = "valid" if not row["refused"] else f"refused by {row['refused']}"
    flag = "" if row["ok"] else "   <-- UNEXPECTED"
    lenient = f" [its leniency: {'; '.join(row['lenient'])}]" if row["lenient"] else ""
    print(f"  {row['instance']:<4} {row['label']}\n       {verdict:<18} IR clauses {str(row['ir']):<9} checker "
          f"{row['checker']}{lenient}{flag}")


def first(instance: dict, candidates, expected: list[int]):
    """The first candidate answer the Python reading refuses by exactly `expected`."""
    for label, solution in candidates:
        if verify.refused_by(instance, solution) == expected:
            return label, solution
    return None


def cheats(by_name: dict) -> list[dict]:
    rows = []

    def add(name: str, label: str, candidates, expected: list[int]) -> None:
        instance = by_name[name]
        found = first(instance, candidates, expected)
        if found is None:
            rows.append(not_built(label, name))
            return
        text, solution = found
        rows.append(judged_row(instance, f"{label}: {text}", solution, expected))

    b2 = by_name["B2"]
    base, trees = seed_trees(b2)

    # --- items and defects -------------------------------------------------------------

    def exchanged():
        """An item leaf and a waste leaf, adjacent siblings, exchanged along their parent."""
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if parent is None or k + 1 >= len(parent["c"]):
                    continue
                a, b = parent["c"][k], parent["c"][k + 1]
                if a["c"] or b["c"] or (a["t"] >= 0) == (b["t"] >= 0) or WASTE not in (a["t"], b["t"]):
                    continue
                changed, (holder,) = edited(trees, position, root, parent)
                swap(holder, k, depth)
                answer = verify.certify(b2, changed)
                hit = _item_overlaps(b2, answer)
                if hit:
                    yield (f"plate {plate}, an item and the waste beside it under a {depth - 1}-cut exchanged; defect "
                           f"{hit[0]} is now inside the item, and defect_leaf names the item"), answer, hit[0]

    add("B2", "an item over a defect", ((t, a) for t, a, _ in exchanged()), [10])

    def forged_leaf():
        for text, answer, d in exchanged():
            plate = b2["defect_plate"][d]
            waste = next(i for i in range(len(answer["type"]))
                         if answer["plate"][i] == plate and answer["type"][i] == WASTE)
            leaves = list(answer["defect_leaf"])
            leaves[d] = waste
            yield (f"the same geometry, defect_leaf[{d}] forged to node {waste}, a waste on its plate that does not "
                   f"contain it"), dict(answer, defect_leaf=leaves)

    add("B2", "a defect left inside an item, its leaf forged", forged_leaf(), [10])

    def through():
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if n["t"] != WASTE or depth not in (1, 2, 3):
                    continue
                pos, size = axis(depth)
                for d, dx, dy, dw, dh in defects(b2, plate):
                    lo, span = (dx, dw) if pos == "x" else (dy, dh)
                    holds = n["x"] <= dx and dx + dw <= n["x"] + n["w"] and n["y"] <= dy and dy + dh <= n["y"] + n["h"]
                    cut = lo + 1
                    if not holds or span < 2 or cut - n[pos] < 20 or n[pos] + n[size] - cut < 20:
                        continue
                    changed, (target, holder) = edited(trees, position, root, n, parent)
                    second = copy.deepcopy(target)
                    target[size] = cut - target[pos]
                    second[pos], second[size] = cut, n[pos] + n[size] - cut
                    holder["c"].insert(next(i for i, m in enumerate(holder["c"]) if m is target) + 1, second)
                    yield (f"plate {plate}, a waste left by a {depth}-cut split in two at {pos} {cut}, through defect "
                           f"{d} ({pos} {lo} to {lo + span})"), verify.certify(b2, changed)

    add("B2", "a cut through a defect", through(), [10])

    def left_out():
        for stack in b2["stacks"]:
            k = stack[0]
            node = base["item_node"][k]
            types = list(base["type"])
            types[node] = WASTE
            yield f"item {k}, the first of its stack, typed -1 at node {node}; item_node[{k}] is -1", \
                verify.recertify(b2, dict(base, type=types))

    add("B2", "a missing item", left_out(), [8])

    def twice():
        for k in range(len(b2["item_w"])):
            w, h = b2["item_w"][k], b2["item_h"][k]
            stripe = nd(BRANCH, 0, 0, w, b2["plate_h"], nd(k, 0, 0, w, h), nd(WASTE, 0, h, w, b2["plate_h"] - h))
            carved = carve(b2, trees, stripe, w)
            if carved:
                yield f"item {k} cut a second time, in a stripe {w} wide carved from the residual", \
                    verify.certify(b2, carved)

    add("B2", "a duplicated item", twice(), [8])

    def reorder():
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if parent is None or k + 1 >= len(parent["c"]):
                    continue
                changed, (holder,) = edited(trees, position, root, parent)
                swap(holder, k, depth)
                yield (f"plate {plate}, two siblings left by {depth}-cuts exchanged: two items of one stack now cut "
                       f"out of order"), verify.certify(b2, changed)

    add("B2", "a stack sequence violation", reorder(), [9])

    def resized():
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if n["t"] < 0 or depth != 4 or k != 0 or len(parent["c"]) != 2 or parent["c"][1]["h"] < 21:
                    continue
                changed, (holder,) = edited(trees, position, root, parent)
                holder["c"][0]["h"] += 1
                holder["c"][1]["y"] += 1
                holder["c"][1]["h"] -= 1
                yield (f"item {n['t']} cut {n['w']} x {n['h'] + 1}, 1 mm higher than it is, the waste above it 1 mm "
                       f"lower"), verify.certify(b2, changed)

    add("B2", "an item with wrong dimensions", resized(), [7])

    # --- the guillotine tree ------------------------------------------------------------

    def third():
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if depth != 3 or len(n["c"]) != 2 or n["c"][1]["t"] != WASTE or n["c"][1]["h"] < 40:
                    continue
                waste = n["c"][1]
                for cut in range(waste["y"] + 20, waste["y"] + waste["h"] - 19):
                    if any(crosses(cut, dy, dh) and waste["x"] < dx + dw and dx < waste["x"] + waste["w"]
                           for _, dx, dy, dw, dh in defects(b2, plate)):
                        continue
                    changed, (holder,) = edited(trees, position, root, n)
                    top = copy.deepcopy(holder["c"][1])
                    holder["c"][1]["h"] = cut - waste["y"]
                    top["y"], top["h"] = cut, waste["y"] + waste["h"] - cut
                    holder["c"].append(top)
                    yield (f"plate {plate}, the waste above item {n['c'][0]['t']} split at y {cut}: its 3-cut piece "
                           f"has three children"), verify.certify(b2, changed)
                    break

    add("B2", "a third child of a 3-cut node", third(), [5])

    def fifth():
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if depth == 4 and n["t"] == WASTE:
                    changed, (target,) = edited(trees, position, root, n)
                    target["c"] = [nd(WASTE, n["x"], n["y"], n["w"], n["h"])]
                    target["t"] = BRANCH
                    yield f"plate {plate}, a 4-cut waste made a branch with one 5-cut waste child", \
                        verify.certify(b2, changed)

    add("B2", "a fifth cut level", fifth(), [3])

    def gap():
        for position, (plate, root) in enumerate(trees):
            for n, parent, depth, k in walk(root):
                if n["t"] != WASTE or depth != 3 or k != len(parent["c"]) - 1 or n["w"] < 21:
                    continue
                changed, (target,) = edited(trees, position, root, n)
                target["w"] -= 1
                yield (f"plate {plate}, a strip's last waste 1 mm narrower: the strip's children end 1 mm short of "
                       f"its edge"), verify.certify(b2, changed)

    add("B2", "children not tiling their parent", gap(), [4])

    def early_residual():
        for position, (plate, root) in enumerate(trees[:-1]):
            if root["c"][-1]["t"] == WASTE:
                changed = copy.deepcopy(trees)
                changed[position][1]["c"][-1]["t"] = RESIDUAL
                yield f"plate {plate}'s last 1-cut waste typed -3", verify.certify(b2, changed)

    add("B2", "a residual not on the last plate", early_residual(), [3])

    b1 = by_name["B1"]
    _, trees1 = seed_trees(b1)

    def plates_swapped():
        changed = copy.deepcopy(trees1)
        changed[-1][1]["c"][-1]["t"] = WASTE      # the residual written as a waste: still valid
        changed[-2], changed[-1] = changed[-1], changed[-2]
        yield (f"the last two plates written in the other order, plate {changed[-2][0]} before plate "
               f"{changed[-1][0]}, each tree unchanged (B1 has no stack order to break)"), verify.certify(b1, changed)

    add("B1", "plates used out of order", plates_swapped(), [2])

    def forged(key: str, delta: int):
        yield f"{key} {base[key]:,} forged to {base[key] + delta:,}", dict(base, **{key: base[key] + delta})

    add("B2", "a forged objective", forged("geo_loss", -1), [11])
    add("B2", "a forged plate count", forged("n_plates", -1), [11])
    add("B2", "a forged residual", forged("residual_w", 1), [11])
    return rows


def bounds(by_name: dict) -> list[dict]:
    """Both sides of every size bound, carved from B2's residual."""
    inst = by_name["B2"]
    _, trees = seed_trees(inst)
    H = inst["plate_h"]

    def stripe(w: int) -> dict:
        return nd(BRANCH, 0, 0, w, H, nd(WASTE, 0, 0, w, H))

    def strip(h: int, w: int = 500) -> dict:
        return nd(BRANCH, 0, 0, w, H, nd(BRANCH, 0, 0, w, h, nd(WASTE, 0, 0, w, h)), nd(WASTE, 0, h, w, H - h))

    def waste(w: int) -> dict:
        return nd(WASTE, 0, 0, w, H)

    cases = [
        ("a stripe 100 wide (min1cut), holding one waste", 100, stripe(100), []),
        ("a stripe 99 wide, holding one waste", 99, stripe(99), [6]),
        ("a stripe 3500 wide (max1cut), holding one waste", 3500, stripe(3500), []),
        ("a stripe 3501 wide, holding one waste", 3501, stripe(3501), [6]),
        ("a stripe 500 wide whose strip, a branch, is 100 high (min2cut)", 500, strip(100), []),
        ("a stripe 500 wide whose strip, a branch, is 99 high", 500, strip(99), [6]),
        ("a waste 20 wide left by a 1-cut (min_waste)", 20, waste(20), []),
        ("a waste 19 wide left by a 1-cut", 19, waste(19), [6]),
        ("a waste stripe 5000 wide: the checker bounds stripes that are branches only", 5000, waste(5000), []),
    ]
    rows = []
    for label, width, piece, expected in cases:
        carved = carve(inst, trees, piece, width)
        rows.append(judged_row(inst, label, verify.certify(inst, carved), expected) if carved
                    else not_built(label, "B2"))
    return rows


def leniencies_rows(by_name: dict) -> list[dict]:
    """What the checker accepts that the subject does not: each refused by both our
    readings, accepted by the checker."""
    inst = by_name["B2"]
    base, trees = seed_trees(inst)
    rows = []
    root = next(i for i in range(1, len(base["type"])) if base["cut"][i] == 0)
    xs = list(base["x"])
    xs[root] = 5
    rows.append(judged_row(inst, f"plate 1's line (node {root}) at x 5", dict(base, x=xs), [4]))
    types = list(base["type"])
    types[root] = WASTE
    rows.append(judged_row(inst, f"plate 1's line (node {root}) typed -1",
                           verify.recertify(inst, dict(base, type=types)), [2, 3]))
    ys = [y + 7 if base["plate"][i] == 0 else y for i, y in enumerate(base["y"])]
    rows.append(judged_row(inst, "plate 0's whole tree, its plate line included, 7 mm up: its top 7 mm off the plate",
                           verify.recertify(inst, dict(base, y=ys)), [4]))
    extra = copy.deepcopy(trees)
    extra[-1][1]["c"][-1]["t"] = WASTE
    extra.append((extra[-1][0] + 1, nd(BRANCH, 0, 0, inst["plate_w"], inst["plate_h"])))
    rows.append(judged_row(inst, f"a plate line with no children after the last plate (plate {extra[-1][0]})",
                           verify.certify(inst, extra), [2, 10]))

    def stub():
        for position, (plate, rootn) in enumerate(trees):
            for n, parent, depth, k in walk(rootn):
                if n["t"] != WASTE or depth != 3 or k != len(parent["c"]) - 1 or n["w"] < 25:
                    continue
                changed, (holder,) = edited(trees, position, rootn, parent)
                last = holder["c"][-1]
                last["w"] -= 5
                holder["c"].append(nd(BRANCH, last["x"] + last["w"], last["y"], 5, last["h"]))
                yield (f"plate {plate}, a strip ending in a 5 mm branch with no children (a 'waste' under the "
                       f"20 mm minimum)"), verify.certify(inst, changed)

    found = first(inst, stub(), [2])
    rows.append(judged_row(inst, found[0], found[1], [2]) if found else not_built("a childless branch", "B2"))
    return rows


def calibration() -> tuple[list[str], int]:
    """The starting program on every instance, three ways, against the rivals."""
    lines = [f"  {'':<4} {'geo_loss':>12} {'plates':>6} {'residual':>8} {'checker OF':>12} {'180 s best':>11} "
             f"{'gap':>6} {'3600 s best':>11} {'gap':>6} {'best known':>11} {'gap':>6}"]
    failures = 0
    total = {"seed": 0, "best_180s": 0, "best_3600s": 0, "best_known": 0}
    for inst in verify.instances():
        answer, _, _ = verify.seed_answer(inst)
        row = verify.quick_three(inst, answer, "calibration")
        good = row["agree"] and not row["refused_by"] and row["checker"]
        failures += not good
        g = answer["geo_loss"]
        total["seed"] += g
        cells = []
        for key in ("best_180s", "best_3600s", "best_known"):
            total[key] += inst[key]
            cells.append(f"{inst[key]:>11,} {(g - inst[key]) / inst[key]:>+6.0%}")
        lines.append(f"  {inst['name']:<4} {g:>12,} {answer['n_plates']:>6} {answer['residual_w']:>8} "
                     f"{row['checker_of'] or 0:>12,} " + " ".join(cells) + ("" if good else "   <-- UNEXPECTED"))
    lines.append(f"  {'all':<4} {total['seed']:>12,} {'':>6} {'':>8} {'':>12} "
                 + " ".join(f"{total[k]:>11,} {(total['seed'] - total[k]) / total[k]:>+6.1%}"
                            for k in ("best_180s", "best_3600s", "best_known")))
    return lines, failures


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    by_name = {inst["name"]: inst for inst in verify.instances()}
    print("THE CALIBRATION: the starting program, valid in all three readings, against the rivals (mm^2)")
    lines, failures = calibration()
    for line in lines:
        print(line)

    print("\nTHE BOUNDS, BOTH SIDES (carved from B2's residual; the certificate derived again):")
    rows = bounds(by_name)
    for row in rows:
        show(row)
    print("\nTHE CHEATS, EACH REFUSED BY EXACTLY ONE CONDITION IN BOTH READINGS:")
    cheat_rows = cheats(by_name)
    for row in cheat_rows:
        show(row)
    print("\nTHE CHECKER'S LENIENCIES: accepted by the checker, refused by the subject's rules and ours:")
    lenient = leniencies_rows(by_name)
    for row in lenient:
        show(row)

    bad = [r for r in rows + cheat_rows + lenient if not r["ok"]]
    geometric = [r for r in cheat_rows if r["refused"] and r["refused"] != [11]]
    checker_missed = [r for r in geometric if r["checker_valid"]]
    forged_refused = [r for r in cheat_rows if r["refused"] == [11] and not r["checker_valid"]]
    lenient_missing = [r for r in lenient if not r["lenient"]]
    if failures or bad or checker_missed or forged_refused or lenient_missing:
        print(f"\nFAILED: {failures} calibration rows, {len(bad)} rows unexpected, {len(checker_missed)} geometric "
              f"cheats the checker accepted, {len(forged_refused)} forged claims whose geometry it refused, "
              f"{len(lenient_missing)} leniencies not shown")
        return 1
    print(f"\nOK: {len(lines) - 2} calibration rows and {len(rows) + len(cheat_rows) + len(lenient)} bound, cheat and "
          f"leniency rows, every one judged alike by both readings clause by clause and consistently by the "
          f"official checker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
