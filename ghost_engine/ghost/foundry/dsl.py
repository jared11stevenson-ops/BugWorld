"""Mechanic DSL: a whole two-player game concept as data. Integer-only, deterministic, portable to GDScript.

spec = {
  "id", "name",
  "vars":    [[name, init, min, max], ...]          per-player integer variables
  "actions": [{"name", "cond": expr|0, "fx": [effect,...]}, ...]   action 0 must have cond 0 (always legal)
  "passive": [effect,...]                           applied every round to each player (me = that player)
  "end":     [[expr, outcome], ...]                 evaluated per player (me); outcome 1 = me wins, -1 = me loses
  "tiebreak": var name or "",  "max_rounds": int,
  "value":   [[var, weight], ...]                   heuristic used by the adaptive agent (own - opponent)
}
expr   := int | ["v", "me"|"opp", var] | ["act", "me"|"opp"] | ["round"] | ["rnd", n]
        | [op, a, b] with op in + - * / min max > < >= <= == != && ||   | ["!", a] | ["?", c, a, b]
effect := ["+=", "me"|"opp", var, expr]          (deltas only: addition commutes, so resolution cannot favour a seat)
Resolution is simultaneous: every expression is evaluated on the pre-round snapshot, deltas are summed, THEN vars are clamped
(so overheal at a cap can absorb same-round damage; this is intended and documented, not a bug).
Restrictions (enforced by validate): no 'act' or 'rnd' inside action conds or end rules (conds see only own state, end rules are
deterministic); literals within +-1000; <=40 nodes per expression; <=400 nodes per spec. Arithmetic saturates at +-1e6."""
import copy, json
from ..kernel import rng as R

BIN = {"+", "-", "*", "/", "min", "max", ">", "<", ">=", "<=", "==", "!=", "&&", "||"}
MAX_ACTIONS = 6
SAT = 1000000
MAX_NODES_EXPR = 40
MAX_NODES_SPEC = 400


def sat(x):
    return SAT if x > SAT else (-SAT if x < -SAT else x)


def tdiv(a, b):
    """Truncating integer division (identical to GDScript's int /)."""
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


# ------------------------------------------------------------------ validation
def _nodes(e):
    if isinstance(e, list) and e:
        return 1 + sum(_nodes(x) for x in e[1:])
    return 1


def _contains(e, heads):
    if isinstance(e, list) and e:
        return e[0] in heads or any(_contains(x, heads) for x in e[1:])
    return False


