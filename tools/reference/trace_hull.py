"""Silhouette-carve Aruun's body from the reference planes (no interpretation: the outline IS the art).

front plane -> X extent at every height z   (mace carved out; it is built separately)
side  plane -> Y extent at every height z
Each (front run) x (side run) pair at height z becomes a rounded cross-section (super-ellipse, n=2.4), so the
model's front and side silhouettes reproduce the drawings; only the depth *inside* the outline is inferred.

Run: python3 -I tools/reference/trace_hull.py  ->  assets/models/aruun_hull.npz (verts, faces) + aruun_mace.json + IoU check
Needs: numpy, pillow, scipy, scikit-image
"""
import json, os
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, gaussian_filter1d, binary_opening
from skimage.measure import marching_cubes

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "references", "aruun"); OUT = os.path.join(ROOT, "assets", "models"); os.makedirs(OUT, exist_ok=True)
PX = 0.002; CX0, GROUND = 800, 1250            # canvas: x=0 at col 800, z=0 at row 1250 (see extract_refs.py)
V = 0.006                                       # voxel size, m
XR, YR, ZR = (-0.80, 0.80), (-0.55, 0.55), (0.0, 2.44)
N_EXP = 2.4

def alpha(name): return np.asarray(Image.open(os.path.join(REF, f"aruun_{name}.png")).getchannel("A")) > 100
F, S = alpha("front"), alpha("side")

