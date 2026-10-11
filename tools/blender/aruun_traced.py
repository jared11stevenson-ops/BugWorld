"""Aruun built from the reference drawings with minimal interpretation.

 body  : silhouette-carved hull (tools/reference/trace_hull.py): front + side outlines reproduce the drawings exactly
 mace  : ball / spikes / haft measured off the front drawing; coloured by the front drawing only
 colour: the ORIGINAL art projected from the front / back / side planes (triplanar), fading to the dark carapace tone on
         faces that are oblique to every drawing instead of smearing
 look  : projected art x soft 3-band cel light + ink outline (renders); plain projected art baked to a 4k texture (glb)
Run (after extract_refs.py + trace_hull.py):  python3 tools/blender/aruun_traced.py [--no-bake] [--no-render]
"""
import bpy, os, sys, json, math
import numpy as np
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF, MODELS, PREV = (os.path.join(ROOT, p) for p in ("references/aruun", "assets/models", "evidence/models"))
TARGET_FACES, TEX, MACE_SCALE = 90000, 4096, 1.0
W, H, Z0 = 3.2, 2.6, -0.1                 # reference plane size and bottom offset (matches extract_refs.py)
NAVY = (0.012, 0.010, 0.030, 1)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ------------------------------------------------------------------ body
d = np.load(os.path.join(MODELS, "aruun_hull.npz"))
me = bpy.data.meshes.new("Aruun_Body"); me.from_pydata(d["verts"].tolist(), [], d["faces"].tolist()); me.update()
body = bpy.data.objects.new("Aruun_Body", me); sc.collection.objects.link(body)
bpy.context.view_layer.objects.active = body; body.select_set(True)
for p in me.polygons: p.use_smooth = True
sm = body.modifiers.new("Smooth", "SMOOTH"); sm.factor = 0.5; sm.iterations = 8
dm = body.modifiers.new("Decimate", "DECIMATE"); dm.ratio = min(1.0, TARGET_FACES / len(me.polygons))
bpy.ops.object.modifier_apply(modifier="Smooth"); bpy.ops.object.modifier_apply(modifier="Decimate")
# horns: round tubes along the fitted 3D curves (joints from tools/blender/aruun_spec_fit.json), joined into the body
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import aruun_spec as S
_spec = S.load(); _P = lambda j: Vector(S.pos(_spec, j))
def tube(name, pts, radii):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = 1.0; cu.bevel_resolution = 6; cu.resolution_u = 14; cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
    for bp, p_, r_ in zip(sp.bezier_points, pts, radii): bp.co = p_; bp.handle_left_type = bp.handle_right_type = "AUTO"; bp.radius = r_
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o); bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.convert(target="MESH"); o = bpy.context.object
    for p_ in o.data.polygons: p_.use_smooth = True
    return o
horns = [tube("HornMain", [_P(j) for j in ("h0", "h1", "h2", "h3")], (0.032, 0.024, 0.016, 0.006)),
         tube("HornFork", [_P(j) for j in ("f0", "f1", "f2", "f3")], (0.028, 0.021, 0.014, 0.006)),
         tube("HornSpur", [_P("f1") + Vector((0, -0.01, 0.01)), _P("f1") + Vector((0.06, -0.04, 0.06)), _P("f2") + Vector((0.10, -0.01, -0.01))], (0.013, 0.009, 0.004))]
_sk = _P("skull"); bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=tuple(_sk)); _cap = bpy.context.object; _cap.scale = (0.080, 0.112, 0.076)
for p_ in _cap.data.polygons: p_.use_smooth = True
horns.append(_cap)
bpy.ops.object.select_all(action="DESELECT"); body.select_set(True)
for o in horns: o.select_set(True)
bpy.context.view_layer.objects.active = body; bpy.ops.object.join()
n_body = len(body.data.polygons); print("body faces", n_body)

