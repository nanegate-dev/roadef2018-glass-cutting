# Cutting Saint-Gobain's glass: the ROADEF/EURO 2018 challenge, dataset B, under its own checker

Saint-Gobain Glass France set the ROADEF/EURO 2018 challenge: cut a customer's
batch of glass items from 6000 × 3210 mm "jumbo" plates, **taken in their given
order**, each plate carrying its own map of small defects from the float line.
Every cut is a guillotine cut, at most four stages deep; no item may cover a
defect and no cut may cross one; the items come in stacks that must be cut in
their order. Smaller is better on the glass lost,

    geo_loss = plates used × 6000 × 3210 − 3210 × the residual's width − the items' area

in whole square millimetres, where the residual is the offcut right of the last
plate's last vertical cut, which goes back on the shelf. This example is **dataset
B, all fifteen instances, exactly as the subject and the official checker define
it**, and the platform's aim on it is the best result it can produce.

> **The result, stage 5 (October 2026).**
> - **Champion.** The champion of Nanegate's fifth run on this example loses
>   28,836,031 mm² an instance on average (15 seeds). That is 83 points, 4th place
>   among the 2018 final's 19 teams on dataset B.
> - **Best single.** The lineage's best single runs lose 25,721,304 (99 points,
>   4th). All fifteen answers were checked by the official checker.
> - **Gap.** The best known results (Libralesso & Fontan 2021) are still 44.7%
>   lower.
>
> The answers, the programs, the run and every check are in
> [`results/`](results/README.md).

> **The challenge's files are not redistributed here.** `make_instance.py`
> builds `instances.json` from the challenge's own CSV files, unpacked into
> `data/`. The result is byte for byte the dataset the run was locked on (sha256
> `826fc809…`).

> **The checker is the authority.** The subject (18/05/2018) and the checker's
> source (`main.cpp`, version 23/05/2018) were both read in full. Where they
> differ, the checker's rule is the rule here, and every difference is listed
> below. Where the checker accepts things it never checks, measured below, this
> example keeps the subject's definition and says so.

> **Three readings, one verdict.** Every answer here is judged by the platform's
> locked IR, by an independent plain-Python reading, and by **the official
> checker itself**, built from its source with the house flags and fed the answer
> as its CSV. They agree on every answer this folder builds.

| | |
|---|---|
| the instances | B1–B15 from the challenge's CSV files, unchanged: 68 to 656 items, 2 to 241 stacks, 107 to 441 defects over 100 plates; `instances.json`, 131,109 bytes |
| the rivals | the challenge's best 180 s and 3600 s results (re-derived from `final_results.xlsx`) and the best published (Libralesso & Fontan 2021); all 45 numbers checked to be objectives an answer can have |
| the starting program | an honest greedy in the stripe / strip / slot shape: **valid on all 15**, total **1,321,059,474 mm²**, +325% over the 180 s column; every seed writes the same bytes |
| its dormant search | a beam over the same constructive and seeded restarts, switched off; with every knob at its maximum it totals 676,128,744 (−48.8%, still +117.7% over the 180 s column), its slowest instance 25.5 s |
| every bound, both sides | a stripe of 100 and 3500, a strip of 100, a waste of 20: accepted by all three readings; 99, 3501, 99, 19: refused by all three |
| every cheat | an item on a defect, a cut through one, a forged leaf, a missing or duplicated item, a stack out of order, a wrong size, a third 4-cut child, a fifth stage, a gap, an early residual, plates out of order, a forged claim: **each refused by exactly one condition in both readings**, and by the checker whenever the geometry is wrong |
| judging | 6.0 s cold, 4.9 s warm for the seed's fifteen answers through the platform's IR (13,544 nodes); 0.35 s in plain Python; 0.54 s through the checker |
| §9's ten gates | all PASSED |
| the statement | 13,130 characters of the 25,000 the API accepts |

## The problem, as the subject and the checker define it

**The plates.** 100 plates of 6000 × 3210 mm, used in order 0, 1, 2, …: a plate
is started only after the one before it. Each carries its defects, small
rectangles (1 to 25 mm a side on dataset B), given per plate.

