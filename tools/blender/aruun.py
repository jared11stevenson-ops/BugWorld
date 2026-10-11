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

# ======================================================================================================
# Layout: every coordinate below was read off references/aruun/aruun_{front,side,back}.png (metres).
# Front view: +X = image right. Side view: character faces -Y. Feet on z=0, total height 2.40 m (horn tip).
# ======================================================================================================
M["mane"] = mat("Mane_Olive", (0.45, 0.42, 0.16), 0.7)
M["green_dark"] = mat("Cape_Dark", (0.10, 0.12, 0.05), 0.9)
M["mantle"] = mat("Mantle_Brown", (0.045, 0.035, 0.03), 0.85)
M["pupil"] = mat("Pupil", (0.01, 0.01, 0.01), 0.2)
M["navy"] = M["carapace"]

def disc(name, p, nrm, r, m, thick=0.5):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=p)
    o = bpy.context.object; o.name = name; o.scale = (r, r, r * thick)
    o.rotation_euler = V(nrm).to_track_quat("Z", "Y").to_euler(); return finish(o, m)

def spot_on(name, center, radii, d, r, m="cream"):
    """pale spot with a dark ring, flush on an ellipsoid shell"""
    d = V(d).normalized(); pos = V(center) + V(d.x * radii[0], d.y * radii[1], d.z * radii[2]) * 0.98
    disc(name + "_ring", pos - d * 0.004, d, r * 1.4, "carapace", 0.2); disc(name, pos + d * 0.002, d, r, m, 0.55)

def ragged(name, xc, y0, y1, z0, z1, w0, w1, m, teeth=3, jag=0.10, seed=0.0):
    bm = bmesh.new()
    tl = bm.verts.new((xc - w0, y0, z0)); tr = bm.verts.new((xc + w0, y0, z0)); bot = []
    n = teeth * 2
    for k in range(n + 1):
        f = k / n; z = z1 + (jag * (1 + 0.6 * math.sin(seed + k * 2.1)) if k % 2 else 0.0)
        bot.append(bm.verts.new((xc - w1 + 2 * w1 * f, y1, z)))
    bm.faces.new([tl, *bot, tr]); bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o); me.materials.append(M[m]); return o

# ---------- torso: lean barbarian, heavy shoulders, bare cream abdomen, forward hunch ----------
sphere("Pelvis", (0.06, -0.03, 1.02), (0.26, 0.15, 0.17), "carapace")
sphere("Abdomen", (0.04, -0.10, 1.28), (0.15, 0.13, 0.21), "cream")
for i, z in enumerate((1.40, 1.30, 1.20)):
    for sx in (-1, 1): sphere(f"Abs_{sx}_{i}", (0.04 + 0.055 * sx, -0.215, z), (0.05, 0.03, 0.045), "cream", 12, 8)
sphere("Chest", (0.05, -0.12, 1.56), (0.27, 0.16, 0.21), "carapace")
for sx in (-1, 1): sphere(f"Pec_{sx}", (0.05 + 0.12 * sx, -0.255, 1.55), (0.12, 0.07, 0.10), "carapace", 18, 10)
sphere("Back_Hump", (0.04, 0.0, 1.63), (0.24, 0.12, 0.19), "carapace")
bpy.ops.mesh.primitive_torus_add(location=(0.05, -0.12, 1.58), major_radius=0.25, minor_radius=0.032)
o = bpy.context.object; o.name = "Sash_Chest"; o.scale = (1, 0.62, 1.15); o.rotation_euler = (0, math.radians(-38), 0); finish(o, "cream")
bpy.ops.mesh.primitive_torus_add(location=(0.05, -0.08, 1.22), major_radius=0.19, minor_radius=0.045)
o = bpy.context.object; o.name = "Belt_Red"; o.scale = (1, 0.75, 1); finish(o, "red")
bpy.ops.mesh.primitive_torus_add(location=(0.05, -0.11, 1.80), major_radius=0.10, minor_radius=0.012)
o = bpy.context.object; o.name = "Necklace"; finish(o, "gold")

# ---------- neck (thin, orange, black-banded) + small head with red beak and the two horns ----------
NECK = [V(0.05, -0.06, 1.70), V(0.04, -0.08, 1.82), V(-0.02, -0.10, 1.92), V(-0.07, -0.12, 1.99)]
curve_tube("Neck", NECK, 0.080, 0.050, "orange")
for i, t in enumerate((0.20, 0.45, 0.70)):
    k = min(int(t * 3), 2); pt = NECK[k].lerp(NECK[k + 1], t * 3 - k); r = 0.082 - 0.032 * t
    sphere(f"Neck_Band_{i}", tuple(pt), (r, r * 0.95, 0.03), "carapace", 16, 6)