# ------------------------------------------------------------------ mace
mp = json.load(open(os.path.join(MODELS, "aruun_mace.json")))
bx, bz = mp["ball_center_xz"]; r_body = mp["ball_body_radius"] * MACE_SCALE; gx, gz = mp["grip_xz"]
co = np.array([v.co[:] for v in body.data.vertices])
near = co[(abs(co[:, 0] - gx) < 0.10) & (abs(co[:, 2] - gz) < 0.12)]
by = float(near[:, 1].mean()) if len(near) else -0.05
parts = []
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=r_body, location=(bx, by, bz)); parts.append(bpy.context.object)
for sp in mp["spikes"]:
    ang = math.radians(sp["angle_deg"]); dv = Vector((math.cos(ang), 0.0, math.sin(ang))); L_ = sp["tip_r"] * MACE_SCALE - r_body
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=max(L_ * 0.55, 0.012), radius2=0.004, depth=L_ * 1.25, location=Vector((bx, by, bz)) + dv * (r_body + L_ * 0.42))
    o = bpy.context.object; o.rotation_euler = dv.to_track_quat("Z", "Y").to_euler(); parts.append(o)
a, b = Vector((bx, by, bz)) + (Vector((gx, by, gz)) - Vector((bx, by, bz))).normalized() * r_body * 0.9, Vector((gx + 0.03, by, gz + 0.04))
bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.032, depth=(b - a).length, location=(a + b) / 2)
o = bpy.context.object; o.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler(); parts.append(o)
bpy.ops.object.select_all(action="DESELECT")
for o in parts: o.select_set(True)
bpy.context.view_layer.objects.active = parts[0]; bpy.ops.object.join(); mace = bpy.context.object
for p in mace.data.polygons: p.use_smooth = True
n_body = len(body.data.polygons)
bpy.ops.object.select_all(action="DESELECT"); body.select_set(True); mace.select_set(True)
bpy.context.view_layer.objects.active = body; bpy.ops.object.join(); body.name = "Aruun"

# ------------------------------------------------------------------ triplanar projection of the original art
IMG = {}
for k in ("front", "back", "side"):
    im = bpy.data.images.load(os.path.join(REF, f"aruun_{k}.png")); im.alpha_mode = "STRAIGHT"; IMG[k] = im

