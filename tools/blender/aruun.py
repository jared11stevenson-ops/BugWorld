"""Aruun the Reaper-- procedural Blender build from references/aruun_sheet.png.
Run:  python3 tools/blender/aruun.py   (needs `pip install bpy`)
Units: metres, +Z up, character faces -Y. Height = 2.40 m (feet at z=0).
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Euler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_GLB = os.path.join(ROOT, "assets/models/aruun.glb")
OUT_BLEND = os.path.join(ROOT, "assets/models/aruun.blend")
PREV = os.path.join(ROOT, "evidence/models")
def V(*a):
    return Vector(a[0]) if len(a) == 1 else Vector(a)

bpy.ops.wm.read_factory_settings(use_empty=True)
col = bpy.data.collections.new("Aruun"); bpy.context.scene.collection.children.link(col)

# ---------- materials (palette sampled from the sheet swatches) ----------
def mat(name, rgb, rough=0.45, metal=0.0, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 2.0
    return m
M = dict(
    carapace=mat("Carapace_Black", (0.012, 0.010, 0.032), 0.3, 0.2),
    red=mat("Chitin_Red", (0.62, 0.04, 0.04), 0.3, 0.1),
    orange=mat("Chitin_Orange", (0.85, 0.30, 0.06), 0.35),
    cream=mat("Bone_Cream", (0.78, 0.66, 0.50), 0.6),
    green=mat("Cape_Olive", (0.30, 0.36, 0.12), 0.8),
    gold=mat("Trinket_Gold", (0.75, 0.55, 0.15), 0.35, 0.8),
    brown=mat("Mace_Wood", (0.16, 0.10, 0.07), 0.7),
    eye=mat("Eye_Yellow", (0.9, 0.75, 0.1), 0.2, 0, emit=(1, 0.8, 0.1)),
    orb=mat("Psionic_Orb", (0.7, 0.03, 0.03), 0.15, 0, emit=(1, 0.05, 0.03)),
)

def finish(o, m, smooth=True, subsurf=0):
    o.data.materials.append(M[m] if isinstance(m, str) else m)
    if smooth:
        for p in o.data.polygons: p.use_smooth = True
    if subsurf:
        md = o.modifiers.new("Subsurf", "SUBSURF"); md.levels = subsurf; md.render_levels = subsurf
    for c in o.users_collection: c.objects.unlink(o)
    col.objects.link(o)
    return o

def sphere(name, p, s, m, seg=24, ring=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=ring, location=p)
    o = bpy.context.object; o.name = name; o.scale = s
    return finish(o, m)

def limb(name, a, b, r1, r2, m, seg=16):
    """tapered capsule-ish cone from a (radius r1) to b (radius r2)"""
    a, b = V(a), V(b); d = b - a
    bpy.ops.mesh.primitive_cone_add(vertices=seg, radius1=r1, radius2=r2, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object; o.name = name
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    finish(o, m)
    return o

def joint(name, p, r, m): return sphere(name, p, (r, r, r), m, 16, 10)

def curve_tube(name, pts, r_start, r_end, m, res=12):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    cu.bevel_depth = 1.0; cu.bevel_resolution = 6; cu.resolution_u = res
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
    for i, (bp, p) in enumerate(zip(sp.bezier_points, pts)):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = "AUTO"
        bp.radius = r_start + (r_end - r_start) * i / (len(pts) - 1)
    o = bpy.data.objects.new(name, cu); col.objects.link(o)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.object
    o.data.materials.append(M[m])
    for p in o.data.polygons: p.use_smooth = True
    return o

def X(x, side): return (x * side)  # mirror helper

# ---------- torso (barbarian: broad chest, narrow waist) ----------
sphere("Pelvis", (0, 0.04, 1.05), (0.27, 0.19, 0.19), "carapace")
sphere("Abdomen", (0, 0.0, 1.28), (0.21, 0.16, 0.23), "carapace")
sphere("Chest", (0, -0.08, 1.58), (0.36, 0.25, 0.30), "carapace")
for i in range(3):   # segmented beetle ribs
    sphere(f"Rib_{i}", (0, -0.27, 1.68 - 0.1 * i), (0.20 - 0.02 * i, 0.04, 0.035), "cream", 16, 8)
sphere("Sternum_Plate", (0, -0.30, 1.52), (0.05, 0.03, 0.10), "orange")
sphere("Hump_Back", (0, 0.16, 1.76), (0.30, 0.20, 0.20), "carapace")
sphere("Hump_Spot", (0, 0.33, 1.80), (0.10, 0.03, 0.08), "red")
bpy.ops.mesh.primitive_torus_add(location=(0, -0.08, 1.58), major_radius=0.30, minor_radius=0.035)
sash = bpy.context.object; sash.name = "Sash"; sash.scale = (1, 0.8, 1.1); sash.rotation_euler = (0, math.radians(35), 0); finish(sash, "cream")

# ---------- neck (long, giraffe-like, forward lean) + head ----------
NECK = [V(0, 0.00, 1.78), V(0, 0.05, 1.97), V(0, -0.08, 2.14), V(0, -0.30, 2.24)]
curve_tube("Neck", NECK, 0.15, 0.085, "carapace")
def neck_at(t):
    seg = min(int(t * 3), 2); u = t * 3 - seg
    return NECK[seg].lerp(NECK[seg + 1], u)
for i, t in enumerate((0.10, 0.24, 0.38, 0.52, 0.66, 0.80)):
    pt = neck_at(t); r = 0.15 + (0.085 - 0.15) * t + 0.02
    sphere(f"Neck_Band_{i}", tuple(pt), (r, r * 0.95, 0.024), "orange" if i % 2 == 0 else "cream", 16, 6)
sphere("Skull", (0, -0.36, 2.29), (0.125, 0.17, 0.115), "carapace")
limb("Snout", (0, -0.40, 2.28), (0, -0.72, 2.18), 0.105, 0.028, "red")
sphere("Jaw", (0, -0.52, 2.17), (0.075, 0.18, 0.035), "cream")
for s in (-1, 1):
    sphere(f"Eye_{s}", (0.095 * s, -0.43, 2.33), (0.042, 0.038, 0.028), "eye", 12, 8)
    # antler-horns: rise, bow outward, then hook forward/inward (giraffe-beetle)
    h = curve_tube(f"Horn_{s}", [V(0.06 * s, -0.33, 2.36), V(0.14 * s, -0.30, 2.54), V(0.24 * s, -0.34, 2.70), V(0.30 * s, -0.50, 2.80)], 0.042, 0.009, "red")
    h.name = f"Horn_{s}"
    curve_tube(f"HornSpur_{s}", [V(0.11 * s, -0.31, 2.48), V(0.21 * s, -0.33, 2.56), V(0.27 * s, -0.40, 2.56)], 0.016, 0.004, "orange")
    sphere(f"Cheek_Spot_{s}", (0.10 * s, -0.40, 2.25), (0.025, 0.05, 0.035), "orange", 10, 6)
    # mane/tuft hair strands behind head (blond tufts on sheet)
    limb(f"Tuft_{s}", (0.06 * s, -0.30, 2.30), (0.18 * s, -0.10, 2.10), 0.03, 0.004, "cream", 6)

# ---------- shoulders: oversized red spotted pauldrons ----------
for s in (-1, 1):
    sphere(f"Pauldron_{s}", (0.45 * s, -0.04, 1.80), (0.21, 0.19, 0.18), "red")
    sphere(f"Pauldron_Rim_{s}", (0.47 * s, -0.04, 1.70), (0.19, 0.17, 0.05), "carapace")
    for i, (dx, dy, dz) in enumerate([(0.07, -0.12, 0.05), (0.0, -0.10, 0.12), (0.12, 0.0, 0.10)]):
        sphere(f"Spot_{s}_{i}", (0.45 * s + dx * s * 1.3, dy * 1.4 - 0.04, 1.80 + dz * 1.3), (0.065, 0.025, 0.065), "cream", 10, 6)
    # arms: upper arm hanging, forearm forward-out, hand
    sh, el, wr = V(0.48 * s, -0.04, 1.66), V(0.58 * s, -0.10, 1.26), V(0.56 * s, -0.30, 1.00)
    joint(f"Shoulder_J_{s}", sh, 0.095, "carapace")
    limb(f"UpperArm_{s}", sh, el, 0.11, 0.085, "carapace")
    joint(f"Elbow_{s}", el, 0.09, "carapace")
    sphere(f"Elbow_Spike_{s}", (el.x + 0.06 * s, 0.07, el.z), (0.025, 0.07, 0.025), "cream", 8, 6)
    limb(f"Forearm_{s}", el, wr, 0.09, 0.065, "carapace")
    limb(f"Bracer_{s}", el + (wr - el) * 0.10, el + (wr - el) * 0.80, 0.105, 0.088, "red")
    sphere(f"Hand_{s}", wr + V(0, -0.03, -0.05), (0.08, 0.09, 0.10), "carapace", 14, 8)
    for k in range(3):
        limb(f"Finger_{s}_{k}", wr + V((-0.03 + 0.03 * k) * s, -0.05, -0.08), wr + V((-0.03 + 0.03 * k) * s, -0.09, -0.18), 0.016, 0.008, "cream", 6)

# ---------- legs: digitigrade, clawed ----------
for s in (-1, 1):
    hip, knee, ank, toe = V(0.15 * s, 0.0, 1.00), V(0.19 * s, -0.12, 0.62), V(0.17 * s, 0.10, 0.24), V(0.17 * s, -0.10, 0.04)
    limb(f"Thigh_{s}", hip, knee, 0.19, 0.12, "carapace")
    sphere(f"Thigh_Stripe_{s}", ((hip + knee) / 2 + V(0.04 * s, -0.04, 0)), (0.08, 0.06, 0.20), "orange")
    joint(f"Knee_{s}", knee, 0.125, "carapace")
    sphere(f"Kneeplate_{s}", knee + V(0, -0.075, 0), (0.105, 0.05, 0.125), "cream", 16, 10)
    sphere(f"Kneecap_Spot_{s}", knee + V(0.0, -0.08, 0.0), (0.06, 0.03, 0.07), "orange", 10, 6)
    limb(f"Shin_{s}", knee, ank, 0.12, 0.065, "carapace")
    joint(f"Ankle_{s}", ank, 0.075, "carapace")
    limb(f"Metatarsus_{s}", ank, toe, 0.07, 0.055, "carapace")
    sphere(f"Foot_{s}", toe + V(0, -0.08, 0.0), (0.12, 0.22, 0.06), "cream", 14, 8)
    for k in range(3):
        cx = toe.x + (-0.045 + 0.045 * k)
        limb(f"Claw_{s}_{k}", V(cx, toe.y - 0.24, 0.05), V(cx, toe.y - 0.42, 0.01), 0.034, 0.005, "orange", 8)
    limb(f"HeelSpur_{s}", ank, ank + V(0, 0.16, -0.05), 0.02, 0.004, "cream", 8)

# ---------- loincloth + tattered green cape + sash ----------
for i, x in enumerate([-0.18, -0.06, 0.06, 0.18]):
    limb(f"Loin_Strip_{i}", V(x, -0.17, 1.10), V(x * 1.1, -0.20, 0.72), 0.04, 0.025, "cream", 6)
    sphere(f"Loin_Bead_{i}", (x * 1.1, -0.20, 0.72), (0.02, 0.02, 0.02), "gold", 8, 6)
bpy.ops.mesh.primitive_torus_add(location=(0, 0, 1.16), major_radius=0.22, minor_radius=0.03)
t = bpy.context.object; t.name = "Belt"; t.scale = (1, 0.75, 1); finish(t, "cream")
def panel(name, top, bot, w0, w1):
    o = limb(name, top, bot, w0, w1, "green", 4)
    o.scale = (1, 0.10, 1); return o
for s in (-1, 1):
    for i in range(4):
        panel(f"Cape_{s}_{i}", V((0.10 + 0.13 * i) * s, 0.26, 1.80 - 0.05 * i), V((0.18 + 0.19 * i) * s, 0.38 + 0.03 * i, 0.30 + 0.07 * i), 0.17, 0.0)
for i in range(3):
    panel(f"Cape_C_{i}", V((i - 1) * 0.10, 0.28, 1.80), V((i - 1) * 0.13, 0.42, 0.20 + 0.05 * (i % 2)), 0.18, 0.0)
# necklace
bpy.ops.mesh.primitive_torus_add(location=(0, -0.10, 1.86), major_radius=0.20, minor_radius=0.014)
n = bpy.context.object; n.name = "Necklace"; n.scale = (1, 0.8, 1); finish(n, "gold")

# ---------- mace: long haft, spiked beetle-shell head w/ red orbs ----------
hand = V(0.52, -0.25, 0.95)
haft_a, haft_b = V(0.52, -0.25, 0.95), V(0.72, -0.56, 0.26)
limb("Mace_Haft", V(0.50, -0.10, 1.20), haft_b, 0.028, 0.036, "brown", 10)
limb("Mace_Grip_Wrap", V(0.50, -0.18, 1.02), V(0.55, -0.30, 0.82), 0.03, 0.03, "cream", 10)
head_c = V(0.76, -0.62, 0.17)
sphere("Mace_Ball", head_c, (0.17, 0.17, 0.17), "carapace", 28, 20)
import random; random.seed(7)
bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.17)
dirs = [v.co.normalized() for v in bm.verts]; bm.free()
for i, d in enumerate(dirs):
    p = head_c + d * 0.17
    if i % 3 == 0:
        limb(f"Mace_Spike_{i}", p - d * 0.02, p + d * 0.08, 0.028, 0.005, "cream", 8)
    elif i % 3 == 1:
        sphere(f"Mace_Orb_{i}", p, (0.04, 0.04, 0.025), "orb" if i % 2 else "red", 10, 6)
limb("Mace_Ferrule", haft_b, head_c + V(-0.1, 0.13, 0.12), 0.04, 0.03, "gold", 10)
# shoulder rim spikes
for s in (-1, 1):
    for k in range(3):
        limb(f"Pauldron_Spike_{s}_{k}", V((0.46 + 0.04 * k) * s, 0.04, 1.90 - 0.03 * k), V((0.50 + 0.07 * k) * s, 0.07, 1.99 - 0.04 * k), 0.02, 0.004, "cream", 6)

# ---------- character detail pass (what makes it Aruun, not a generic bug-man) ----------
M["mane"] = mat("Mane_Blond", (0.82, 0.68, 0.30), 0.7)
M["green_dark"] = mat("Cape_Dark", (0.14, 0.18, 0.07), 0.9)
M["pupil"] = mat("Pupil", (0.01, 0.01, 0.01), 0.2)

for o in [o for o in col.objects if o.name.startswith("Spot_")]:
    bpy.data.objects.remove(o, do_unlink=True)
def disc(name, p, nrm, r, m):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=p)
    o = bpy.context.object; o.name = name; o.scale = (r, r, r * (0.2 if "Ring" in name else 0.55))
    o.rotation_euler = V(nrm).to_track_quat("Z", "Y").to_euler(); return finish(o, m)
for s in (-1, 1):
    c, rad = V(0.45 * s, -0.04, 1.80), V(0.21, 0.19, 0.18)
    for i, (d, r) in enumerate([((0.35 * s, -0.80, 0.50), 0.060), ((0.25 * s, -0.25, 0.93), 0.052), ((0.85 * s, -0.40, 0.30), 0.055), ((0.65 * s, -0.10, 0.75), 0.040)]):
        d = V(d).normalized(); pos = c + V(d.x * rad.x, d.y * rad.y, d.z * rad.z) * 0.98
        disc(f"PSpotRing_{s}_{i}", pos - d * 0.004, d, r * 1.4, "carapace")
        disc(f"PSpot_{s}_{i}", pos + d * 0.002, d, r, "cream")
for s in (-1, 1):
    sphere(f"Pec_{s}", (0.15 * s, -0.25, 1.64), (0.16, 0.10, 0.12), "carapace", 20, 12)
    for r_, z_ in enumerate((1.37, 1.24, 1.11)):
        sphere(f"Abs_{s}_{r_}", (0.065 * s, -0.17 + 0.0 * r_, z_), (0.075, 0.05, 0.055), "carapace", 14, 8)
sphere("Abs_Stripe", (0, -0.205, 1.24), (0.012, 0.012, 0.15), "orange", 8, 6)
# black rings around every cream/orange spot (the sheet outlines each spot in dark chitin)
for o in [o for o in col.objects if o.name.startswith(("Spot_", "Cheek_Spot", "Hump_Spot", "Kneecap_Spot"))]:
    ring = o.copy(); ring.data = o.data.copy(); col.objects.link(ring); ring.name = "Ring_" + o.name
    ring.scale = o.scale * 1.38; ring.location = o.location + V(0, 0.012, 0)
    ring.data.materials.clear(); ring.data.materials.append(M["carapace"])

# eyes: slit pupils, heavy brow ridge, nostrils, mouth line
for s in (-1, 1):
    sphere(f"Pupil_{s}", (0.107 * s, -0.447, 2.332), (0.008, 0.012, 0.022), "pupil", 10, 6)
    limb(f"Brow_{s}", V(0.03 * s, -0.36, 2.385), V(0.14 * s, -0.49, 2.375), 0.034, 0.014, "carapace", 8)
    sphere(f"Nostril_{s}", (0.020 * s, -0.685, 2.215), (0.009, 0.011, 0.008), "pupil", 8, 6)
    # blond mane: long swept-back strands behind the skull and down the nape
    for k in range(4):
        sx = (0.03 + 0.035 * k) * s
        curve_tube(f"Mane_{s}_{k}", [V(sx, -0.27, 2.34 - 0.02 * k), V(sx * 1.4, -0.12, 2.28 - 0.05 * k), V(sx * 2.6, 0.02 + 0.03 * k, 2.20 - 0.05 * k)], 0.030, 0.003, "mane")
    # cream wraps on forearm / shin / bicep, as on the sheet
    wr, el = V(0.56 * s, -0.30, 1.00), V(0.58 * s, -0.10, 1.26)
    limb(f"Wrap_Wrist_{s}", wr + (el - wr) * 0.05, wr + (el - wr) * 0.22, 0.078, 0.082, "cream", 14)
    ank, kn = V(0.17 * s, 0.10, 0.24), V(0.19 * s, -0.12, 0.62)
    limb(f"Wrap_Shin_{s}", ank + (kn - ank) * 0.20, ank + (kn - ank) * 0.36, 0.088, 0.098, "cream", 14)
    limb(f"Wrap_Shin2_{s}", ank + (kn - ank) * 0.40, ank + (kn - ank) * 0.46, 0.103, 0.106, "orange", 14)
sphere("Mouth_Line", (0, -0.54, 2.205), (0.07, 0.16, 0.007), "pupil", 12, 6)
# belt trinkets: hanging skull-talisman + gold beads + green feathers (sheet shows all three)
sphere("Talisman", (0, -0.23, 1.04), (0.055, 0.04, 0.065), "cream", 14, 8)
sphere("Talisman_Eye_L", (-0.02, -0.265, 1.05), (0.012, 0.01, 0.014), "pupil", 8, 6)
sphere("Talisman_Eye_R", (0.02, -0.265, 1.05), (0.012, 0.01, 0.014), "pupil", 8, 6)
limb("Talisman_Cord", V(0, -0.20, 1.16), V(0, -0.23, 1.09), 0.006, 0.006, "gold", 6)
for i, x in enumerate((-0.30, -0.24, 0.24, 0.30)):
    limb(f"Feather_{i}", V(x, -0.10, 1.12), V(x * 1.25, -0.14, 0.70), 0.055, 0.0, "green", 4).scale = (1, 0.12, 1)
for i in range(5):
    sphere(f"Belt_Bead_{i}", (-0.14 + 0.07 * i, -0.215, 1.17), (0.016, 0.016, 0.016), "gold", 8, 6)
# ragged tattered cloak: zig-zag hems, two layers (olive over dark)
for o in [o for o in col.objects if o.name.startswith("Cape")]:
    bpy.data.objects.remove(o, do_unlink=True)
def ragged(name, xc, y0, y1, z0, z1, w0, w1, m, teeth=3, jag=0.10, seed=0.0):
    bm = bmesh.new()
    top_l = bm.verts.new((xc - w0, y0, z0)); top_r = bm.verts.new((xc + w0, y0, z0))
    bot = []
    n = teeth * 2
    for k in range(n + 1):
        f = k / n
        z = z1 + (jag * (1 + 0.6 * math.sin(seed + k * 2.1)) if k % 2 else 0.0)
        bot.append(bm.verts.new((xc - w1 + 2 * w1 * f, y0 + (y1 - y0) * (1 - (z - z1) / max(z0 - z1, 1e-3) * 0.0), z)))
    bm.faces.new([top_l, *bot, top_r])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    me.materials.append(M[m]); [setattr(pp, "use_smooth", False) for pp in me.polygons]
    return o
for i, x in enumerate((-0.42, -0.26, -0.09, 0.09, 0.26, 0.42)):
    ragged(f"CapeBack_{i}", x * 1.15, 0.30, 0.50, 1.76, 0.12 + 0.10 * (i % 3), 0.13, 0.17, "green_dark", 3, 0.12, i)
for i, x in enumerate((-0.40, -0.20, 0.0, 0.20, 0.40)):
    ragged(f"Cape_{i}", x, 0.24, 0.36, 1.80, 0.30 + 0.12 * ((i + 1) % 3), 0.12, 0.15, "green", 3, 0.10, i * 1.7)
for s in (-1, 1):
    ragged(f"Cape_Side_{s}", 0.47 * s, 0.10, 0.20, 1.76, 0.55 + 0.1 * (s > 0), 0.05, 0.08, "green", 2, 0.09, 3.0 + s)

# ---------- subtle surface: subsurf on every mesh for clean silhouettes ----------
for o in col.objects:
    if o.type == "MESH" and not any(k in o.name for k in ("Spike", "Claw", "Finger", "Strip", "Cape", "Tuft", "Horn", "Neck", "Mane", "Feather", "Cord")):
        md = o.modifiers.new("Subsurf", "SUBSURF"); md.levels = 1; md.render_levels = 1

# =====================================================================
#  NPR / cel look (matches the sheet: ink line, 3-band cel, warm light /
#  cool-violet shadow, hard chitin glints, paper background)
# =====================================================================
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 24
sc.render.resolution_x, sc.render.resolution_y = 768, 960
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
PAPER = (0.80, 0.72, 0.58)
SHADOW_TINT, MID_TINT, LIT_TINT = (0.42, 0.36, 0.64), (0.82, 0.80, 0.86), (1.0, 0.96, 0.88)
SPEC = dict(Carapace_Black=0.7, Chitin_Red=0.8, Chitin_Orange=0.4, Trinket_Gold=0.9, Eye_Yellow=0.5, Mace_Wood=0.1, Pupil=0.9)

def toon_mat(src):
    b = src.node_tree.nodes["Principled BSDF"]
    base = tuple(b.inputs["Base Color"].default_value)[:3]
    m = bpy.data.materials.new(src.name + "_toon"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial"); em = N("ShaderNodeEmission")
    # --- light bands
    diff = N("ShaderNodeBsdfDiffuse"); diff.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = N("ShaderNodeShaderToRGB"); L(diff.outputs[0], s2r.inputs[0])
    band = N("ShaderNodeValToRGB"); band.color_ramp.interpolation = "CONSTANT"
    e = band.color_ramp.elements; e[0].position = 0.0; e[0].color = (*SHADOW_TINT, 1)
    e[1].position = 0.34; e[1].color = (*MID_TINT, 1)
    e.new(0.80).color = (*LIT_TINT, 1)
    L(s2r.outputs[0], band.inputs[0])
    # --- albedo (with subtle chitin micro-variation on the hard shells)
    alb = N("ShaderNodeRGB"); alb.outputs[0].default_value = (*[min(1, c * 1.18) for c in base], 1)
    shell = src.name in ("Carapace_Black", "Chitin_Red", "Chitin_Orange")
    if shell:
        tc = N("ShaderNodeTexCoord"); noise = N("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 40
        L(tc.outputs["Object"], noise.inputs["Vector"])
        nr = N("ShaderNodeValToRGB"); nr.color_ramp.elements[0].color = (0.86, 0.86, 0.86, 1); nr.color_ramp.elements[1].color = (1, 1, 1, 1)
        L(noise.outputs["Fac"], nr.inputs[0])
        v = N("ShaderNodeMix"); v.data_type = "RGBA"; v.blend_type = "MULTIPLY"; v.inputs[0].default_value = 1
        L(alb.outputs[0], v.inputs[6]); L(nr.outputs[0], v.inputs[7]); alb_out = v.outputs[2]
    else:
        alb_out = alb.outputs[0]
    if src.name == "Chitin_Red":   # red -> orange gradient along each part (sheet shows orange at the tips)
        tc2 = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc2.outputs["Generated"], sep.inputs[0])
        gr = N("ShaderNodeValToRGB"); gr.color_ramp.elements[0].color = (0.62, 0.04, 0.04, 1); gr.color_ramp.elements[1].color = (0.80, 0.11, 0.04, 1)
        L(sep.outputs["Z"], gr.inputs[0]); alb2 = N("ShaderNodeMix"); alb2.data_type = "RGBA"; alb2.blend_type = "MULTIPLY"; alb2.inputs[0].default_value = 1
        L(gr.outputs[0], alb2.inputs[6]); L(nr.outputs[0], alb2.inputs[7]); alb_out = alb2.outputs[2]
    lit = N("ShaderNodeMix"); lit.data_type = "RGBA"; lit.blend_type = "MULTIPLY"; lit.inputs[0].default_value = 1
    L(alb_out, lit.inputs[6]); L(band.outputs[0], lit.inputs[7])
    col_out = lit.outputs[2]
    # --- hard specular glint
    k = SPEC.get(src.name, 0.0)
    if k:
        gl = N("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.22
        g2 = N("ShaderNodeShaderToRGB"); L(gl.outputs[0], g2.inputs[0])
        gr2 = N("ShaderNodeValToRGB"); gr2.color_ramp.interpolation = "CONSTANT"
        gr2.color_ramp.elements[0].position = 0.0; gr2.color_ramp.elements[0].color = (0, 0, 0, 1)
        gr2.color_ramp.elements[1].position = 1.6; gr2.color_ramp.elements[1].color = (k, k, k, 1)
        L(g2.outputs[0], gr2.inputs[0])
        add = N("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"; add.inputs[0].default_value = 1
        L(col_out, add.inputs[6]); L(gr2.outputs[0], add.inputs[7]); col_out = add.outputs[2]
    # --- rim: fresnel-thresholded cool/warm edge light
    fr = N("ShaderNodeLayerWeight"); fr.inputs["Blend"].default_value = 0.3
    rr = N("ShaderNodeValToRGB"); rr.color_ramp.interpolation = "CONSTANT"
    rr.color_ramp.elements[0].position = 0.0; rr.color_ramp.elements[0].color = (0, 0, 0, 1)
    rr.color_ramp.elements[1].position = 0.80; rr.color_ramp.elements[1].color = (0.10, 0.08, 0.04, 1)
    L(fr.outputs["Facing"], rr.inputs[0])   # Facing is 1.0 at the silhouette edge
    ra = N("ShaderNodeMix"); ra.data_type = "RGBA"; ra.blend_type = "ADD"; ra.inputs[0].default_value = 1
    L(col_out, ra.inputs[6]); L(rr.outputs[0], ra.inputs[7]); col_out = ra.outputs[2]
    if src.name == "Psionic_Orb":
        em.inputs["Color"].default_value = (0.85, 0.05, 0.03, 1); em.inputs["Strength"].default_value = 1.0
    elif src.name == "Eye_Yellow":
        em.inputs["Color"].default_value = (1.0, 0.82, 0.12, 1); em.inputs["Strength"].default_value = 1.0
    else:
        L(col_out, em.inputs["Color"])
    L(em.outputs[0], out.inputs[0])
    return m

INK = bpy.data.materials.new("Ink"); INK.use_nodes = True; INK.use_backface_culling = True
_n = INK.node_tree; _n.nodes.clear(); _e = _n.nodes.new("ShaderNodeEmission"); _e.inputs["Color"].default_value = (0.045, 0.02, 0.03, 1)
_o = _n.nodes.new("ShaderNodeOutputMaterial"); _n.links.new(_e.outputs[0], _o.inputs[0])

def go_toon():
    orig = {}
    cache = {}
    for o in col.objects:
        if o.type != "MESH": continue
        orig[o.name] = list(o.data.materials)
        mats = [cache.setdefault(m.name, toon_mat(m)) for m in o.data.materials]
        o.data.materials.clear()
        for m in mats: o.data.materials.append(m)
        o.data.materials.append(INK)
        sol = o.modifiers.new("Outline", "SOLIDIFY")
        sol.thickness = min(0.013, max(0.0035, max(o.dimensions) * 0.035)); sol.offset = 1
        sol.use_flip_normals = True; sol.material_offset = len(mats)
    return orig

def back_to_pbr(orig):
    for o in col.objects:
        if o.name in orig:
            o.data.materials.clear()
            for m in orig[o.name]: o.data.materials.append(m)
            md = o.modifiers.get("Outline")
            if md: o.modifiers.remove(md)

# world: paper for camera rays, soft neutral ambient for lighting
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear(); N, L = nt.nodes.new, nt.links.new
b1 = N("ShaderNodeBackground"); b1.inputs["Color"].default_value = (*PAPER, 1); b1.inputs["Strength"].default_value = 1.0
b2 = N("ShaderNodeBackground"); b2.inputs["Color"].default_value = (0.9, 0.85, 0.95, 1); b2.inputs["Strength"].default_value = 0.30
lp = N("ShaderNodeLightPath"); mx = N("ShaderNodeMixShader"); wo = N("ShaderNodeOutputWorld")
L(lp.outputs["Is Camera Ray"], mx.inputs[0]); L(b2.outputs[0], mx.inputs[1]); L(b1.outputs[0], mx.inputs[2]); L(mx.outputs[0], wo.inputs[0])

def sun(name, rot_deg, color, strength, angle=0.03):
    d = bpy.data.lights.new(name, "SUN"); d.energy = strength; d.color = color; d.angle = angle
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o)
    o.rotation_euler = tuple(math.radians(a) for a in rot_deg); return o
sun("Key", (52, 0, -38), (1.0, 0.90, 0.76), 1.55)     # warm, front-left-high
sun("Rim", (62, 0, 150), (0.65, 0.75, 1.0), 1.0)      # cool, back-right
sun("Fill", (80, 0, 60), (0.9, 0.8, 1.0), 0.25)       # faint violet bounce from the right

# floor: same paper colour as the backdrop, a single cool band where the figure shadows it
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0)); fl = bpy.context.object; fl.name = "Floor"
fm = bpy.data.materials.new("Floor"); fm.use_nodes = True; fn = fm.node_tree; fn.nodes.clear()
fd = fn.nodes.new("ShaderNodeBsdfDiffuse"); fs = fn.nodes.new("ShaderNodeShaderToRGB"); fr_ = fn.nodes.new("ShaderNodeValToRGB")
fr_.color_ramp.interpolation = "CONSTANT"; fr_.color_ramp.elements[0].position = 0.0; fr_.color_ramp.elements[0].color = (PAPER[0] * 0.70, PAPER[1] * 0.66, PAPER[2] * 0.72, 1)
fr_.color_ramp.elements[1].position = 0.30; fr_.color_ramp.elements[1].color = (*PAPER, 1)
fe = fn.nodes.new("ShaderNodeEmission"); fo = fn.nodes.new("ShaderNodeOutputMaterial")
fn.links.new(fd.outputs[0], fs.inputs[0]); fn.links.new(fs.outputs[0], fr_.inputs[0]); fn.links.new(fr_.outputs[0], fe.inputs[0]); fn.links.new(fe.outputs[0], fo.inputs[0])
fl.data.materials.append(fm)

cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.type = "ORTHO"; cam_d.ortho_scale = 3.3

def shot(name, loc, target=(0.15, 0, 1.30), ortho=3.3):
    cam.location = loc; cam_d.ortho_scale = ortho
    cam.rotation_euler = (V(target) - V(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(PREV, name + ".png"); bpy.ops.render.render(write_still=True)

if "--no-render" not in sys.argv:
    os.makedirs(PREV, exist_ok=True)
    orig = go_toon()
    shot("aruun_front", (0, -8, 1.30)); shot("aruun_side", (8, 0, 1.30)); shot("aruun_back", (0, 8, 1.30))
    cam_d.type = "PERSP"; cam_d.lens = 55
    shot("aruun_3q", (4.2, -5.0, 1.8), (0.1, 0, 1.2))
    cam_d.lens = 85; shot("aruun_head", (1.3, -2.6, 2.5), (0, -0.30, 2.35))
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND.replace(".blend", "_toon.blend"))
    back_to_pbr(orig)

# ---------- export (PBR materials, no render-only objects) ----------
for o in [fl, cam, *[o for o in sc.objects if o.type == "LIGHT"]]: bpy.data.objects.remove(o, do_unlink=True)
os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("OK", OUT_GLB)
