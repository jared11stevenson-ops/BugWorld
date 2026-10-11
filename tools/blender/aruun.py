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
# Built from tools/blender/aruun_spec.py (+ aruun_spec_fit.json, tuned by tools/reference/fit_silhouette.py so the
# model's front and side silhouettes overlap the reference drawings). Metres, +Z up, character faces -Y.
# ======================================================================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aruun_spec as S
spec = S.load()
Pj = lambda j: Vector(S.pos(spec, j))
M["mane"] = mat("Mane_Olive", (0.45, 0.42, 0.16), 0.7)
M["green_dark"] = mat("Cape_Dark", (0.10, 0.12, 0.05), 0.9)
M["mantle"] = mat("Mantle_Brown", (0.045, 0.035, 0.03), 0.85)
M["pupil"] = mat("Pupil", (0.01, 0.01, 0.01), 0.2)

def loft(name, A, B, ra, rb, m, seg=20, link=True):
    """tapered elliptical capsule: ra/rb = (rx, ry) at each end; rx lies along world X (front view), ry along ~Y (side view)"""
    A, B = Vector(A), Vector(B); d = B - A; L = d.length
    if L < 1e-5: return sphere(name, tuple(A), (ra[0], ra[1], ra[0]), m, 16, 10)
    dn = d / L; ref = Vector((1, 0, 0)) if abs(dn.x) < 0.9 else Vector((0, 1, 0))
    e1 = (ref - dn * ref.dot(dn)).normalized(); e2 = dn.cross(e1)
    bm = bmesh.new(); rings = []
    def ring(c, sx, sy):
        if sx < 1e-6: return [bm.verts.new(c)]
        return [bm.verts.new(c + e1 * (sx * math.cos(2 * math.pi * k / seg)) + e2 * (sy * math.sin(2 * math.pi * k / seg))) for k in range(seg)]
    ths = [math.radians(t) for t in (90, 68, 45, 22)]; ma, mb = (ra[0] + ra[1]) / 2, (rb[0] + rb[1]) / 2
    for th in ths: rings.append(ring(A - dn * ma * math.sin(th), ra[0] * math.cos(th), ra[1] * math.cos(th)))
    rings += [ring(A, *ra), ring(B, *rb)]
    for th in reversed(ths): rings.append(ring(B + dn * mb * math.sin(th), rb[0] * math.cos(th), rb[1] * math.cos(th)))
    for r0, r1 in zip(rings[:-1], rings[1:]):
        if len(r0) == 1:
            for k in range(seg): bm.faces.new((r0[0], r1[(k + 1) % seg], r1[k]))
        elif len(r1) == 1:
            for k in range(seg): bm.faces.new((r0[k], r0[(k + 1) % seg], r1[0]))
        else:
            for k in range(seg): bm.faces.new((r0[k], r0[(k + 1) % seg], r1[(k + 1) % seg], r1[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); col.objects.link(o); me.materials.append(M[m] if isinstance(m, str) else m)
    for pp in me.polygons: pp.use_smooth = True
    return o

def bone(nm): return next(b for b in spec["B"] if b[0] == nm)
def shell(nm, t0, t1, k, m, name=None, off=(0, 0, 0)):
    """armour plate riding on part of a bone (e.g. the red bracer on the forearm)"""
    _, a, b_, ra, rb, *_ = bone(nm); A, B = Pj(a), Pj(b_); lerp = lambda t: A + (B - A) * t; r = lambda t, i: (ra[i] + (rb[i] - ra[i]) * t) * k
    return loft(name or nm + "_" + m, lerp(t0) + Vector(off), lerp(t1) + Vector(off), (r(t0, 0), r(t0, 1)), (r(t1, 0), r(t1, 1)), m)

def disc(name, p, nrm, r, m, thick=0.5):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=p)
    o = bpy.context.object; o.name = name; o.scale = (r, r, r * thick)
    o.rotation_euler = V(nrm).to_track_quat("Z", "Y").to_euler(); return finish(o, m)
def spot_on(name, center, radii, d, r, m="cream"):
    d = V(d).normalized(); pos = V(center) + V(d.x * radii[0], d.y * radii[1], d.z * radii[2]) * 0.98
    disc(name + "_ring", pos - d * 0.004, d, r * 1.4, "carapace", 0.2); disc(name, pos + d * 0.002, d, r, m, 0.55)
def ragged(name, c, m, y, scale_w=1.0, dz=0.0, seed=0.0):
    bm = bmesh.new(); pts = [(c["xtl"], c["ztop"]), (c["xtr"], c["ztop"])]; n = c["teeth"] * 2
    for k in range(n + 1):
        f = 1 - k / n; pts.append((c["xbl"] + (c["xbr"] - c["xbl"]) * f, c["zbot"] + dz + (c["jag"] * (1 + 0.5 * math.sin(seed + k * 2.1)) if k % 2 else 0.0)))
    vs = [bm.verts.new((x * scale_w, y, z)) for x, z in pts]; bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); col.objects.link(o); me.materials.append(M[m]); return o