def validate(spec):
    """Static checks. Returns list of problems (empty = valid). Never raises."""
    try:
        return _validate(spec)
    except Exception as ex:   # malformed input of any shape is a validation error, not a crash
        return [f"malformed spec: {ex!r}"]


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _validate(spec):
    errs = []
    if not isinstance(spec, dict):
        return ["spec must be an object"]
    for k, typ in (("vars", list), ("actions", list), ("passive", list), ("end", list), ("value", list)):
        if not isinstance(spec.get(k), typ):
            return [f"{k} must be a list"]
    if not isinstance(spec.get("tiebreak"), str) or not _is_int(spec.get("max_rounds")):
        return ["tiebreak must be a string and max_rounds an int"]
    if not isinstance(spec.get("name"), str):
        errs.append("name must be a string")
    names = []
    for v in spec["vars"]:
        if not (isinstance(v, list) and len(v) == 4 and isinstance(v[0], str) and all(_is_int(x) for x in v[1:]) and v[2] <= v[1] <= v[3]):
            errs.append(f"bad var {v}")
        else:
            names.append(v[0])
    if len(set(names)) != len(names) or not names:
        errs.append("vars must be unique and non-empty")
    acts = spec["actions"]
    if not 2 <= len(acts) <= MAX_ACTIONS:
        errs.append("need 2..6 actions")
    if not spec["end"]:
        errs.append("need at least one end rule")
    if spec["tiebreak"] and spec["tiebreak"] not in names:
        errs.append("tiebreak var unknown")
    if not 3 <= spec["max_rounds"] <= 60:
        errs.append("max_rounds out of range 3..60")
    for vt in spec["value"]:
        if not (isinstance(vt, list) and len(vt) == 2 and vt[0] in names and _is_int(vt[1]) and abs(vt[1]) <= 100):
            errs.append("bad value term")

    def chk(e, depth=0):
        if depth > 12:
            errs.append("expr too deep"); return
        if _is_int(e):
            if abs(e) > 1000:
                errs.append(f"literal {e} out of +-1000")
            return
        if not isinstance(e, list) or not e or not isinstance(e[0], str):
            errs.append(f"bad expr {e!r}"); return
        h = e[0]
        if h == "v":
            if len(e) != 3 or e[1] not in ("me", "opp") or e[2] not in names:
                errs.append(f"bad var ref {e}")
        elif h == "act":
            if len(e) != 2 or e[1] not in ("me", "opp"):
                errs.append(f"bad act ref {e}")
        elif h == "round":
            pass
        elif h == "rnd":
            if len(e) != 2 or not _is_int(e[1]) or not 1 <= e[1] <= 100:
                errs.append(f"bad rnd {e}")
        elif h in BIN:
            if len(e) != 3:
                errs.append(f"bad arity {e}")
            else:
                chk(e[1], depth + 1); chk(e[2], depth + 1)
        elif h == "!":
            chk(e[1], depth + 1) if len(e) == 2 else errs.append("bad !")
        elif h == "?":
            if len(e) != 4:
                errs.append("bad ?")
            else:
                for x in e[1:]:
                    chk(x, depth + 1)
        else:
            errs.append(f"unknown op {h!r}")

    total = [0]
    def budget(e):
        n = _nodes(e)
        total[0] += n
        if n > MAX_NODES_EXPR:
            errs.append(f"expression has {n} nodes (max {MAX_NODES_EXPR})")

    def chk_fx(fx):
        if not isinstance(fx, list):
            errs.append("fx must be a list"); return
        for f in fx:
            if not (isinstance(f, list) and len(f) == 4) or f[0] != "+=" or f[1] not in ("me", "opp") or f[2] not in names:
                errs.append(f"bad effect {f} (only '+=' deltas are allowed)")
            else:
                chk(f[3]); budget(f[3])
    for a in acts:
        if not isinstance(a, dict):
            errs.append("action must be an object"); continue
        if not isinstance(a.get("name"), str) or not a.get("name"):
            errs.append("action needs a string name")
        if "cond" not in a or "fx" not in a:
            errs.append("action needs cond and fx"); continue
        chk(a["cond"]); budget(a["cond"]); chk_fx(a["fx"])
        if _contains(a["cond"], ("act", "rnd")):
            errs.append("action cond may not use 'act' or 'rnd'")
    if acts and isinstance(acts[0], dict) and acts[0].get("cond") != 0:
        errs.append("action 0 must be always legal (cond 0)")
    chk_fx(spec["passive"])
    for er in spec["end"]:
        if not (isinstance(er, list) and len(er) == 2) or er[1] not in (1, -1):
            errs.append("end rule must be [expr, 1|-1]"); continue
        chk(er[0]); budget(er[0])
        if _contains(er[0], ("rnd",)):
            errs.append("end rules may not use 'rnd'")
    if total[0] > MAX_NODES_SPEC:
        errs.append(f"spec has {total[0]} expression nodes (max {MAX_NODES_SPEC})")
    return errs


# ------------------------------------------------------------------ static relevance (which vars/actions can affect the result)
def _reads(e, out):
    if isinstance(e, list) and e:
        if e[0] == "v":
            out.add(e[2])
        for x in e[1:]:
            _reads(x, out)


def _has_act(e):
    return isinstance(e, list) and e and (e[0] == "act" or any(_has_act(x) for x in e[1:]))


def _act_dependent(spec, R):
    """True if any effect that writes a result-relevant var reads the chosen actions (['act', ...]):
    then the *identity* of the chosen action matters even if that action writes nothing itself."""
    fxs = [f for a in spec["actions"] for f in a["fx"]] + list(spec["passive"])
    return any(f[2] in R and _has_act(f[3]) for f in fxs)


