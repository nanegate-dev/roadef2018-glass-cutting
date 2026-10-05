// Starting program for the ROADEF/EURO 2018 glass-cutting example (Saint-Gobain, dataset B).
// Contract: candidate <input.json> <output.json> --seed N
// Output: {"plate":[..],"cut":[..],"type":[..],"x":[..],"y":[..],"w":[..],"h":[..],   the cutting tree, pre-order
//          "parent":[..],"end":[..],                                                 its certificate
//          "item_node":[..],"defect_leaf":[..],                                      who cuts what, where each defect lies
//          "n_plates":..,"residual_w":..,"geo_loss":..}                              the claims
// An input holding a list of instances gets a list of answers, in the same order.
//
// The rules are `problem.txt`'s and are not restated here: read them there.
// What matters to this file: cut every item of the batch from the jumbo plates,
// used in order, with a guillotine tree of at most four stages -- vertical
// stripes (1-cuts), horizontal strips inside them (2-cuts), slots inside those
// (3-cuts), and at most one 4-cut in a slot -- every item free of defects, no
// cut through a defect, each stack cut in its order. The score, MINIMISED, is the
// glass lost: the plates used, less the residual right of the last plate's last
// 1-cut, less the items' area, in whole mm^2.
//
// UNITS: EVERY LENGTH IS A WHOLE NUMBER OF MILLIMETRES AND EVERY AREA A WHOLE
// NUMBER OF SQUARE MILLIMETRES, in the answer and everywhere in this file.
//
// WHERE TO EDIT: `solve` (the constructive and its search) and `guide` (how a
// partial layout is ranked). `solve` returns a Layout: the items in cutting order,
// each with its plate, stripe, strip and slot. Nothing else.
//
// WHAT NOT TO EDIT: the emit layer (`emit`, at the bottom). The tree, its
// parents and subtree ends, every item's node, every defect's leaf and the three
// claims are a CERTIFICATE the rules recompute, and the emit layer derives every
// one of them from the Layout exactly as problem.txt defines them, fills the
// gaps between stripes, strips and slots with wastes, and makes the region right
// of the last stripe the residual. It then judges the whole answer against all
// eleven conditions with the rules' own arithmetic and writes it. It NEVER
// repairs: a Layout that breaks a rule is written exactly as returned, the stderr
// account says which condition it breaks, and the judge refuses it.
//
// WHAT IT DOES. A constructive in the stripe/strip/slot shape: at every step each
// stack's next item, in each allowed orientation, is tried (A) in the next slot of
// the current strip, (B) in a new strip above it, (C) in a new stripe right of
// the current one, (D) on the next plate; each at the first position, left to
// right or bottom to top, where no item covers a defect and no cut crosses one
// (a waste of at least min_waste is left in front when a defect is in the way).
// Every candidate is ranked by `guide` of the layout it would make -- the glass
// already lost behind the front, the area behind it, the items' area and their
// mean -- and the best is taken. Items are only ever taken from the stack heads
// and placed in cutting order, so every stack is cut in its order by
// construction. With the shipped knobs every seed writes the same bytes.
//
// WHAT IT CAN DO. `beam_width` above 1 turns the constructive into a beam search
// that keeps that many partial layouts, ranked by `guide`, at every step;
// `restarts` re-runs it with the guide's ranks perturbed by `noise`, from the
// seed, and keeps the best. Both are switched off (1 and 0). A fixed work budget,
// counted in candidate positions tried and never read off a clock, stops the
// restarts in time whatever the knobs say, and keeps every seed's runs the same.
// `policy` and `rotation` are choices: rank every candidate by the guide, or fill
// the current strip (1) or stripe (2) before opening the next; turn items freely,
// or keep their long side vertical (1) or horizontal (2). `guide` is an
// `evolve:expr`.

// WHERE THE LOSS IS. Measured on this program, nine seeds an instance: B5 alone
// loses 127,110,815 mm^2 -- about 23.2 plates for 16.6 plates of items, 26% of the
// fifteen-instance total -- against 72,155,615 (about 20.35 plates) for the best
// answer known for B5, and it loses exactly that on every seed, so restarts and
// noise have nothing to choose between there. B5 is 207 items in two stacks, 187
// and 20, each cut in its given order, with 209 defects. With the order fixed, the
// long stack is a sequence to be cut into consecutive groups -- which items share a
// strip, which strips share a stripe, where a stripe and a plate end -- and a
// dynamic program or a lookahead over the next items of the stack can decide what
// a greedy head-of-stack choice cannot. Next furthest from the best known answers:
// B1 (+133%), B9 (+111%), B11 (+82%); nearest: B7 (+35%), B4 (+40%).
//
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using ll = long long;

// --- the knobs ---------------------------------------------------------------
//
// `beam_width` partial layouts are kept at every step (1: the plain constructive);
// `restarts` more runs are made with every guide value multiplied by 1 + noise x u,
// u drawn uniformly in [-1, 1] from the seed; the best answer is kept. `policy`:
// 0 ranks every candidate by the guide; 1 takes a slot in the current strip
// whenever one exists; 2 stays in the current stripe whenever it can. `rotation`:
// 0 tries both orientations; 1 only the one with the long side vertical; 2 only
// the one with the long side horizontal.

constexpr int kBeamWidth = 256;                // evolve:param beam_width int 1 256
constexpr int kRestarts = 54;                 // evolve:param restarts int 0 200
constexpr double kNoise = 0.00732421875;               // evolve:param noise real 0.0 0.5
constexpr int kTopK = 1;                     // evolve:param top_k int 1 16
constexpr int kPolicy = 2;                   // evolve:param policy choice 0 1 2
constexpr int kTabuLen = 1;                  // evolve:param tabu_len int 1 64
constexpr int kRotation = 0;                 // evolve:param rotation choice 0 1 2
constexpr int kKeepPrefix = 47;                // evolve:param keep_prefix int 0 64
constexpr int kWindowLen = 32;                 // evolve:param window_len int 1 64
constexpr int kPopSize = 18;                    // evolve:param pop_size int 2 32
constexpr int kGenerations = 256;               // evolve:param generations int 1 256
constexpr int kBlockLen = 6;                  // evolve:param block_len int 1 64
constexpr int kRunLook = 15;                    // evolve:param run_look int 1 32
constexpr int kTabuTries = 12;                   // evolve:param tabu_tries int 1 32
constexpr double kRunWeight = 0.248046875;            // evolve:param run_weight real 0.0 2.0
constexpr int kGroupLook = 1;                   // evolve:param group_look int 1 32
constexpr double kGroupWeight = 0.6875;           // evolve:param group_weight real 0.0 2.0
constexpr double kPrefixDecay = 360.6455078125;           // evolve:param prefix_decay real 1.0 400.0
constexpr double kPlateWeight = 1.52734375;           // evolve:param plate_weight real 0.0 4.0
constexpr double kAbsoluteWeight = 0.5;       // evolve:param absolute_weight real 0.0 4.0