sphere("Skull", (-0.11, -0.12, 2.06), (0.075, 0.105, 0.068), "carapace")
limb("Beak", V(-0.12, -0.17, 2.05), V(-0.20, -0.31, 1.93), 0.058, 0.016, "red", 14)
limb("Beak_Under", V(-0.12, -0.17, 2.01), V(-0.19, -0.29, 1.93), 0.04, 0.012, "orange", 10)
sphere("Eye_R", (-0.065, -0.185, 2.09), (0.026, 0.022, 0.022), "eye", 12, 8); sphere("Pupil_R", (-0.058, -0.205, 2.09), (0.007, 0.01, 0.018), "pupil", 8, 6)
sphere("Eye_L", (-0.16, -0.185, 2.09), (0.026, 0.022, 0.022), "eye", 12, 8); sphere("Pupil_L", (-0.166, -0.205, 2.09), (0.007, 0.01, 0.018), "pupil", 8, 6)
limb("Brow_R", V(-0.07, -0.15, 2.12), V(-0.04, -0.21, 2.12), 0.022, 0.01, "carapace", 8); limb("Brow_L", V(-0.15, -0.15, 2.12), V(-0.18, -0.21, 2.12), 0.022, 0.01, "carapace", 8)
for i, (dx, dz, dy) in enumerate([(0.10, 0.07, 0.07), (0.15, 0.02, 0.09), (-0.12, 0.06, 0.07), (-0.17, 0.0, 0.1), (0.0, 0.10, 0.08), (0.05, -0.04, 0.12)]):
    curve_tube(f"Mane_{i}", [V(-0.11, -0.10, 2.08), V(-0.11 + dx * 0.6, -0.06, 2.08 + dz * 0.6), V(-0.11 + dx, 0.0 + dy * 0.3, 2.06 + dz - 0.04)], 0.022, 0.003, "mane")
# big crescent horn (rises, arcs over and hooks forward-right) and the shorter forked horn
curve_tube("Horn_Main", [V(-0.12, -0.10, 2.12), V(-0.11, -0.16, 2.26), V(-0.05, -0.27, 2.35), V(0.08, -0.40, 2.39)], 0.030, 0.006, "red")
curve_tube("Horn_Fork", [V(-0.20, -0.10, 2.12), V(-0.25, -0.18, 2.22), V(-0.26, -0.26, 2.30), V(-0.22, -0.32, 2.33)], 0.026, 0.006, "red")
curve_tube("Horn_Spur", [V(-0.26, -0.18, 2.23), V(-0.20, -0.22, 2.28), V(-0.16, -0.26, 2.29)], 0.012, 0.004, "orange")

# ---------- shoulders / arms ----------
R_SH = V(0.34, 0.02, 1.68)
sphere("Pauldron_R", tuple(R_SH), (0.12, 0.11, 0.11), "red")
sphere("Pauldron_R_Rim", (0.34, 0.02, 1.58), (0.125, 0.115, 0.03), "cream")
for i, (d, r) in enumerate([((0.15, -0.8, 0.55), 0.045), ((0.35, -0.25, 0.9), 0.04), ((0.8, -0.3, 0.4), 0.04)]):
    spot_on(f"PSpot_R_{i}", R_SH, (0.12, 0.11, 0.11), d, r)
sphere("Pauldron_L", (-0.27, 0.0, 1.60), (0.11, 0.11, 0.10), "red")
for i, (d, r) in enumerate([((-0.3, -0.8, 0.5), 0.04), ((-0.8, -0.3, 0.4), 0.035)]): spot_on(f"PSpot_L_{i}", V(-0.27, 0.0, 1.60), (0.11, 0.11, 0.10), d, r)
ragged("Mantle", -0.22, 0.03, 0.05, 1.74, 1.38, 0.17, 0.14, "mantle", 3, 0.09, 1.0)           # dark cloak over the left shoulder
# right arm hangs behind the chest line; big red bracer
sh, el, wr = V(0.36, 0.03, 1.60), V(0.38, 0.06, 1.24), V(0.36, 0.07, 0.96)
limb("UpperArm_R", sh, el, 0.085, 0.07, "carapace"); joint("Elbow_R", el, 0.075, "cream")
limb("Forearm_R", el, wr, 0.075, 0.055, "carapace"); limb("Bracer_R", el + (wr - el) * 0.08, el + (wr - el) * 0.85, 0.09, 0.075, "red")
sphere("Hand_R", tuple(wr + V(0, 0, -0.07)), (0.07, 0.065, 0.085), "carapace", 14, 8)
for k in range(3): limb(f"Finger_R_{k}", wr + V(-0.03 + 0.03 * k, 0.0, -0.10), wr + V(-0.03 + 0.03 * k, -0.02, -0.19), 0.017, 0.008, "cream", 6)
# left arm swings out to the mace
lsh, lel, lwr = V(-0.27, 0.0, 1.58), V(-0.24, -0.02, 1.28), V(-0.50, -0.08, 0.95)
limb("UpperArm_L", lsh, lel, 0.085, 0.07, "carapace"); joint("Elbow_L", lel, 0.075, "cream")
limb("Forearm_L", lel, lwr, 0.075, 0.055, "carapace"); limb("Bracer_L", lel + (lwr - lel) * 0.1, lel + (lwr - lel) * 0.85, 0.100, 0.082, "red")
sphere("Hand_L", tuple(lwr + V(-0.02, 0, -0.04)), (0.07, 0.07, 0.07), "carapace", 14, 8)