def projected_art(nt, front_only=False):
    """returns the colour socket of the triplanar-projected art inside node tree nt"""
    N, L = nt.nodes.new, nt.links.new
    tc = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep.inputs[0])
    geo = N("ShaderNodeNewGeometry"); ns = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Normal"], ns.inputs[0])
    def math_(op, a, b=None, clamp=False):
        n = N("ShaderNodeMath"); n.operation = op
        if isinstance(a, (int, float)): n.inputs[0].default_value = a
        else: L(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)): n.inputs[1].default_value = b
            else: L(b, n.inputs[1])
        n.use_clamp = clamp; return n.outputs[0]
    madd = lambda inp, mul, add: (lambda n: (L(inp, n.inputs[0]), setattr(n.inputs[1], "default_value", mul), setattr(n.inputs[2], "default_value", add), n.outputs[0])[-1])(
        (lambda n: (setattr(n, "operation", "MULTIPLY_ADD"), n)[1])(N("ShaderNodeMath")))
    z_v = madd(sep.outputs["Z"], 1 / H, -Z0 / H)
    uv = dict(front=(madd(sep.outputs["X"], 1 / W, 0.5), z_v), back=(madd(sep.outputs["X"], -1 / W, 0.5), z_v), side=(madd(sep.outputs["Y"], -1 / W, 0.5), z_v))
    nyneg = math_("MAXIMUM", math_("MULTIPLY", ns.outputs["Y"], -1.0), 0.0); nypos = math_("MAXIMUM", ns.outputs["Y"], 0.0); nxa = math_("ABSOLUTE", ns.outputs["X"])
    w = dict(front=math_("ADD", math_("MULTIPLY", math_("POWER", nyneg, 6.0), 1.3), 0.01), back=math_("POWER", nypos, 6.0), side=math_("POWER", nxa, 6.0))
    if front_only: w = dict(front=math_("ADD", math_("MULTIPLY", ns.outputs["Y"], 0.0), 1.0), back=math_("MULTIPLY", ns.outputs["Y"], 0.0), side=math_("MULTIPLY", ns.outputs["Y"], 0.0))
    csum = wsum = None
    for k in ("front", "back", "side"):
        comb = N("ShaderNodeCombineXYZ"); L(uv[k][0], comb.inputs[0]); L(uv[k][1], comb.inputs[1])
        tex = N("ShaderNodeTexImage"); tex.image = IMG[k]; tex.extension = "CLIP"; tex.interpolation = "Linear"; L(comb.outputs[0], tex.inputs[0])
        ww = math_("MULTIPLY", w[k], tex.outputs["Alpha"])
        v_ = N("ShaderNodeVectorMath"); v_.operation = "SCALE"; L(tex.outputs["Color"], v_.inputs[0]); L(ww, v_.inputs["Scale"])
        if csum is None: csum, wsum = v_.outputs[0], ww
        else:
            va = N("ShaderNodeVectorMath"); va.operation = "ADD"; L(csum, va.inputs[0]); L(v_.outputs[0], va.inputs[1]); csum = va.outputs[0]; wsum = math_("ADD", wsum, ww)
    inv = math_("DIVIDE", 1.0, math_("MAXIMUM", wsum, 1e-4)); art = N("ShaderNodeVectorMath"); art.operation = "SCALE"; L(csum, art.inputs[0]); L(inv, art.inputs["Scale"])
    wmax = math_("MAXIMUM", math_("MAXIMUM", w["front"], w["back"]), w["side"])
    fade = N("ShaderNodeMapRange"); fade.clamp = True; fade.inputs["From Min"].default_value = 0.06; fade.inputs["From Max"].default_value = 0.30; L(wmax, fade.inputs["Value"])
    if front_only: fade.inputs["From Min"].default_value = -1; fade.inputs["From Max"].default_value = 0.0
    cover = math_("MULTIPLY", math_("MULTIPLY", wsum, 40.0, clamp=True), fade.outputs[0])
    ledge = math_("MULTIPLY", math_("SUBTRACT", math_("ABSOLUTE", ns.outputs["Z"]), 0.45), 4.0, clamp=True)   # near-horizontal faces: keep the neighbouring art row, not navy
    cover = math_("MAXIMUM", cover, ledge)
    mix = N("ShaderNodeMix"); mix.data_type = "RGBA"; mix.inputs[6].default_value = NAVY; L(cover, mix.inputs[0]); L(art.outputs[0], mix.inputs[7])
    return mix.outputs[2]

def material(name, cel):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); N, L = nt.nodes.new, nt.links.new
    out = N("ShaderNodeOutputMaterial"); em = N("ShaderNodeEmission"); L(em.outputs[0], out.inputs[0])
    return m, nt, em
def build(name, cel, front_only=False):
    m, nt, em = material(name, cel); N, L = nt.nodes.new, nt.links.new
    art = projected_art(nt, front_only)
    if cel:   # soft 3-band cel light with warm light / violet shadow, multiplied over the painted art
        diff = N("ShaderNodeBsdfDiffuse"); s2r = N("ShaderNodeShaderToRGB"); L(diff.outputs[0], s2r.inputs[0])
        band = N("ShaderNodeValToRGB"); band.color_ramp.interpolation = "CONSTANT"
        e = band.color_ramp.elements; e[0].position = 0.0; e[0].color = (0.58, 0.52, 0.80, 1); e[1].position = 0.30; e[1].color = (0.86, 0.85, 0.93, 1); e.new(0.78).color = (1.0, 0.98, 0.94, 1)
        L(s2r.outputs[0], band.inputs[0])
        mm = N("ShaderNodeMix"); mm.data_type = "RGBA"; mm.blend_type = "MULTIPLY"; mm.inputs[0].default_value = 1.0
        L(art, mm.inputs[6]); L(band.outputs[0], mm.inputs[7]); art = mm.outputs[2]
    L(art, em.inputs["Color"]); return m