# ---------- 1. every spec part ----------
base_parts = []; ELL = {}
for nm, a, b_, ra, rb, m, base, view in spec["B"]:
    if nm.startswith(("Horn", "Neck")): continue                       # smooth curves, built below
    o = loft(nm, Pj(a), Pj(b_), ra, rb, m); (base_parts if base else []).append(o)
for nm, c, r, m, base, view in spec["E"]:
    o = sphere(nm, tuple(Pj(c)), r, m, 32, 20); ELL[nm] = (Pj(c), r)
    if base: base_parts.append(o)
# neck + horns as smooth tubes through the fitted joints
def chain(nm, joints, m):
    pts = [Pj(j) for j in joints]; rs = [bone(f"{nm}{i}")[3][0] for i in range(len(joints) - 1)] + [bone(f"{nm}{len(joints) - 2}")[4][0]]
    return curve_tube(nm, pts, rs[0], rs[-1], m)
chain("Neck", ["neck0", "neck1", "neck2", "neck3"], "orange"); chain("HornMain", ["h0", "h1", "h2", "h3"], "red"); chain("HornFork", ["f0", "f1", "f2", "f3"], "red")
curve_tube("HornSpur", [Pj("f1") + V(0.0, -0.01, 0.01), Pj("f1") + V(0.06, -0.04, 0.06), Pj("f2") + V(0.10, -0.01, -0.01)], 0.012, 0.004, "orange")

# ---------- 2. extra body mass the sheet shows (pecs, ribs) merged into the carapace ----------
ch, cr = ELL["Chest"]
for sx in (-1, 1): base_parts.append(sphere(f"Pec_{sx}", tuple(ch + V(0.12 * sx, -cr[1] * 0.85, -0.01)), (0.12, 0.07, 0.10), "carapace", 18, 10))
# ---------- 3. one continuous carapace: join + voxel remesh + light smooth ----------
bpy.ops.object.select_all(action="DESELECT")
for o in base_parts: o.select_set(True)
bpy.context.view_layer.objects.active = base_parts[0]; bpy.ops.object.join(); body = bpy.context.object; body.name = "Aruun_Body"
body.data.remesh_voxel_size = 0.010; bpy.ops.object.voxel_remesh()
sm = body.modifiers.new("Smooth", "SMOOTH"); sm.factor = 0.5; sm.iterations = 3; bpy.ops.object.modifier_apply(modifier="Smooth")
for pp in body.data.polygons: pp.use_smooth = True
body.data.materials.clear(); body.data.materials.append(M["carapace"])
print("carapace verts", len(body.data.vertices))

