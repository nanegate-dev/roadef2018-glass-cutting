"""The rules in plain Python, in the locked IR and through the official checker; the seed's build; the check.

    python verify.py                   # compile, run and judge the seed on all fifteen instances, three ways
    python verify.py --search 20       # ... and the dormant search switched on, 20 seeds x 15 instances
    python verify.py --pack            # rebuild starting-program.json from solver/
    python verify.py --self-test       # the readings against each other and the checker, thousands of ways
    python verify.py --timing          # the IR judge's time per instance, cold and warm

THE PROBLEM IS THE CHALLENGE'S, AS ITS CHECKER DEFINES IT. Cut every item of a
batch from Saint-Gobain's defective 6000 x 3210 jumbo plates, used in order, with
a guillotine cutting tree of at most four stages, every item defect-free, no cut
through a defect, every stack's order respected; minimise the glass lost. Where
the subject (18/05/2018) and the official checker (main.cpp, 23/05/2018) differ,
the checker's rule is the rule; README.md lists every difference.

AN ANSWER CARRIES ITS TREE IN PRE-ORDER, AND A CERTIFICATE. The IR has no fold
and no recursion, so everything the checker finds by walking the tree is carried
and proven locally, one node at a time: every node's parent and the end of its
subtree prove the order is a depth-first pre-order with siblings in cutting order;
the children of every branch tile it exactly; every item names the node that cuts
it; every defect of a used plate names the waste leaf that contains it. The
checker's cut order is then the order of the item nodes, and a defect inside one
waste leaf of a tiling is inside no item and crossed by no cut.

TWO READINGS, WRITTEN INDEPENDENTLY, AND THE CHECKER. `validity_reasons` is the
arithmetic a person would write from problem.txt, in loops. `clause_trees` says
the same in the IR the platform locks, a formula per quantity (`define`/`call`).
`judge_both` compares the verdict, each of the eleven clauses alone, the objective
and every per-node, per-item and per-defect intermediate. `run_checker` converts
the answer to the checker's CSV and runs the checker, built from its own source
with the house flags, and reads back validSolution and the objective it prints.

EVERYTHING HERE IS `problem.txt`, TRANSCRIBED. If this file and problem.txt
disagree, problem.txt is right and this file is the defect.
"""

from __future__ import annotations

import argparse
import atexit
import itertools
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SOLVER = HERE / "solver"
BUNDLE = HERE / "starting-program.json"
INSTANCES = HERE / "instances.json"
sys.path.insert(0, str(HERE))

import make_instance  # noqa: E402

#: The one command every C++ file here is built with: the platform's own profile on
#: this machine (`evolve.research.build.default_flags`, ADR 0011) at C++17.
COMPILE = ["g++", "-std=c++17", "-O2", "-DNDEBUG", "-D_GLIBCXX_ASSERTIONS",
           "-static", "-Wl,--no-insert-timestamp"]

#: `evolve.workers.handlers.experiment.CANDIDATE_RUNTIME_SECONDS`: what one run may take.
SANDBOX_SECONDS = 120
SANDBOX_BYTES = 64 * 1024 ** 2

#: The seed's total over the fifteen instances, pinned (the README quotes it).
PINNED_TOTAL: int | None = 1_321_059_474

WASTE, BRANCH, RESIDUAL = -1, -2, -3

#: The answer, in the order problem.txt lists it.
NODE_KEYS = ("plate", "cut", "type", "x", "y", "w", "h", "parent", "end")
LIST_KEYS = (*NODE_KEYS, "item_node", "defect_leaf")
CLAIM_KEYS = ("n_plates", "residual_w", "geo_loss")
SOLUTION_KEYS = (*LIST_KEYS, *CLAIM_KEYS)

#: The eleven conditions, in the order the rule checks them.
CONDITIONS = {
    1: "the answer is not the shape the instance asks for",
    2: "the node list is not a pre-order tree of plates used in order",
    3: "a node's type or level is not allowed where it is",
    4: "the children of a node do not tile it exactly (or a plate is not the whole plate)",
    5: "a node obtained by a 3-cut has more than two children",
    6: "a stripe, strip, waste or residual is outside its size bounds",
    7: "an item node is not its item's size, turned or not",
    8: "an item is not cut exactly once",
    9: "a stack is not cut in its order",
    10: "a defect of a used plate is not inside the waste leaf it names",
    11: "a claim does not recompute",
}

__all__ = [
    "certify",
    "judge_both",
    "objective",
    "objective_tree",
    "recertify",
    "refused_by",
    "run_checker",
    "validity_reasons",
    "validity_tree",
]


def _evolve_source() -> Path:
    return REPO_ROOT / "backend" / "src"


# --- the Python reading -------------------------------------------------------


def read(value: Any) -> int:
    """A number as the rules read it: the IR's `round`, which is the number itself
    for a whole number and refuses anything that is not a finite number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{value!r} is not a number")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{value!r} is not finite")
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _whole(value: Any) -> bool:
    """`value mod 1 = 0`, as the IR computes it (a non-finite remainder is a refusal)."""
    remainder = value % 1
    if isinstance(remainder, float) and not math.isfinite(remainder):
        raise ValueError("not finite")
    return remainder == 0


class _Reader:
    """Reads a solution the way problem.txt says: every number through `read`."""

    def __init__(self, instance: dict, solution: dict) -> None:
        self.i = instance
        self.s = solution

    def n(self) -> int:
        return len(self.s["type"])

    def at(self, key: str, index: int) -> int:
        return read(self.s[key][index])

    def m(self) -> int:
        return self.at("plate", self.n() - 1) + 1


def _tree_ok(r: _Reader, i: int) -> bool:
    """A root starts the next plate and its subtree runs to the next root; any other
    node sits inside its parent's subtree and is followed by its next sibling or by
    its parent's end; a branch's first child follows it; a leaf's subtree is itself."""
    n = r.n()
    cut, par, end = r.at("cut", i), r.at("parent", i), r.at("end", i)
    if cut == 0:
        numbered = (r.at("plate", i) == 0) if i == 0 else (r.at("plate", i) == r.at("plate", i - 1) + 1)
        placed = (par == -1 and numbered and r.at("plate", i) < r.i["n_plates_max"]
                  and i < end <= n and (end == n or r.at("cut", end) == 0))
    else:
        placed = (0 <= par < i and r.at("plate", i) == r.at("plate", par) and cut == r.at("cut", par) + 1
                  and i < end <= r.at("end", par)
                  and (end == r.at("end", par) or (end < n and r.at("parent", end) == par)))
    if not placed:
        return False
    if r.at("type", i) == BRANCH:
        return end >= i + 2 and i + 1 < n and r.at("parent", i + 1) == i
    return end == i + 1


def _type_ok(r: _Reader, i: int) -> bool:
    kind, cut = r.at("type", i), r.at("cut", i)
    known = kind in (RESIDUAL, BRANCH, WASTE) or (kind >= 0 and kind < len(r.i["item_w"]))
    return (known and cut >= 0 and cut <= 4
            and (cut != 0 or kind == BRANCH)
            and (kind != BRANCH or cut <= 3)
            and (kind != RESIDUAL or (cut == 1 and i == r.n() - 1)))


def _sane(r: _Reader, i: int) -> bool:
    """The pointers condition 4 may follow: 0 <= parent < i < end <= N, parent's end <= N."""
    par = r.at("parent", i)
    return (par >= 0 and par < i and i < r.at("end", i) and r.at("end", i) <= r.n()
            and r.at("end", par) <= r.n())


def _geom_ok(r: _Reader, i: int) -> bool:
    cut = r.at("cut", i)
    if cut == 0:
        return (r.at("x", i) == 0 and r.at("y", i) == 0 and r.at("w", i) == r.i["plate_w"]
                and r.at("h", i) == r.i["plate_h"])
    if not _sane(r, i):
        return True
    p, e = r.at("parent", i), r.at("end", i)
    ep = r.at("end", p)
    if cut % 2 == 1:   # 1-cuts and 3-cuts: children side by side, left to right
        along, span, across, depth = "x", "w", "y", "h"
    else:              # 2-cuts and 4-cuts: children stacked, bottom to top
        along, span, across, depth = "y", "h", "x", "w"
    if r.at(across, i) != r.at(across, p) or r.at(depth, i) != r.at(depth, p):
        return False
    if i == p + 1 and r.at(along, i) != r.at(along, p):
        return False
    reach = r.at(along, i) + r.at(span, i)
    if e < ep:
        return r.at(along, e) == reach
    return reach == r.at(along, p) + r.at(span, p)


def _trim_ok(r: _Reader, i: int) -> bool:
    if r.at("cut", i) != 4:
        return True
    par = r.at("parent", i)
    if not (par >= 0 and par < i):
        return True
    return i == par + 1 or r.at("end", i) == r.at("end", par)


def _dims_ok(r: _Reader, i: int) -> bool:
    """Sizes are read only for the kinds that have a bound, as the IR reads them."""
    kind, inst = r.at("type", i), r.i
    if kind == BRANCH:
        cut = r.at("cut", i)
        if cut == 1 and not (r.at("w", i) >= inst["min1cut"] and r.at("w", i) <= inst["max1cut"]):
            return False
        if cut == 2 and not r.at("h", i) >= inst["min2cut"]:
            return False
    if kind == WASTE and not (r.at("w", i) >= inst["min_waste"] and r.at("h", i) >= inst["min_waste"]):
        return False
    return kind != RESIDUAL or r.at("w", i) >= inst["min_waste"]


def _ident_ok(r: _Reader, i: int) -> bool:
    kind = r.at("type", i)
    if not (kind >= 0 and kind < len(r.i["item_w"])):
        return True
    w, h = r.at("w", i), r.at("h", i)
    iw, ih = r.i["item_w"][kind], r.i["item_h"][kind]
    return (w == iw and h == ih) or (w == ih and h == iw)


def _made_ok(r: _Reader, k: int) -> bool:
    node = r.at("item_node", k)
    return node >= 0 and node < r.n() and r.at("type", node) == k