mat_flat = build("Aruun_Art", False); mat_flat_m = build("Aruun_Art_Mace", False, True)
mat_cel = build("Aruun_Cel", True); mat_cel_m = build("Aruun_Cel_Mace", True, True)
def assign(a, b):
    body.data.materials.clear(); body.data.materials.append(a); body.data.materials.append(b)
    for i, p in enumerate(body.data.polygons): p.material_index = 1 if i >= n_body else 0
assign(mat_flat, mat_flat_m)

INK = bpy.data.materials.new("Ink"); INK.use_nodes = True; INK.use_backface_culling = True
_n = INK.node_tree; _n.nodes.clear(); _e = _n.nodes.new("ShaderNodeEmission"); _e.inputs["Color"].default_value = (0.04, 0.02, 0.03, 1)
_o = _n.nodes.new("ShaderNodeOutputMaterial"); _n.links.new(_e.outputs[0], _o.inputs[0])

# ------------------------------------------------------------------ cameras / world / lights
def cam_ortho(name, loc, rot, scale=3.2, clip=0.1):
    cd = bpy.data.cameras.new(name); cd.type = "ORTHO"; cd.ortho_scale = scale; cd.sensor_fit = "HORIZONTAL"; cd.clip_start = clip
    o = bpy.data.objects.new(name, cd); o.location = loc; o.rotation_euler = tuple(math.radians(a) for a in rot); sc.collection.objects.link(o); return o
CAM = dict(front=cam_ortho("cF", (-0.45, -8, Z0 + H / 2 + 0.05), (90, 0, 0), 3.0), left=cam_ortho("cS", (-8, 0, Z0 + H / 2 + 0.05), (90, 0, -90), 3.0, 7.33), back=cam_ortho("cB", (0, 8, Z0 + H / 2 + 0.05), (90, 0, 180), 3.0))
cq = bpy.data.cameras.new("q"); cq.lens = 60; Q = bpy.data.objects.new("q", cq); Q.location = (-3.6, -5.0, 1.55); sc.collection.objects.link(Q)
Q.rotation_euler = (Vector((-0.35, 0, 1.1)) - Q.location).to_track_quat("-Z", "Y").to_euler()
ch = bpy.data.cameras.new("h"); ch.lens = 85; Hh = bpy.data.objects.new("h", ch); Hh.location = (0.9, -2.7, 2.5); sc.collection.objects.link(Hh)
Hh.rotation_euler = (Vector((-0.1, -0.15, 2.1)) - Hh.location).to_track_quat("-Z", "Y").to_euler()
sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = 24; sc.view_settings.view_transform = "Standard"
PAPER = (0.80, 0.72, 0.58)
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; nt = w.node_tree; nt.nodes.clear(); N, L = nt.nodes.new, nt.links.new
b1 = N("ShaderNodeBackground"); b1.inputs["Color"].default_value = (*PAPER, 1); b2 = N("ShaderNodeBackground"); b2.inputs["Color"].default_value = (0.9, 0.85, 0.95, 1); b2.inputs["Strength"].default_value = 0.30
lp = N("ShaderNodeLightPath"); mx = N("ShaderNodeMixShader"); wo = N("ShaderNodeOutputWorld")
L(lp.outputs["Is Camera Ray"], mx.inputs[0]); L(b2.outputs[0], mx.inputs[1]); L(b1.outputs[0], mx.inputs[2]); L(mx.outputs[0], wo.inputs[0])
def sun(name, rot, colr, e):
    ld = bpy.data.lights.new(name, "SUN"); ld.energy = e; ld.color = colr; ld.angle = 0.03
    o = bpy.data.objects.new(name, ld); o.rotation_euler = tuple(math.radians(a_) for a_ in rot); sc.collection.objects.link(o)