def relevant_vars(spec):
    """Fixpoint: vars read by end rules / tiebreak, plus everything that feeds an effect writing a relevant var."""
    R = set()
    for e, _o in spec["end"]:
        _reads(e, R)
    if spec["tiebreak"]:
        R.add(spec["tiebreak"])
    changed = True
    while changed:
        changed = False
        before = len(R)
        for a in spec["actions"]:
            for f in a["fx"]:
                if f[2] in R:
                    _reads(f[3], R); _reads(a["cond"], R)
        for f in spec["passive"]:
            if f[2] in R:
                _reads(f[3], R)
        if _act_dependent(spec, R):
            for a in spec["actions"]:
                _reads(a["cond"], R)          # legality gates which action indices are reachable
        changed = len(R) != before
    return R


def inert_actions(spec):
    """Actions that cannot influence the result: they write no relevant var AND no relevant effect reads action identity."""
    R = relevant_vars(spec)
    if _act_dependent(spec, R):
        return []
    return [i for i, a in enumerate(spec["actions"]) if not any(f[2] in R for f in a["fx"])]


# ------------------------------------------------------------------ evaluation
def new_match(spec, seed):
    return {"p": [{v[0]: v[1] for v in spec["vars"]} for _ in range(2)], "round": 0, "rng": R.seed_state(seed),
            "done": 0, "winner": -1, "timeout": 0, "acts": [[], []], "last": [-1, -1]}


def ev(e, m, me, acts, mode):
    """mode 0 = rolled (consumes RNG), 1 = expected (rnd -> n//2, no RNG)."""
    if isinstance(e, int):
        return e
    h = e[0]
    if h == "v":
        return m["p"][me if e[1] == "me" else 1 - me][e[2]]
    if h == "act":
        return acts[me if e[1] == "me" else 1 - me]
    if h == "round":
        return m["round"]
    if h == "rnd":
        return R.rand(m, e[1]) if mode == 0 else e[1] // 2
    if h == "!":
        return 0 if ev(e[1], m, me, acts, mode) else 1
    if h == "?":
        return ev(e[2], m, me, acts, mode) if ev(e[1], m, me, acts, mode) else ev(e[3], m, me, acts, mode)
    a = ev(e[1], m, me, acts, mode)
    if h == "&&":
        return 1 if (a and ev(e[2], m, me, acts, mode)) else 0
    if h == "||":
        return 1 if (a or ev(e[2], m, me, acts, mode)) else 0
    b = ev(e[2], m, me, acts, mode)
    if h == "+": return sat(a + b)
    if h == "-": return sat(a - b)
    if h == "*": return sat(a * b)
    if h == "/": return tdiv(a, b)
    if h == "min": return min(a, b)
    if h == "max": return max(a, b)
    if h == ">": return 1 if a > b else 0
    if h == "<": return 1 if a < b else 0
    if h == ">=": return 1 if a >= b else 0
    if h == "<=": return 1 if a <= b else 0
    if h == "==": return 1 if a == b else 0
    return 1 if a != b else 0


def legal(spec, m, me, a):
    c = spec["actions"][a]["cond"]
    return c == 0 or ev(c, m, me, [0, 0], 1) != 0


def sanitize(spec, m, me, a):
    return a if 0 <= a < len(spec["actions"]) and legal(spec, m, me, a) else 0


def _pending(spec, m, acts, mode):
    out = []
    for me in (0, 1):
        for f in spec["actions"][acts[me]]["fx"]:
            out.append((f[0], me if f[1] == "me" else 1 - me, f[2], ev(f[3], m, me, acts, mode)))
    for me in (0, 1):
        for f in spec["passive"]:
            out.append((f[0], me if f[1] == "me" else 1 - me, f[2], ev(f[3], m, me, acts, mode)))
    return out


def _apply(spec, m, pend):
    for op, who, var, val in pend:
        m["p"][who][var] = sat(m["p"][who][var] + val)
    for v in spec["vars"]:
        for who in (0, 1):
            m["p"][who][v[0]] = max(v[2], min(v[3], m["p"][who][v[0]]))


