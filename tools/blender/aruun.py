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
    carapace=mat("Carapace_Black", (0.035, 0.03, 0.07), 0.3, 0.2),
    red=mat("Chitin_Red", (0.55, 0.05, 0.04), 0.3, 0.1),
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
NECK = [V(0, 0.00, 1.78), V(0, -0.10, 1.98), V(0, -0.20, 2.14), V(0, -0.30, 2.24)]
curve_tube("Neck", NECK, 0.15, 0.085, "carapace")
for i, t in enumerate((0.12, 0.30, 0.48, 0.66, 0.84)):
    pz = 1.78 + (2.24 - 1.78) * t; py = -0.30 * (t ** 1.1)
    sphere(f"Neck_Band_{i}", (0, py, pz), (0.14 - 0.05 * t, 0.12 - 0.04 * t, 0.028), "orange" if i % 2 == 0 else "cream", 16, 6)
sphere("Skull", (0, -0.36, 2.29), (0.11, 0.15, 0.10), "carapace")
limb("Snout", (0, -0.40, 2.28), (0, -0.66, 2.20), 0.09, 0.05, "red")
sphere("Snout_Tip", (0, -0.675, 2.195), (0.055, 0.05, 0.045), "orange")
sphere("Jaw", (0, -0.52, 2.17), (0.065, 0.16, 0.035), "cream")
for s in (-1, 1):
    sphere(f"Eye_{s}", (0.095 * s, -0.43, 2.33), (0.032, 0.03, 0.022), "eye", 12, 8)
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
    joint(f"Knee_{s}", knee, 0.125, "cream")
    sphere(f"Kneecap_Spot_{s}", knee + V(0.0, -0.08, 0.0), (0.06, 0.03, 0.07), "orange", 10, 6)
    limb(f"Shin_{s}", knee, ank, 0.12, 0.065, "carapace")
    joint(f"Ankle_{s}", ank, 0.075, "carapace")
    limb(f"Metatarsus_{s}", ank, toe, 0.07, 0.055, "carapace")
    sphere(f"Foot_{s}", toe + V(0, -0.08, 0.0), (0.10, 0.17, 0.05), "cream", 14, 8)
    for k in range(3):
        cx = toe.x + (-0.045 + 0.045 * k)
        limb(f"Claw_{s}_{k}", V(cx, toe.y - 0.19, 0.045), V(cx, toe.y - 0.34, 0.01), 0.03, 0.005, "orange", 8)
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
        panel(f"Cape_{s}_{i}", V((0.10 + 0.13 * i) * s, 0.26, 1.80 - 0.05 * i), V((0.18 + 0.19 * i) * s, 0.38 + 0.03 * i, 0.30 + 0.07 * i), 0.10, 0.03)
for i in range(3):
    panel(f"Cape_C_{i}", V((i - 1) * 0.10, 0.28, 1.80), V((i - 1) * 0.13, 0.42, 0.20 + 0.05 * (i % 2)), 0.11, 0.03)
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

# ---------- subtle surface: subsurf on every mesh for clean silhouettes ----------
for o in col.objects:
    if o.type == "MESH" and not any(k in o.name for k in ("Spike", "Claw", "Finger", "Strip", "Cape", "Tuft", "Horn", "Neck")):
        md = o.modifiers.new("Subsurf", "SUBSURF"); md.levels = 1; md.render_levels = 1

# ---------- render setup ----------
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 24; sc.cycles.device = "CPU"
sc.cycles.use_denoising = False
sc.render.resolution_x, sc.render.resolution_y = 640, 800
sc.render.film_transparent = False
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.82, 0.76, 0.64, 1); bg.inputs[1].default_value = 1.0
def light(name, loc, e, kind="AREA", size=3):
    d = bpy.data.lights.new(name, kind); d.energy = e
    if kind == "AREA": d.size = size
    o = bpy.data.objects.new(name, d); o.location = loc; sc.collection.objects.link(o)
    o.rotation_euler = (V(0, 0, 1.2) - V(loc)).to_track_quat("-Z", "Y").to_euler()
light("Key", (-3, -4, 4), 700); light("Fill", (4, -3, 2), 250); light("Rim", (0, 4, 3), 400)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0)); fl = bpy.context.object
fl.data.materials.append(mat("Floor", (0.72, 0.66, 0.55), 0.9))
cam_d = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.type = "ORTHO"; cam_d.ortho_scale = 3.2

def shot(name, loc, target=(0.15, 0, 1.25), ortho=3.2):
    cam.location = loc; cam_d.ortho_scale = ortho
    cam.rotation_euler = (V(target) - V(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(PREV, name + ".png"); bpy.ops.render.render(write_still=True)

if "--no-render" not in sys.argv:
    os.makedirs(PREV, exist_ok=True)
    shot("aruun_front", (0, -8, 1.25)); shot("aruun_side", (8, 0, 1.25)); shot("aruun_back", (0, 8, 1.25))
    cam_d.type = "PERSP"; cam_d.lens = 55
    shot("aruun_3q", (4.2, -5.0, 1.8), (0.1, 0, 1.2))
    shot("aruun_head", (1.6, -2.2, 2.45), (0, -0.25, 2.35))

# ---------- export (strip render-only objects) ----------
for o in (fl, cam, *[o for o in sc.objects if o.type == "LIGHT"]): bpy.data.objects.remove(o, do_unlink=True)
os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("OK", OUT_GLB)