**The items and the stacks.** Each item is a rectangle that may be turned 90°. The
batch is partitioned into stacks; within a stack the items must be cut in the
given order. Dataset B has from 2 stacks (B5: 187 and 20 items) to one item per
stack (B1, B7: no order at all).

**The cutting tree.** A plate is cut by vertical 1-cuts into stripes, a stripe by
horizontal 2-cuts into strips, a strip by vertical 3-cuts into pieces, and a piece
by at most one horizontal 4-cut, "trimming". Every part not cut further is an
item, a waste, or the residual. The items are cut in the order of a depth-first
walk of the tree, children left to right or bottom to top. Sizes: a stripe 100 to
3500 wide, a strip at least 100 high, a waste at least 20 × 20, the residual at
least 20 wide.

**Defects.** An item may not overlap a defect; a cut may not cross one. The
checker's test, exactly: for every used plate, count over its leaves (items,
wastes, the residual) the defects each overlaps — overlap is strict, so a cut
along a defect's edge does not touch it; that count must equal the plate's number
of defects, every overlapping defect must lie wholly inside the leaf, and no item
may overlap one. Since the leaves tile the plate, this is: **every defect lies
wholly inside one leaf, and that leaf is not an item.**

**The objective.** The checker prints `OF = plates × W × H − H × residual − Σ
item areas`, the subject's `H W m − H r_m − Σ w_i h_i`. A waste left by the last
1-cut of the last plate is the residual, as the checker counts it.

## Where the checker and the subject differ: the checker's rule is the rule

1. **Size bounds bind branches only.** The subject bounds "the width between two
   consecutive 1-cuts" to 100–3500 except for wastes (minimum) and the residual
   (maximum), and strips to at least 100 except wastes. The checker checks 100–3500
   only for a 1-cut node that is a branch and 100 only for a 2-cut branch. So a
   1-cut **waste may be wider than 3500** (measured: a 5000 mm waste stripe is
   accepted by all three readings), and a 1-cut or 2-cut **item** has no bound.
   The latter is moot on dataset B: every item side is 123 to 2952 mm, so no item
   can fill a 3210 mm stripe and none is under 100. A plate may therefore be cut
   by a single 6000 mm waste stripe, where the subject would need two.
2. **"A cutting pattern must contain at least one 1-cut"** (subject). The checker
   accepts a plate with no nodes at all, as an all-waste plate counted in full.
   Here a plate needs one 1-cut, which may be that single 6000 mm waste: the same
   objective on any plate but the last, where that waste is the residual.
3. **The residual.** The checker takes a −3 node only as a 1-cut node on the last
   plate and its **last line**, and turns a −1 node in that place into the residual.
   It checks its width against minWaste (20). This is the subject's "waste at
   right of the last 1-cut", made precise.
4. **At most one 4-cut in a 3-cut's piece.** The checker refuses a third child of
   any node cut 3 or deeper, and a fifth stage anywhere. The subject's figure 4 is
   the same rule.
5. **The stack order is the batch file's row order**, not its SEQUENCE column; the
   defects are read with `atoi` ("428.0" is 428) and only up to the first defect of
   an unused plate. On dataset B all three are harmless and asserted by
   `make_instance.py --self-test`: rows sorted by stack then sequence, every
   coordinate whole, defects sorted by plate.