sun("Key", (52, 0, -38), (1.0, 0.92, 0.80), 1.55); sun("Rim", (62, 0, 150), (0.65, 0.75, 1.0), 1.0); sun("Fill", (80, 0, 60), (0.9, 0.8, 1.0), 0.25)
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0)); fl = bpy.context.object; fl.name = "Floor"
fm = bpy.data.materials.new("Floor"); fm.use_nodes = True; fn = fm.node_tree; fn.nodes.clear()
fd = fn.nodes.new("ShaderNodeBsdfDiffuse"); fs = fn.nodes.new("ShaderNodeShaderToRGB"); fr_ = fn.nodes.new("ShaderNodeValToRGB"); fr_.color_ramp.interpolation = "CONSTANT"
fr_.color_ramp.elements[0].color = (PAPER[0] * 0.72, PAPER[1] * 0.68, PAPER[2] * 0.74, 1); fr_.color_ramp.elements[1].position = 0.30; fr_.color_ramp.elements[1].color = (*PAPER, 1)
fe = fn.nodes.new("ShaderNodeEmission"); fo = fn.nodes.new("ShaderNodeOutputMaterial")
for a_, b_ in ((fd.outputs[0], fs.inputs[0]), (fs.outputs[0], fr_.inputs[0]), (fr_.outputs[0], fe.inputs[0]), (fe.outputs[0], fo.inputs[0])): fn.links.new(a_, b_)
fl.data.materials.append(fm)

def shot(name, cam, res=(768, 960), transparent=False):
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = res; sc.render.film_transparent = transparent; fl.hide_render = transparent
    sc.render.filepath = os.path.join(PREV, name + ".png"); bpy.ops.render.render(write_still=True)

if "--no-render" not in sys.argv:
    os.makedirs(PREV, exist_ok=True)
    # 1) the art exactly as projected (no light) at the reference scale -> direct comparison with the drawings
    for k in ("front", "left", "back"): shot(f"traced_art_{k}", CAM[k], (1000, 1250), True)
    shot("traced_art_3q", Q, (1000, 1250), True)
    # 2) cel-lit + ink outline
    assign(mat_cel, mat_cel_m)
    body.data.materials.append(INK); ink_idx = len(body.data.materials) - 1
    sol = body.modifiers.new("Outline", "SOLIDIFY"); sol.thickness = 0.007; sol.offset = 1; sol.use_flip_normals = True; sol.material_offset = ink_idx - 0
    # the solidify shell uses material_offset on the ORIGINAL slot index; slots are [body, mace, ink] -> offset 2 maps body->ink, mace->(out of range, clamps to ink)
    sol.material_offset = 2
    for k in ("front", "left", "back"): shot(f"traced_cel_{k}", CAM[k], (768, 960))
    shot("traced_cel_3q", Q, (768, 960)); shot("traced_cel_head", Hh, (768, 960))
    body.modifiers.remove(sol); body.data.materials.pop(index=ink_idx); assign(mat_flat, mat_flat_m)

# ------------------------------------------------------------------ UV + bake the projected art into one texture (glb)
if "--no-bake" not in sys.argv:
    bpy.ops.object.select_all(action="DESELECT"); body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002); bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("Aruun_BaseColor", TEX, TEX, alpha=False); img.colorspace_settings.name = "sRGB"
    for mm in (mat_flat, mat_flat_m):
        node = mm.node_tree.nodes.new("ShaderNodeTexImage"); node.image = img; mm.node_tree.nodes.active = node
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
    sc.render.bake.margin = 8; sc.render.bake.use_clear = True
    print("baking...", flush=True); bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = os.path.join(MODELS, "aruun_projected_basecolor.png"); img.file_format = "PNG"; img.save()
    pm = bpy.data.materials.new("Aruun"); pm.use_nodes = True; n = pm.node_tree; b = n.nodes["Principled BSDF"]
    t = n.nodes.new("ShaderNodeTexImage"); t.image = img; n.links.new(t.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.6
    body.data.materials.clear(); body.data.materials.append(pm)
    for p in body.data.polygons: p.material_index = 0

for o in [o for o in sc.objects if o.type in ("CAMERA", "LIGHT") or o.name == "Floor"]: bpy.data.objects.remove(o, do_unlink=True)
os.makedirs(MODELS, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=os.path.join(MODELS, "aruun_projected.glb"), export_format="GLB")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(MODELS, "aruun_projected.blend"))
print("OK")