# ---------- 4. armour plates (colour = the sheet's red / cream / orange patches) ----------
shell("Forearm_R", 0.04, 0.88, 1.38, "red", "Bracer_R"); shell("Forearm_L", 0.04, 0.88, 1.38, "red", "Bracer_L")
shell("Shin_R", 0.18, 0.72, 1.07, "orange", "ShinOrange_R"); shell("Shin_L", 0.18, 0.72, 1.07, "orange", "ShinOrange_L")
for tag in ("R", "L"):
    kn = Pj(f"{tag}knee"); hip = Pj(f"{tag}hip"); sx = 1 if tag == "R" else -1
    tp = hip + (kn - hip) * 0.5; rr = bone(f"Thigh_{tag}")[3]
    sphere(f"ThighPlate_{tag}", tuple(tp + V(0.01 * sx, -rr[1] * 0.78, 0.0)), (rr[0] * 0.62, 0.05, 0.17), "cream")
    spot_on(f"ThighSpot_{tag}", tp + V(0.01 * sx, -rr[1] * 0.78, 0.0), (rr[0] * 0.62, 0.05, 0.17), (0.1 * sx, -1, 0.15), 0.045, "red")
    sphere(f"Kneeplate_{tag}", tuple(kn + V(0, -0.08, 0.02)), (0.085, 0.045, 0.10), "cream", 16, 10)
    sphere(f"Ankle_{tag}", tuple(Pj(f"{tag}ank")), (0.075, 0.075, 0.075), "red", 14, 8)
    for k in range(3):
        tip = Pj(f"{tag}tip"); toe = Pj(f"{tag}toe"); cx = toe.x + (-0.045 + 0.045 * k)
        limb(f"Claw_{tag}_{k}", V(cx, tip.y - 0.02, 0.04), V(cx + 0.03 * (1 if tag == "R" else -1), tip.y - 0.13, 0.01), 0.026, 0.005, "orange", 8)
    el = Pj(f"{tag}el"); sphere(f"Elbow_{tag}", tuple(el), (0.075, 0.075, 0.075), "cream", 14, 8)
    hd = Pj(f"{tag}hand")
    for k in range(3): limb(f"Finger_{tag}_{k}", hd + V(-0.03 + 0.03 * k, 0.0, -0.05), hd + V(-0.03 + 0.03 * k, -0.02, -0.14), 0.017, 0.008, "cream", 6)
# pauldron spots + rim
for tag, jn in (("R", "Rpaul"), ("L", "Lpaul")):
    c, r = ELL[f"Pauldron_{tag}"]; sx = 1 if tag == "R" else -1
    sphere(f"Pauldron_Rim_{tag}", tuple(c + V(0, 0, -r[2] * 0.9)), (r[0] * 1.03, r[1] * 1.03, 0.03), "cream")
    for i, (d, rr) in enumerate([((0.15 * sx, -0.8, 0.55), 0.045), ((0.35 * sx, -0.25, 0.9), 0.04), ((0.8 * sx, -0.3, 0.4), 0.04)]): spot_on(f"PSpot_{tag}_{i}", c, r, d, rr)

# ---------- 5. torso dressing: belt, sash, loincloth, talisman, necklace ----------
pel, ab = Pj("pelvis"), Pj("abdomen")
bpy.ops.mesh.primitive_torus_add(location=tuple(ab + V(0, 0, -0.06)), major_radius=0.19, minor_radius=0.045)
o = bpy.context.object; o.name = "Belt_Red"; o.scale = (1, 0.75, 1); finish(o, "red")
bpy.ops.mesh.primitive_torus_add(location=tuple(ch + V(0, 0, 0.02)), major_radius=0.25, minor_radius=0.032)
o = bpy.context.object; o.name = "Sash_Chest"; o.scale = (1, 0.62, 1.15); o.rotation_euler = (0, math.radians(-38), 0); finish(o, "cream")
bpy.ops.mesh.primitive_torus_add(location=tuple(Pj("neck0") + V(0, -0.04, 0.08)), major_radius=0.10, minor_radius=0.012); o = bpy.context.object; o.name = "Necklace"; finish(o, "gold")
for i, dx in enumerate((-0.20, -0.11, 0.08, 0.17)):
    limb(f"Loin_{i}", pel + V(dx, -0.12, 0.10), pel + V(dx * 1.05, -0.14, -0.30 - 0.04 * (i % 2)), 0.045, 0.028, "cream", 6).scale = (1, 0.35, 1)
