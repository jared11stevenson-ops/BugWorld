"""Fit Aruun's joint positions and bone/ellipsoid thicknesses to the front + side silhouettes (numpy only).
Every bone/ellipsoid projects to a 2D tapered capsule / ellipse in each view, so the union silhouette is rasterised directly
and the parameters are tuned by coordinate descent to maximise IoU(front)+IoU(side). Writes tools/blender/aruun_spec_fit.json.
Run: python3 -I tools/reference/fit_silhouette.py"""
import json, os, sys, math, copy, time
import numpy as np
from PIL import Image, ImageDraw
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "blender")); import aruun_spec as S
REF = os.path.join(ROOT, "references", "aruun")
STEP = 0.008
XF = np.arange(-1.50, 0.75, STEP); YS = np.arange(-0.60, 0.60, STEP); ZZ = np.arange(0.0, 2.52, STEP)
def ref_mask(name, axis):
    a = np.asarray(Image.open(os.path.join(REF, f"aruun_{name}.png")).getchannel("A")) > 100
    if axis == "x": cols = np.clip((800 + XF / 0.002).astype(int), 0, 1599)
    else: cols = np.clip((800 - YS / 0.002).astype(int), 0, 1599)
    rows = np.clip((1250 - ZZ / 0.002).astype(int), 0, 1299)
    # area-average so thin features survive: sample a 4x4 px neighbourhood
    out = np.zeros((len(ZZ), len(cols)), np.float32)
    for dr in range(0, 4):
        for dc in range(0, 4):
            out += a[np.clip(rows + dr - 2, 0, 1299)][:, np.clip(cols + dc - 2, 0, 1599)]
    return (out / 16) > 0.35
RF, RS = ref_mask("front", "x"), ref_mask("side", "y")
# the side drawing has no mace: it is only ever scored against front-view parts in the front view
GX, GZf = np.meshgrid(XF, ZZ); GY, GZs = np.meshgrid(YS, ZZ)

def capsule(mask, G1, G2, p0, p1, r0, r1):
    d = np.array(p1) - np.array(p0); L2 = float(d @ d)
    t = np.clip(((G1 - p0[0]) * d[0] + (G2 - p0[1]) * d[1]) / max(L2, 1e-9), 0, 1)
    cx, cz = p0[0] + t * d[0], p0[1] + t * d[1]; r = r0 + (r1 - r0) * t
    mask |= ((G1 - cx) ** 2 + (G2 - cz) ** 2) <= r * r

def poly_mask(shape, pts, xs, zs):
    im = Image.new("L", (len(xs), len(zs)), 0); d = ImageDraw.Draw(im)
    px = [((x - xs[0]) / STEP, (zs[-1] - z) / STEP) for x, z in pts]; d.polygon(px, fill=1)
    return np.asarray(im)[::-1] > 0   # rows ascend with z

def cape_poly(c, jag=True):
    pts = [(c["xtl"], c["ztop"]), (c["xtr"], c["ztop"])]
    n = c["teeth"] * 2
    for k in range(n + 1):
        f = 1 - k / n; x = c["xbl"] + (c["xbr"] - c["xbl"]) * f
        z = c["zbot"] + (c["jag"] if k % 2 else 0.0) * 0.7
        pts.append((x, z))
    return pts

def render(spec):
    mf = np.zeros(RF.shape, bool); ms = np.zeros(RS.shape, bool)
    P = lambda j: S.pos(spec, j)
    for name, a, b, ra, rb, mat, base, view in spec["B"]:
        A, Bp = P(a), P(b)
        capsule(mf, GX, GZf, (A[0], A[2]), (Bp[0], Bp[2]), ra[0], rb[0])
        if view == "both": capsule(ms, GY, GZs, (A[1], A[2]), (Bp[1], Bp[2]), ra[1], rb[1])
    for name, c, r, mat, base, view in spec["E"]:
        C = P(c)
        mf |= ((GX - C[0]) / r[0]) ** 2 + ((GZf - C[2]) / r[2]) ** 2 <= 1
        if view == "both": ms |= ((GY - C[1]) / r[1]) ** 2 + ((GZs - C[2]) / r[2]) ** 2 <= 1
    for key in ("CAPE", "MANTLE"):
        c = spec[key]; mf |= poly_mask(mf.shape, cape_poly(c), XF, ZZ)
        ms[(ZZ >= c["zbot"])[:, None] & (ZZ <= c["ztop"])[:, None] & (YS >= c["y"][0])[None, :] & (YS <= c["y"][1])[None, :]] = True
    return mf, ms
def iou(a, b): return float((a & b).sum() / max((a | b).sum(), 1))
def score(spec):
    mf, ms = render(spec); return iou(mf, RF) + iou(ms, RS), mf, ms

