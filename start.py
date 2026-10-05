"""Open this example over the API, with the specification SUPPLIED.

    python examples/roadef2018-glass-b/start.py
    python examples/roadef2018-glass-b/start.py --api http://127.0.0.1:8100/api/v1

SUPPLIED, not drafted, for the reason its sister examples give: the document
exists, it has been through all ten of §9's gates, and drafting it again would
spend model calls reproducing it. This one carries a cutting tree in pre-order
with parent and subtree-end pointers, every item's node, every defect's leaf and
three claims, each proven locally by one of eleven conditions; a draft is unlikely
to get all of that right first time. The stored version records `source: SUPPLIED`.

EVERY UPLOAD CARRIES A DESCRIPTION: discovery hands `description` straight to
the model as its evidence list, and an undescribed reference document is how the
solomon-200 discovery pass failed four times running. Each is under the 1,000
characters the artifact description field accepts, and `main` refuses to send
one that is not. The three are the fifteen instances, the starting program and
this folder's README, which is the example's reference: the problem as the
subject and the official checker define it, every difference between the two,
the certificate and why it is sound, the calibration and the rivals.

This stops once the definition is ready, as the sister examples do: locking the
problem, the baseline, the evaluation and evolution scopes and the experiment
are decisions to take on the screen, not in a script. It has not been run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SISTER = HERE.parent / "alphaevolve-autocorrelation" / "start.py"

#: ADR 0101/0102 bounds `objective` on POST /projects and `content` on a message
#: at this. `main` refuses rather than letting the statement come back a 422.
CEILING = 25_000
#: The artifact description field's bound.
DESCRIPTION_CEILING = 1_000

_spec = importlib.util.spec_from_file_location("autocorr_start", SISTER)
S = importlib.util.module_from_spec(_spec)
_writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # read another example's folder, never write to it
try:
    _spec.loader.exec_module(S)
finally:
    sys.dont_write_bytecode = _writes


def describe_instance(path: Path) -> str:
    """One paragraph about the instances, in the words the file itself uses."""
    instances = json.loads(path.read_text(encoding="utf-8"))
    items = [len(i["item_w"]) for i in instances]
    defects = [len(i["defect_x"]) for i in instances]
    first = instances[0]
    return (
        f"The {len(instances)} instances of dataset B of the ROADEF/EURO 2018 challenge (Saint-Gobain glass "
        f"cutting), {', '.join(i['name'] for i in instances)}, as the official CSV files give them: items "
        f"{min(items)} to {max(items)} per instance as item_w, item_h (mm; an item may be turned), stacks as lists "
        f"of item ids in the order they must be cut, and every defect of all {first['n_plates_max']} plates as "
        f"defect_plate, defect_x, defect_y, defect_w, defect_h ({min(defects)} to {max(defects)} per instance). "
        f"Global parameters in each: plate_w {first['plate_w']}, plate_h {first['plate_h']}, n_plates_max "
        f"{first['n_plates_max']}, min1cut {first['min1cut']}, max1cut {first['max1cut']}, min2cut "
        f"{first['min2cut']}, min_waste {first['min_waste']}. Labels no rule reads: best_180s, best_3600s (the "
        f"challenge's best results) and best_known (Libralesso and Fontan 2021), mm^2 of glass lost."
    )


DESCRIPTIONS = {
    "starting-program.json": (
        "The starting program, C++17. `solve` builds a Layout: each item, taken only from a stack's head so every "
        "stack is cut in order, placed in the next slot of the current strip, a new strip, a new stripe or the "
        "next plate, at the first position where no item covers a defect and no cut crosses one; the candidate "
        "the guide ranks best is taken. An emit layer turns the Layout into the pre-order tree with parent and "
        "end pointers, item_node, defect_leaf and the three claims exactly as problem.txt defines them, checks "
        "all eleven conditions and writes the answer as it stands. Valid on all 15 instances, total geo_loss "
        "1,321,059,474 mm^2. Holes: beam_width and restarts (the search, off), noise, policy and rotation "
        "(choices) as evolve:param; the guide as evolve:expr guide(waste, area, placed, mean), author body "
        "waste / area."
    ),
    "README.md": (
        "The example's own account. The ROADEF/EURO 2018 glass-cutting problem on dataset B exactly as the "
        "subject (18/05/2018) and the official checker (23/05/2018) define it, with every difference between "
        "the two and the checker's measured leniencies; the certificate an answer carries (the tree in pre-order "
        "with parent and subtree-end pointers, every item's node, every defect's waste leaf) and why local checks "
        "prove the checker's global ones; the three readings (Python, IR, official checker) and their agreement; "
        "the calibration: the seed on all 15 instances against the challenge's best 180 s and 3600 s results "
        "and the best published, every bound and every cheat refused by name; the IR judge's time; what this "
        "is not."
    ),
}


def upload_described(api: str, project: str, path: Path, kind: str, description: str) -> str:
    """The sister's three-step upload, with the description it never sent."""
    if len(description) >= DESCRIPTION_CEILING:
        raise SystemExit(f"the description of {path.name} is {len(description)} characters; "
                         f"the field accepts fewer than {DESCRIPTION_CEILING}")
    body = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    intent = S.call(
        "POST",
        f"{api}/projects/{project}/artifacts/upload-intents",
        {
            "filename": path.name,
            "kind": kind,
            "size_bytes": len(body),
            "content_type": "text/markdown" if path.suffix == ".md" else "application/json",
            "description": description,
        },
        {"Idempotency-Key": f"upload-{kind}-{path.name}-{len(body)}"},
    )
    artifact = intent["artifact_id"]
    url = intent.get("upload_url") or f"{api}/artifacts/{artifact}/content"
    if url.startswith("/"):
        url = api.rsplit("/api/", 1)[0] + url
    put = urllib.request.Request(url, data=body, method="PUT")
    put.add_header("Content-Type", "application/octet-stream")
    put.add_header("Authorization", f"Bearer {S.ACTOR}")
    with urllib.request.urlopen(put, timeout=300):
        pass
    S.call(
        "POST",
        f"{api}/projects/{project}/artifacts/{artifact}/complete",
        {"sha256": digest, "size_bytes": len(body)},
        {"Idempotency-Key": f"complete-{artifact}"},
    )
    return artifact