// THE GUIDE: how good a partial layout looks, smaller is better. waste is the glass
// already lost behind the front (mm^2): the area of every plate before the current
// one, every stripe left of the current one, every strip below the current one and
// the current strip up to its next slot, less the items in it; area is that area;
// placed is the items' area; mean is placed over the number of items placed. The
// author's rule is the waste percentage of Libralesso and Fontan's tree search:
// the share of the glass behind the front that is lost. Their key finding was the
// guide: waste percentage, and waste percentage over the mean item area, ranked
// partial layouts better than plain waste.
// evolve:expr guide real (real waste, real area, real placed, real mean) ops + - * / min max depth 4 nodes 24
static double guide(double waste, double area, double placed, double mean) { return ([](double x, double y) { return y == 0.0 ? 1.0 : x / y; }(waste, ([](double x, double y) { return y == 0.0 ? 1.0 : x / y; }(waste, mean) + 1.0)) - [](double x, double y) { return y == 0.0 ? 1.0 : x / y; }(placed, [](double x, double y) { return y == 0.0 ? 1.0 : x / y; }(waste, mean))); }

// --- a generator whose every draw is written here ----------------------------

struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed * 0x9E3779B97F4A7C15ULL + 0x632BE59BD9B4E019ULL) {}
    uint64_t next() {
        uint64_t z = (s += 0x9E3779B97F4A7C15ULL);
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
    double uniform() { return static_cast<double>(next() >> 11) * (1.0 / 9007199254740992.0); }
};

// --- reading the instance ----------------------------------------------------
//
// A small JSON reader: the runner writes canonical JSON with its keys sorted and no
// whitespace, and nothing here assumes either.

struct Json {
    enum Kind { Null, Bool, Number, String, Array, Object } kind = Null;
    double number = 0;
    bool boolean = false;
    std::string text;
    std::vector<Json> items;
    std::vector<std::pair<std::string, Json>> fields;
    const Json* get(const std::string& key) const {
        for (const auto& f : fields)
            if (f.first == key) return &f.second;
        return nullptr;
    }
};

struct Parser {
    const std::string& t;
    size_t at = 0;
    explicit Parser(const std::string& text) : t(text) {}
    void space() { while (at < t.size() && std::isspace(static_cast<unsigned char>(t[at]))) ++at; }
    bool fail(const char* what) { throw std::runtime_error(what); }
    Json value() {
        space();
        if (at >= t.size()) fail("unexpected end of input");
        Json out;
        char c = t[at];
        if (c == '{') {
            out.kind = Json::Object;
            ++at;
            space();
            if (t[at] == '}') { ++at; return out; }
            for (;;) {
                space();
                Json key = value();
                if (key.kind != Json::String) fail("an object key is not a string");
                space();
                if (t[at] != ':') fail("expected ':'");
                ++at;
                out.fields.emplace_back(key.text, value());
                space();
                if (t[at] == ',') { ++at; continue; }
                if (t[at] == '}') { ++at; return out; }
                fail("expected ',' or '}'");
            }
        }
        if (c == '[') {
            out.kind = Json::Array;
            ++at;
            space();
            if (t[at] == ']') { ++at; return out; }
            for (;;) {
                out.items.push_back(value());
                space();
                if (t[at] == ',') { ++at; continue; }
                if (t[at] == ']') { ++at; return out; }
                fail("expected ',' or ']'");
            }
        }
        if (c == '"') {
            out.kind = Json::String;
            ++at;
            while (at < t.size() && t[at] != '"') {
                if (t[at] == '\\' && at + 1 < t.size()) { out.text += t[at + 1]; at += 2; continue; }
                out.text += t[at++];
            }
            ++at;
            return out;
        }
        if (t.compare(at, 4, "true") == 0) { out.kind = Json::Bool; out.boolean = true; at += 4; return out; }
        if (t.compare(at, 5, "false") == 0) { out.kind = Json::Bool; at += 5; return out; }
        if (t.compare(at, 4, "null") == 0) { at += 4; return out; }
        size_t used = 0;
        out.kind = Json::Number;
        out.number = std::stod(t.substr(at, 40), &used);
        at += used;
        return out;
    }
};

struct Defect { ll x, y, w, h; };

struct Inst {
    std::string name;
    ll W = 0, H = 0, nmax = 0, min1 = 0, max1 = 0, min2 = 0, minw = 0;
    std::vector<ll> iw, ih;
    std::vector<std::vector<int>> stacks;
    std::vector<int> dplate;
    std::vector<ll> dx, dy, dw, dh;
    std::vector<std::vector<Defect>> on;   // the defects of each plate
};

static ll whole(const Json& v, const char* key) {
    const Json* f = v.get(key);
    if (!f || f->kind != Json::Number) throw std::runtime_error(std::string("missing number ") + key);
    return static_cast<ll>(std::llround(f->number));
}

static std::vector<ll> wholes(const Json& v, const char* key) {
    const Json* f = v.get(key);
    if (!f || f->kind != Json::Array) throw std::runtime_error(std::string("missing list ") + key);
    std::vector<ll> out;
    for (const auto& x : f->items) out.push_back(static_cast<ll>(std::llround(x.number)));
    return out;
}

static Inst read_instance(const Json& v) {
    Inst in;
    if (const Json* n = v.get("name")) in.name = n->text;
    in.W = whole(v, "plate_w"); in.H = whole(v, "plate_h"); in.nmax = whole(v, "n_plates_max");
    in.min1 = whole(v, "min1cut"); in.max1 = whole(v, "max1cut"); in.min2 = whole(v, "min2cut");
    in.minw = whole(v, "min_waste");
    in.iw = wholes(v, "item_w"); in.ih = wholes(v, "item_h");
    const Json* st = v.get("stacks");
    if (!st) throw std::runtime_error("missing stacks");
    for (const auto& s : st->items) {
        std::vector<int> members;
        for (const auto& x : s.items) members.push_back(static_cast<int>(std::llround(x.number)));
        in.stacks.push_back(members);
    }
    std::vector<ll> dp = wholes(v, "defect_plate");
    in.dx = wholes(v, "defect_x"); in.dy = wholes(v, "defect_y");
    in.dw = wholes(v, "defect_w"); in.dh = wholes(v, "defect_h");
    in.on.assign(static_cast<size_t>(in.nmax), {});
    for (size_t d = 0; d < dp.size(); ++d) {
        in.dplate.push_back(static_cast<int>(dp[d]));
        if (dp[d] >= 0 && dp[d] < in.nmax)
            in.on[static_cast<size_t>(dp[d])].push_back({in.dx[d], in.dy[d], in.dw[d], in.dh[d]});
    }
    return in;
}

// --- the layout --------------------------------------------------------------
//
// One placement per item, in cutting order: the item, the size it is cut at (w
// across, h up), its plate, the stripe it is in (x, width), the strip (y, height)
// and the slot's x. The item sits at the bottom of its slot; the emit layer fills
// everything else with wastes and the residual.

struct Placement {
    int item = -1;
    ll w = 0, h = 0;
    int plate = 0;
    ll stripe_x = 0, stripe_w = 0;
    ll strip_y = 0, strip_h = 0;
    ll slot_x = 0;
    int back = -1;   // the placement before it in its partial layout (the beam's arena)
};

struct Layout {
    std::vector<Placement> placed;
};

// --- the geometry of defects ---------------------------------------------------