def _stack_ok(r: _Reader, s: int) -> bool:
    members = r.i["stacks"][s]
    return all(r.at("item_node", members[j - 1]) < r.at("item_node", members[j]) for j in range(1, len(members)))


def _defect_ok(r: _Reader, d: int) -> bool:
    inst = r.i
    leaf = r.at("defect_leaf", d)
    dp, dx, dy, dw, dh = (inst[k][d] for k in make_instance.DEFECT_KEYS)
    named = leaf == -1 or (
        leaf >= 0 and leaf < r.n() and r.at("plate", leaf) == dp and r.at("type", leaf) in (WASTE, RESIDUAL)
        and r.at("x", leaf) <= dx and dx + dw <= r.at("x", leaf) + r.at("w", leaf)
        and r.at("y", leaf) <= dy and dy + dh <= r.at("y", leaf) + r.at("h", leaf))
    return named and (dp >= r.m() or leaf != -1)


def item_area(instance: dict) -> int:
    return sum(w * h for w, h in zip(instance["item_w"], instance["item_h"]))


def residual_of(r: _Reader) -> int:
    """The residual's width: the last node's, when it is a waste or residual left by a 1-cut."""
    last = r.n() - 1
    if r.at("cut", last) == 1 and r.at("type", last) in (WASTE, RESIDUAL):
        return r.at("w", last)
    return 0


def _claims_ok(r: _Reader) -> bool:
    inst, s = r.i, r.s
    plates, residual = read(s["n_plates"]), read(s["residual_w"])
    if plates != r.m():
        return False
    if residual != residual_of(r):
        return False
    return read(s["geo_loss"]) == (plates * inst["plate_w"] * inst["plate_h"] - inst["plate_h"] * residual
                                   - item_area(inst))


def _shapes_ok(r: _Reader) -> bool:
    s, n = r.s, r.n()
    if not n >= 1:
        return False
    for key in NODE_KEYS:
        if key != "type" and len(s[key]) != n:
            return False
    if len(s["item_node"]) != len(r.i["item_w"]) or len(s["defect_leaf"]) != len(r.i["defect_x"]):
        return False
    for key in LIST_KEYS:
        if not all(_whole(v) for v in s[key]):
            return False
    return all(_whole(s[key]) for key in CLAIM_KEYS)


def _holds(check) -> bool:
    try:
        return bool(check())
    except (TypeError, IndexError, KeyError, ValueError, ZeroDivisionError, OverflowError, AttributeError):
        return False


def validity_reasons(instance: dict, solution: dict) -> list[str]:
    """Every condition this solution breaks, numbered as problem.txt numbers them.
    Unlike the IR's top-level `and`, every condition is evaluated."""
    r = _Reader(instance, solution)
    n_items, n_defects = len(instance["item_w"]), len(instance["defect_x"])

    def nodes(test) -> bool:
        return all(test(r, i) for i in range(r.n()))

    checks = {
        1: lambda: _shapes_ok(r),
        2: lambda: nodes(_tree_ok),
        3: lambda: nodes(_type_ok),
        4: lambda: nodes(_geom_ok),
        5: lambda: nodes(_trim_ok),
        6: lambda: nodes(_dims_ok),
        7: lambda: nodes(_ident_ok),
        8: lambda: (all(_made_ok(r, k) for k in range(n_items))
                    and sum(1 for i in range(r.n()) if r.at("type", i) >= 0) == n_items),
        9: lambda: all(_stack_ok(r, s) for s in range(len(instance["stacks"]))),
        10: lambda: all(_defect_ok(r, d) for d in range(n_defects)),
        11: lambda: _claims_ok(r),
    }
    return [f"{number}: {CONDITIONS[number]}" for number, check in checks.items() if not _holds(check)]


def refused_by(instance: dict, solution: dict) -> list[int]:
    return [int(reason.split(":")[0]) for reason in validity_reasons(instance, solution)]


def objective(instance: dict, solution: dict) -> int:
    """geo_loss, which condition 11 proves is plates x W x H - H x residual - the items' area."""
    return read(solution["geo_loss"])


def per_node(instance: dict, solution: dict) -> dict[str, list]:
    """Every per-node, per-item, per-defect and per-stack intermediate the probes compare."""
    r = _Reader(instance, solution)
    n = r.n()
    out = {
        "tree_ok": [_tree_ok(r, i) for i in range(n)],
        "type_ok": [_type_ok(r, i) for i in range(n)],
        "geom_ok": [_geom_ok(r, i) for i in range(n)],
        "trim_ok": [_trim_ok(r, i) for i in range(n)],
        "dims_ok": [_dims_ok(r, i) for i in range(n)],
        "ident_ok": [_ident_ok(r, i) for i in range(n)],
        "x_end": [r.at("x", i) + r.at("w", i) for i in range(n)],
        "y_end": [r.at("y", i) + r.at("h", i) for i in range(n)],
        "made_ok": [_made_ok(r, k) for k in range(len(instance["item_w"]))],
        "stack_ok": [_stack_ok(r, s) for s in range(len(instance["stacks"]))],
        "defect_ok": [_defect_ok(r, d) for d in range(len(instance["defect_x"]))],
    }
    out["scalars"] = {"plates_used": r.m(), "items_area": item_area(instance), "residual": residual_of(r),
                      "item_nodes": sum(1 for i in range(n) if r.at("type", i) >= 0)}
    return out


# --- the same statements as the locked IR reads them --------------------------


def _c(value: Any) -> dict:
    return {"op": "const", "value": value}


def _v(path: str) -> dict:
    return {"op": "var", "path": path}


def _i(name: str) -> dict:
    return {"op": "index", "name": name}


def _at(of: Any, position: Any) -> dict:
    return {"op": "at", "of": of, "index": position}


def _len(of: Any) -> dict:
    return {"op": "len", "of": of}


def _range(of: Any) -> dict:
    return {"op": "range", "of": of}


def _b(op: str, left: Any, right: Any) -> dict:
    return {"op": op, "left": left, "right": right}


def _mul(*operands: Any) -> dict:
    return {"op": "mul", "operands": list(operands)}


def _add(*operands: Any) -> dict:
    return {"op": "add", "operands": list(operands)}


def _not(of: Any) -> dict:
    return {"op": "not", "of": of}


def _and(*operands: Any) -> dict:
    return {"op": "and", "operands": list(operands)}


def _or(*operands: Any) -> dict:
    return {"op": "or", "operands": list(operands)}


def _round(of: Any) -> dict:
    return {"op": "round", "of": of}


def _in(value: Any, members: Any) -> dict:
    return {"op": "in", "value": value, "set": members}


def _agg(op: str, over: Any, name: str, body: Any, where: Any = None) -> dict:
    node = {"op": op, "over": over, "as": name, "body": body}
    if where is not None:
        node["where"] = where
    return node


def _call(name: str, *arguments: Any) -> dict:
    return {"op": "call", "name": name, "args": list(arguments)}


def _inst(key: str) -> dict:
    return _v(f"instance.{key}")


def _sol(key: str) -> dict:
    return _v(f"solution.{key}")


def _whole_ir(value: Any) -> dict:
    return _b("eq", _b("mod", value, _c(1)), _c(0))


def _eq(a: Any, b: Any) -> dict:
    return _b("eq", a, b)


def _ne(a: Any, b: Any) -> dict:
    return _b("ne", a, b)


def _lt(a: Any, b: Any) -> dict:
    return _b("lt", a, b)


def _le(a: Any, b: Any) -> dict:
    return _b("le", a, b)


def _ge(a: Any, b: Any) -> dict:
    return _b("ge", a, b)


def _gt(a: Any, b: Any) -> dict:
    return _b("gt", a, b)


def _sub(a: Any, b: Any) -> dict:
    return _b("sub", a, b)


#: The formula each node list is read through: `<key>_of(i)` = round(solution.<key>[i]).
READS = {"plate": "plate_of", "cut": "cut_of", "type": "type_of", "x": "x_of", "y": "y_of", "w": "w_of",
         "h": "h_of", "parent": "parent_of", "end": "end_of", "item_node": "node_of", "defect_leaf": "leaf_of"}