def specification() -> dict:
    """`specification.json`, rebuilt and compared rather than trusted."""
    document = HERE / "specification.json"
    if not document.is_file():
        raise SystemExit(
            f"{document.name} is missing. It is written, and checked against the gates, by:\n"
            "    python specification.py --out specification.json"
        )
    held = json.loads(document.read_text(encoding="utf-8"))
    sys.path.insert(0, str(HERE))
    from specification import document as rebuild

    if json.loads(json.dumps(rebuild())) != held:
        raise SystemExit(
            f"{document.name} no longer matches the sources it was built from. Rebuild it:\n"
            "    python specification.py --out specification.json"
        )
    return held


def seed_program() -> Path:
    """`starting-program.json`, rebuilt from the source that is actually edited.
    Only `solver/candidate.cpp` is bundled; `verify.py --pack` writes the same file."""
    source = (HERE / "solver" / "candidate.cpp").read_text(encoding="utf-8")
    wrapped = HERE / "starting-program.json"
    held = None
    if wrapped.is_file():
        held = json.loads(wrapped.read_text(encoding="utf-8"))
    if held != {"solver/candidate.cpp": source}:
        wrapped.write_text(
            json.dumps({"solver/candidate.cpp": source}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"  rebuilt {wrapped.name}: it did not match candidate.cpp")
    return wrapped


def main() -> int:
    api = sys.argv[sys.argv.index("--api") + 1] if "--api" in sys.argv else S.API
    instances = HERE / "instances.json"
    if not instances.is_file():
        raise SystemExit("instances.json is missing. Write it with:\n    python make_instance.py")
    statement = (HERE / "problem.txt").read_text(encoding="utf-8")
    if len(statement) > CEILING:
        raise SystemExit(
            f"problem.txt is {len(statement):,} characters and the API bounds both\n"
            f"`objective` and a message's `content` at {CEILING:,} (ADR 0101), so this\n"
            "would come back a 422 twice over."
        )
    descriptions = {"instances.json": describe_instance(instances), **DESCRIPTIONS}
    for what, text in descriptions.items():
        if len(text) >= DESCRIPTION_CEILING:
            raise SystemExit(f"the description of {what} is {len(text)} characters")
    document = specification()

    print("opening the project")
    project = S.call(
        "POST",
        f"{api}/projects",
        {"mode": "CREATE", "objective": statement},
        {"Idempotency-Key": f"roadef2018-glass-b-{int(time.time())}"},
    )["id"]
    print(f"  {project}")

    print("uploading the evidence, described")
    upload_described(api, project, instances, "DATASET", descriptions["instances.json"])
    upload_described(api, project, seed_program(), "CANDIDATE_SOURCE", DESCRIPTIONS["starting-program.json"])
    upload_described(api, project, HERE / "README.md", "DOCUMENT", DESCRIPTIONS["README.md"])

    print("sending the statement")
    S.call(
        "POST",
        f"{api}/projects/{project}/messages",
        {"content": statement},
        {"Idempotency-Key": f"statement-{project}"},
    )
    S.settle(api, project, {"CLARIFICATION_REQUIRED", "PROBLEM_DEFINITION_READY"})

    print("compiling with the specification supplied")
    S.call(
        "POST",
        f"{api}/projects/{project}/problem/compile",
        {"specification": document},
        {"Idempotency-Key": f"supplied-{project}", "If-Match": S.etag(api, project)},
    )
    S.settle(api, project, {"PROBLEM_DEFINITION_READY"})

    view = S.call("GET", f"{api}/projects/{project}")
    print(f"\n{project} is at {view.get('state')}")
    print(f"  problem version {view['active_versions'].get('problem_version_id')}")
    print("  open it on the screen, read the definition, and lock it there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