struct Geometry {
    const Inst& in;
    explicit Geometry(const Inst& i) : in(i) {}
    const std::vector<Defect>& on(int plate) const { return in.on[static_cast<size_t>(plate)]; }
    // A vertical cut at x over [y0, y1) goes through a defect.
    bool cuts_v(int plate, ll x, ll y0, ll y1) const {
        for (const Defect& d : on(plate))
            if (d.x < x && x < d.x + d.w && d.y < y1 && d.y + d.h > y0) return true;
        return false;
    }
    bool cuts_h(int plate, ll y, ll x0, ll x1) const {
        for (const Defect& d : on(plate))
            if (d.y < y && y < d.y + d.h && d.x < x1 && d.x + d.w > x0) return true;
        return false;
    }
    bool covers(int plate, ll x, ll y, ll w, ll h) const {
        for (const Defect& d : on(plate))
            if (d.x < x + w && x < d.x + d.w && d.y < y + h && y < d.y + d.h) return true;
        return false;
    }
    // A leftover of this size can be a waste: none, or at least min_waste.
    bool leftover(ll size) const { return size == 0 || size >= in.minw; }
    // Where the next piece may start, from `from`: there, or past a waste of at
    // least min_waste, and just clear of each defect.
    std::vector<ll> starts(int plate, ll from, ll size, bool along_x) const {
        std::vector<ll> out = {from, from + in.minw};
        for (const Defect& d : on(plate)) {
            ll lo = along_x ? d.x : d.y, hi = along_x ? d.x + d.w : d.y + d.h;
            for (ll s : {hi, lo - size, hi - size})
                if (s >= from + in.minw) out.push_back(s);
        }
        std::sort(out.begin(), out.end());
        out.erase(std::unique(out.begin(), out.end()), out.end());
        return out;
    }
    // The first slot position in the strip [x0, x1) x [y0, y0 + th) from `from`, or -1.
    ll slot(int plate, ll x0, ll x1, ll y0, ll th, ll from, ll w, ll h) const {
        (void)x0;
        if (h > th || !leftover(th - h)) return -1;
        for (ll x : starts(plate, from, w, true)) {
            if (x + w > x1) break;
            if (!leftover(x1 - x - w)) continue;
            if (x != from && cuts_v(plate, x, y0, y0 + th)) continue;
            if (x + w != x1 && cuts_v(plate, x + w, y0, y0 + th)) continue;
            if (covers(plate, x, y0, w, h)) continue;
            if (h != th && cuts_h(plate, y0 + h, x, x + w)) continue;
            return x;
        }
        return -1;
    }
    // The slot position in the strip that leaves the least waste in front of the
    // item, among the positions `starts` offers. Same legality checks as `slot`.
    ll slot_best(int plate, ll x0, ll x1, ll y0, ll th, ll from, ll w, ll h) const {
        (void)x0;
        if (h > th || !leftover(th - h)) return -1;
        ll best = -1, best_gap = 0;
        for (ll x : starts(plate, from, w, true)) {
            if (x + w > x1) break;
            if (!leftover(x1 - x - w)) continue;
            if (x != from && cuts_v(plate, x, y0, y0 + th)) continue;
            if (x + w != x1 && cuts_v(plate, x + w, y0, y0 + th)) continue;
            if (covers(plate, x, y0, w, h)) continue;
            if (h != th && cuts_h(plate, y0 + h, x, x + w)) continue;
            ll gap = x - from;
            if (best < 0 || gap < best_gap) { best = x; best_gap = gap; }
        }
        return best;
    }
    // A new strip in the stripe [x0, x1) from `from` up, with the item in its first
    // slot: (strip y, slot x), or (-1, -1).
    std::pair<ll, ll> strip(int plate, ll x0, ll x1, ll from, ll w, ll h) const {
        if (w > x1 - x0) return {-1, -1};
        for (ll y : starts(plate, from, h, false)) {
            if (y + h > in.H) break;
            if (!leftover(in.H - y - h)) continue;
            if (y != from && cuts_h(plate, y, x0, x1)) continue;
            if (y + h != in.H && cuts_h(plate, y + h, x0, x1)) continue;
            ll x = slot(plate, x0, x1, y, h, x0, w, h);
            if (x >= 0) return {y, x};
        }
        return {-1, -1};
    }
    // A new stripe as wide as the item, from `from` right: (stripe x, strip y, slot x).
    bool stripe(int plate, ll from, ll w, ll h, ll& sx, ll& sy, ll& slx) const {
        if (w < in.min1 || w > in.max1) return false;
        for (ll x : starts(plate, from, w, true)) {
            if (x + w > in.W) break;
            if (!leftover(in.W - x - w)) continue;
            if (x != from && cuts_v(plate, x, 0, in.H)) continue;
            if (x + w != in.W && cuts_v(plate, x + w, 0, in.H)) continue;
            auto got = strip(plate, x, x + w, 0, w, h);
            if (got.first >= 0) { sx = x; sy = got.first; slx = got.second; return true; }
        }
        return false;
    }
};

// --- the constructive, and the beam around it -----------------------------------

struct State {
    int plate = 0;
    ll sx = 0, sw = 0;   // the current stripe (sw 0: none yet on this plate)
    ll ty = 0, th = 0;   // the current strip
    ll cx = 0;           // where the next slot of the current strip may start
    ll placed_area = 0;
    int count = 0;
    int last = -1;       // its last placement, in the arena
    std::vector<int> head;
};

struct Move {
    int from = 0;        // the state it extends
    int kind = 0;        // 0 slot, 1 strip, 2 stripe, 3 plate
    Placement p;
    ll area = 0;         // the area behind the front after it
    double rank = 0;
    int order = 0;       // generation order, the tie-break
};

static ll area_behind(const Inst& in, int plate, ll sx, ll sw, ll ty, ll th, ll cx) {
    return static_cast<ll>(plate) * in.W * in.H + sx * in.H + sw * ty + th * (cx - sx);
}

static void orientations(const Inst& in, int item, std::vector<std::pair<ll, ll>>& out) {
    out.clear();
    ll a = in.iw[static_cast<size_t>(item)], b = in.ih[static_cast<size_t>(item)];
    ll lo = std::min(a, b), hi = std::max(a, b);
    if (kRotation == 0 || kRotation == 1) out.push_back({lo, hi});           // long side vertical
    if ((kRotation == 0 && lo != hi) || kRotation == 2) out.push_back({hi, lo});  // long side horizontal
}

// Candidate positions tried so far, over every run: the work the budget counts.
static long long g_work = 0;

// How much of the near future a stripe of width `sw` and height `th` can absorb,
// given the stack the move takes from and the item it takes. Walks the next
// `kRunLook` items of that stack in the orientation the move uses and sums the
// widths of the longest prefix that fits `sw` with every height at most `th`.
// Returns packed area over stripe area, in [0, 1].
static double run_reach(const Inst& in, int stack, int taken, ll sw, ll th, ll w, ll h) {
    if (sw <= 0 || th <= 0) return 0.0;
    ll used = w;
    ll area = w * h;
    const std::vector<int>& s = in.stacks[static_cast<size_t>(stack)];
    int at = taken + 1;
    for (int step = 0; step < kRunLook && at < static_cast<int>(s.size()); ++step, ++at) {
        int item = s[static_cast<size_t>(at)];
        ll a = in.iw[static_cast<size_t>(item)], b = in.ih[static_cast<size_t>(item)];
        ll lo = std::min(a, b), hi = std::max(a, b);
        ll nw = (h >= w) ? lo : hi;   // keep the same long-side orientation as the move
        ll nh = (h >= w) ? hi : lo;
        if (nh > th) break;
        if (used + nw > sw) break;
        used += nw;
        area += nw * nh;
    }
    return static_cast<double>(area) / static_cast<double>(sw * th);
}

