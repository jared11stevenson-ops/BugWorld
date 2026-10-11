"""Aruun body spec: joints, bones (elliptical tapered capsules), ellipsoids, cape panel.
Pure python (no bpy) so the silhouette fitter and the Blender builder share one source of truth.
Metres, +Z up, character faces -Y; front view: +X = image right.
Each bone/ellipsoid has `view`: "both" (counts in front+side silhouette), "front" (mace: not in the side drawing).
`base`=True parts are merged into the one continuous dark carapace body; others are coloured armour shells.
fit_silhouette.py writes aruun_spec_fit.json (joint positions + radii); load() merges it over these defaults."""
import json, os, copy

J = {  # explicit joints [x, y, z]; ["lerp", A, B, t] = derived
    "pelvis": [0.06, -0.03, 1.02], "abdomen": [0.04, -0.10, 1.28], "chest": [0.05, -0.12, 1.56], "hump": [0.04, 0.0, 1.63],
    "neck0": [0.05, -0.06, 1.70], "neck1": [0.04, -0.08, 1.82], "neck2": [-0.02, -0.10, 1.92], "neck3": [-0.07, -0.12, 1.99],
    "skull": [-0.11, -0.12, 2.06], "beak0": [-0.12, -0.17, 2.05], "beak1": [-0.20, -0.31, 1.93],
    "h0": [-0.12, -0.10, 2.12], "h1": [-0.11, -0.16, 2.26], "h2": [-0.05, -0.27, 2.35], "h3": [0.08, -0.40, 2.39],
    "f0": [-0.20, -0.10, 2.12], "f1": [-0.25, -0.18, 2.22], "f2": [-0.26, -0.26, 2.30], "f3": [-0.22, -0.32, 2.33],
    "Rsh": [0.36, 0.03, 1.60], "Rel": [0.38, 0.06, 1.24], "Rwr": [0.36, 0.07, 0.96], "Rhand": [0.36, 0.07, 0.88], "Rpaul": [0.34, 0.02, 1.68],
    "Lsh": [-0.27, 0.0, 1.58], "Lel": [-0.24, -0.02, 1.28], "Lwr": [-0.50, -0.08, 0.95], "Lhand": [-0.52, -0.08, 0.90], "Lpaul": [-0.27, 0.0, 1.60],
    "Rhip": [0.17, -0.02, 1.0], "Rknee": [0.26, -0.10, 0.62], "Rank": [0.38, 0.10, 0.24], "Rtoe": [0.41, -0.06, 0.07], "Rtip": [0.43, -0.28, 0.05],
    "Lhip": [-0.12, -0.02, 1.0], "Lknee": [-0.28, -0.10, 0.58], "Lank": [-0.22, 0.09, 0.22], "Ltoe": [-0.28, -0.10, 0.07], "Ltip": [-0.38, -0.28, 0.05],
    "mace": [-1.042, -0.08, 0.35], "grip": [-0.52, -0.08, 0.93], "haft0": [-0.84, -0.08, 0.57],
    "mane_a": [-0.02, 0.0, 2.04], "mane_b": [-0.30, 0.0, 2.04],
}
# bones: name, a, b, (rx,ry) at a, (rx,ry) at b, material, base?, view
B = [
    ("Neck0", "neck0", "neck1", (0.080, 0.075), (0.066, 0.062), "orange", False, "both"),
    ("Neck1", "neck1", "neck2", (0.066, 0.062), (0.056, 0.052), "orange", False, "both"),
    ("Neck2", "neck2", "neck3", (0.056, 0.052), (0.050, 0.046), "orange", False, "both"),
    ("Beak", "beak0", "beak1", (0.058, 0.058), (0.016, 0.016), "red", False, "both"),
    ("HornMain0", "h0", "h1", (0.030, 0.030), (0.024, 0.024), "red", False, "both"), ("HornMain1", "h1", "h2", (0.024, 0.024), (0.016, 0.016), "red", False, "both"), ("HornMain2", "h2", "h3", (0.016, 0.016), (0.006, 0.006), "red", False, "both"),
    ("HornFork0", "f0", "f1", (0.026, 0.026), (0.021, 0.021), "red", False, "both"), ("HornFork1", "f1", "f2", (0.021, 0.021), (0.015, 0.015), "red", False, "both"), ("HornFork2", "f2", "f3", (0.015, 0.015), (0.006, 0.006), "red", False, "both"),
    ("ManeA", "skull", "mane_a", (0.03, 0.03), (0.004, 0.004), "mane", False, "both"), ("ManeB", "skull", "mane_b", (0.03, 0.03), (0.004, 0.004), "mane", False, "both"),
    ("UpperArm_R", "Rsh", "Rel", (0.085, 0.085), (0.07, 0.07), "carapace", True, "both"), ("Forearm_R", "Rel", "Rwr", (0.075, 0.075), (0.055, 0.055), "carapace", True, "both"),
    ("UpperArm_L", "Lsh", "Lel", (0.085, 0.085), (0.07, 0.07), "carapace", True, "both"), ("Forearm_L", "Lel", "Lwr", (0.075, 0.075), (0.055, 0.055), "carapace", True, "both"),
    ("Thigh_R", "Rhip", "Rknee", (0.17, 0.15), (0.12, 0.11), "carapace", True, "both"), ("Shin_R", "Rknee", "Rank", (0.115, 0.10), (0.066, 0.06), "carapace", True, "both"), ("Meta_R", "Rank", "Rtoe", (0.07, 0.06), (0.06, 0.05), "carapace", True, "both"),
    ("Thigh_L", "Lhip", "Lknee", (0.17, 0.15), (0.12, 0.11), "carapace", True, "both"), ("Shin_L", "Lknee", "Lank", (0.115, 0.10), (0.066, 0.06), "carapace", True, "both"), ("Meta_L", "Lank", "Ltoe", (0.07, 0.06), (0.06, 0.05), "carapace", True, "both"),
    ("Foot_R", "Rtoe", "Rtip", (0.10, 0.05), (0.07, 0.04), "cream", False, "both"), ("Foot_L", "Ltoe", "Ltip", (0.10, 0.05), (0.07, 0.04), "cream", False, "both"),
    ("Haft", "grip", "haft0", (0.034, 0.034), (0.03, 0.03), "brown", False, "front"), ("Haft1", "haft0", "mace", (0.03, 0.03), (0.03, 0.03), "brown", False, "front"),
]
# ellipsoids: name, centre (joint name or [x,y,z]), (rx,ry,rz), material, base?, view
E = [
    ("Pelvis", "pelvis", (0.26, 0.15, 0.17), "carapace", True, "both"), ("Abdomen", "abdomen", (0.15, 0.13, 0.21), "cream", False, "both"),
    ("Chest", "chest", (0.27, 0.16, 0.21), "carapace", True, "both"), ("Hump", "hump", (0.24, 0.12, 0.19), "carapace", True, "both"),
    ("Skull", "skull", (0.075, 0.105, 0.068), "carapace", True, "both"),
    ("Pauldron_R", "Rpaul", (0.12, 0.11, 0.11), "red", False, "both"), ("Pauldron_L", "Lpaul", (0.11, 0.11, 0.10), "red", False, "both"),
    ("Hand_R", "Rhand", (0.07, 0.065, 0.085), "carapace", True, "both"), ("Hand_L", "Lhand", (0.07, 0.07, 0.07), "carapace", True, "both"),
    ("Knee_R", "Rknee", (0.11, 0.11, 0.11), "carapace", True, "both"), ("Knee_L", "Lknee", (0.11, 0.11, 0.11), "carapace", True, "both"),
    ("Heel_R", "Rank", (0.085, 0.08, 0.11), "cream", False, "both"), ("Heel_L", "Lank", (0.085, 0.08, 0.11), "cream", False, "both"),
    ("MaceBall", "mace", (0.30, 0.30, 0.30), "carapace", False, "front"),
]
# cape: front-view trapezoid with ragged hem (+ thin depth strip in side view)
CAPE = dict(ztop=1.08, zbot=0.40, xtl=-0.30, xtr=0.40, xbl=-0.48, xbr=0.50, y=(0.06, 0.14), teeth=8, jag=0.09)
MANTLE = dict(ztop=1.74, zbot=1.38, xtl=-0.38, xtr=-0.05, xbl=-0.36, xbr=-0.08, y=(0.02, 0.06), teeth=3, jag=0.09)

FIT_PATH = os.path.join(os.path.dirname(__file__), "aruun_spec_fit.json")

def load(use_fit=True):
    spec = dict(J=copy.deepcopy(J), B=[list(b) for b in B], E=[list(e) for e in E], CAPE=dict(CAPE), MANTLE=dict(MANTLE))
    if use_fit and os.path.exists(FIT_PATH):
        f = json.load(open(FIT_PATH))
        for k, v in f["J"].items(): spec["J"][k] = v
        for i, b in enumerate(f["B"]): spec["B"][i][3], spec["B"][i][4] = tuple(b[0]), tuple(b[1])
        for i, e in enumerate(f["E"]): spec["E"][i][2] = tuple(e)
        spec["CAPE"].update(f["CAPE"]); spec["MANTLE"].update(f.get("MANTLE", {}))
    return spec

def pos(spec, j):
    v = spec["J"][j] if isinstance(j, str) else j
    if isinstance(v, list) and v and v[0] == "lerp":
        a, b = pos(spec, v[1]), pos(spec, v[2]); return [a[i] + (b[i] - a[i]) * v[3] for i in range(3)]
    return list(v)