for i, dx in enumerate((-0.18, -0.02, 0.18)):
    limb(f"Tassel_{i}", pel + V(dx, -0.13, 0.12), pel + V(dx * 1.05, -0.15, -0.12), 0.014, 0.01, "red", 6); sphere(f"Bead_{i}", tuple(pel + V(dx * 1.05, -0.15, -0.13)), (0.02, 0.02, 0.02), "gold", 8, 6)
sphere("Talisman", tuple(pel + V(-0.02, -0.19, 0.10)), (0.07, 0.05, 0.085), "cream", 16, 10); sphere("Talisman_Hollow", tuple(pel + V(-0.02, -0.235, 0.10)), (0.035, 0.02, 0.04), "pupil", 10, 6)

# ---------- 6. head details ----------
sk, sr = ELL["Skull"]
for sx, nm in ((1, "R"), (-1, "L")):
    sphere(f"Eye_{nm}", tuple(sk + V(0.047 * sx, -0.065, 0.03)), (0.026, 0.022, 0.022), "eye", 12, 8); sphere(f"Pupil_{nm}", tuple(sk + V(0.054 * sx, -0.085, 0.03)), (0.007, 0.01, 0.018), "pupil", 8, 6)
    limb(f"Brow_{nm}", sk + V(0.03 * sx, -0.03, 0.055), sk + V(0.075 * sx, -0.09, 0.055), 0.022, 0.01, "carapace", 8)
loft("Beak_Under", Pj("beak0") + V(0, 0.0, -0.03), Pj("beak1") + V(0, 0.0, -0.012), (0.04, 0.04), (0.012, 0.012), "orange")
for i, (dx, dz, dy) in enumerate([(0.10, 0.07, 0.07), (0.15, 0.02, 0.09), (-0.12, 0.06, 0.07), (-0.17, 0.0, 0.10), (0.0, 0.10, 0.08), (0.05, -0.04, 0.12)]):
    curve_tube(f"Mane_{i}", [sk + V(0, 0.02, 0.02), sk + V(dx * 0.6, 0.06, 0.02 + dz * 0.6), sk + V(dx, 0.12 + dy * 0.3, dz - 0.04)], 0.022, 0.003, "mane")

# ---------- 7. cloth: wide ragged cape (two layers), dark mantle over the left shoulder ----------
cp = spec["CAPE"]; y0, y1 = cp["y"]
ragged("CapeBack", cp, "green_dark", y1 + 0.03, 1.02, -0.04, 0.5); ragged("Cape", cp, "green", y0, 0.94, 0.02, 2.0)
mn = spec["MANTLE"]; ragged("Mantle", mn, "mantle", mn["y"][0], 1.0, 0.0, 1.0)

# ---------- 8. mace: ball + spikes read off the drawn silhouette + studs ----------
mc, mr = ELL["MaceBall"]
for i, ang in enumerate((20, 75, 120, 160, 205, 250, 295, 335)):
    a_ = math.radians(ang); dv = V(math.cos(a_), 0, math.sin(a_))
    limb(f"Mace_Spike_{i}", mc + dv * (mr[0] - 0.01), mc + dv * (mr[0] + 0.075), 0.045, 0.006, "cream", 10)
for i, (dx, dz, r, m) in enumerate([(-0.17, 0.04, 0.085, "orb"), (0.08, 0.14, 0.05, "orange"), (-0.05, -0.12, 0.05, "cream"), (0.14, -0.08, 0.055, "red"), (-0.20, -0.14, 0.045, "orange"), (0.02, 0.0, 0.045, "gold")]):
    disc(f"Mace_Stud_{i}", mc + V(dx, -mr[0] * 0.93, dz), (0, -1, 0), r, m, 0.4)
limb("Mace_Grip", Pj("grip") + V(-0.06, 0, -0.06), Pj("grip") + V(0.03, 0, 0.04), 0.04, 0.04, "cream", 10)

# ---------- subtle surface: subsurf on every mesh for clean silhouettes ----------
for o in col.objects:
    if o.type == "MESH" and not any(k in o.name for k in ("Spike", "Claw", "Finger", "Strip", "Cape", "Tuft", "Horn", "Neck", "Mane", "Feather", "Cord", "Body")):
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