// The best packed area of a prefix of the stack `stack` starting at `taken`, cut
// into consecutive groups, each group packed into a stripe of width `sw` and
// height `th` with the same 1-D rule `pack_stripe` uses: a group is a sequence of
// consecutive items, each in the orientation the move uses, whose widths sum to at
// most `sw` and whose heights are at most `th`. dp[j] = the best area using the
// first j items of the lookahead window; the answer is dp[window]. This is the
// property the constructive ignores: the stack is a fixed sequence, so the choice
// of where a stripe ends is a 1-D segmentation, not a greedy head choice.
static ll group_area(const Inst& in, int stack, int taken, ll sw, ll th, ll w, ll h) {
    if (sw <= 0 || th <= 0) return 0;
    const std::vector<int>& s = in.stacks[static_cast<size_t>(stack)];
    int n = static_cast<int>(s.size()) - taken;
    if (n > kGroupLook) n = kGroupLook;
    if (n <= 0) return 0;
    std::vector<ll> dp(static_cast<size_t>(n) + 1, 0);
    for (int j = 1; j <= n; ++j) {
        dp[static_cast<size_t>(j)] = dp[static_cast<size_t>(j) - 1];
        ll used = 0, area = 0;
        for (int k = j; k >= 1; --k) {
            int item = s[static_cast<size_t>(taken + k - 1)];
            ll a = in.iw[static_cast<size_t>(item)], b = in.ih[static_cast<size_t>(item)];
            ll lo = std::min(a, b), hi = std::max(a, b);
            ll nw = (h >= w) ? lo : hi;
            ll nh = (h >= w) ? hi : lo;
            if (nh > th) break;
            used += nw;
            if (used > sw) break;
            area += nw * nh;
            ll val = dp[static_cast<size_t>(k) - 1] + area;
            if (val > dp[static_cast<size_t>(j)]) dp[static_cast<size_t>(j)] = val;
        }
    }
    return dp[static_cast<size_t>(n)];
}

// Every move from state `s` (index `from`), appended to `moves`.
static void expand(const Inst& in, const Geometry& g, const State& s, int from, std::vector<Move>& moves,
                   int& order) {
    std::vector<std::pair<ll, ll>> sizes;
    size_t first = moves.size();
    for (size_t k = 0; k < in.stacks.size(); ++k) {
        if (s.head[k] >= static_cast<int>(in.stacks[k].size())) continue;
        int item = in.stacks[k][static_cast<size_t>(s.head[k])];
        orientations(in, item, sizes);
        for (auto [w, h] : sizes) {
            g_work += 4;
            Move m;
            m.from = from;
            m.p.item = item; m.p.w = w; m.p.h = h;
            // (A) the next slot of the current strip
            if (s.sw > 0 && s.th > 0) {
                ll x = g.slot_best(s.plate, s.sx, s.sx + s.sw, s.ty, s.th, s.cx, w, h);
                if (x >= 0) {
                    Move a = m;
                    a.kind = 0;
                    a.p.plate = s.plate; a.p.stripe_x = s.sx; a.p.stripe_w = s.sw;
                    a.p.strip_y = s.ty; a.p.strip_h = s.th; a.p.slot_x = x;
                    a.area = area_behind(in, s.plate, s.sx, s.sw, s.ty, s.th, x + w);
                    a.order = order++;
                    moves.push_back(a);
                }
            }
            // (B) a new strip above the current one
            if (s.sw > 0) {
                auto got = g.strip(s.plate, s.sx, s.sx + s.sw, s.ty + s.th, w, h);
                if (got.first >= 0) {
                    Move b = m;
                    b.kind = 1;
                    b.p.plate = s.plate; b.p.stripe_x = s.sx; b.p.stripe_w = s.sw;
                    b.p.strip_y = got.first; b.p.strip_h = h; b.p.slot_x = got.second;
                    b.area = area_behind(in, s.plate, s.sx, s.sw, got.first, h, got.second + w);
                    b.order = order++;
                    moves.push_back(b);
                }
            }
            // (C) a new stripe on this plate, (D) the next plate
            for (int kind = 2; kind <= 3; ++kind) {
                int plate = kind == 2 ? s.plate : s.plate + 1;
                ll start = kind == 2 ? s.sx + s.sw : 0;
                if (plate >= in.nmax) continue;
                ll sx, sy, slx;
                if (!g.stripe(plate, start, w, h, sx, sy, slx)) continue;
                Move c = m;
                c.kind = kind;
                c.p.plate = plate; c.p.stripe_x = sx; c.p.stripe_w = w;
                c.p.strip_y = sy; c.p.strip_h = h; c.p.slot_x = slx;
                c.area = area_behind(in, plate, sx, w, sy, h, slx + w);
                c.order = order++;
                moves.push_back(c);
            }
        }
    }
    // The policy: keep only the moves that stay where it says, when there are any.
    if (kPolicy != 0) {
        int keep = kPolicy == 1 ? 0 : 1;
        bool any = false;
        for (size_t q = first; q < moves.size(); ++q) any = any || moves[q].kind <= keep;
        if (any) {
            size_t w = first;
            for (size_t q = first; q < moves.size(); ++q)
                if (moves[q].kind <= keep) moves[w++] = moves[q];
            moves.resize(w);
        }
    }
}

// Exact 1-D packing of the available stack heads into a stripe of width `sw`:
// a dynamic program over the stripe width that picks the sequence of items (each
// taken from its stack head, in stack order) maximising the packed area. Returns
// the chosen (item, w, h, slot_x) in cutting order.
struct StripePick { int item; ll w, h, x; };

static std::vector<StripePick> pack_stripe(const Inst& in, const Geometry& g, int plate, ll sx, ll sw,
                                           ll ty, ll th, const std::vector<int>& head) {
    std::vector<StripePick> out;
    if (sw <= 0 || th <= 0) return out;
    // Candidate items: the head of every stack, in both orientations that fit.
    struct Cand { int item; ll w, h; };
    std::vector<Cand> cands;
    std::vector<std::pair<ll, ll>> sizes;
    for (size_t k = 0; k < in.stacks.size(); ++k) {
        if (head[k] >= static_cast<int>(in.stacks[k].size())) continue;
        int item = in.stacks[k][static_cast<size_t>(head[k])];
        orientations(in, item, sizes);
        for (auto [w, h] : sizes)
            if (w <= sw && h <= th) cands.push_back({item, w, h});
    }
    if (cands.empty()) return out;
    // dp[x] = best packed area using the stripe up to x; choice[x] = the candidate.
    std::vector<ll> dp(static_cast<size_t>(sw) + 1, -1);
    std::vector<int> choice(static_cast<size_t>(sw) + 1, -1);
    std::vector<ll> prev(static_cast<size_t>(sw) + 1, 0);
    dp[0] = 0;
    for (ll x = 0; x <= sw; ++x) {
        if (dp[static_cast<size_t>(x)] < 0) continue;
        for (size_t c = 0; c < cands.size(); ++c) {
            const Cand& cd = cands[c];
            ll nx = x + cd.w;
            if (nx > sw) continue;
            if (!g.leftover(sw - nx)) continue;
            if (x != 0 && g.cuts_v(plate, x, ty, ty + th)) continue;
            if (nx != sw && g.cuts_v(plate, nx, ty, ty + th)) continue;
            if (g.covers(plate, x, ty, cd.w, cd.h)) continue;
            if (cd.h != th && g.cuts_h(plate, ty + cd.h, x, nx)) continue;
            ll val = dp[static_cast<size_t>(x)] + cd.w * cd.h;
            if (val > dp[static_cast<size_t>(nx)]) {
                dp[static_cast<size_t>(nx)] = val;
                choice[static_cast<size_t>(nx)] = static_cast<int>(c);
                prev[static_cast<size_t>(nx)] = x;
            }
        }
    }
    ll best = -1, best_x = 0;
    for (ll x = 0; x <= sw; ++x)
        if (dp[static_cast<size_t>(x)] > best) { best = dp[static_cast<size_t>(x)]; best_x = x; }
    if (best <= 0) return out;
    std::vector<StripePick> rev;
    for (ll x = best_x; x > 0;) {
        int c = choice[static_cast<size_t>(x)];
        if (c < 0) break;
        ll px = prev[static_cast<size_t>(x)];
        rev.push_back({cands[static_cast<size_t>(c)].item, cands[static_cast<size_t>(c)].w,
                       cands[static_cast<size_t>(c)].h, px});
        x = px;
    }
    std::reverse(rev.begin(), rev.end());
    return rev;
}