# ---- carve the mace out of the front silhouette (ball + haft, measured on the cut-out; hand stays) ----
ball_c, ball_r = (279, 1075), 205              # px, includes spikes + the knob cluster at the haft base
haft_a, haft_b, haft_hw = (300, 950), (462, 806), 30
jj, ii = np.mgrid[0:F.shape[0], 0:F.shape[1]]
mace = (ii - ball_c[0]) ** 2 + (jj - ball_c[1]) ** 2 < ball_r ** 2
ax, ay, bx, by = *haft_a, *haft_b; t = np.clip(((ii - ax) * (bx - ax) + (jj - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2), 0, 1)
mace |= (ii - (ax + t * (bx - ax))) ** 2 + (jj - (ay + t * (by - ay))) ** 2 < (haft_hw * (1.9 - 0.9 * t)) ** 2   # fatter near the ball (rope + knobs)
mace |= (ii < 470) & (jj > 826) & (jj < 1060)     # knob cluster / rope where the haft meets the ball (cape starts right of x=470)
F_body = F & ~mace

xs = np.arange(XR[0], XR[1], V) + V / 2; ys = np.arange(YR[0], YR[1], V) + V / 2; zs = np.arange(ZR[0], ZR[1], V) + V / 2
def sample_front(m):   # [z, x]
    c = np.clip((CX0 + xs / PX).astype(int), 0, m.shape[1] - 1)[None, :]; r = np.clip((GROUND - zs / PX).astype(int), 0, m.shape[0] - 1)[:, None]; return m[r, c]
def sample_side(m):    # [z, y]   side image: right = -Y
    c = np.clip((CX0 - ys / PX).astype(int), 0, m.shape[1] - 1)[None, :]; r = np.clip((GROUND - zs / PX).astype(int), 0, m.shape[0] - 1)[:, None]; return m[r, c]
def soften(m, sigma_px=3.0):      # remove 2 mm pixel jitter from the drawn edge so the carve has no horizontal ledges (<6 mm change)
    return gaussian_filter(m.astype(np.float32), sigma_px) > 0.5
def thin_free(m, k):   # drop protrusions thinner than ~k voxels (cords, tassels, hair tufts would extrude into full-width planks)
    return binary_opening(m, structure=np.ones((k, k), bool))
MF, MS = thin_free(sample_front(soften(F_body)), 4), thin_free(sample_side(soften(S)), 4)

def runs_center_half(row):
    """per-sample centre and half-width of the run it belongs to (0 outside)"""
    c = np.zeros(row.size); h = np.zeros(row.size); i = 0
    while i < row.size:
        if row[i]:
            j = i
            while j + 1 < row.size and row[j + 1]: j += 1
            c[i:j + 1] = (i + j) / 2; h[i:j + 1] = (j - i + 1) / 2 + 0.5; i = j + 1
        else: i += 1
    return c, h
CXs = np.zeros(MF.shape); HXs = np.zeros(MF.shape); CYs = np.zeros(MS.shape); HYs = np.zeros(MS.shape)
for k in range(len(zs)):
    CXs[k], HXs[k] = runs_center_half(MF[k]); CYs[k], HYs[k] = runs_center_half(MS[k])

HULL_MODE = os.environ.get("HULL_MODE", "ellipse")
def zsmooth(Cv, Hv, sigma=3.0):
    """smooth the per-height run centre / half-width along z (normalised convolution, so empty rows don't drag values to 0)"""
    m = (Hv > 0).astype(np.float32); den = gaussian_filter1d(m, sigma, axis=0, mode="nearest") + 1e-6
    Cs = gaussian_filter1d(Cv * m, sigma, axis=0, mode="nearest") / den; Hs = gaussian_filter1d(Hv * m, sigma, axis=0, mode="nearest") / den
    return np.where(m > 0, Cs, 0), np.where(m > 0, np.maximum(Hs, 1.0), 0)
if HULL_MODE == "ellipse":
    CXs, HXs = zsmooth(CXs, HXs); CYs, HYs = zsmooth(CYs, HYs)
occ = np.zeros((len(xs), len(ys), len(zs)), bool)
if HULL_MODE == "box":
    occ = MF.T[:, None, :] & MS.T[None, :, :]                     # [x, y, z]: front mask extruded along Y  AND  side mask extruded along X
else:
    ix = np.arange(len(xs)); iy = np.arange(len(ys))
    for k in range(len(zs)):
        if not (MF[k].any() and MS[k].any()): continue
        u = np.abs((ix - CXs[k]) / np.maximum(HXs[k], 1e-6)); u[HXs[k] == 0] = 9
        v = np.abs((iy - CYs[k]) / np.maximum(HYs[k], 1e-6)); v[HYs[k] == 0] = 9
        occ[:, :, k] = (u[:, None] ** N_EXP + v[None, :] ** N_EXP) <= 1.0

occ[:, :, zs > 2.13] = False        # horns above the skull are rebuilt as round tubes in Blender (a carve makes them flat slabs)

# ---- silhouette check: project the carve back and compare with the drawings ----
pf = occ.any(1).T; ps = occ.any(0).T   # [z,x], [z,y]
iou = lambda a, b: float((a & b).sum() / max((a | b).sum(), 1))
print("IoU front", round(iou(pf, MF), 4), " side", round(iou(ps, MS), 4))

field = gaussian_filter(occ.astype(np.float32), (2.4, 2.4, 1.6) if HULL_MODE == 'box' else (1.0, 1.0, 1.4))
verts, faces, _, _ = marching_cubes(field, 0.5, spacing=(V, V, V))
verts += np.array([XR[0], YR[0], ZR[0]])
verts = verts.astype(np.float32); faces = faces[:, ::-1].astype(np.int32)   # outward normals for Blender winding
np.savez_compressed(os.path.join(OUT, "aruun_hull.npz"), verts=verts, faces=faces)
print("verts", len(verts), "faces", len(faces), "bbox", verts.min(0).round(3), verts.max(0).round(3))

# ---- read the mace's drawn spikes straight off the silhouette (radial profile around the ball centre) ----
cx, cy = ball_c; prof = np.zeros(360)
for a_ in range(360):
    ang = np.radians(a_); r_ = 0; miss = 0
    while r_ < 280:
        px_, py_ = int(round(cx + r_ * np.cos(ang))), int(round(cy - r_ * np.sin(ang)))   # +angle = up (z)
        if 0 <= px_ < F.shape[1] and 0 <= py_ < F.shape[0] and F[py_, px_]: miss = 0; last = r_
        else:
            miss += 1
            if miss > 4: break
        r_ += 1
    prof[a_] = last if r_ else 0
valid = prof < 232                                   # rays that run into the haft / hand are not ball
r_med = float(np.median(prof[valid & (prof > 100)]))
sm = np.convolve(np.r_[prof[-3:], prof, prof[:3]], np.ones(5) / 5, "valid")
spikes = []
for a_ in range(360):
    win = [sm[(a_ + k) % 360] for k in range(-5, 6)]
    if valid[a_] and sm[a_] == max(win) and sm[a_] - r_med > 7 and sm[a_] < 232: spikes.append(dict(angle_deg=a_, tip_r=round(float(sm[a_]) * PX, 4)))
print("ball body r px", round(r_med, 1), "spikes found", len(spikes))

# ---- mace parameters in metres (ball centre, radius incl. spikes, grip) for the Blender builder ----
mp = lambda px, py: [round((px - CX0) * PX, 4), round((GROUND - py) * PX, 4)]
json.dump(dict(ball_center_xz=mp(*ball_c), ball_radius_incl_spikes=round(190 * PX, 4), ball_body_radius=round(r_med * PX, 4), spikes=spikes,
               haft_from_xz=mp(*haft_a), grip_xz=mp(480, 800)), open(os.path.join(OUT, "aruun_mace.json"), "w"), indent=1)
print(open(os.path.join(OUT, "aruun_mace.json")).read())