# ---------- legs: digitigrade, asymmetric stance (left leg steps wide), clawed feet ----------
def leg(tag, hip, knee, ank, toe, claw_dx, claw_len, thigh_r=0.15):
    limb(f"Thigh_{tag}", hip, knee, thigh_r, 0.12, "carapace"); joint(f"Knee_{tag}", knee, 0.11, "carapace")
    sphere(f"Kneeplate_{tag}", knee + V(0, -0.07, 0.02), (0.085, 0.045, 0.10), "cream", 16, 10)
    limb(f"Shin_{tag}", knee, ank, 0.115, 0.066, "carapace"); limb(f"ShinOrange_{tag}", knee + (ank - knee) * 0.2, knee + (ank - knee) * 0.7, 0.095, 0.075, "orange", 12)
    joint(f"Ankle_{tag}", ank, 0.075, "red"); limb(f"Metatarsus_{tag}", ank, toe, 0.07, 0.06, "carapace")
    sphere(f"Foot_{tag}", toe + V(claw_dx * 0.4, -0.10, -0.015), (0.10, 0.17, 0.05), "cream", 14, 8)
    sphere(f"Heel_{tag}", ank + V(0, 0.04, -0.06), (0.085, 0.08, 0.11), "cream", 12, 8)
    for k in range(3):
        cx = toe.x + claw_dx * 0.4 + (-0.045 + 0.045 * k)
        limb(f"Claw_{tag}_{k}", V(cx, toe.y - 0.20, 0.04), V(cx + claw_dx * 0.25, toe.y - 0.20 - claw_len, 0.01), 0.026, 0.005, "orange", 8)
leg("R", V(0.17, -0.02, 1.0), V(0.26, -0.10, 0.62), V(0.38, 0.10, 0.24), V(0.41, -0.06, 0.07), 0.05, 0.10, 0.17)
sphere("ThighPlate_R", (0.25, -0.12, 0.84), (0.11, 0.05, 0.17), "cream"); spot_on("ThighSpot_R", V(0.25, -0.12, 0.84), (0.11, 0.05, 0.17), (0.1, -1, 0.1), 0.045, "red")
leg("L", V(-0.12, -0.02, 1.0), V(-0.28, -0.10, 0.58), V(-0.22, 0.09, 0.22), V(-0.28, -0.10, 0.07), -0.12, 0.10, 0.17)

# ---------- loincloth, tassels, talisman, cape ----------
sphere("Talisman", (0.04, -0.22, 1.12), (0.07, 0.05, 0.085), "cream", 16, 10); sphere("Talisman_Hollow", (0.04, -0.265, 1.12), (0.035, 0.02, 0.04), "pupil", 10, 6)
for i, x in enumerate((-0.14, -0.05, 0.14, 0.23)):
    limb(f"Loin_Strip_{i}", V(x, -0.15, 1.12), V(x * 1.05, -0.17, 0.72 - 0.04 * (i % 2)), 0.045, 0.028, "cream", 6).scale = (1, 0.35, 1)
for i, x in enumerate((-0.18, -0.02, 0.18)):
    limb(f"Tassel_{i}", V(x, -0.15, 1.15), V(x * 1.05, -0.17, 0.90), 0.014, 0.01, "red", 6); sphere(f"Bead_{i}", (x * 1.05, -0.17, 0.89), (0.02, 0.02, 0.02), "gold", 8, 6)
ragged("CapeBack", 0.04, 0.10, 0.14, 1.06, 0.36, 0.30, 0.50, "green_dark", 8, 0.10, 0.5)
ragged("Cape", 0.04, 0.05, 0.09, 1.08, 0.42, 0.27, 0.44, "green", 8, 0.09, 2.0)
ragged("Cape_Edge_L", -0.42, 0.08, 0.12, 1.02, 0.34, 0.04, 0.07, "mantle", 2, 0.08, 4.0); ragged("Cape_Edge_R", 0.49, 0.08, 0.12, 0.92, 0.38, 0.04, 0.06, "mantle", 2, 0.08, 5.0)