static ll final_loss(const Inst& in, const State& s, ll total_area) {
    ll residual = in.W - (s.sx + s.sw);
    return static_cast<ll>(s.plate + 1) * in.W * in.H - in.H * residual - total_area;
}

// One run of the constructive (a beam of `width`), the guide perturbed by `noise`
// draws from `rng` when `noisy`. Returns the best complete layout's placements. A
// guide that ranks wasteful moves first can use up every plate before the last
// item; then the layout so far is returned as it is, `loss` is the largest number
// there is, and the emit layer writes it and the judge refuses it. Never a crash.
static Layout construct(const Inst& in, int width, bool noisy, Rng& rng, ll& loss, int tabu_len,
                       const std::vector<Placement>& prefix) {
    Geometry g(in);
    ll total_area = 0;
    for (size_t k = 0; k < in.iw.size(); ++k) total_area += in.iw[k] * in.ih[k];
    size_t n_items = in.iw.size();
    std::vector<Placement> arena;
    State start;
    start.head.assign(in.stacks.size(), 0);
    std::vector<State> beam = {start};
    std::vector<Move> moves;
    size_t depth = 0;
    for (; depth < n_items; ++depth) {
        moves.clear();
        int order = 0;
        for (size_t b = 0; b < beam.size(); ++b) expand(in, g, beam[b], static_cast<int>(b), moves, order);
        if (moves.empty()) break;   // no plate left for the next item
        if (depth < prefix.size()) {
            const Placement& want = prefix[depth];
            size_t keep_one = moves.size();
            for (size_t q = 0; q < moves.size(); ++q) {
                const Move& m = moves[q];
                if (m.p.item == want.item && m.p.plate == want.plate &&
                    m.p.stripe_x == want.stripe_x && m.p.stripe_w == want.stripe_w &&
                    m.p.strip_y == want.strip_y && m.p.strip_h == want.strip_h &&
                    m.p.slot_x == want.slot_x && m.p.w == want.w && m.p.h == want.h) {
                    keep_one = q;
                    break;
                }
            }
            if (keep_one < moves.size()) {
                std::swap(moves[0], moves[keep_one]);
                moves.resize(1);
            } else {
                moves.clear();
                break;
            }
        }
        for (Move& m : moves) {
            const State& s = beam[static_cast<size_t>(m.from)];
            double placed = static_cast<double>(s.placed_area + m.p.w * m.p.h);
            double area = static_cast<double>(m.area);
            double mean = placed / static_cast<double>(s.count + 1);
            double absolute_waste = area - placed;
            m.rank = guide(absolute_waste, area, placed, mean);
            if (kAbsoluteWeight > 0.0) {
                double plate_area = static_cast<double>(in.W) * static_cast<double>(in.H);
                m.rank += kAbsoluteWeight * (absolute_waste / plate_area);
            }
            if (kRunWeight > 0.0 && m.kind >= 2) {
                int stack = -1, taken = -1;
                for (size_t k = 0; k < in.stacks.size(); ++k) {
                    const std::vector<int>& sk = in.stacks[k];
                    for (size_t j = 0; j < sk.size(); ++j)
                        if (sk[j] == m.p.item) { stack = static_cast<int>(k); taken = static_cast<int>(j); break; }
                    if (stack >= 0) break;
                }
                if (stack >= 0) {
                    m.rank -= kRunWeight * run_reach(in, stack, taken, m.p.stripe_w, m.p.strip_h, m.p.w, m.p.h);
                    if (kGroupWeight > 0.0) {
                        ll ga = group_area(in, stack, taken, m.p.stripe_w, m.p.strip_h, m.p.w, m.p.h);
                        double reach = static_cast<double>(ga) /
                                       static_cast<double>(m.p.stripe_w * m.p.strip_h);
                        m.rank -= kGroupWeight * reach;
                    }
                }
            }
            // Plate pressure: a state at plate p with placed area A can never beat
            // A + (nmax - p - 1) * W * H, so among equal-waste states the one that
            // packs more area per plate already opened is strictly closer to that
            // bound. The guide never sees the plate index; this term does.
            if (kPlateWeight > 0.0 && m.kind >= 2) {
                double plate_area = static_cast<double>(in.W) * static_cast<double>(in.H);
                double per_plate = placed / (static_cast<double>(m.p.plate) + 1.0);
                m.rank -= kPlateWeight * (per_plate / plate_area);
            }
            if (noisy) m.rank *= 1.0 + kNoise * (2.0 * rng.uniform() - 1.0);
            if (m.rank != m.rank) m.rank = 1e300;   // a NaN ranks last, never first
        }
        size_t keep = std::min(moves.size(), static_cast<size_t>(std::max(1, width)));
        if (noisy && kTopK > 1 && moves.size() > 1) {
            size_t kk = std::min(moves.size(), static_cast<size_t>(kTopK));
            std::partial_sort(moves.begin(), moves.begin() + static_cast<long>(kk), moves.end(),
                              [](const Move& a, const Move& b) {
                                  if (a.rank != b.rank) return a.rank < b.rank;
                                  return a.order < b.order;
                              });
            size_t pick = static_cast<size_t>(rng.next() % kk);
            std::swap(moves[0], moves[pick]);
        }
        std::partial_sort(moves.begin(), moves.begin() + static_cast<long>(keep), moves.end(),
                          [](const Move& a, const Move& b) {
                              if (a.rank != b.rank) return a.rank < b.rank;
                              return a.order < b.order;
                          });
        std::vector<State> next;
        next.reserve(keep);
        for (size_t q = 0; q < keep; ++q) {
            const Move& m = moves[q];
            State s = beam[static_cast<size_t>(m.from)];
            Placement p = m.p;
            p.back = s.last;
            arena.push_back(p);
            s.last = static_cast<int>(arena.size()) - 1;
            s.plate = p.plate; s.sx = p.stripe_x; s.sw = p.stripe_w;
            s.ty = p.strip_y; s.th = p.strip_h; s.cx = p.slot_x + p.w;
            s.placed_area += p.w * p.h;
            s.count += 1;
            for (size_t k = 0; k < in.stacks.size(); ++k)
                if (s.head[k] < static_cast<int>(in.stacks[k].size()) &&
                    in.stacks[k][static_cast<size_t>(s.head[k])] == p.item) { s.head[k] += 1; break; }
            // Deduplicate: skip if an identical state is already in next.
            bool dup = false;
            for (const State& t : next) {
                if (t.plate == s.plate && t.sx == s.sx && t.sw == s.sw &&
                    t.ty == s.ty && t.th == s.th && t.cx == s.cx &&
                    t.head == s.head) { dup = true; break; }
            }
            if (!dup) next.push_back(std::move(s));
        }
        beam = std::move(next);
    }
    size_t best = 0;
    for (size_t b = 1; b < beam.size(); ++b)
        if (final_loss(in, beam[b], total_area) < final_loss(in, beam[best], total_area)) best = b;
    loss = depth == n_items ? final_loss(in, beam[best], total_area) : std::numeric_limits<ll>::max();
    Layout out;
    for (int at = beam[best].last; at >= 0; at = arena[static_cast<size_t>(at)].back)
        out.placed.push_back(arena[static_cast<size_t>(at)]);
    std::reverse(out.placed.begin(), out.placed.end());
    return out;
}