# ---- parameter handles ----
def handles(spec):
    H = []   # (getter, setter, kind, lo, hi)
    for j, v in spec["J"].items():
        if v[0] == "lerp" or j in ("mace",): continue
        for ax in range(3):
            H.append((f"J.{j}.{'xyz'[ax]}", ("J", j, ax), "pos", v[ax] - 0.07, v[ax] + 0.07))
    for i, b in enumerate(spec["B"]):
        if not (b[6] or b[0].startswith("Neck")): continue          # armour / horns / mace keep their designed thickness
        for k, which in ((3, "a"), (4, "b")):
            for ax in range(2):
                H.append((f"B.{b[0]}.{which}{'xy'[ax]}", ("B", i, k, ax), "rad", b[k][ax] * 0.70, b[k][ax] * 1.7))
    for i, e in enumerate(spec["E"]):
        if not e[4]: continue                                         # only dark carapace ellipsoids are refit
        for ax in range(3): H.append((f"E.{e[0]}.{'xyz'[ax]}", ("E", i, 2, ax), "rad", e[2][ax] * 0.70, e[2][ax] * 1.7))
    for key in ("CAPE", "MANTLE"):
        for kk in ("ztop", "zbot", "xtl", "xtr", "xbl", "xbr"):
            H.append((f"{key}.{kk}", (key, kk), "pos", spec[key][kk] - 0.15, spec[key][kk] + 0.15))
    return H
def get(spec, p):
    if p[0] == "J": return spec["J"][p[1]][p[2]]
    if p[0] == "B": return spec["B"][p[1]][p[2]][p[3]]
    if p[0] == "E": return spec["E"][p[1]][p[2]][p[3]]
    return spec[p[0]][p[1]]
def put(spec, p, v):
    if p[0] == "J": spec["J"][p[1]][p[2]] = v
    elif p[0] == "B": t = list(spec["B"][p[1]][p[2]]); t[p[3]] = v; spec["B"][p[1]][p[2]] = tuple(t)
    elif p[0] == "E": t = list(spec["E"][p[1]][p[2]]); t[p[3]] = v; spec["E"][p[1]][p[2]] = tuple(t)
    else: spec[p[0]][p[1]] = v

def main():
    spec = S.load(use_fit=False); H = handles(spec); base = copy.deepcopy(spec)
    best, _, _ = score(spec); print("start", round(best, 4), "params", len(H))
    LAM = 0.02
    def reg(spec):
        s = 0.0
        for name, p, kind, lo, hi in H:
            v0, v = get(base, p), get(spec, p)
            s += ((v - v0) / 0.10) ** 2 if kind == "pos" else (math.log(max(v, 1e-4) / max(v0, 1e-4))) ** 2
        return LAM * s / len(H)
    cur = best - reg(spec); t0 = time.time()
    for rnd, (dp, mr) in enumerate([(0.04, 1.20), (0.02, 1.10), (0.01, 1.05), (0.005, 1.025), (0.0025, 1.012)]):
        improved = 0
        for name, p, kind, lo, hi in H:
            v0 = get(spec, p)
            for cand in ((v0 + dp, v0 - dp) if kind == "pos" else (v0 * mr, v0 / mr)):
                cand = min(max(cand, lo), hi)
                if cand == v0: continue
                put(spec, p, cand); sc_, _, _ = score(spec); sc_ -= reg(spec)
                if sc_ > cur + 1e-6: cur, v0 = sc_, cand; improved += 1
                else: put(spec, p, v0)
        s2, mf, ms = score(spec)
        print(f"round {rnd}: IoU front+side = {s2:.4f}  (front {iou(mf, RF):.3f}, side {iou(ms, RS):.3f})  accepted {improved}  {time.time() - t0:.0f}s", flush=True)
    s2, mf, ms = score(spec)
    out = dict(J={k: v for k, v in spec["J"].items() if v[0] != "lerp"}, B=[[list(b[3]), list(b[4])] for b in spec["B"]], E=[list(e[2]) for e in spec["E"]], CAPE=spec["CAPE"], MANTLE=spec["MANTLE"])
    json.dump(out, open(S.FIT_PATH, "w"), indent=1)
    for nm, m, r in (("front", mf, RF), ("side", ms, RS)):
        ov = np.zeros(m.shape + (3,), np.uint8); ov[m & r] = (0, 200, 0); ov[m & ~r] = (255, 0, 0); ov[r & ~m] = (0, 0, 255)
        Image.fromarray(ov[::-1]).resize((ov.shape[1] * 3, ov.shape[0] * 3), Image.NEAREST).save(os.path.join(ROOT, "evidence", "models", f"fit2_overlay_{nm}.png"))
    print("saved", S.FIT_PATH)
main()