6. **`totalGeoLoss` in the checker's statistics file is not the objective.** It is
   a percentage: the mean over the plates of each plate's waste share, with integer
   divisions (the worked answer's is "24%"). The mm² objective is `OF`, printed in
   the log and, with the `0` flag, on stdout. `run_checker` reads `validSolution`
   from the statistics file and `OF` from both the log and stdout, and they agree.

## Where the checker accepts more than the subject, and what this example does

Measured by `tricks.py` on B2's seed answer and met again by `verify.py
--self-test` (the last row once, on the worked answer); each is refused by both
readings here and **accepted by the checker**:

| what | the checker | here |
|---|---|---|
| a plate line at x = 5 | never reads a plate line's X | refused by 4: a plate is the whole plate |
| a plate line typed −1 | never reads a plate line's TYPE | refused by 2 and 3 |
| a whole plate's tree, plate line included, 7 mm up | compares the 1-cut nodes' y with the plate line's Y and no node with the plate's height: the tree's top 7 mm lie off the plate | refused by 4 |
| a strip closed by a 5 mm branch with no children | takes a childless branch for a leaf with **no size rule**: a 5 mm offcut passes where the subject's minimum waste is 20 × 20 | refused by 2: a branch has children |
| a plate line with no children after the last plate | accepted, the plate counted in full | refused by 2 and 10 |
| the nodes breadth-first, parents before children | reads any parents-first order (the worked answer written breadth-first is valid, at 535,000 with its residual written as a waste: a residual is only the residual on its plate's last line) | the answer is always the pre-order, the checker's own sample's order |

None of these is a rule the checker states; they are fields and structures it
does not look at. Two of them could lower an objective — a 5 mm offcut passing as
no waste at all, a tree moved partly off the glass to clear a defect — and a
result that used either would not be a result under the subject; the others
change nothing an answer can achieve. The direction that matters holds on every
answer built here: **whatever both readings accept, the checker accepts, at the
same objective.**

## What an answer is: the tree, and a certificate

The IR has no recursion and no fold, so what the checker finds by walking the tree
is carried in the answer and proven one node at a time:

| carried | proven by |
|---|---|
| `plate, cut, type, x, y, w, h` per node, in pre-order | the rules below |
| `parent`, `end` per node: its parent, one past its subtree | 2: every node checks its place locally |
| `item_node` per item: the node that cuts it | 8: it has that item's type, and exactly n nodes are items |
| `defect_leaf` per defect: the waste leaf holding it, or −1 on an unused plate | 10: it is a −1 or −3 leaf on the defect's plate and contains it |
| `n_plates, residual_w, geo_loss` | 11: each recomputed |

**Why local checks prove the global ones.** Condition 2 asks of every node: a plate
line's subtree runs to the next plate line; any other node lies inside its parent's
subtree and is followed by its next sibling (whose parent it names) or by its
parent's end; a branch's first child follows it; a leaf's subtree is itself. By
induction on subtree size, `[i, end[i])` is then exactly `i`'s subtree and the list
is a depth-first pre-order: every node is reached once, from its own parent. So:

- **the checker's cut order is the order of the item nodes**, since the checker
  walks the same tree depth-first with siblings in their tiling order; a stack's
  order is then `item_node[a] < item_node[b]` for each two items next to each other
  in it (condition 9), and each item cut exactly once is condition 8;
- **the leaves of each plate tile it**: condition 4 makes every branch's children
  tile it exactly, left to right or bottom to top, from the plate down. A defect
  of positive area inside one waste leaf of a tiling overlaps no other leaf, so it
  is inside no item and crossed by no cut; conversely, if the checker's count
  holds with every overlap whole, each defect overlaps exactly one leaf, which
  contains it. **Condition 10 is the checker's defect test.**

A defect on an unused plate needs no leaf; a used plate is one numbered below
`plate[last] + 1`, recomputed, never the claim.

## The rules, in brief

`problem.txt` states eleven conditions, checked in order; each is one clause of
the IR's top-level `and`, and each is read alone by the platform to explain a
refusal. (1) shapes; (2) the tree; (3) types and levels; (4) tiling; (5) at most
one 4-cut per piece; (6) sizes; (7) identity, turned or not; (8) production;
(9) sequence; (10) defects; (11) the claims. The objective reads `geo_loss`,
which 11 proves.

**Units.** Every length whole millimetres, every area whole mm². **There is no
division** anywhere in the rules; the largest product is plates × W × H, at most
100 × 6000 × 3210 = 1.93 × 10⁹, under 2³¹ (the checker keeps OF in an unsigned
32-bit integer, which this also fits). Every read of an answer's number goes
through `round`, so a string, null, a list or NaN is a refusal, never a number.

**The guards.** Conditions 4, 5, 7 and 10 follow a pointer only when it is in
range (`where` a node's parent and end are sane, `where` a type names an item),
so each clause read alone ends in False or a clean refusal on any answer, and a
broken pointer is refused by condition 2 alone. `verify.py --self-test` puts a
string, a list, null, true, 1e308, NaN, 3.5, −1, 0.5 and 10³⁰ into every key,
whole and at its first and last entry: 360 answers, no escape, the two readings
alike clause by clause.

## The three readings, and how far they agree

| what | answers | agreement |
|---|---|---|
| the worked examples (`specification.py`) | 24 | each invalid one breaks exactly its one condition in both readings, clause by clause; the checker accepts exactly the three valid ones, at 210,000, 210,000 and 260,000 |
| the starting program on all 15 instances (`verify.py`) | 15 | valid three ways; the checker's OF equals geo_loss; 117,495 per-node, per-item, per-defect and per-stack intermediates bit-equal between the readings |
| one-change answers around the worked answer and five seed answers (`--self-test`) | 1,000 | clause by clause, 0 disagreements; 250 of them with every intermediate and through the checker, which accepts exactly the valid ones, and beyond them only through the leniencies above |
| hostile entries and structures (`--self-test`) | 368 | clause by clause, no escape |
| the bounds, cheats and leniencies (`tricks.py`) | 29 | as tabled below |
| the search sweep and random guides (`verify.py --search 20`) | 660, and 45 re-runs | the three readings alike on every one: the 360 searched answers valid, OF = geo_loss; the guides' 112 refusals refused by all three |

## The calibration, measured

`python tricks.py` prints every table here. Every row is judged by all three
readings.

**The starting program against the rivals** (mm² of glass lost; the gap is the
starting program's excess over the rival):

| | geo_loss | plates | residual | 180 s best | gap | 3600 s best | gap | best known | gap |
|---|---|---|---|---|---|---|---|---|---|
| B1 | 28,758,618 | 6 | 3019 | 3,232,698 | +790% | 2,661,318 | +981% | 2,661,318 | +981% |
| B2 | 72,179,585 | 21 | 5273 | 15,635,435 | +362% | 13,674,125 | +428% | 11,931,095 | +505% |
| B3 | 88,740,473 | 23 | 1324 | 20,540,813 | +332% | 18,191,093 | +388% | 15,786,803 | +462% |
| B4 | 37,669,435 | 10 | 2095 | 8,269,045 | +356% | 8,269,045 | +356% | 7,315,675 | +415% |
| B5 | 223,410,815 | 29 | 4803 | 72,155,615 | +210% | 72,155,615 | +210% | 72,155,615 | +210% |
| B6 | 56,109,577 | 13 | 435 | 12,116,527 | +363% | 11,195,257 | +401% | 10,800,427 | +420% |
| B7 | 39,499,239 | 12 | 1207 | 9,601,299 | +311% | 8,355,819 | +373% | 6,628,839 | +496% |
| B8 | 130,299,019 | 25 | 3677 | 17,865,559 | +629% | 16,067,959 | +711% | 14,398,759 | +805% |
| B9 | 109,110,817 | 21 | 474 | 18,502,147 | +490% | 17,484,577 | +524% | 16,495,897 | +561% |
| B10 | 103,292,933 | 24 | 4063 | 26,012,183 | +297% | 21,951,533 | +371% | 21,951,533 | +371% |
| B11 | 85,304,570 | 22 | 736 | 25,251,890 | +238% | 22,584,380 | +278% | 20,626,280 | +314% |
| B12 | 61,604,737 | 17 | 1850 | 15,868,657 | +288% | 13,958,707 | +341% | 12,514,207 | +392% |
| B13 | 122,392,425 | 32 | 3070 | 28,349,055 | +332% | 24,471,375 | +400% | 22,657,725 | +440% |
| B14 | 42,162,310 | 12 | 3998 | 9,346,480 | +351% | 8,656,330 | +387% | 8,023,960 | +425% |
| B15 | 120,524,921 | 29 | 1700 | 27,794,441 | +334% | 24,517,031 | +392% | 22,619,921 | +433% |
| **all** | **1,321,059,474** | 296 | | 310,541,844 | +325.4% | 284,194,164 | +364.8% | 266,568,054 | +395.6% |

The checker's OF equals geo_loss on all fifteen. In plates, the starting program
uses 1 to 8 more than the 180 s column on each instance: 296 against 246 (the
3600 s column also 246, the best known 244).

The rivals: the challenge's final phase, best over all teams, 180 s and 3600 s runs
on the organisers' machines; and Libralesso & Fontan, "An anytime tree search
algorithm for the 2018 ROADEF/EURO challenge glass cutting problem", EJOR 291(3)
2021, Table 4 (as transcribed; the 180 s and 3600 s columns are re-derived from
`final_results.xlsx`). The challenge's winning team was J28, Libralesso & Fontan
(`sheet4`: first in the ranking). B5's three columns are equal: 21 plates,
residual 3923, for its two stacks of 187 and 20 items.
**Each of the 45 numbers decomposes** as m × 6000 × 3210 − 3210 × r − the items'
area with whole m and 0 ≤ r < 6000 (`make_instance.py --self-test`), which a
mistyped digit would not.

**The bounds bind, both sides** (carved from B2's residual, the certificate derived
again):

| answer | both readings | the checker |
|---|---|---|
| a stripe 100 wide / 99 wide | valid / refused by 6 | valid / Nodes Dimensions |
| a stripe 3500 wide / 3501 wide | valid / refused by 6 | valid / Nodes Dimensions |
| a strip (a branch) 100 high / 99 high | valid / refused by 6 | valid / Nodes Dimensions |
| a waste 20 wide / 19 wide | valid / refused by 6 | valid / Nodes Dimensions |
| a waste stripe 5000 wide | valid | valid |

**Cheats, every one refused by name.** Each is the starting program's answer on B2
(B1 for the plate order, which B2's stacks would also break) with one thing changed
and its certificate derived again, or one number forged:

| cheat | both readings | the checker |
|---|---|---|
| **an item over a defect**: plate 0, an item and the waste beside it exchanged under a 2-cut; defect 0 is now inside the item, and `defect_leaf` names it | **10**, exactly | Defects Superposing |
| **a defect left inside an item, its leaf forged**: the same tree, `defect_leaf[0]` naming a waste on the plate that does not contain it | **10**, exactly | Defects Superposing |
| **a cut through a defect**: plate 13, a waste split at x 1495, through defect 15 (x 1494 to 1496) | **10**, exactly | Defects Superposing |
| **a missing item**: item 0, the first of its stack, typed −1 in place | **8**, exactly | Items production |
| **a duplicated item**: item 0 cut again in a 628 mm stripe carved from the residual | **8**, exactly | Items production |
| **a stack out of order**: plate 0, two 2-cut siblings exchanged | **9**, exactly | Sequence |
| **a wrong size**: item 150 cut 415 × 1579, 1 mm too high, the trim above it 1 mm lower | **7**, exactly | Identity |
| **a third child of a 3-cut piece**: the trim above item 150 split at y 2620 | **5**, exactly | Solution Tree Structure (and Nodes Dimensions) |
| **a fifth stage**: a 4-cut waste made a branch with one 5-cut waste | **3**, exactly | Solution Tree Structure |
| **children not tiling their parent**: a strip's last waste 1 mm narrower | **4**, exactly | Nodes Dimensions |
| **a residual not on the last plate**: plate 0's last 1-cut waste typed −3 | **3**, exactly | Solution Tree Structure |
| **plates out of order** (B1): the last two plates listed plate 5 first, each tree unchanged | **2**, exactly | logs "Plate utilization Sequence Constraint violated", then crashes (access violation) without statistics |
| **a forged objective**: geo_loss 72,179,585 claimed as 72,179,584 | **11**, exactly | valid, OF 72,179,585 |
| **a forged plate count**: n_plates 21 claimed as 20 | **11**, exactly | valid, OF 72,179,585 |
| **a forged residual**: residual_w 5,273 claimed as 5,274 | **11**, exactly | valid, OF 72,179,585 |

A forged claim leaves the geometry valid: the checker has no claim to read,
accepts the tree, and prints the true objective, which is what refuses the claim.

## What the starting program does

`solver/candidate.cpp` has one editable function that matters, `solve`, and one
decision function, `guide`. `solve` returns a Layout: every item in cutting order,
with its plate, stripe, strip and slot. One **emit layer** (marked DO NOT EDIT)
builds the tree from it — gaps become wastes, the region right of the last stripe
the residual — derives parents, ends, `item_node`, `defect_leaf` and the three
claims exactly as `problem.txt` defines them, judges all eleven conditions with
the rules' arithmetic, and writes the answer **as it stands**. It never moves an
item. `verify.py` pins this by splicing model-style mistakes in (on B2):

| mistake spliced into `solve` | both readings | the checker | stderr |
|---|---|---|---|
| the first item's slot 1 mm right, a 1 mm gap in front of it | 4 (and 6) | Nodes Dimensions | "breaks condition 4, 6, emitted as it stands" |
| the first item left out | 8, exactly | Items production | "breaks condition 8 …" |
| the second item written with the first's number | 8 (and 9) | Items production | "breaks condition 8, 9 …" |
| every item written turned, its slot unchanged | 4 (and 6, 10) | refuses the file while reading it | "breaks condition 4, 6, 10 …" |
| the whole layout moved to the next plate | 10, exactly | Defects Superposing | "breaks condition 10 …" |

A guide that ranks wasteful moves first can use every plate before the last item
(a sampled `placed / area` does). The constructive then hands on the layout so far,
the emit layer writes it, and the judge refuses it by 8: it never crashes.

**The constructive.** At every step each stack's next item, in each allowed
orientation, is tried (A) in the next slot of the current strip, (B) in a new strip
above it, (C) in a new stripe, (D) on the next plate, each at the first position
where no item covers a defect and no cut crosses one, behind a waste of at least
20 when a defect is in the way. Items are taken only from stack heads and placed in
cutting order, so **every stack is cut in its order by construction**. Every
candidate is ranked by the guide of the layout it would make, and the best is
taken. A new stripe is as wide as its first item and a new strip as high as its
first item; a slot holds one item with a trim above it. With the shipped knobs every
seed writes the same bytes: total **1,321,059,474**.

**The expression hole is the guide**, the decision Libralesso and Fontan found
mattered most: how a partial layout is ranked.

```cpp
// evolve:expr guide real (real waste, real area, real placed, real mean) ops + - * / min max depth 4 nodes 24
static double guide(double waste, double area, double placed, double mean) { return waste / area; }
```

`waste` is the glass already lost behind the front (every plate before the current
one, every stripe left of the current one, every strip below the current one and
the current strip up to its next slot, less the items in it), `area` that area,
`placed` the items' area, `mean` their mean. The author's body is L&F's waste
percentage; with the greedy it beats plain waste by a wide margin (measured on all
15: `waste` totals 2,133,719,124, `waste / area` 1,321,059,474, `waste / area /
mean` 1,381,410,684). The same guide ranks the beam's layouts when the search is
on, which is where L&F used it. `parameter_space_of` finds six holes:

| hole | kind | range | author's value |
|---|---|---|---|
| beam_width | int | 1 to 256 | **1**: the plain constructive |
| restarts | int | 0 to 200 | **0**: no restarts |
| noise | real | 0 to 0.5 | 0.1: the restarts' perturbation of the guide |
| policy | choice | 0, 1, 2 | 0: rank every candidate; 1: fill the strip first; 2: fill the stripe first |
| rotation | choice | 0, 1, 2 | 0: both orientations; 1: long side vertical; 2: long side horizontal |
| guide | expression over waste, area, placed, mean; + − × / min max; depth 4, 24 nodes | | `waste / area` |

**The work budget.** A restart is begun only if one more run the size of the first
still fits under 30,000,000 candidate positions tried, counted, never timed, so the
same seed makes the same runs. The first run is never cut: at its widest, a beam of
256 on B7, it tries 59 million positions in 24 s. With every knob at its maximum
(a beam of 256, 200 restarts) the slowest instance, B7, takes 24 to 26 s run alone;
a first budget of 150 million let B11 take 82 s, and was cut to a fifth.

**Robustness, measured** (`verify.py --search 20`; every variant written by
`tunables.substitute`; every answer judged by all three readings; the first two
variants six runs at a time, so their times are pessimistic, the third one at a
time):

| variant | runs | crashed / invalid / readings differ | total over the 15 instances | slowest |
|---|---|---|---|---|
| beam_width 8, restarts 10 | seeds 1–20 × 15 = 300 | 0 / 0 / 0 | 855,927,264 to 861,313,644 (−35%; the seeds within 0.6%) | 11.8 s |
| beam_width 64 | seeds 1–3 × 15 = 45 | 0 / 0 / 0 | 760,317,414 on every seed (−42%) | 7.8 s |
| every knob at its maximum: beam 256, 200 restarts | seed 1 × 15 | 0 / 0 / 0 | 676,128,744 (−49%) | 25.5 s |
| 5 guides from `hole.sample`, search off and on (beam 8) | 150 | 0 crashed; 122 valid, 28 refused as they stand, by 8 | best 1,006,916,034, from `waste`, search on | 1.5 s |
| 5 one-step mutations of the author's guide (`hole.step`), off and on | 150 | 0 crashed; 66 valid, 84 refused as they stand, by 8 | best 1,826,409,774 | 1.4 s |

A second run with the same seed writes the same bytes on every instance, for each
search variant. The refusals are guides that rank wasteful moves first (`placed / area`
is one): they run out of plates, and their answers are written and refused. The
first sweep, before that was handled, is how it was found: 112 runs exited without
an answer.

## Judging, and the run

The platform judges a candidate on instances × seeds answers, each through the
validity and objective trees. Measured by `verify.py --timing` on the starting
program's answers, the IR's first evaluation in a fresh process (cold) and the
median of five more (warm), with the Python reading, the checker and the seed:

| | nodes | IR cold | IR warm | Python | checker | the seed's run |
|---|---|---|---|---|---|---|
| B1 | 209 | 154 ms | 74 ms | 5 ms | 34 ms | 0.19 s |
| B2 | 1,104 | 460 ms | 390 ms | 26 ms | 36 ms | 0.02 s |
| B3 | 1,005 | 448 ms | 355 ms | 26 ms | 30 ms | 0.02 s |
| B4 | 758 | 335 ms | 271 ms | 19 ms | 36 ms | 0.03 s |
| B5 | 633 | 302 ms | 227 ms | 15 ms | 33 ms | 0.02 s |
| B6 | 599 | 295 ms | 230 ms | 14 ms | 37 ms | 0.02 s |
| B7 | 659 | 354 ms | 260 ms | 16 ms | 36 ms | 0.13 s |
| B8 | 1,021 | 431 ms | 355 ms | 25 ms | 33 ms | 0.03 s |
| B9 | 757 | 351 ms | 286 ms | 19 ms | 38 ms | 0.02 s |
| B10 | 689 | 328 ms | 247 ms | 17 ms | 35 ms | 0.03 s |
| B11 | 887 | 387 ms | 328 ms | 22 ms | 40 ms | 0.04 s |
| B12 | 1,206 | 522 ms | 449 ms | 38 ms | 39 ms | 0.04 s |
| B13 | 1,956 | 782 ms | 741 ms | 57 ms | 38 ms | 0.04 s |
| B14 | 766 | 352 ms | 279 ms | 19 ms | 40 ms | 0.03 s |
| B15 | 1,295 | 523 ms | 445 ms | 35 ms | 37 ms | 0.03 s |
| **all 15** | 13,544 | **6.02 s** | **4.94 s** | 0.35 s | 0.54 s | 0.69 s |

About 0.4 ms of IR a node (0.36 warm, 0.44 cold), linear in the answer: a better answer has fewer
plates, so fewer nodes, and judges faster. The judge is not the bottleneck.

**The recommendation: all fifteen instances, one seed each while evolving, three
at validation.**

- **Judging is cheap**: 15 answers are about 5 s of IR a candidate (45 at
  validation, about 15 s), and less as answers improve and lose plates.
- **The candidate's own runtime is what grows**: the seed takes 0.7 s for all
  fifteen; the dormant search at its maximum up to 25.5 s an instance, held there
  by the work budget, against a 120 s cap. A searching candidate costs minutes of
  CPU per evaluation, not the judge.
- **One seed suffices while evolving**: the starting program, and any candidate
  that leaves `restarts` at 0, writes the same bytes on every seed; with restarts on
  (beam 8, 10 restarts) the totals spread 0.6% over 20 seeds. Three seeds at
  validation measure that spread for the champion.
- **Do not subset.** Each instance is its own claim, and the platform's mean over
  the fifteen is the total glass lost on dataset B over 15, the sum the three rival
  columns add up to (310,541,844; 284,194,164; 266,568,054). B5 weighs most in that
  sum (223 M of the seed's 1,321 M); the per-instance scores are recorded, and a
  record is a per-instance claim.

## How much headroom there is, honestly

The starting program is far from the rivals: its waste is 3 to 9 times theirs,
from 1 to 8 plates more per instance. The largest share is structural: 44 to 81%
of its waste per instance is the top of stripes left empty when no stack head fits a new
strip, because a stripe is as wide as its first item. The dormant search at its
maximum recovers 64% of the excess over the 180 s column (a beam of 64 alone,
56%); the rest needs other structure — stripes sized
for what will follow, two items stacked in a piece by its 4-cut, strips mixing
heights under trims, plates planned against their defects.

No result from this folder is a record, and none will be claimed as one unless it
is below a rival **on the same rules**, verified by the official checker.

## What this is not

- **Not the challenge's conditions.** A candidate here runs at most 120 s per
  instance on this machine (the seed takes at most 0.2 s); the rivals ran 180 s and
  3600 s on the organisers' hardware, and the published best came from longer
  experiments. A comparison with the columns is a comparison of results, not of
  budgets.
- **Not the other datasets.** Dataset A and the hidden dataset X are not here.
- **Not a different problem.** The rules are the checker's; the only format rules
  added are the certificate's (pre-order, pointers, claims), and the checker's
  leniencies above are refused.
- **The defects of all 100 plates are carried**, so no answer is bounded by the
  instance to fewer plates than the challenge allows.

## Verifying it

```bash
python make_instance.py               # writes instances.json from the official CSVs (131,109 bytes)
python make_instance.py --check       # rebuilds it and compares byte for byte
python make_instance.py --self-test   # the data as the checker reads it, the 45 rivals, the round trip
python specification.py --out specification.json   # §9's ten gates, all PASSED; the checker on the 24 examples
python verify.py --pack               # starting-program.json from solver/
python verify.py                      # the seed on all 15, three ways; the emit layer's edits; the holes
python verify.py --search 20          # the search switched on, 20 seeds x 15 instances; random guides
python verify.py --self-test          # both readings against each other and the checker (about 6 minutes)
python verify.py --timing             # the IR judge per instance, cold and warm
python tricks.py                      # every table above (about 30 s)
```

The official files are read from `$ROADEF2018_DIR` (default: the folder they were
unpacked into for this example): `dataset_B/` with the fifteen batch and defect
CSVs, and `checker/` with the checker's source and `instances_checker/
global_param.csv`. The checker is built from its own source, never from the
binary in its archive, with the same flags as every C++ file here: `g++ -std=c++17
-O2 -DNDEBUG -D_GLIBCXX_ASSERTIONS -static -Wl,--no-insert-timestamp` (a bare `g++
-O2` binary crashes on this machine). The bundle is `solver/candidate.cpp` and
nothing else.

The rules live in two independent readings. The Python one is `validity_reasons`,
loops over whole numbers. The IR one is `validity_tree` and `objective_tree`, a
formula per quantity (`define`/`call`), through `evolve.problem.expression.evaluate`.
`judge_both` compares the verdict, each clause alone, the objective and every
intermediate; `three_way` adds the checker, which reads no certificate: it must
accept exactly the answers whose honestly re-derived certificate is valid, at the
same objective, and beyond them only through a named leniency.

`start.py` uploads `instances.json`, `starting-program.json` and this README, each
with a description under 1,000 characters (716, 821 and 718), and supplies the
specification. It has not been run.

## Files

```
make_instance.py        the official CSVs to instances.json, --only, --check, --self-test; the worked instance
instances.json          the fifteen instances (131,109 bytes)
problem.txt             the statement, 13,130 characters
verify.py               the rules in Python and in the IR, the checker bridge, the certificate, the seed's build,
                        the emit-layer edits, the search and guide sweeps, the timing, the self-test
specification.py        the specification and §9's gates; writes specification.json
specification.json      the supplied specification
tricks.py               the calibration, bound, cheat and leniency tables, every row judged three ways
start.py                opens the project over the API with the specification supplied
solver/candidate.cpp    the starting program
starting-program.json   the same file, in the shape the composer accepts
```