def value(spec, m, me):
    t = 0
    for vn, w in spec["value"]:
        t += w * (m["p"][me][vn] - m["p"][1 - me][vn])
    return t


def payoff(spec, m, me, a, b):
    """Expected one-round heuristic swing for `me` choosing a vs opponent b (no RNG consumed, state untouched)."""
    acts = [0, 0]
    acts[me], acts[1 - me] = a, b
    sim = {"p": [dict(m["p"][0]), dict(m["p"][1])], "round": m["round"], "rng": 0}
    _apply(spec, sim, _pending(spec, sim, acts, 1))
    return value(spec, sim, me) - value(spec, m, me)


def step(spec, m, a0, a1):
    """One simultaneous round. Returns the sanitized (a0, a1)."""
    acts = [sanitize(spec, m, 0, a0), sanitize(spec, m, 1, a1)]
    _apply(spec, m, _pending(spec, m, acts, 0))
    for i in (0, 1):
        m["acts"][i].append(acts[i])
        m["last"][i] = acts[i]
    m["round"] += 1
    res = [0, 0]
    hit = 0
    for me in (0, 1):
        for e, o in spec["end"]:
            if ev(e, m, me, acts, 1) != 0:
                res[me] = o
                hit = 1
                break
    if hit:
        t = res[0] - res[1]
        m["done"] = 1
        m["winner"] = 0 if t > 0 else (1 if t < 0 else -1)
    elif m["round"] >= spec["max_rounds"]:
        m["done"] = 1
        m["timeout"] = 1
        tb = spec["tiebreak"]
        if tb and m["p"][0][tb] != m["p"][1][tb]:
            m["winner"] = 0 if m["p"][0][tb] > m["p"][1][tb] else 1
    return acts


def match_digest(spec, m):
    parts = [m["round"], m["winner"], m["timeout"], m["rng"]]
    for who in (0, 1):
        for v in spec["vars"]:
            parts.append(m["p"][who][v[0]])
        parts += m["acts"][who]
    return R.fnv32_str(",".join(str(x) for x in parts))


def clone_match(m):
    return copy.deepcopy(m)


# ------------------------------------------------------------------ human-readable rules
def expr_text(e):
    if isinstance(e, int):
        return str(e)
    h = e[0]
    if h == "v":
        return ("my " if e[1] == "me" else "their ") + e[2]
    if h == "act":
        return ("my" if e[1] == "me" else "their") + " action"
    if h == "round":
        return "round"
    if h == "rnd":
        return f"d{e[1]}"
    if h == "!":
        return f"not({expr_text(e[1])})"
    if h == "?":
        return f"({expr_text(e[1])} ? {expr_text(e[2])} : {expr_text(e[3])})"
    if h in ("min", "max"):
        return f"{h}({expr_text(e[1])}, {expr_text(e[2])})"
    return f"({expr_text(e[1])} {h} {expr_text(e[2])})"


def fx_text(f):
    who = "my" if f[1] == "me" else "their"
    return f"{who} {f[2]} {'+=' if f[0] == '+=' else '='} {expr_text(f[3])}"


def spec_text(spec):
    L = [f"{spec['name']}: " + ", ".join(f"{v[0]} {v[1]} [{v[2]}..{v[3]}]" for v in spec["vars"])]
    for i, a in enumerate(spec["actions"]):
        c = "" if a["cond"] == 0 else f" only if {expr_text(a['cond'])}"
        L.append(f"  [{i}] {a['name']}{c}: " + "; ".join(fx_text(f) for f in a["fx"]))
    if spec["passive"]:
        L.append("  each round: " + "; ".join(fx_text(f) for f in spec["passive"]))
    L.append("  ends: " + "; ".join(f"{expr_text(e)} => {'I win' if o == 1 else 'I lose'}" for e, o in spec["end"])
             + f"; after {spec['max_rounds']} rounds higher '{spec['tiebreak']}' wins")
    return "\n".join(L)


def spec_hash(spec):
    s = dict(spec)
    s.pop("id", None); s.pop("name", None)
    return "%08x" % R.fnv32_str(json.dumps(s, sort_keys=True))