def _formula_bodies() -> dict[str, tuple[list[str], dict]]:
    """Each quantity of problem.txt, as a named formula. The order is the order they
    are defined in: a body calls only formulas above it."""
    i, k, d, s, j = _i("i"), _i("k"), _i("d"), _i("s"), _i("j")

    def f(key: str, arg: dict) -> dict:
        return _call(READS[key], arg)

    N, last = _call("N"), _call("last")
    W, H = _inst("plate_w"), _inst("plate_h")
    bodies: dict[str, tuple[list[str], dict]] = {
        "N": ([], _len(_sol("type"))),
        "last": ([], _sub(_call("N"), _c(1))),
        "n_items": ([], _len(_inst("item_w"))),
    }
    for key, name in READS.items():
        bodies[name] = (["i"], _round(_at(_sol(key), i)))
    bodies["plates_used"] = ([], _add(f("plate", last), _c(1)))
    bodies["items_area"] = ([], _agg("sum", _range(_inst("item_w")), "k",
                                     _mul(_at(_inst("item_w"), k), _at(_inst("item_h"), k))))
    p, e = f("parent", i), f("end", i)
    ep = f("end", p)

    # condition 2: the tree
    root = _and(_eq(f("cut", i), _c(0)), _eq(p, _c(-1)),
                _or(_and(_eq(i, _c(0)), _eq(f("plate", i), _c(0))),
                    _and(_gt(i, _c(0)), _eq(f("plate", i), _add(f("plate", _sub(i, _c(1))), _c(1))))),
                _lt(f("plate", i), _inst("n_plates_max")),
                _lt(i, e), _le(e, N),
                _or(_eq(e, N), _eq(f("cut", e), _c(0))))
    child = _and(_ne(f("cut", i), _c(0)), _ge(p, _c(0)), _lt(p, i),
                 _eq(f("plate", i), f("plate", p)), _eq(f("cut", i), _add(f("cut", p), _c(1))),
                 _lt(i, e), _le(e, ep),
                 _or(_eq(e, ep), _and(_lt(e, N), _eq(f("parent", e), p))))
    shape = _or(_and(_eq(f("type", i), _c(BRANCH)), _ge(e, _add(i, _c(2))), _lt(_add(i, _c(1)), N),
                     _eq(f("parent", _add(i, _c(1))), i)),
                _and(_ne(f("type", i), _c(BRANCH)), _eq(e, _add(i, _c(1)))))
    bodies["tree_ok"] = (["i"], _and(_or(root, child), shape))

    # condition 3: types and levels
    t, c = f("type", i), f("cut", i)
    bodies["type_ok"] = (["i"], _and(
        _or(_in(t, [RESIDUAL, BRANCH, WASTE]), _and(_ge(t, _c(0)), _lt(t, _call("n_items")))),
        _ge(c, _c(0)), _le(c, _c(4)),
        _or(_ne(c, _c(0)), _eq(t, _c(BRANCH))),
        _or(_ne(t, _c(BRANCH)), _le(c, _c(3))),
        _or(_ne(t, _c(RESIDUAL)), _and(_eq(c, _c(1)), _eq(i, last)))))

    # condition 4: tiling
    sane = _and(_ge(p, _c(0)), _lt(p, i), _lt(i, e), _le(e, N), _le(ep, N))

    def chain(along: str, span: str, across: str, depth: str) -> dict:
        reach = _add(f(along, i), f(span, i))
        return _and(_eq(f(across, i), f(across, p)), _eq(f(depth, i), f(depth, p)),
                    _or(_ne(i, _add(p, _c(1))), _eq(f(along, i), f(along, p))),
                    _or(_and(_lt(e, ep), _eq(f(along, e), reach)),
                        _and(_ge(e, ep), _eq(reach, _add(f(along, p), f(span, p))))))

    odd = _eq(_b("mod", c, _c(2)), _c(1))
    bodies["geom_ok"] = (["i"], _or(
        _and(_eq(c, _c(0)), _eq(f("x", i), _c(0)), _eq(f("y", i), _c(0)), _eq(f("w", i), W), _eq(f("h", i), H)),
        _and(_ne(c, _c(0)), _or(_not(sane),
                                _and(odd, chain("x", "w", "y", "h")),
                                _and(_not(odd), chain("y", "h", "x", "w"))))))

    # condition 5: at most one 4-cut in a 3-cut's piece
    bodies["trim_ok"] = (["i"], _or(_ne(c, _c(4)), _not(_and(_ge(p, _c(0)), _lt(p, i))),
                                    _eq(i, _add(p, _c(1))), _eq(e, ep)))

    # condition 6: sizes
    w, h = f("w", i), f("h", i)
    bodies["dims_ok"] = (["i"], _and(
        _or(_ne(t, _c(BRANCH)), _ne(c, _c(1)), _and(_ge(w, _inst("min1cut")), _le(w, _inst("max1cut")))),
        _or(_ne(t, _c(BRANCH)), _ne(c, _c(2)), _ge(h, _inst("min2cut"))),
        _or(_ne(t, _c(WASTE)), _and(_ge(w, _inst("min_waste")), _ge(h, _inst("min_waste")))),
        _or(_ne(t, _c(RESIDUAL)), _ge(w, _inst("min_waste")))))

    # condition 7: identity
    iw, ih = _at(_inst("item_w"), t), _at(_inst("item_h"), t)
    bodies["ident_ok"] = (["i"], _or(
        _not(_and(_ge(t, _c(0)), _lt(t, _call("n_items")))),
        _and(_eq(w, iw), _eq(h, ih)), _and(_eq(w, ih), _eq(h, iw))))
    bodies["x_end"] = (["i"], _add(f("x", i), f("w", i)))
    bodies["y_end"] = (["i"], _add(f("y", i), f("h", i)))

    # condition 8: production
    node = f("item_node", k)
    bodies["made_ok"] = (["k"], _and(_ge(node, _c(0)), _lt(node, N), _eq(f("type", node), k)))
    bodies["item_nodes"] = ([], _agg("sum", _range(N), "i", _c(1), where=_ge(f("type", i), _c(0))))

    # condition 9: sequence
    members = _at(_inst("stacks"), s)
    bodies["stack_ok"] = (["s"], _agg("all", _range(members), "j",
                                      _lt(f("item_node", _at(members, _sub(j, _c(1)))),
                                          f("item_node", _at(members, j))),
                                      where=_gt(j, _c(0))))

    # condition 10: defects
    leaf = f("defect_leaf", d)

    def dfield(key: str) -> dict:
        return _at(_inst(key), d)

    dp, dx, dy, dw, dh = (dfield(key) for key in make_instance.DEFECT_KEYS)
    named = _or(_eq(leaf, _c(-1)), _and(
        _ge(leaf, _c(0)), _lt(leaf, N), _eq(f("plate", leaf), dp), _in(f("type", leaf), [WASTE, RESIDUAL]),
        _le(f("x", leaf), dx), _le(_add(dx, dw), _add(f("x", leaf), f("w", leaf))),
        _le(f("y", leaf), dy), _le(_add(dy, dh), _add(f("y", leaf), f("h", leaf)))))
    bodies["defect_ok"] = (["d"], _and(named, _or(_ge(dp, _call("plates_used")), _ne(leaf, _c(-1)))))

    # condition 11: the claims
    edge = _and(_eq(f("cut", last), _c(1)), _in(f("type", last), [WASTE, RESIDUAL]))
    bodies["residual"] = ([], _agg("sum", _range(_c(1)), "i", f("w", last), where=edge))
    return bodies


FORMULAS = _formula_bodies()
ORDER = tuple(FORMULAS)


def _calls(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["name"]} if node.get("op") == "call" else set()
        for value in node.values():
            found |= _calls(value)
        return found
    if isinstance(node, list):
        return set().union(*(_calls(item) for item in node)) if node else set()
    return set()


def _closure(names: set[str]) -> set[str]:
    needed, frontier = set(), set(names)
    while frontier:
        name = frontier.pop()
        if name in needed:
            continue
        needed.add(name)
        frontier |= _calls(FORMULAS[name][1]) - needed
    return needed


def with_formulas(body: dict) -> dict:
    """`body` inside the definitions of every formula it calls, directly or not,
    outermost first, so each formula's body sees the ones above it."""
    needed = _closure(_calls(body))
    for name in reversed([n for n in ORDER if n in needed]):
        params, formula = FORMULAS[name]
        body = {"op": "define", "name": name, "params": params, "body": formula, "in": body}
    return body


def clause_trees() -> list[dict]:
    """The eleven conditions, each a self-contained tree, in order."""
    N = _call("N")

    def every_node(name: str) -> dict:
        return _agg("all", _range(N), "i", _call(name, _i("i")))

    shapes = _and(
        _ge(N, _c(1)),
        *(_eq(_len(_sol(key)), N) for key in NODE_KEYS if key != "type"),
        _eq(_len(_sol("item_node")), _len(_inst("item_w"))),
        _eq(_len(_sol("defect_leaf")), _len(_inst("defect_x"))),
        *(_agg("all", _range(_sol(key)), "t", _whole_ir(_at(_sol(key), _i("t")))) for key in LIST_KEYS),
        *(_whole_ir(_sol(key)) for key in CLAIM_KEYS))
    production = _and(_agg("all", _range(_inst("item_w")), "k", _call("made_ok", _i("k"))),
                      _eq(_call("item_nodes"), _call("n_items")))
    sequence = _agg("all", _range(_inst("stacks")), "s", _call("stack_ok", _i("s")))
    defects = _agg("all", _range(_inst("defect_x")), "d", _call("defect_ok", _i("d")))
    plates, residual = _round(_sol("n_plates")), _round(_sol("residual_w"))
    W, H = _inst("plate_w"), _inst("plate_h")
    claims = _and(_eq(plates, _call("plates_used")), _eq(residual, _call("residual")),
                  _eq(_round(_sol("geo_loss")),
                      _sub(_sub(_mul(plates, W, H), _mul(H, residual)), _call("items_area"))))
    return [with_formulas(tree) for tree in (
        shapes, every_node("tree_ok"), every_node("type_ok"), every_node("geom_ok"), every_node("trim_ok"),
        every_node("dims_ok"), every_node("ident_ok"), production, sequence, defects, claims)]


def validity_tree() -> dict:
    """The eleven conditions, as one expression, with `and` at the top."""
    return _and(*clause_trees())


def objective_tree() -> dict:
    """geo_loss, proven by condition 11 to be plates x W x H - H x residual - the items' area."""
    return _round(_sol("geo_loss"))


def probe_tree(name: str, *arguments: int) -> dict:
    """One formula at one node, item, defect or stack (or a scalar), as the IR computes it inside the rules."""
    return with_formulas(_call(name, *(_c(a) for a in arguments)))


#: The per-element formulas the probes compare, and what they range over.
PROBED = (("tree_ok", "type"), ("type_ok", "type"), ("geom_ok", "type"), ("trim_ok", "type"),
          ("dims_ok", "type"), ("ident_ok", "type"), ("x_end", "type"), ("y_end", "type"),
          ("made_ok", "item_node"), ("stack_ok", None), ("defect_ok", "defect_leaf"))
SCALAR_PROBED = ("plates_used", "items_area", "residual", "item_nodes")


def _list_probe(name: str) -> dict:
    """Every element of one formula against the Python reading's list, in one walk."""
    values = _sol(f"_probe_{name}")
    return with_formulas(_agg("all", _range(values), "q", _eq(_call(name, _i("q")), _at(values, _i("q")))))


# --- both readings, compared --------------------------------------------------


def _evaluate():
    sys.path.insert(0, str(_evolve_source()))
    from evolve.problem.expression import evaluate

    return evaluate