// THE WORK BUDGET, not a knob: a restart is begun only if one more run of the size
// of the first still fits under it, so every setting of the knobs ends in time, and
// a run's length is counted in candidate positions tried, never read off a clock,
// so the same seed always makes the same runs.
constexpr long long kWorkBudget = 30000000;

// A population of layouts, recombined by a contiguous block of placements taken
// from one parent and forced as a prefix of a fresh constructive. A restart loop
// can only ever re-derive one lineage; a population keeps several lineages alive
// and lets a child inherit a good middle block from a parent that is not the
// incumbent, which no single-trajectory search can reach.
struct Individual {
    Layout layout;
    ll loss = std::numeric_limits<ll>::max();
};

// The population's size, the number of generations it is bred for, and the
// mutation rate: a child is a prefix of one parent re-derived by the beam
// constructive, and with probability kMutate the prefix is taken from a random
// cut of the parent instead of the parent's own head.
constexpr int kPopSize2 = 22;                 // evolve:param pop_size2 int 2 32
constexpr int kGens2 = 40;                    // evolve:param gens2 int 1 200
constexpr double kMutate = 0.35;              // evolve:param mutate real 0.0 1.0
constexpr int kTourney = 3;                   // evolve:param tourney int 1 8
constexpr int kImmigrant = 5;                 // evolve:param immigrant int 0 32

// A population of layouts bred by prefix recombination: every child is a fresh
// beam constructive whose first `cut` placements are forced to a parent's, so a
// child inherits a good head from one lineage and re-derives the rest with the
// full beam. This is a different family from the restart loop -- several lineages
// are alive at once and a child can take its head from a parent that is not the
// incumbent -- and it is the only way to reach a layout whose good part is not a
// prefix of the incumbent's.
static Layout solve(const Inst& in, uint64_t seed) {
    Rng rng(seed);
    long long before = g_work;
    std::vector<Placement> empty;
    Layout cur;
    ll cur_loss = std::numeric_limits<ll>::max();
    cur = construct(in, kBeamWidth, true, rng, cur_loss, kTabuLen, empty);
    int runs = 1;
    long long one_run = g_work - before;
    if (one_run <= 0) one_run = 1;
    // The population: the incumbent plus kPopSize2 - 1 more layouts, each a fresh
    // constructive with a random prefix of the incumbent forced.
    std::vector<Individual> pop;
    pop.push_back({cur, cur_loss});
    for (int p = 1; p < kPopSize2; ++p) {
        if (g_work - before + one_run > kWorkBudget) break;
        size_t n = cur.placed.size();
        if (n == 0) break;
        size_t cut = static_cast<size_t>(rng.next() % (n + 1));
        std::vector<Placement> prefix;
        for (size_t q = 0; q < cut; ++q) prefix.push_back(cur.placed[q]);
        Layout cand;
        ll cand_loss = std::numeric_limits<ll>::max();
        cand = construct(in, kBeamWidth, true, rng, cand_loss, kTabuLen, prefix);
        ++runs;
        pop.push_back({std::move(cand), cand_loss});
        if (cand_loss < cur_loss) { cur = pop.back().layout; cur_loss = cand_loss; }
    }
    // Breed: pick two parents by tournament, force the better one's head as the
    // child's prefix, and let the beam re-derive the rest. The child replaces the
    // worst individual when it is better than it. Every kImmigrant-th generation a
    // fresh random restart is injected instead, so the population does not collapse
    // onto one lineage.
    for (int gen = 0; gen < kGens2; ++gen) {
        if (kImmigrant > 0 && gen % kImmigrant == 0) {
            if (g_work - before + one_run > kWorkBudget) break;
            ll fresh_loss = std::numeric_limits<ll>::max();
            std::vector<Placement> none;
            Layout fresh = construct(in, kBeamWidth, true, rng, fresh_loss, kTabuLen, none);
            ++runs;
            size_t worst0 = 0;
            for (size_t q = 1; q < pop.size(); ++q)
                if (pop[q].loss > pop[worst0].loss) worst0 = q;
            if (fresh_loss < pop[worst0].loss) {
                pop[worst0] = {std::move(fresh), fresh_loss};
                if (fresh_loss < cur_loss) { cur = pop[worst0].layout; cur_loss = fresh_loss; }
            }
            continue;
        }
        if (g_work - before + one_run > kWorkBudget) break;
        if (pop.size() < 2) break;
        auto pick = [&]() -> size_t {
            size_t best = static_cast<size_t>(rng.next() % pop.size());
            for (int t = 1; t < kTourney; ++t) {
                size_t c = static_cast<size_t>(rng.next() % pop.size());
                if (pop[c].loss < pop[best].loss) best = c;
            }
            return best;
        };
        size_t a = pick(), b = pick();
        const Individual& parent = pop[pop[a].loss <= pop[b].loss ? a : b];
        size_t n = parent.layout.placed.size();
        if (n == 0) break;
        size_t cut = static_cast<size_t>(rng.next() % (n + 1));
        if (rng.uniform() < kMutate) cut = static_cast<size_t>(rng.next() % (n + 1));
        std::vector<Placement> prefix;
        for (size_t q = 0; q < cut; ++q) prefix.push_back(parent.layout.placed[q]);
        Layout cand;
        ll cand_loss = std::numeric_limits<ll>::max();
        cand = construct(in, kBeamWidth, true, rng, cand_loss, kTabuLen, prefix);
        ++runs;
        size_t worst = 0;
        for (size_t q = 1; q < pop.size(); ++q)
            if (pop[q].loss > pop[worst].loss) worst = q;
        if (cand_loss < pop[worst].loss) {
            pop[worst] = {std::move(cand), cand_loss};
            if (cand_loss < cur_loss) { cur = pop[worst].layout; cur_loss = cand_loss; }
        }
    }
    const Layout& layout = cur;
    ll loss = cur_loss;
    std::cerr << in.name << ": " << runs << " run(s) of a beam of " << kBeamWidth << ", "
              << (g_work - before) << " candidate positions tried, ";
    if (layout.placed.size() == in.iw.size())
        std::cerr << "best geo_loss " << loss << "\n";
    else
        std::cerr << "the plates ran out after " << layout.placed.size() << " of " << in.iw.size()
                  << " items: the layout so far is handed on as it stands\n";
    return layout;  // the layout, as the emit layer receives it
}

// ============================================================================
// THE EMIT LAYER -- DO NOT EDIT. It derives the tree and the certificate from the
// Layout exactly as problem.txt defines them, judges them, and writes them.
// ============================================================================

struct Node { int plate, cut, type; ll x, y, w, h; int parent, end; };

struct Answer {
    std::vector<Node> nodes;
    std::vector<int> item_node, defect_leaf;
    ll n_plates = 0, residual_w = 0, geo_loss = 0;
};

