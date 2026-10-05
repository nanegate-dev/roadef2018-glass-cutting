"""The specification `problem.txt` describes, and §9's gates run on it.

    python specification.py               # run the gates and print them
    python specification.py --out specification.json

EVERY EXAMPLE IS BUILT, NOT TYPED. Each solution below is a cutting tree of the
worked instance with the certificate an honest emitter derives from it
(`verify.certify`), or one of those with one thing changed -- a node's type, a
size, the order of two siblings, a split, a pointer or a claim -- and `main`
checks that every number `problem.txt` prints is the number that was built, that
each counterexample breaks exactly the one condition it is for in both readings
(§9's clause-coverage gate splits the rule on its top-level `and`, and a
counterexample that broke two would leave one witnessed by nothing), and that the
OFFICIAL CHECKER, fed the same trees, agrees: it accepts exactly the examples
whose geometry is valid under the honest certificate, at the same objective.

THE WORKED INSTANCE IS SMALL ON PURPOSE (`make_instance.FIXTURE`): 1000 x 500
plates, six items in three stacks, four defects, the challenge's cut rules with
max1cut 600 so that a stripe too wide fits inside one plate. Its worked answer
uses every stage: a stripe of full-width items, a strip with a 3-cut item and a
4-cut trim, a 2-cut item, a waste stripe, and a residual.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(HERE))

#: ADR 0101/0102: `objective` on POST /projects and a message's `content` are
#: both bounded at this, and `start.py` posts the statement to both.
CEILING = 25_000

_spec = importlib.util.spec_from_file_location("roadef2018_verify", HERE / "verify.py")
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

import make_instance  # noqa: E402

SHIPPED = json.loads((HERE / "instances.json").read_text(encoding="utf-8"))
FIXTURE = make_instance.fixture()
nd = verify.node
W, H = FIXTURE["plate_w"], FIXTURE["plate_h"]

_INT = {"type": "integer"}
_INTS = {"type": "array", "items": _INT}

INPUT_SCHEMA = {
    "type": "object",
    "required": [*make_instance.PARAM_KEYS, *make_instance.ITEM_KEYS, "stacks", *make_instance.DEFECT_KEYS],
    "properties": {
        "name": {"type": "string"},
        "source": {"type": "string"},
        "best_180s": _INT,
        "best_3600s": _INT,
        "best_known": _INT,
        **{key: _INT for key in make_instance.PARAM_KEYS},
        **{key: _INTS for key in (*make_instance.ITEM_KEYS, *make_instance.DEFECT_KEYS)},
        "stacks": {"type": "array", "items": _INTS},
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "required": list(verify.SOLUTION_KEYS),
    "properties": {
        **{key: _INTS for key in verify.LIST_KEYS},
        **{key: _INT for key in verify.CLAIM_KEYS},
    },
}


# --- the worked answer and its variants -------------------------------------------


def plate0(*, stripe1=None, waste4=None, trim=None, last=-1) -> dict:
    """Plate 0 of the worked answer. The keyword arguments replace one part."""
    first = stripe1 or [nd(0, 0, 0, 300, 200), nd(1, 0, 200, 300, 200), *(waste4 or [nd(-1, 0, 400, 300, 100)])]
    slot = trim or [nd(4, 500, 0, 250, 150), nd(-1, 500, 150, 250, 150)]
    return nd(-2, 0, 0, W, H,
              nd(-2, 0, 0, 300, 500, *first),
              nd(-2, 300, 0, 450, 500,
                 nd(-2, 300, 0, 450, 300, nd(3, 300, 0, 200, 300), nd(-2, 500, 0, 250, 300, *slot)),
                 nd(2, 300, 300, 450, 200)),
              nd(last, 750, 0, 250, 500))


def plate1(*, residual=-3, rotated=True, carve=None, residual_x=350) -> dict:
    """Plate 1 of the worked answer: item 5 turned (350 x 450) in a 350 wide stripe,
    the residual right of it; or item 5 as given (450 x 350); or a stripe carved
    out of the residual (`carve`, placed at x 350)."""
    if rotated:
        stripe = nd(-2, 0, 0, 350, 500, nd(5, 0, 0, 350, 450), nd(-1, 0, 450, 350, 50))
        right = 350
    else:
        stripe = nd(-2, 0, 0, 450, 500, nd(5, 0, 0, 450, 350), nd(-1, 0, 350, 450, 150))
        right = 450
    extra = [carve] if carve is not None else []
    x = residual_x if carve is not None else right
    return nd(-2, 0, 0, W, H, stripe, *extra, nd(residual, x, 0, W - x, H))


def worked(**changes) -> dict:
    return verify.certify(FIXTURE, [(0, plate0()), (1, plate1())], **changes)


V1 = worked()
V2 = verify.certify(FIXTURE, [(0, plate0()), (1, plate1(residual=-1))])
V3 = verify.certify(FIXTURE, [(0, plate0()), (1, plate1(rotated=False))])


def _edit(base: dict, **changes) -> dict:
    out = copy.deepcopy(base)
    out.update(copy.deepcopy(changes))
    return out


def _retyped(base: dict, at: int, kind: int) -> dict:
    types = list(base["type"])
    types[at] = kind
    return verify.recertify(FIXTURE, _edit(base, type=types))


def _reordered() -> dict:
    """The first stripe's children bottom-up as waste, item 0, item 1: defect 0 at
    (150, 450) is now inside item 1."""
    return verify.certify(FIXTURE, [(0, plate0(stripe1=[nd(-1, 0, 0, 300, 100), nd(0, 0, 100, 300, 200),
                                                        nd(1, 0, 300, 300, 200)])), (1, plate1())])


REORDERED = _reordered()
SWAPPED = V1["type"][:2] + [1, 0] + V1["type"][4:]

#: (name, solution, the condition it breaks, the note).
INVALID = [
    ("an_extra_x", _edit(V1, x=[*V1["x"], 0]), 1, "x has 19 entries for 18 nodes"),
    ("plates_in_the_other_order",
     verify.certify(FIXTURE, [(1, plate1(residual=-1)), (0, plate0())]), 2,
     "the second answer's plates written plate 1 first: the first plate is not plate 0"),
    ("a_residual_on_the_first_plate", _retyped(V1, 12, -3), 3,
     "node 12, plate 0's last stripe, typed -3"),
    ("a_fifth_cut",
     verify.certify(FIXTURE, [(0, plate0(trim=[nd(4, 500, 0, 250, 150),
                                              nd(-2, 500, 150, 250, 150, nd(-1, 500, 150, 250, 150))])),
                              (1, plate1())]), 3,
     "node 10 made a branch with one 5-cut waste child, the same rectangle"),
    ("the_residual_short_of_the_edge",
     verify.certify(FIXTURE, [(0, plate0()), (1, nd(-2, 0, 0, W, H, plate1()["c"][0], nd(-3, 350, 0, 649, 500)))]),
     4, "the residual 649 wide: plate 1's last child ends at 999, not 1000"),
    ("three_children_under_a_3_cut",
     verify.certify(FIXTURE, [(0, plate0(trim=[nd(4, 500, 0, 250, 150), nd(-1, 500, 150, 250, 70),
                                              nd(-1, 500, 220, 250, 80)])), (1, plate1())]), 5,
     "the waste above item 4 split into 250 x 70 and 250 x 80: node 8 has three children"),
    ("a_waste_19_high",
     verify.certify(FIXTURE, [(0, plate0(waste4=[nd(-1, 0, 400, 300, 19), nd(-1, 0, 419, 300, 81)])),
                              (1, plate1())]), 6,
     "node 4 split into 300 x 19 and 300 x 81; defect 0 is in the second"),
    ("a_stripe_99_wide",
     verify.certify(FIXTURE, [(0, plate0()), (1, plate1(carve=nd(-2, 350, 0, 99, 500, nd(-1, 350, 0, 99, 500)),
                                                       residual_x=449))]), 6,
     "a 1-cut branch 99 wide at x 350, holding one waste, carved from the residual"),
    ("a_stripe_601_wide",
     verify.certify(FIXTURE, [(0, plate0()), (1, plate1(carve=nd(-2, 350, 0, 601, 500, nd(-1, 350, 0, 601, 500)),
                                                       residual_x=951))]), 6,
     "a 1-cut branch 601 wide at x 350 over max1cut 600; the residual is 49"),
    ("a_strip_99_high",
     verify.certify(FIXTURE, [(0, plate0()), (1, plate1(
         carve=nd(-2, 350, 0, 200, 500, nd(-2, 350, 0, 200, 99, nd(-1, 350, 0, 200, 99)), nd(-1, 350, 99, 200, 401)),
         residual_x=550))]), 6,
     "a 1-cut branch 200 wide at x 350 whose first strip, a 2-cut branch, is 99 high"),
    ("an_item_a_millimetre_tall",
     verify.certify(FIXTURE, [(0, plate0(trim=[nd(4, 500, 0, 250, 151), nd(-1, 500, 151, 250, 149)])),
                              (1, plate1())]), 7,
     "item 4 cut 250 x 151 and the waste above it 250 x 149"),
    ("an_item_left_out", _retyped(V1, 15, -1), 8, "node 15 typed -1: item 5 is not cut; item_node[5] is -1"),
    ("an_item_cut_twice", _retyped(V1, 10, 4), 8, "node 10, the 250 x 150 waste above item 4, typed 4"),
    ("two_items_of_a_stack_swapped", verify.recertify(FIXTURE, _edit(V1, type=SWAPPED)), 9,
     "nodes 2 and 3 typed 1 and 0: item 1 is cut before item 0"),
    ("an_item_on_a_defect", REORDERED, 10,
     "the first stripe's children in the order waste, item 0, item 1: defect 0 is inside item 1, which "
     "defect_leaf names"),
    ("a_defect_under_an_item_named_in_a_waste",
     _edit(REORDERED, defect_leaf=[2, *REORDERED["defect_leaf"][1:]]), 10,
     "the same, with defect_leaf[0] naming node 2, the waste now at y 0 to 100"),
    ("a_cut_through_a_defect",
     verify.certify(FIXTURE, [(0, plate0(waste4=[nd(-1, 0, 400, 300, 52), nd(-1, 0, 452, 300, 48)])),
                              (1, plate1())]), 10,
     "node 4 split at y 452, through defect 0 (y 450 to 454)"),
    ("a_defect_of_a_used_plate_unaccounted", _edit(V1, defect_leaf=[4, 12, -1, -1]), 10,
     "defect_leaf[2] is -1 for defect 2, on plate 1, which is used"),
    ("the_loss_claimed_one_short", _edit(V1, geo_loss=V1["geo_loss"] - 1), 11, "geo_loss 209999 for 210000"),
    ("a_residual_claimed_wider", _edit(V1, residual_w=651, geo_loss=V1["geo_loss"] - H), 11,
     "residual_w 651 and geo_loss 209500, consistent with each other, not with the tree"),
    ("one_plate_claimed", _edit(V1, n_plates=1, geo_loss=V1["geo_loss"] - W * H), 11,
     "n_plates 1 and geo_loss -290000 for the two plates used"),
]

EXAMPLES = [
    {"name": "the_worked_answer", "solution": V1, "expect_valid": True,
     "note": "two plates, the residual 650 wide on the second; scores 210,000"},
    {"name": "the_residual_written_as_a_waste", "solution": V2, "expect_valid": True,
     "note": "the same tree with its last node typed -1: it is the residual all the same; scores 210,000"},
    {"name": "item_5_as_given", "solution": V3, "expect_valid": True,
     "note": "item 5 cut 450 x 350, not turned: the residual is 550 wide; scores 260,000"},
    *({"name": name, "solution": solution, "expect_valid": False,
       "note": f"condition {condition}: {note}"} for name, solution, condition, note in INVALID),
]

COMPARISONS = [{"stronger": V1, "weaker": V3}]

WORKED = {
    "instance": FIXTURE,
    "priced": [
        {"solution": V1, "total": verify.objective(FIXTURE, V1), "quote": "It scores 210,000."},
        {"solution": V2, "total": verify.objective(FIXTURE, V2), "quote": "It scores 210,000 as well."},
        {"solution": V3, "total": verify.objective(FIXTURE, V3), "quote": "It scores 260,000."},
    ],
}


def document() -> dict:
    """The whole thing, in the shape the compile endpoint accepts."""
    return {
        "spec": {
            "input_schema": INPUT_SCHEMA,
            "output_schema": OUTPUT_SCHEMA,
            "decision_variables": [f"solution.{key}" for key in verify.SOLUTION_KEYS],
            "instance_mode": "SINGLE_INSTANCE",
            "validity": verify.validity_tree(),
            "objective": {"direction": "MINIMIZE", "expression": verify.objective_tree()},
        },
        "instance": FIXTURE,
        "examples": EXAMPLES,
        "comparisons": COMPARISONS,
        "worked": WORKED,
    }


def printed() -> list[str]:
    """Text `problem.txt` must contain, built from the objects above."""
    f = FIXTURE
    rows = [json.dumps(V1, separators=(", ", ": "))[1:-1]]
    rows += [f"{key} {json.dumps(f[key])}" for key in (*make_instance.ITEM_KEYS, "stacks", *make_instance.DEFECT_KEYS)]
    rows += [f"{key} {f[key]}" for key in make_instance.PARAM_KEYS]
    by_name = {name: solution for name, solution, _, _ in INVALID}
    rows += [
        f"geo_loss {V1['geo_loss']}",
        f"residual_w {V3['residual_w']}",
        f"defect_leaf {json.dumps(REORDERED['defect_leaf'])}",
        f"item_node {json.dumps(by_name['two_items_of_a_stack_swapped']['item_node'])}",
        f"geo_loss {by_name['one_plate_claimed']['geo_loss']}",
    ]
    return rows


def arithmetic() -> list[str]:
    """The worked answer's claims and objective, worked as problem.txt works them."""
    f, s = FIXTURE, V1
    area = verify.item_area(f)
    parts = " + ".join(f"{w} x {h}" for w, h in zip(f["item_w"], f["item_h"]))
    return [
        f"the items' area is {parts} = {area}",
        f"n_plates = plate[17] + 1 = {s['n_plates']}",
        f"residual_w = w[17] = {s['residual_w']}",
        f"geo_loss = {s['n_plates']} x {f['plate_w']} x {f['plate_h']} - {f['plate_h']} x {s['residual_w']} - {area} "
        f"= {s['geo_loss']}",
    ]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from evolve.llm import DraftRejected
    from evolve.problem.compiler import validate_supplied_specification
    from evolve.problem.expression import evaluate
    from evolve.problem.spec import ClaimOrigin, ProblemBrief, ProblemClaim

    statement = (HERE / "problem.txt").read_text(encoding="utf-8")
    flattened = " ".join(statement.split())
    if len(statement) > CEILING:
        print(f"!! problem.txt is {len(statement):,} characters and the API accepts {CEILING:,}.")
        return 1

    missing = [row for row in printed() if row not in flattened]
    if missing:
        print("problem.txt does not print what was built:")
        for row in missing:
            print(f"  {row[:200]}")
        return 1
    print(f"every number problem.txt prints is the one that was built ({len(printed())} rows)")

    worked_lines = arithmetic()
    wrong = [line for line in worked_lines if line not in flattened]
    if wrong:
        print("problem.txt does not work the arithmetic out as built:")
        for line in wrong:
            print(f"  {line}")
        return 1
    print(f"the worked arithmetic reproduces, all {len(worked_lines)} lines")

    for entry in WORKED["priced"]:
        here = verify.objective(FIXTURE, entry["solution"])
        there = evaluate(verify.objective_tree(), instance=FIXTURE, solution=entry["solution"])
        if not (here == there == entry["total"]) or entry["quote"] not in flattened:
            print(f"worked total: statement says {entry['total']}, python {here}, IR {there}")
            return 1
    print(f"the statement's worked totals reproduce ({len(WORKED['priced'])} of them)")

    for example in EXAMPLES:
        try:
            held = evaluate(verify.validity_tree(), instance=FIXTURE, solution=example["solution"])
        except Exception:  # noqa: BLE001 - an expression error is a refusal
            held = False
        reasons = verify.refused_by(FIXTURE, example["solution"])
        if held is not example["expect_valid"] or bool(reasons) is example["expect_valid"]:
            print(f"{example['name']}: expected valid={example['expect_valid']}, IR {held}, python {reasons}")
            return 1
        if not example["expect_valid"]:
            wanted = int(example["note"].split(":")[0].replace("condition ", ""))
            falsified = verify.ir_refusals(FIXTURE, example["solution"])
            if reasons != [wanted] or falsified != [wanted]:
                print(f"{example['name']}: should break exactly condition {wanted}; python {reasons}, "
                      f"IR clauses refusing {falsified}")
                return 1
    print(f"every example behaves as written ({len(EXAMPLES)} of them), each invalid one breaking exactly the "
          f"one condition it names, in both readings, clause by clause")

    disagreements = []
    for example in EXAMPLES:
        row = verify.three_way(FIXTURE, example["solution"], "spec")
        if not row["agree"]:
            disagreements.append((example["name"], row["checker"]["stage"], row["honest"]))
    if disagreements:
        print(f"the official checker disagrees on {disagreements}")
        return 1
    print(f"the official checker agrees on all {len(EXAMPLES)}: it accepts exactly the trees whose honest "
          f"certificate is valid, at the same objective")

    words = {24: "twenty-four"}
    invalid = {21: "Twenty-one"}
    count, refused = len(EXAMPLES), sum(not e["expect_valid"] for e in EXAMPLES)
    counted = f"all {words.get(count, count)},"
    if counted not in flattened or f"{invalid.get(refused, refused)} INVALID" not in flattened:
        print(f"problem.txt does not count the examples as built ({count}, {refused} invalid)")
        return 1

    brief = ProblemBrief(claims=(
        ProblemClaim(id="claim-1", text=statement.splitlines()[0], origin=ClaimOrigin.EXPLICIT),
    ))
    try:
        validated = validate_supplied_specification(document(), brief=brief, instance=SHIPPED)
    except DraftRejected as rejected:
        print(f"REFUSED by the same gates a compile faces:\n  {rejected}")
        return 1

    print(f"\nproblem.txt is {len(statement):,} characters; the API accepts {CEILING:,}")
    print(f"validation {validated.summary.status.value}   source {validated.source}")
    for check in validated.summary.checks:
        print(f"  {check.status.value:<7} {check.name}: {str(check.detail)[:110]}")

    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
        out.write_text(json.dumps(document(), indent=2), encoding="utf-8", newline="\n")
        print(f"written {out.name} ({out.stat().st_size / 1024:.0f} KiB)")
    return 0 if validated.summary.status.value == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