def ir_refusals(instance: dict, solution: dict) -> list[int]:
    """The conditions the IR refuses, each clause read ALONE -- the walk the
    platform's verifier makes to explain a refusal. A clause that cannot be
    evaluated (an ExpressionError) is a refusal, as the verifier treats it;
    anything else escaping is a defect, and is let through to fail loudly."""
    sys.path.insert(0, str(_evolve_source()))
    from evolve.problem.expression import ExpressionError, evaluate

    out = []
    for number, clause in enumerate(clause_trees(), start=1):
        try:
            held = evaluate(clause, instance=instance, solution=solution)
        except ExpressionError:
            held = False
        if held is not True:
            out.append(number)
    return out


def _well_typed(instance: dict, solution: dict) -> bool:
    """Lists of whole ints of the rules' lengths and whole-int claims: the answers
    whose every intermediate the two readings can be asked for."""
    if not isinstance(solution, dict):
        return False
    t = solution.get("type")
    if not isinstance(t, list) or not t:
        return False

    def ints(values: Any, length: int) -> bool:
        return (isinstance(values, list) and len(values) == length
                and all(isinstance(v, int) and not isinstance(v, bool) for v in values))

    return (all(ints(solution.get(k), len(t)) for k in NODE_KEYS)
            and ints(solution.get("item_node"), len(instance["item_w"]))
            and ints(solution.get("defect_leaf"), len(instance["defect_x"]))
            and all(isinstance(solution.get(k), int) and not isinstance(solution.get(k), bool) for k in CLAIM_KEYS))


def probes(instance: dict, solution: dict) -> tuple[int, list]:
    """Every per-node, per-item, per-defect and per-stack intermediate, IR against
    Python, bit for bit: each formula over its range in one walk, then the scalars
    one call each. Returns how many values were compared and the disagreements."""
    evaluate = _evaluate()
    python = per_node(instance, solution)
    augmented = dict(solution)
    count, wrong = 0, []
    for name, _ in PROBED:
        augmented[f"_probe_{name}"] = python[name]
        count += len(python[name])
    for name, _ in PROBED:
        if evaluate(_list_probe(name), instance=instance, solution=augmented) is not True:
            for position, want in enumerate(python[name]):
                got = evaluate(probe_tree(name, position), instance=instance, solution=solution)
                if got != want or type(got) is not type(want):
                    wrong.append((name, position, want, got))
                    break
    for name in SCALAR_PROBED:
        got = evaluate(probe_tree(name), instance=instance, solution=solution)
        want = python["scalars"][name]
        count += 1
        if got != want or type(got) is not type(want):
            wrong.append((name, None, want, got))
    return count, wrong


def judge_both(instance: dict, solution: dict, *, with_probes: bool = True) -> dict[str, Any]:
    """One answer through both readings, timed: the whole verdict, every clause
    alone, the objective, and every intermediate (for an answer of whole numbers)."""
    evaluate = _evaluate()
    started = time.perf_counter()
    reasons = validity_reasons(instance, solution)
    python_seconds = time.perf_counter() - started
    started = time.perf_counter()
    try:
        held = evaluate(validity_tree(), instance=instance, solution=solution)
    except Exception as error:  # noqa: BLE001 - an expression error is a refusal
        held = f"refused: {type(error).__name__}: {error}"
    ir_seconds = time.perf_counter() - started
    python_numbers = [int(r.split(":")[0]) for r in reasons]
    result: dict[str, Any] = {"reasons": reasons, "refused_by": python_numbers, "ir": held,
                              "python_seconds": python_seconds, "ir_seconds": ir_seconds,
                              "probes": 0, "probe_disagreements": []}
    result["ir_clauses"] = ir_refusals(instance, solution)
    result["agree"] = ((held is True) == (not reasons)) and result["ir_clauses"] == python_numbers
    if held is True and not reasons:
        here = objective(instance, solution)
        there = evaluate(objective_tree(), instance=instance, solution=solution)
        result["objective"] = (here, there)
        result["agree"] = result["agree"] and here == there and type(there) is int
    if with_probes and _well_typed(instance, solution):
        result["probes"], result["probe_disagreements"] = probes(instance, solution)
        result["agree"] = result["agree"] and not result["probe_disagreements"]
    return result


# --- trees, and the certificate problem.txt defines ---------------------------


def node(kind: int, x: int, y: int, w: int, h: int, *children: dict) -> dict:
    """A node of a cutting tree: its type, its rectangle and its children in cutting order."""
    return {"t": kind, "x": x, "y": y, "w": w, "h": h, "c": list(children)}


def flatten(plates: list[tuple[int, dict]]) -> dict[str, list[int]]:
    """Pre-order columns (plate, cut, type, x, y, w, h, parent) of plates given as
    (plate id, root) pairs; the cut is the depth."""
    cols: dict[str, list[int]] = {key: [] for key in ("plate", "cut", "type", "x", "y", "w", "h", "parent")}

    def walk(n: dict, plate: int, depth: int, parent: int) -> None:
        index = len(cols["type"])
        for key, value in (("plate", plate), ("cut", depth), ("type", n["t"]), ("x", n["x"]), ("y", n["y"]),
                           ("w", n["w"]), ("h", n["h"]), ("parent", parent)):
            cols[key].append(value)
        for child in n["c"]:
            walk(child, plate, depth + 1, index)

    for plate, root in plates:
        walk(root, plate, 0, -1)
    return cols


def recertify(instance: dict, solution: dict) -> dict:
    """The answer's geometry -- plate, cut, type, x, y, w, h and parent of every node,
    in the order given -- with the certificate an honest emitter derives from it:
    each subtree's end (the list read as a pre-order), each item's first node, each
    defect's leaf (on a used plate: the leaf containing it, else the first leaf
    overlapping it, else -1; elsewhere -1), and the three claims."""
    n = len(solution["type"])
    cols = {key: [int(v) for v in solution[key][:n]]
            for key in ("plate", "cut", "type", "x", "y", "w", "h", "parent")}
    size = [1] * n
    for i in range(n - 1, -1, -1):
        p = cols["parent"][i]
        if 0 <= p < i:
            size[p] += size[i]
    end = [i + size[i] for i in range(n)]
    out: dict[str, Any] = dict(cols)
    out["end"] = end
    first: dict[int, int] = {}
    for i, kind in enumerate(cols["type"]):
        if kind >= 0 and kind not in first:
            first[kind] = i
    out["item_node"] = [first.get(k, -1) for k in range(len(instance["item_w"]))]
    used = cols["plate"][-1] + 1
    leaves = [i for i in range(n) if end[i] == i + 1]
    by_plate: dict[int, list[int]] = {}
    for i in leaves:
        by_plate.setdefault(cols["plate"][i], []).append(i)
    pointers = []
    for d in range(len(instance["defect_x"])):
        dp, dx, dy, dw, dh = (instance[k][d] for k in make_instance.DEFECT_KEYS)
        chosen = -1
        if dp < used:
            inside = overlap = -1
            for i in by_plate.get(dp, []):
                x, y, w, h = cols["x"][i], cols["y"][i], cols["w"][i], cols["h"][i]
                if x <= dx and dx + dw <= x + w and y <= dy and dy + dh <= y + h:
                    inside = i
                    break
                if overlap < 0 and x < dx + dw and dx < x + w and y < dy + dh and dy < y + h:
                    overlap = i
            chosen = inside if inside >= 0 else overlap
        pointers.append(chosen)
    out["defect_leaf"] = pointers
    last = n - 1
    residual = cols["w"][last] if cols["cut"][last] == 1 and cols["type"][last] in (WASTE, RESIDUAL) else 0
    out["n_plates"] = used
    out["residual_w"] = residual
    out["geo_loss"] = (used * instance["plate_w"] * instance["plate_h"] - instance["plate_h"] * residual
                       - item_area(instance))
    return {key: out[key] for key in SOLUTION_KEYS}


def certify(instance: dict, plates: list[tuple[int, dict]], **forged: Any) -> dict:
    """An answer from plates given as trees, with the honest certificate; `forged`
    overwrites any key afterwards (the counterexamples' one changed thing)."""
    answer = recertify(instance, flatten(plates))
    answer.update(forged)
    return answer


def trees_of(solution: dict) -> list[tuple[int, dict]]:
    """The plates of a well-formed answer, back as (plate id, root) trees."""
    n = len(solution["type"])
    made: list[dict] = []
    plates: list[tuple[int, dict]] = []
    for i in range(n):
        this = node(solution["type"][i], solution["x"][i], solution["y"][i], solution["w"][i], solution["h"][i])
        made.append(this)
        p = solution["parent"][i]
        if p < 0:
            plates.append((solution["plate"][i], this))
        else:
            made[p]["c"].append(this)
    return plates


def leaves_of(root: dict) -> list[dict]:
    if not root["c"]:
        return [root]
    return [leaf for child in root["c"] for leaf in leaves_of(child)]


# --- the official checker -----------------------------------------------------


def roadef_dir() -> Path:
    return Path(os.environ.get("ROADEF2018_DIR", str(make_instance.DEFAULT_DIR)))