# ---------- mace: measured on the front drawing (ball centre, radius, spike tips, grip) ----------
MX, MY, MZ, MR = -1.042, -0.08, 0.35, 0.30
bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=28, radius=MR, location=(MX, MY, MZ)); ball = bpy.context.object; ball.name = "Mace_Ball"; finish(ball, "carapace")
for i, ang in enumerate((20, 75, 120, 160, 205, 250, 295, 335)):     # spike angles read off the drawn silhouette
    a_ = math.radians(ang); dv = V(math.cos(a_), 0, math.sin(a_)); tip = 0.075
    limb(f"Mace_Spike_{i}", V(MX, MY, MZ) + dv * (MR - 0.01), V(MX, MY, MZ) + dv * (MR + tip), 0.045, 0.006, "cream", 10)
for i, (dx, dz, r, m) in enumerate([(-0.17, 0.04, 0.085, "orb"), (0.08, 0.14, 0.05, "orange"), (-0.05, -0.12, 0.05, "cream"), (0.14, -0.08, 0.055, "red"), (-0.20, -0.14, 0.045, "orange"), (0.02, 0.0, 0.045, "gold")]):
    disc(f"Mace_Stud_{i}", V(MX + dx, MY - MR * 0.93, MZ + dz), (0, -1, 0), r, m, 0.4)
limb("Mace_Haft", V(MX + 0.20, MY, MZ + 0.22), V(-0.52, -0.08, 0.93), 0.034, 0.03, "brown", 12); limb("Mace_Grip", V(-0.60, -0.08, 0.86), V(-0.50, -0.08, 0.97), 0.04, 0.04, "cream", 10)

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

    # ---- fit check: model silhouette vs the drawn silhouette, at the reference planes' exact scale (1 px = 2 mm) ----
    import numpy as _np
    def _alpha(path):
        im = bpy.data.images.load(path); w_, h_ = im.size; px = _np.array(im.pixels[:], dtype=_np.float32).reshape(h_, w_, 4)[::-1, :, 3]; bpy.data.images.remove(im); return px > 0.4
    fl.hide_render = True; sc.render.film_transparent = True; sc.render.resolution_x, sc.render.resolution_y = 1600, 1300
    cam_d.type = "ORTHO"; cam_d.ortho_scale = 3.2; cam_d.sensor_fit = "HORIZONTAL"
    for nm, loc, rot, clip in (("front", (0, -8, 1.2), (90, 0, 0), 0.1), ("side", (-8, 0, 1.2), (90, 0, -90), 7.33)):
        cam.location = loc; cam.rotation_euler = tuple(math.radians(a_) for a_ in rot); cam_d.clip_start = clip
        sc.render.filepath = os.path.join(PREV, f"fit_{nm}.png"); bpy.ops.render.render(write_still=True)
        mine, ref = _alpha(sc.render.filepath), _alpha(os.path.join(ROOT, "references", "aruun", f"aruun_{nm}.png"))
        print(f"FIT {nm}: IoU={(mine & ref).sum() / max((mine | ref).sum(), 1):.3f}  model-only={(mine & ~ref).sum() * 4e-6:.3f} m2  drawing-only={(ref & ~mine).sum() * 4e-6:.3f} m2")
        # overlay: green = both, red = model only, blue = drawing only
        ov = _np.zeros((1300, 1600, 4), _np.float32); ov[..., 3] = 1; ov[mine & ref, 1] = 0.8; ov[mine & ~ref, 0] = 1; ov[ref & ~mine, 2] = 1
        im = bpy.data.images.new(f"ov_{nm}", 1600, 1300); im.pixels = ov[::-1].ravel(); im.filepath_raw = os.path.join(PREV, f"fit_overlay_{nm}.png"); im.file_format = "PNG"; im.save()
    fl.hide_render = False; sc.render.film_transparent = False; sc.render.resolution_x, sc.render.resolution_y = 768, 960; cam_d.clip_start = 0.1
    shot("aruun_front", (-0.45, -8, 1.25), (-0.45, 0, 1.25), 3.0); shot("aruun_side", (-8, 0, 1.25), (0, 0, 1.25), 3.0); shot("aruun_back", (0, 8, 1.25), (0, 0, 1.25), 3.0)
    cam_d.type = "PERSP"; cam_d.lens = 55
    shot("aruun_3q", (-3.4, -5.2, 1.8), (-0.3, 0, 1.15))
    cam_d.lens = 85; shot("aruun_head", (0.9, -2.7, 2.5), (-0.1, -0.15, 2.1))
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND.replace(".blend", "_toon.blend"))
    back_to_pbr(orig)

# ---------- export (PBR materials, no render-only objects) ----------
for o in [fl, cam, *[o for o in sc.objects if o.type == "LIGHT"]]: bpy.data.objects.remove(o, do_unlink=True)
os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format="GLB", export_apply=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("OK", OUT_GLB)