static int add_node(std::vector<Node>& nodes, int plate, int cut, int type, ll x, ll y, ll w, ll h, int parent) {
    nodes.push_back({plate, cut, type, x, y, w, h, parent, -1});
    return static_cast<int>(nodes.size()) - 1;
}

// The tree of a Layout: per plate, its stripes left to right, their strips bottom to
// top, their slots left to right; every gap a waste; right of the last plate's last
// stripe, the residual. The placements are taken as they are, in the order given.
static Answer build(const Inst& in, const Layout& layout) {
    Answer a;
    std::vector<Node>& nodes = a.nodes;
    const std::vector<Placement>& ps = layout.placed;
    int last_plate = ps.empty() ? 0 : ps.back().plate;
    size_t q = 0;
    for (int plate = 0; plate <= last_plate; ++plate) {
        int root = add_node(nodes, plate, 0, -2, 0, 0, in.W, in.H, -1);
        ll right = 0;
        while (q < ps.size() && ps[q].plate == plate) {
            ll sx = ps[q].stripe_x, sw = ps[q].stripe_w;
            if (sx > right) add_node(nodes, plate, 1, -1, right, 0, sx - right, in.H, root);
            int stripe = add_node(nodes, plate, 1, -2, sx, 0, sw, in.H, root);
            ll top = 0;
            while (q < ps.size() && ps[q].plate == plate && ps[q].stripe_x == sx) {
                ll ty = ps[q].strip_y, th = ps[q].strip_h;
                if (ty > top) add_node(nodes, plate, 2, -1, sx, top, sw, ty - top, stripe);
                size_t end = q;
                while (end < ps.size() && ps[end].plate == plate && ps[end].stripe_x == sx && ps[end].strip_y == ty)
                    ++end;
                bool single = end == q + 1 && ps[q].slot_x == sx && ps[q].w == sw && ps[q].h == th;
                if (single) {
                    add_node(nodes, plate, 2, ps[q].item, sx, ty, sw, th, stripe);
                } else {
                    int strip = add_node(nodes, plate, 2, -2, sx, ty, sw, th, stripe);
                    ll along = sx;
                    for (size_t k = q; k < end; ++k) {
                        const Placement& p = ps[k];
                        if (p.slot_x > along) add_node(nodes, plate, 3, -1, along, ty, p.slot_x - along, th, strip);
                        if (p.h == th) {
                            add_node(nodes, plate, 3, p.item, p.slot_x, ty, p.w, th, strip);
                        } else {
                            int slot = add_node(nodes, plate, 3, -2, p.slot_x, ty, p.w, th, strip);
                            add_node(nodes, plate, 4, p.item, p.slot_x, ty, p.w, p.h, slot);
                            add_node(nodes, plate, 4, -1, p.slot_x, ty + p.h, p.w, th - p.h, slot);
                        }
                        along = p.slot_x + p.w;
                    }
                    if (sx + sw > along) add_node(nodes, plate, 3, -1, along, ty, sx + sw - along, th, strip);
                }
                top = ty + th;
                q = end;
            }
            if (in.H > top) add_node(nodes, plate, 2, -1, sx, top, sw, in.H - top, stripe);
            right = sx + sw;
        }
        if (in.W > right) add_node(nodes, plate, 1, plate == last_plate ? -3 : -1, right, 0, in.W - right, in.H, root);
    }
    // The certificate: subtree ends, every item's node, every defect's leaf, the claims.
    int n = static_cast<int>(nodes.size());
    std::vector<int> size(static_cast<size_t>(n), 1);
    for (int i = n - 1; i >= 0; --i)
        if (nodes[static_cast<size_t>(i)].parent >= 0)
            size[static_cast<size_t>(nodes[static_cast<size_t>(i)].parent)] += size[static_cast<size_t>(i)];
    for (int i = 0; i < n; ++i) nodes[static_cast<size_t>(i)].end = i + size[static_cast<size_t>(i)];
    a.item_node.assign(in.iw.size(), -1);
    for (int i = n - 1; i >= 0; --i) {
        int t = nodes[static_cast<size_t>(i)].type;
        if (t >= 0 && t < static_cast<int>(in.iw.size())) a.item_node[static_cast<size_t>(t)] = i;
    }
    int used = n > 0 ? nodes.back().plate + 1 : 0;
    for (size_t d = 0; d < in.dx.size(); ++d) {
        int leaf = -1, overlap = -1;
        if (in.dplate[d] < used) {
            for (int i = 0; i < n; ++i) {
                const Node& v = nodes[static_cast<size_t>(i)];
                if (v.end != i + 1 || v.plate != in.dplate[d]) continue;
                bool inside = v.x <= in.dx[d] && in.dx[d] + in.dw[d] <= v.x + v.w && v.y <= in.dy[d] &&
                              in.dy[d] + in.dh[d] <= v.y + v.h;
                if (inside) { leaf = i; break; }
                bool meets = v.x < in.dx[d] + in.dw[d] && in.dx[d] < v.x + v.w && v.y < in.dy[d] + in.dh[d] &&
                             in.dy[d] < v.y + v.h;
                if (meets && overlap < 0) overlap = i;
            }
            if (leaf < 0) leaf = overlap;
        }
        a.defect_leaf.push_back(leaf);
    }
    ll area = 0;
    for (size_t k = 0; k < in.iw.size(); ++k) area += in.iw[k] * in.ih[k];
    const Node& last = nodes.back();
    a.n_plates = used;
    a.residual_w = (last.cut == 1 && (last.type == -1 || last.type == -3)) ? last.w : 0;
    a.geo_loss = a.n_plates * in.W * in.H - in.H * a.residual_w - area;
    return a;
}