def checker_binary() -> Path:
    """The official checker, built from its own source (checker/src, checker/include)
    with the house flags into <roadef>/build/checker.exe, once."""
    folder = roadef_dir()
    source = folder / "checker"
    binary = folder / "build" / "checker.exe"
    units = sorted((source / "src").glob("*.cpp"))
    if not units:
        raise SystemExit(f"the checker's source is not in {source}/src; set ROADEF2018_DIR")
    newest = max(p.stat().st_mtime for p in [*units, *sorted((source / "include").glob("*.h"))])
    if not binary.is_file() or binary.stat().st_mtime < newest:
        binary.parent.mkdir(parents=True, exist_ok=True)
        done = subprocess.run([*COMPILE, f"-I{source / 'include'}", *map(str, units), "-o", str(binary)],
                              capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise SystemExit(f"the checker did not build:\n{done.stderr[-3000:]}")
    return binary


def to_csv(solution: dict) -> str | None:
    """The answer in the checker's solution format, PLATE_ID;NODE_ID;X;Y;WIDTH;HEIGHT;
    TYPE;CUT;PARENT, one line per node in the answer's order, a plate's line with an
    empty PARENT. None when the node lists are not lists of whole numbers."""
    try:
        n = len(solution["type"])
        cols = {k: [int(v) for v in solution[k][:n]] for k in ("plate", "cut", "type", "x", "y", "w", "h",
                                                                 "parent")}
        if any(len(v) != n for v in cols.values()) or any(
                isinstance(v, bool) or not isinstance(v, int) for k in cols for v in solution[k][:n]):
            return None
    except (TypeError, ValueError, KeyError):
        return None
    lines = ["PLATE_ID;NODE_ID;X;Y;WIDTH;HEIGHT;TYPE;CUT;PARENT"]
    for i in range(n):
        parent = "" if cols["parent"][i] < 0 else str(cols["parent"][i])
        lines.append(f"{cols['plate'][i]};{i};{cols['x'][i]};{cols['y'][i]};{cols['w'][i]};{cols['h'][i]};"
                     f"{cols['type'][i]};{cols['cut'][i]};{parent}")
    return "\n".join(lines) + "\n"


def _instance_csvs(instance: dict) -> dict[str, str]:
    """batch, defects and global_param CSVs for an instance that is not a dataset-B
    one (the worked instance): written from the instance, in the challenge's columns."""
    batch = ["ITEM_ID;LENGTH_ITEM;WIDTH_ITEM;STACK;SEQUENCE"]
    for s, members in enumerate(instance["stacks"]):
        for q, item in enumerate(members, start=1):
            batch.append(f"{item};{instance['item_h'][item]};{instance['item_w'][item]};{s};{q}")
    defects = ["DEFECT_ID;PLATE_ID;X;Y;WIDTH;HEIGHT"]
    for d in range(len(instance["defect_x"])):
        defects.append(";".join(str(v) for v in (d, *(instance[k][d] for k in make_instance.DEFECT_KEYS))))
    params = ["NAME;VALUE"] + [f"{name};{instance[key]}" for name, key in make_instance.PARAMS]
    return {"batch": "\n".join(batch) + "\n", "defects": "\n".join(defects) + "\n",
            "global_param": "\n".join(params) + "\n"}


#: Each checker run gets its own folder: the sweeps call it from several threads.
_RUNS = itertools.count(1)
_RUNS_LOCK = threading.Lock()


def run_checker(instance: dict, solution: dict, tag: str = "run") -> dict[str, Any]:
    """The official checker on this answer. For a dataset-B instance it reads the
    challenge's own batch, defects and global_param files; for the worked instance,
    files written from it. Returns what it says: stage (parse / invalid / valid),
    validSolution and the rest of its statistics row, the objective it prints (OF,
    mm^2), the constraint families its log names, and its first ERROR lines."""
    text = to_csv(solution)
    if text is None:
        return {"stage": "unconvertible", "valid": None, "of": None, "violated": [], "errors": []}
    with _RUNS_LOCK:
        number = next(_RUNS)
    base = roadef_dir() / "runs" / f"{tag}-{os.getpid()}-{number}"
    if base.exists():
        shutil.rmtree(base)
    folder = base / "instances_checker"
    folder.mkdir(parents=True)
    (base / "logs").mkdir()
    name = instance["name"]
    official = roadef_dir() / "dataset_B"
    if name in make_instance.RIVALS and (official / f"{name}_batch.csv").is_file():
        shutil.copyfile(official / f"{name}_batch.csv", folder / f"{name}_batch.csv")
        shutil.copyfile(official / f"{name}_defects.csv", folder / f"{name}_defects.csv")
        shutil.copyfile(roadef_dir() / "checker" / "instances_checker" / "global_param.csv",
                        folder / "global_param.csv")
    else:
        files = _instance_csvs(instance)
        (folder / f"{name}_batch.csv").write_text(files["batch"], encoding="utf-8", newline="\n")
        (folder / f"{name}_defects.csv").write_text(files["defects"], encoding="utf-8", newline="\n")
        (folder / "global_param.csv").write_text(files["global_param"], encoding="utf-8", newline="\n")
    (folder / f"{name}_solution.csv").write_text(text, encoding="utf-8", newline="\n")
    started = time.perf_counter()
    done = subprocess.run([str(checker_binary()), name, "0"], cwd=base, capture_output=True, text=True,
                          timeout=300, check=False)
    seconds = time.perf_counter() - started
    # With no statistics file the checker either refused a file while parsing it
    # (EXIT_FAILURE, 1) or crashed: it does so, measured, on plates listed out of order.
    out: dict[str, Any] = {"stage": "parse" if done.returncode in (0, 1) else "crashed", "valid": False,
                           "of": None, "violated": [], "errors": [], "seconds": seconds, "exit": done.returncode,
                           "stdout": done.stdout.strip()[-300:]}
    stats = base / "logs" / f"{name}_statistics.csv"
    log = base / "logs" / f"{name}_log.txt"
    if stats.is_file():
        header, row = stats.read_text(encoding="utf-8", errors="replace").splitlines()[:2]
        out["statistics"] = dict(zip(header.split(";"), row.split(";")))
        out["valid"] = out["statistics"].get("validSolution") == "1"
        out["stage"] = "valid" if out["valid"] else "invalid"
    if log.is_file():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        out["errors"] = [line.strip() for line in lines if "ERROR" in line][:6]
        out["violated"] = [line.strip()[2:].replace(" Constraint violated", "") for line in lines
                           if line.strip().startswith("- ") and "violated" in line]
        for line in lines:
            if "--- OF = " in line:
                out["of"] = int(line.split("OF =")[1].split("-")[0].strip())
    if "VALID SOLUTION" in done.stdout and "INVALID" not in done.stdout:
        printed = int(done.stdout.strip().split("|")[-1].strip())
        if out["of"] is not None and printed != out["of"]:
            out["errors"].append(f"stdout OF {printed} differs from the log's {out['of']}")
        out["of"] = printed
    shutil.rmtree(base, ignore_errors=True)
    return out


def leniencies(solution: dict) -> list[str]:
    """What the official checker accepts that the subject, and these rules, do not.
    Measured, not supposed: the checker never reads a plate line's X or TYPE; it
    compares its 1-cut nodes' y with the plate line's Y and no node with the plate's
    height, so a whole tree may sit shifted up; and it takes a branch with no
    children -- a plate line with none included -- for a leaf, with no size rule and
    room for a defect. The subject's leaves are items, wastes and the residual."""
    found = []
    n = len(solution["type"])
    parents = [solution["parent"][i] for i in range(n)]
    plates = [i for i in range(n) if parents[i] < 0]
    if any(solution["x"][i] != 0 for i in plates):
        found.append("a plate line's X is not 0")
    if any(solution["y"][i] != 0 for i in plates):
        found.append("a plate line's Y is not 0")
    if any(solution["type"][i] != BRANCH for i in plates):
        found.append("a plate line's TYPE is not -2")
    with_children = {p for p in parents if p >= 0}
    if any(solution["type"][i] == BRANCH and i not in with_children for i in range(n)):
        found.append("a branch with no children")
    if all(p < i for i, p in enumerate(parents)):
        open_nodes: list[int] = []
        for i, p in enumerate(parents):
            while open_nodes and open_nodes[-1] != p:
                open_nodes.pop()
            if p >= 0 and not open_nodes:
                found.append("the nodes are parents-first, not in pre-order")
                break
            open_nodes.append(i)
    return found


def three_way(instance: dict, solution: dict, tag: str = "row", *, with_probes: bool = False) -> dict[str, Any]:
    """The two readings on the answer, and the checker on its geometry. The checker
    reads no certificate, so what it must agree with is the honest certificate of
    the same geometry (`recertify`): when that is valid, the checker must accept at
    the same objective; when it is refused, the checker must refuse too, unless the
    geometry uses one of the checker's measured `leniencies` -- then the row says so."""
    judged = judge_both(instance, solution, with_probes=with_probes)
    checker = run_checker(instance, solution, tag)
    honest, lenient = None, []
    if checker["stage"] != "unconvertible":
        try:
            again = recertify(instance, solution)
            honest = {"refused_by": refused_by(instance, again), "geo_loss": again["geo_loss"]}
        except (TypeError, ValueError, KeyError, IndexError):
            honest = None
    agrees = judged["agree"]
    if honest is not None:
        if not honest["refused_by"]:
            agrees = agrees and checker["valid"] is True and checker["of"] == honest["geo_loss"]
        elif checker["valid"]:
            lenient = leniencies(solution)
            agrees = agrees and bool(lenient)
    return {"judged": judged, "checker": checker, "honest": honest, "lenient": lenient, "agree": agrees}


def quick_three(instance: dict, solution: dict, tag: str = "sweep") -> dict[str, Any]:
    """The whole verdict three ways, without the per-clause walk and the probes: the
    Python reading, the IR's validity and objective trees, the checker. For sweeps."""
    evaluate = _evaluate()
    reasons = refused_by(instance, solution)
    try:
        held = evaluate(validity_tree(), instance=instance, solution=solution)
    except Exception:  # noqa: BLE001 - an expression error is a refusal
        held = False
    score = evaluate(objective_tree(), instance=instance, solution=solution) if held is True else None
    checker = run_checker(instance, solution, tag)
    python_score = objective(instance, solution) if not reasons else None
    agree = ((held is True) == (not reasons) == checker["valid"]) and (
        reasons or (score == python_score == checker["of"]))
    return {"refused_by": reasons, "ir": held is True, "checker": checker["valid"], "score": python_score,
            "checker_of": checker["of"], "agree": bool(agree)}


# --- building and running ------------------------------------------------------


def instances() -> list[dict]:
    return json.loads(INSTANCES.read_text(encoding="utf-8"))


def source_files() -> list[Path]:
    """The only files that are bundled: C++ translation units in `solver/`."""
    return [p for p in sorted(SOLVER.iterdir()) if p.is_file() and p.suffix == ".cpp"]


def strays() -> list[Path]:
    """Anything else in `solver/`. Never bundled; `check` says so and fails."""
    return [p for p in sorted(SOLVER.iterdir()) if p.is_file() and p.suffix != ".cpp"]


def bundle_from_solver() -> dict[str, str]:
    return {f"solver/{p.name}": p.read_text(encoding="utf-8") for p in source_files()}


def pack() -> int:
    bundle = bundle_from_solver()
    if set(bundle) != {"solver/candidate.cpp"} or strays():
        sys.exit(f"solver/ must hold solver/candidate.cpp and nothing else; it holds "
                 f"{sorted(bundle)} and {[p.name for p in strays()]}")
    BUNDLE.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {BUNDLE.name} ({BUNDLE.stat().st_size:,} bytes)")
    return 0


_WORKDIR: Path | None = None
_BUILT: dict[str, Path] = {}


def workdir() -> Path:
    """One scratch directory per process, removed when it exits."""
    global _WORKDIR
    if _WORKDIR is None:
        _WORKDIR = Path(tempfile.mkdtemp(prefix="roadef2018-glass-b-"))
        atexit.register(shutil.rmtree, _WORKDIR, True)
    return _WORKDIR


def compile_source(source: str, stem: str) -> Path:
    """Compile one translation unit with the platform's flags; the same source is
    compiled once per process."""
    key = f"{stem}:{hash(source)}"
    if key in _BUILT:
        return _BUILT[key]
    unit = workdir() / f"{stem}-{len(_BUILT)}.cpp"
    unit.write_text(source, encoding="utf-8")
    binary = unit.with_suffix(".exe")
    done = subprocess.run([*COMPILE, "-o", str(binary), str(unit)], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        sys.exit(f"{stem} did not compile:\n{done.stderr[-4000:]}")
    _BUILT[key] = binary
    return binary


def run_binary(binary: Path, instance_path: Path, out: Path, seed: int,
               timeout: float = 300) -> tuple[float, int, str]:
    """Run a candidate; returns seconds, exit code and stderr (never exits)."""
    started = time.perf_counter()
    done = subprocess.run([str(binary), str(instance_path), str(out), "--seed", str(seed)],
                          capture_output=True, text=True, timeout=timeout, check=False)
    return time.perf_counter() - started, done.returncode, done.stderr


def single_instance(instance: dict, stem: str | None = None) -> Path:
    """§9 hands a candidate ONE instance, in canonical JSON: keys sorted, no
    whitespace. The seed must not care about either."""
    path = workdir() / f"{stem or instance['name']}.json"
    if not path.is_file():
        path.write_text(json.dumps(instance, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


def seed_answer(instance: dict, *, source: str | None = None, seed: int = 1) -> tuple[dict, float, str]:
    """The starting program's answer on `instance` (or a variant's, from `source`),
    its runtime and its stderr account."""
    binary = compile_source(source or (SOLVER / "candidate.cpp").read_text(encoding="utf-8"), "candidate")
    out = workdir() / f"answer-{instance['name']}-{seed}.json"
    seconds, code, account = run_binary(binary, single_instance(instance), out, seed)
    if code != 0:
        sys.exit(f"the seed exited {code} on {instance['name']}\n{account[-2000:]}")
    return json.loads(out.read_text(encoding="utf-8")), seconds, account


def parameter_space() -> list[str]:
    """The holes the platform's inner search will find in the seed, as it finds them."""
    sys.path.insert(0, str(_evolve_source()))
    from evolve.research.patch import SourceTree
    from evolve.research.tunables import defaults_of, parameter_space_of

    tree = SourceTree(files=bundle_from_solver())
    space = parameter_space_of(tree)
    if space is None:
        return ["no declared holes"]
    defaults = defaults_of(tree).values
    lines = []
    for hole in space.parameters:
        kind = str(getattr(hole, "kind", "EXPRESSION"))
        if hasattr(hole, "operators"):
            lines.append(f"{hole.name:<11} EXPRESSION returns {hole.returns}, args "
                         f"{', '.join(f'{t} {n}' for t, n in hole.arguments)}, ops "
                         f"{' '.join(hole.operators)}, depth {hole.depth}, nodes {hole.nodes}; "
                         f"author's tree {defaults[hole.name]}")
        elif hole.choices:
            lines.append(f"{hole.name:<11} {kind.split('.')[-1]:<11} {list(hole.choices)}  author's value "
                         f"{defaults[hole.name]}")
        else:
            lines.append(f"{hole.name:<11} {kind.split('.')[-1]:<11} [{hole.low:g}, {hole.high:g}]  author's value "
                         f"{defaults[hole.name]}")
    return lines


def _holes() -> dict[str, Any]:
    sys.path.insert(0, str(_evolve_source()))
    from evolve.research.patch import SourceTree
    from evolve.research.tunables import parameter_space_of

    tree = SourceTree(files=bundle_from_solver())
    return {hole.name: hole for hole in parameter_space_of(tree).parameters}


def variant_source(**changes: Any) -> str:
    """`solver/candidate.cpp` with some holes set to other values, written by
    `evolve.research.tunables.substitute` exactly as the inner search writes one."""
    sys.path.insert(0, str(_evolve_source()))
    from evolve.research.patch import SourceTree
    from evolve.research.search import Individual
    from evolve.research.tunables import defaults_of, substitute

    tree = SourceTree(files=bundle_from_solver())
    holes = _holes()
    values = dict(defaults_of(tree).values)
    for name, value in changes.items():
        values[name] = holes[name].canonical(value) if hasattr(holes[name], "operators") else value
    return substitute(tree, Individual(values)).files["solver/candidate.cpp"]


# --- the check -------------------------------------------------------------------


#: Mistakes spliced into `solve` just before it hands the Layout to the emit layer.
#: Each is a Layout a model could plausibly return; the emit layer must write it as
#: it stands and the judge must refuse it for the right reason.
#: (label, the C++ spliced in, (how, refusals), the stderr words.)
HOOK = "    return layout;  // the layout, as the emit layer receives it"
EDITS = (
    ("the first item's slot moved 1 mm right, leaving a 1 mm gap in front of it",
     "    layout.placed[0].slot_x += 1;\n", ("first", [4]), "breaks condition"),
    ("the first item left out of the layout", "    layout.placed.erase(layout.placed.begin());\n",
     ("exactly", [8]), "breaks condition 8"),
    ("the second item written with the first item's number",
     "    layout.placed[1].item = layout.placed[0].item;\n", ("first", [8]), "breaks condition 8"),
    ("every item written turned, its slot unchanged",
     "    for (Placement& p : layout.placed) std::swap(p.w, p.h);\n", ("first", [4]), "breaks condition"),
    ("the whole layout moved to the next plate",
     "    for (Placement& p : layout.placed) p.plate += 1;\n", ("first", [10]), "breaks condition 10"),
)


def _edits(instance: dict, problems: list[str]) -> list[str]:
    """The emit layer, pinned: a mistaken Layout is written as it stands and refused
    by the judge -- both readings and the checker -- never repaired."""
    source = (SOLVER / "candidate.cpp").read_text(encoding="utf-8")
    lines = []
    print(f"\nthe emit layer on mistakes spliced into `solve` ({instance['name']}):")
    if source.count(HOOK) != 1:
        problems.append(f"the line `{HOOK.strip()}` is not in candidate.cpp exactly once")
        return lines
    single = single_instance(instance)
    for label, splice, (how, expected), words in EDITS:
        binary = compile_source(source.replace(HOOK, splice + HOOK), "edited")
        out = workdir() / "edited.json"
        _, code, account = run_binary(binary, single, out, seed=1)
        answer = json.loads(out.read_text(encoding="utf-8"))
        row = three_way(instance, answer, "edit")
        refused = row["judged"]["refused_by"]
        named = refused == expected if how == "exactly" else refused[:1] == expected
        ok = code == 0 and named and row["agree"] and words in account and row["checker"]["valid"] is False
        line = (f"  {label:<76} refused by {refused} ({how} {expected}); IR "
                f"{'agrees' if row['judged']['agree'] else 'DISAGREES'}; checker {row['checker']['stage']} "
                f"({', '.join(row['checker']['violated']) or '-'}); stderr says '{words}': {words in account}"
                f"{'' if ok else '   UNEXPECTED'}")
        print(line)
        lines.append(line)
        if not ok:
            problems.append(f"{label}: refused by {refused} (IR {row['judged'].get('ir_clauses')}), expected "
                            f"{how} {expected}; exit {code}; checker {row['checker']}; stderr: {account.strip()[:300]}")
    return lines


def _pool(jobs: list, work, workers: int | None = None) -> list:
    """Run `work(job)` for every job on a few threads (each job is a subprocess)."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers or max(1, min(6, (os.cpu_count() or 2) // 2))) as pool:
        return list(pool.map(work, jobs))


#: The dormant search switched on, every variant written by `tunables.substitute`:
#: (label, changes, seeds cap, runs at a time -- one for the timing that must be honest).
SEARCH_VARIANTS = (
    ("beam_width 8 + restarts 10", {"beam_width": 8, "restarts": 10}, 20, 6),
    ("beam_width 64", {"beam_width": 64}, 3, 6),
    ("every knob at its maximum (beam_width 256, restarts 200)", {"beam_width": 256, "restarts": 200}, 1, 1),
)


def _run_all(binary: Path, seeds: range, tag: str, workers: int | None = None) -> list[dict]:
    """Every instance under every seed: runtime, exit, the answer judged three ways."""
    jobs = [(inst, seed) for seed in seeds for inst in instances()]

    def work(job):
        inst, seed = job
        out = workdir() / f"{tag}-{inst['name']}-{seed}.json"
        if out.exists():
            out.unlink()
        seconds, code, account = run_binary(binary, single_instance(inst), out, seed)
        row = {"name": inst["name"], "seed": seed, "seconds": seconds, "code": code, "account": account[-300:]}
        if code == 0 and out.is_file():
            answer = json.loads(out.read_text(encoding="utf-8"))
            row.update(quick_three(inst, answer, tag))
            row["bytes"] = out.read_bytes()
        return row

    return _pool(jobs, work, workers)


def _search(seeds: int, problems: list[str]) -> list[str]:
    lines = []
    print("\nthe dormant search switched on (variants written by evolve.research.tunables.substitute), "
          "on all fifteen instances, every answer judged three ways; the first two variants six runs at a time "
          "(their times pessimistic), the last one run at a time:")
    for label, changes, cap, workers in SEARCH_VARIANTS:
        runs = min(seeds, cap)
        binary = compile_source(variant_source(**changes), "search")
        rows = _run_all(binary, range(1, runs + 1), "search", workers)
        crashed = [r for r in rows if r["code"] != 0 or "bytes" not in r]
        invalid = [r for r in rows if "bytes" in r and r["refused_by"]]
        disagree = [r for r in rows if "bytes" in r and not r["agree"]]
        slowest = max(r["seconds"] for r in rows)
        totals: dict[int, int] = {}
        for r in rows:
            if "bytes" in r and not r["refused_by"]:
                totals[r["seed"]] = totals.get(r["seed"], 0) + r["score"]
        line = (f"  {label:<58} {len(rows)} runs (seeds 1..{runs} x 15): {len(crashed)} crashed, {len(invalid)} "
                f"invalid, {len(disagree)} where the three readings differ; total over 15 "
                + (f"{min(totals.values()):,} to {max(totals.values()):,}" if totals else "-")
                + f"; slowest {slowest:.1f} s")
        print(line)
        lines.append(line)
        for r in crashed[:3]:
            problems.append(f"{label}, {r['name']} seed {r['seed']}: exit {r['code']} {r['account'][-200:]}")
        for r in invalid[:3]:
            problems.append(f"{label}, {r['name']} seed {r['seed']}: invalid {r['refused_by']}")
        for r in disagree[:3]:
            problems.append(f"{label}, {r['name']} seed {r['seed']}: the readings differ {r}")
        if slowest > SANDBOX_SECONDS / 2:
            problems.append(f"{label}: {slowest:.0f} s, not well under the {SANDBOX_SECONDS} s a run may take")
        # the same seed writes the same bytes
        again = _run_all(binary, range(3, 4) if runs >= 3 else range(1, 2), "again")
        before = {(r["name"], r["seed"]): r.get("bytes") for r in rows}
        differ = [r["name"] for r in again if before.get((r["name"], r["seed"])) != r.get("bytes")]
        if differ:
            problems.append(f"{label}: a second run with the same seed wrote different bytes on {differ}")
        print(f"    a second run with seed {again[0]['seed']}: {'the same bytes on all 15' if not differ else differ}")
    return lines


def _random_guides(count: int, problems: list[str]) -> list[str]:
    """Guides drawn by the hole itself, as the inner search draws them, written in by
    `tunables.substitute`, the search off and on: every run must exit 0 and write an
    answer the three readings judge alike -- valid or not, since a bad guide may be
    worse, never crash."""
    sys.path.insert(0, str(_evolve_source()))
    from evolve.domain.seeds import Pcg64
    from evolve.research.patch import SourceTree
    from evolve.research.tunables import defaults_of

    hole = _holes()["guide"]
    author = defaults_of(SourceTree(files=bundle_from_solver())).values["guide"]
    lines = []
    for family, draw in (("sampled afresh (hole.sample)", lambda n: hole.sample(Pcg64(1000 + n))),
                         ("one mutation of the author's guide (hole.step)",
                          lambda n: hole.step(author, Pcg64(2000 + n)))):
        runs = crashed = valid = 0
        firsts: dict[int, int] = {}
        slowest, best = 0.0, None
        for k in range(count):
            law = draw(k)
            for label, knobs in (("off", {}), ("on", {"beam_width": 8})):
                binary = compile_source(variant_source(guide=law, **knobs), "guide")
                rows = _run_all(binary, range(k + 1, k + 2), "guide")
                for r in rows:
                    runs += 1
                    slowest = max(slowest, r["seconds"])
                    if r["code"] != 0 or "bytes" not in r:
                        crashed += 1
                        problems.append(f"guide {law} ({label}) on {r['name']}: exit {r['code']} {r['account'][-200:]}")
                        continue
                    if not r["agree"]:
                        problems.append(f"guide {law} on {r['name']}: the readings differ")
                    if not r["refused_by"]:
                        valid += 1
                    else:
                        firsts[r["refused_by"][0]] = firsts.get(r["refused_by"][0], 0) + 1
                total = sum(r["score"] for r in rows if "bytes" in r and not r["refused_by"])
                if all("bytes" in r and not r["refused_by"] for r in rows) and (best is None or total < best[0]):
                    best = (total, law, label)
        line = (f"  {count} guides {family}, each with the search off and on (beam 8), on all 15 instances: {runs} "
                f"runs, {crashed} crashed, {valid} valid, {runs - crashed - valid} refused as they stand (first "
                f"refusing condition: {dict(sorted(firsts.items()))}), the three readings alike on every one; "
                f"slowest {slowest:.1f} s" + (f"; best total {best[0]:,} from {best[1]} (search {best[2]})"
                                             if best else ""))
        print(line)
        lines.append(line)
    return lines


def check(search_seeds: int) -> int:
    problems: list[str] = []
    stored = json.loads(BUNDLE.read_text(encoding="utf-8")) if BUNDLE.exists() else None
    if stored != bundle_from_solver():
        problems.append("starting-program.json is not the solver/ sources - run with --pack")
    if stored is not None and set(stored) != {"solver/candidate.cpp"}:
        problems.append(f"starting-program.json bundles {sorted(stored)}, not the one .cpp")
    for path in strays():
        problems.append(f"solver/{path.name} is not a .cpp and must not be there")

    everything = instances()
    source = (SOLVER / "candidate.cpp").read_text(encoding="utf-8")
    binary = compile_source(source, "candidate")
    print(f"{INSTANCES.name}: {len(everything)} instances; compiled with {' '.join(COMPILE)}")
    print(f"official checker: {checker_binary()} (built from {roadef_dir() / 'checker' / 'src'})")

    first = everything[0]
    outputs = []
    for seed in (42, 42, 1, 7):
        out = workdir() / f"det-{len(outputs)}.json"
        _, code, _ = run_binary(binary, single_instance(first), out, seed)
        outputs.append(out.read_bytes() if code == 0 else b"")
    if outputs[0] != outputs[1]:
        problems.append("two runs with seed 42 wrote different bytes (§14.6)")
    if not outputs[0] == outputs[2] == outputs[3]:
        problems.append("with the search switched off, the answer should not depend on the seed")
    print(f"{first['name']}: a second run with seed 42 wrote the same bytes: {outputs[0] == outputs[1]}; seeds 1 and 7 "
          f"the same bytes as 42 (the search is off): {outputs[0] == outputs[2] == outputs[3]}")

    print(f"\n{'':<4} {'geo_loss':>12} {'plates':>6} {'resid':>5} {'nodes':>5} {'run s':>6} {'IR s':>5} "
          f"{'values':>7} {'checker OF':>12}  {'vs 180 s':>8} {'vs 3600 s':>9} {'vs best':>8}")
    total = {"seed": 0, "best_180s": 0, "best_3600s": 0, "best_known": 0}
    for inst in everything:
        answer, seconds, account = seed_answer(inst)
        if answer != recertify(inst, answer):
            problems.append(f"{inst['name']}: the seed's certificate is not the one problem.txt defines from its tree")
        row = three_way(inst, answer, "check", with_probes=True)
        judged, checker = row["judged"], row["checker"]
        if judged["reasons"] or judged["ir"] is not True or not row["agree"] or not checker["valid"]:
            problems.append(f"{inst['name']}: python {judged['reasons']}, IR {judged['ir']}, clauses "
                            f"{judged.get('ir_clauses')}, probes {judged['probe_disagreements'][:2]}, "
                            f"checker {checker}")
        g = answer["geo_loss"]
        total["seed"] += g
        for key in ("best_180s", "best_3600s", "best_known"):
            total[key] += inst[key]
        print(f"{inst['name']:<4} {g:>12,} {answer['n_plates']:>6} {answer['residual_w']:>5} {len(answer['type']):>5} "
              f"{seconds:>6.2f} {judged['ir_seconds']:>5.2f} {judged['probes']:>7,} {checker['of'] or 0:>12,}  "
              + "  ".join(f"{(g - inst[k]) / inst[k]:>+8.0%}" for k in ("best_180s", "best_3600s", "best_known")))
        if seconds > SANDBOX_SECONDS / 10:
            problems.append(f"{inst['name']}: the seed took {seconds:.1f} s")
    print(f"{'all':<4} {total['seed']:>12,}" + " " * 60 + "  ".join(
        f"{(total['seed'] - total[k]) / total[k]:>+8.1%}" for k in ("best_180s", "best_3600s", "best_known")))
    if PINNED_TOTAL is not None and total["seed"] != PINNED_TOTAL:
        problems.append(f"the seed's total is {total['seed']:,}, not the pinned {PINNED_TOTAL:,}")

    _edits(everything[1], problems)
    if search_seeds:
        _search(search_seeds, problems)
        _random_guides(max(1, search_seeds // 4), problems)

    print("\nthe holes the platform's inner search finds in the seed (evolve.research.tunables.parameter_space_of):")
    for line in parameter_space():
        print(f"    {line}")

    if problems:
        print("\nFAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nOK")
    return 0


# --- timing -------------------------------------------------------------------------

_TIMING_CHILD = r"""
import json, sys, time, statistics
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import verify
from evolve.problem.expression import evaluate
inst = json.loads(open(sys.argv[3], encoding="utf-8").read())
answer = json.loads(open(sys.argv[4], encoding="utf-8").read())
tree, score = verify.validity_tree(), verify.objective_tree()
started = time.perf_counter()
ok = evaluate(tree, instance=inst, solution=answer)
evaluate(score, instance=inst, solution=answer)
cold = time.perf_counter() - started
warm = []
for _ in range(5):
    started = time.perf_counter()
    evaluate(tree, instance=inst, solution=answer)
    evaluate(score, instance=inst, solution=answer)
    warm.append(time.perf_counter() - started)
print(json.dumps({"valid": ok, "cold": cold, "warm": statistics.median(warm), "slowest": max(warm)}))
"""


def timing() -> int:
    """The IR judge (validity and objective, as the platform evaluates them) on the
    seed's answer per instance: cold -- the first evaluation in a fresh process --
    and warm, the median of five more; and the Python reading and the checker."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    child = workdir() / "timing_child.py"
    child.write_text(_TIMING_CHILD, encoding="utf-8")
    print(f"{'':<4} {'nodes':>5} {'IR cold ms':>10} {'IR warm ms':>10} {'python ms':>9} {'checker ms':>10} "
          f"{'seed s':>6}")
    total = {"cold": 0.0, "warm": 0.0, "python": 0.0, "checker": 0.0, "seed": 0.0}
    for inst in instances():
        answer, seconds, _ = seed_answer(inst)
        path = workdir() / f"timing-{inst['name']}.json"
        path.write_text(json.dumps(answer), encoding="utf-8")
        done = subprocess.run([sys.executable, str(child), str(HERE), str(_evolve_source()),
                               str(single_instance(inst)), str(path)], capture_output=True, text=True, check=True)
        measured = json.loads(done.stdout.strip().splitlines()[-1])
        started = time.perf_counter()
        validity_reasons(inst, answer)
        python = time.perf_counter() - started
        checker = run_checker(inst, answer, "timing")["seconds"]
        for key, value in (("cold", measured["cold"]), ("warm", measured["warm"]), ("python", python),
                           ("checker", checker), ("seed", seconds)):
            total[key] += value
        print(f"{inst['name']:<4} {len(answer['type']):>5} {measured['cold'] * 1000:>10.0f} "
              f"{measured['warm'] * 1000:>10.0f} {python * 1000:>9.0f} {checker * 1000:>10.0f} {seconds:>6.2f}")
    print(f"{'all':<4} {'':>5} {total['cold']:>9.2f}s {total['warm']:>9.2f}s {total['python'] * 1000:>8.0f}m "
          f"{total['checker']:>9.2f}s {total['seed']:>5.2f}s")
    return 0


# --- the self-test ------------------------------------------------------------------

#: What a hostile answer may put where a number or a list belongs.
HOSTILE = ("seven", [1, 2], None, True, 1e308, float("nan"), 3.5, -1, 0.5, 10 ** 30)


def _clause_verdicts(instance: dict, solution: Any) -> tuple[list[int], list[int], list[str]]:
    """Each clause alone, both readings: (python refusals, IR refusals, escapes)."""
    sys.path.insert(0, str(_evolve_source()))
    from evolve.problem.expression import ExpressionError, evaluate

    escapes = []
    ir = []
    for number, clause in enumerate(clause_trees(), start=1):
        try:
            held = evaluate(clause, instance=instance, solution=solution)
        except ExpressionError:
            held = False
        except Exception as error:  # noqa: BLE001 - reported, not swallowed
            escapes.append(f"clause {number}: {type(error).__name__}: {error}")
            held = False
        if held is not True:
            ir.append(number)
    try:
        python = refused_by(instance, solution)
    except Exception as error:  # noqa: BLE001
        escapes.append(f"python: {type(error).__name__}: {error}")
        python = []
    return python, ir, escapes


def _mutations(solution: dict, rng: random.Random, count: int) -> list[tuple[str, dict]]:
    """Answers one change away from `solution`: a number moved a little or a lot, two
    entries swapped, a node retyped, a pointer redirected, a claim moved."""
    n = len(solution["type"])
    out = []
    for _ in range(count):
        s = json.loads(json.dumps(solution))
        key = rng.choice(SOLUTION_KEYS)
        if key in CLAIM_KEYS:
            s[key] += rng.choice((-1, 1, -3210, 3210, 19_260_000))
            out.append((f"{key} moved", s))
            continue
        values = s[key]
        if not values:
            continue
        at = rng.randrange(len(values))
        how = rng.choice(("nudge", "jump", "swap", "retype"))
        if how == "nudge":
            values[at] += rng.choice((-1, 1, -20, 20))
        elif how == "jump":
            values[at] = rng.choice((-1, 0, 1, n - 1, n, rng.randrange(-5, n + 5), rng.randrange(0, 6001)))
        elif how == "swap":
            other = rng.randrange(len(values))
            values[at], values[other] = values[other], values[at]
        else:
            values[at] = rng.choice((-3, -2, -1, 0, rng.randrange(0, 50)))
        out.append((f"{key}[{at}] {how}", s))
    return out


def _self_test() -> int:
    """The two readings against each other and against the checker: the worked
    examples, hostile entries and structures, and thousands of one-change answers
    around real ones."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import importlib.util

    spec = importlib.util.spec_from_file_location("roadef2018_spec", HERE / "specification.py")
    specification = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(specification)
    fixture = specification.FIXTURE
    problems: list[str] = []

    # 1. the worked examples, clause by clause and through the checker
    for example in specification.EXAMPLES:
        row = three_way(fixture, example["solution"], "self", with_probes=True)
        if not row["agree"]:
            problems.append(f"worked example {example['name']}: {row['judged']['refused_by']} / "
                            f"{row['judged']['ir_clauses']} / checker {row['checker']['stage']}")
    print(f"the {len(specification.EXAMPLES)} worked examples: both readings clause by clause, every intermediate, "
          f"and the checker on the geometry -- {'all agree' if not problems else 'DISAGREE'}")

    # 2. hostile entries: every key, whole and one entry at a time
    base = specification.V1
    hostile_runs = escapes = 0
    accepted = []
    for key in SOLUTION_KEYS:
        for value in HOSTILE:
            variants = [(f"{key} = {value!r}", dict(base, **{key: value}))]
            if key in LIST_KEYS:
                for at in (0, len(base[key]) - 1):
                    changed = list(base[key])
                    changed[at] = value
                    variants.append((f"{key}[{at}] = {value!r}", dict(base, **{key: changed})))
            for label, solution in variants:
                python, ir, escaped = _clause_verdicts(fixture, solution)
                hostile_runs += 1
                escapes += len(escaped)
                if escaped or python != ir:
                    problems.append(f"hostile {label}: python {python}, IR {ir}, escaped {escaped}")
                elif not ir:
                    accepted.append(label)
    print(f"hostile entries (a string, a list, null, true, 1e308, NaN, 3.5, -1, 0.5, 10^30) in every key, whole and "
          f"at its first and last entry: {hostile_runs} answers, every clause alone False or a clean refusal "
          f"({escapes} escapes), the two readings alike clause by clause; accepted by both, and rightly: "
          f"{', '.join(accepted) or 'none'}")
    expected_accepted = {"type[17] = -1", "parent[0] = -1", "defect_leaf[3] = -1"}
    if set(accepted) != expected_accepted:
        problems.append(f"hostile entries accepted: {accepted}, expected exactly {sorted(expected_accepted)} (the "
                        f"residual typed as a waste, and two entries that were -1 already)")

    structures = [None, [], "answer", {}, {k: base[k] for k in SOLUTION_KEYS if k != "end"},
                  dict(base, type=[]), dict(base, type=[-2]), dict(base, extra=[1, 2, 3])]
    for solution in structures:
        python, ir, escaped = _clause_verdicts(fixture, solution)
        if escaped or python != ir:
            problems.append(f"hostile structure {str(solution)[:60]}: python {python}, IR {ir}, escaped {escaped}")
    print(f"hostile structures (not an object, empty, a key missing, no nodes, one node, an extra key): "
          f"{len(structures)}, the two readings alike clause by clause")

    # 3. one-change answers around the worked answer and around real seed answers
    rng = random.Random(2018)
    compared = checked = disagreements = valid = 0
    lenient: dict[str, int] = {}
    pools = [(fixture, base, 400)]
    for inst in instances()[:15:3]:
        answer, _, _ = seed_answer(inst)
        pools.append((inst, answer, 120))
    for inst, answer, count in pools:
        for label, solution in _mutations(answer, rng, count):
            python, ir, escaped = _clause_verdicts(inst, solution)
            compared += 1
            if escaped or python != ir:
                disagreements += 1
                problems.append(f"{inst['name']} {label}: python {python}, IR {ir}, escaped {escaped}")
                continue
            valid += not python
            if _well_typed(inst, solution) and compared % 4 == 0:
                row = three_way(inst, solution, "mutation", with_probes=True)
                checked += 1
                for kind in row["lenient"]:
                    lenient[kind] = lenient.get(kind, 0) + 1
                if not row["agree"]:
                    disagreements += 1
                    problems.append(f"{inst['name']} {label}: three ways {row['judged']['refused_by']} "
                                    f"checker {row['checker']['stage']} honest {row['honest']} "
                                    f"probes {row['judged']['probe_disagreements'][:2]}")
    print(f"one-change answers around the worked answer and five seed answers: {compared} compared clause by clause "
          f"({valid} of them valid), {checked} of them also with every intermediate and through the checker; "
          f"{disagreements} disagreements; the checker accepted where the rules refuse only through its measured "
          f"leniencies: {lenient or 'none'}")

    if problems:
        print("\nFAILED")
        for problem in problems[:20]:
            print(f"  - {problem}")
        return 1
    print("\nOK")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", action="store_true")
    parser.add_argument("--search", type=int, default=0, metavar="SEEDS")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--timing", action="store_true")
    args = parser.parse_args()
    if args.pack:
        return pack()
    if args.self_test:
        return _self_test()
    if args.timing:
        return timing()
    return check(args.search)


if __name__ == "__main__":
    raise SystemExit(main())