// The eleven conditions of problem.txt, with its arithmetic. Returns those broken.
static std::vector<int> judge(const Inst& in, const Answer& a) {
    const std::vector<Node>& v = a.nodes;
    int n = static_cast<int>(v.size());
    int n_items = static_cast<int>(in.iw.size());
    std::vector<int> broken;
    auto node = [&](int i) -> const Node& { return v[static_cast<size_t>(i)]; };
    bool ok2 = n >= 1, ok3 = true, ok4 = true, ok5 = true, ok6 = true, ok7 = true;
    for (int i = 0; i < n; ++i) {
        const Node& u = node(i);
        bool placed;
        if (u.cut == 0) {
            bool numbered = i == 0 ? u.plate == 0 : u.plate == node(i - 1).plate + 1;
            placed = u.parent == -1 && numbered && u.plate < in.nmax && i < u.end && u.end <= n &&
                     (u.end == n || node(u.end).cut == 0);
        } else {
            int p = u.parent;
            placed = p >= 0 && p < i && u.plate == node(p).plate && u.cut == node(p).cut + 1 && i < u.end &&
                     u.end <= node(p).end && (u.end == node(p).end || (u.end < n && node(u.end).parent == p));
        }
        if (placed) placed = u.type == -2 ? (u.end >= i + 2 && i + 1 < n && node(i + 1).parent == i) : u.end == i + 1;
        ok2 = ok2 && placed;
        bool known = (u.type >= -3 && u.type <= -1) || (u.type >= 0 && u.type < n_items);
        ok3 = ok3 && known && u.cut >= 0 && u.cut <= 4 && (u.cut != 0 || u.type == -2) &&
              (u.type != -2 || u.cut <= 3) && (u.type != -3 || (u.cut == 1 && i == n - 1));
        if (u.cut == 0) {
            ok4 = ok4 && u.x == 0 && u.y == 0 && u.w == in.W && u.h == in.H;
        } else if (u.parent >= 0 && u.parent < i && i < u.end && u.end <= n && node(u.parent).end <= n) {
            const Node& p = node(u.parent);
            bool odd = u.cut % 2 == 1;
            ll along = odd ? u.x : u.y, span = odd ? u.w : u.h, p_along = odd ? p.x : p.y, p_span = odd ? p.w : p.h;
            bool same = odd ? (u.y == p.y && u.h == p.h) : (u.x == p.x && u.w == p.w);
            bool first = i != u.parent + 1 || along == p_along;
            bool next = u.end < p.end ? (odd ? node(u.end).x : node(u.end).y) == along + span
                                      : along + span == p_along + p_span;
            ok4 = ok4 && same && first && next;
        }
        if (u.cut == 4 && u.parent >= 0 && u.parent < i)
            ok5 = ok5 && (i == u.parent + 1 || u.end == node(u.parent).end);
        if (u.type == -2 && u.cut == 1) ok6 = ok6 && u.w >= in.min1 && u.w <= in.max1;
        if (u.type == -2 && u.cut == 2) ok6 = ok6 && u.h >= in.min2;
        if (u.type == -1) ok6 = ok6 && u.w >= in.minw && u.h >= in.minw;
        if (u.type == -3) ok6 = ok6 && u.w >= in.minw;
        if (u.type >= 0 && u.type < n_items) {
            ll iw = in.iw[static_cast<size_t>(u.type)], ih = in.ih[static_cast<size_t>(u.type)];
            ok7 = ok7 && ((u.w == iw && u.h == ih) || (u.w == ih && u.h == iw));
        }
    }
    bool ok8 = true;
    int items = 0;
    for (int i = 0; i < n; ++i) items += node(i).type >= 0 ? 1 : 0;
    for (int k = 0; k < n_items; ++k) {
        int at = a.item_node[static_cast<size_t>(k)];
        ok8 = ok8 && at >= 0 && at < n && node(at).type == k;
    }
    ok8 = ok8 && items == n_items;
    bool ok9 = true;
    for (const auto& s : in.stacks)
        for (size_t j = 1; j < s.size(); ++j)
            ok9 = ok9 && a.item_node[static_cast<size_t>(s[j - 1])] < a.item_node[static_cast<size_t>(s[j])];
    bool ok10 = true;
    int used = n > 0 ? node(n - 1).plate + 1 : 0;
    for (size_t d = 0; d < in.dx.size(); ++d) {
        int leaf = a.defect_leaf[d];
        bool named = leaf == -1 ||
                     (leaf >= 0 && leaf < n && node(leaf).plate == in.dplate[d] &&
                      (node(leaf).type == -1 || node(leaf).type == -3) && node(leaf).x <= in.dx[d] &&
                      in.dx[d] + in.dw[d] <= node(leaf).x + node(leaf).w && node(leaf).y <= in.dy[d] &&
                      in.dy[d] + in.dh[d] <= node(leaf).y + node(leaf).h);
        ok10 = ok10 && named && (in.dplate[d] >= used || leaf != -1);
    }
    ll area = 0;
    for (size_t k = 0; k < in.iw.size(); ++k) area += in.iw[k] * in.ih[k];
    ll residual = 0;
    if (n > 0 && node(n - 1).cut == 1 && (node(n - 1).type == -1 || node(n - 1).type == -3)) residual = node(n - 1).w;
    bool ok11 = a.n_plates == used && a.residual_w == residual &&
                a.geo_loss == a.n_plates * in.W * in.H - in.H * a.residual_w - area;
    bool oks[] = {true, ok2, ok3, ok4, ok5, ok6, ok7, ok8, ok9, ok10, ok11};
    for (int c = 0; c < 11; ++c)
        if (!oks[c]) broken.push_back(c + 1);
    return broken;
}

static void write_list(std::ostream& out, const char* key, const std::vector<ll>& values, bool first) {
    out << (first ? "" : ",") << '"' << key << "\":[";
    for (size_t i = 0; i < values.size(); ++i) out << (i ? "," : "") << values[i];
    out << ']';
}

static std::string emit(const Inst& in, const Layout& layout) {
    Answer a = build(in, layout);
    std::vector<int> broken = judge(in, a);
    std::ostringstream account;
    account << in.name << ": " << layout.placed.size() << " items on " << a.n_plates << " plates, residual "
            << a.residual_w << " mm, geo_loss " << a.geo_loss << " mm^2, " << a.nodes.size() << " nodes";
    if (broken.empty()) {
        account << "; all eleven conditions hold";
    } else {
        account << "; breaks condition";
        for (size_t c = 0; c < broken.size(); ++c) account << (c ? ", " : " ") << broken[c];
        account << ", emitted as it stands";
    }
    std::cerr << account.str() << "\n";
    std::ostringstream out;
    std::vector<ll> col;
    auto column = [&](auto field) {
        col.clear();
        for (const Node& v : a.nodes) col.push_back(static_cast<ll>(field(v)));
        return col;
    };
    out << '{';
    write_list(out, "plate", column([](const Node& v) { return v.plate; }), true);
    write_list(out, "cut", column([](const Node& v) { return v.cut; }), false);
    write_list(out, "type", column([](const Node& v) { return v.type; }), false);
    write_list(out, "x", column([](const Node& v) { return v.x; }), false);
    write_list(out, "y", column([](const Node& v) { return v.y; }), false);
    write_list(out, "w", column([](const Node& v) { return v.w; }), false);
    write_list(out, "h", column([](const Node& v) { return v.h; }), false);
    write_list(out, "parent", column([](const Node& v) { return v.parent; }), false);
    write_list(out, "end", column([](const Node& v) { return v.end; }), false);
    write_list(out, "item_node", std::vector<ll>(a.item_node.begin(), a.item_node.end()), false);
    write_list(out, "defect_leaf", std::vector<ll>(a.defect_leaf.begin(), a.defect_leaf.end()), false);
    out << ",\"n_plates\":" << a.n_plates << ",\"residual_w\":" << a.residual_w << ",\"geo_loss\":" << a.geo_loss
        << '}';
    return out.str();
}

int main(int argc, char** argv) {
    if (argc != 5 || std::strcmp(argv[3], "--seed") != 0) {
        std::cerr << "usage: candidate <input.json> <output.json> --seed N\n";
        return 64;
    }
    uint64_t seed = std::strtoull(argv[4], nullptr, 10);
    std::string text;
    {
        std::ifstream f(argv[1], std::ios::binary);
        if (!f) { std::cerr << "cannot read " << argv[1] << "\n"; return 65; }
        std::stringstream ss;
        ss << f.rdbuf();
        text = ss.str();
    }
    std::string result;
    try {
        Parser parser(text);
        Json root = parser.value();
        if (root.kind == Json::Array) {
            result = "[";
            for (size_t k = 0; k < root.items.size(); ++k) {
                Inst in = read_instance(root.items[k]);
                result += (k ? "," : "") + emit(in, solve(in, seed));
            }
            result += "]";
        } else {
            Inst in = read_instance(root);
            result = emit(in, solve(in, seed));
        }
    } catch (const std::exception& error) {
        std::cerr << "no answer: " << error.what() << "\n";
        return 70;
    }
    std::ofstream out(argv[2], std::ios::binary);
    if (!out) { std::cerr << "cannot write " << argv[2] << "\n"; return 73; }
    out << result << "\n";
    return 0;
}
