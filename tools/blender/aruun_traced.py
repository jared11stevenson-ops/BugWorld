"""Aruun, traced from the reference planes with minimal interpretation.

 body   : silhouette-carved hull (tools/reference/trace_hull.py), lightly smoothed + decimated
 mace   : ball / spikes / haft placed from measurements taken on the cut-out front plane
 colour : the ORIGINAL art, projected from the front / back / side planes (triplanar) and baked to one 4k texture
Run (after extract_refs.py + trace_hull.py):  python3 tools/blender/aruun_traced.py [--no-bake] [--no-render]
Out: assets/models/aruun_traced.glb, aruun_traced.blend, evidence/models/traced_*.png
"""
import bpy, bmesh, os, sys, json, math
import numpy as np
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF, MODELS, PREV = (os.path.join(ROOT, p) for p in ("references/aruun", "assets/models", "evidence/models"))
TARGET_FACES = 90000
MACE_SCALE = 1.0          # 1.0 = exactly as drawn on the sheet
TEX = 4096
W, H, Z0, PXM = 3.2, 2.6, -0.1, 0.002       # plane size / bottom offset / m per px (matches extract_refs.py)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ------------------------------------------------------------------ body
d = np.load(os.path.join(MODELS, "aruun_hull.npz"))
me = bpy.data.meshes.new("Aruun_Body"); me.from_pydata(d["verts"].tolist(), [], d["faces"].tolist()); me.update()
body = bpy.data.objects.new("Aruun_Body", me); sc.collection.objects.link(body)
bpy.context.view_layer.objects.active = body; body.select_set(True)
for p in me.polygons: p.use_smooth = True
sm = body.modifiers.new("Smooth", "SMOOTH"); sm.factor = 0.5; sm.iterations = 4
dm = body.modifiers.new("Decimate", "DECIMATE"); dm.ratio = min(1.0, TARGET_FACES / len(me.polygons))
bpy.ops.object.modifier_apply(modifier="Smooth"); bpy.ops.object.modifier_apply(modifier="Decimate")
print("body faces", len(body.data.polygons))

# ------------------------------------------------------------------ mace (measured on the front cut-out)
mp = json.load(open(os.path.join(MODELS, "aruun_mace.json")))
bx, bz = mp["ball_center_xz"]; r_body = mp["ball_body_radius"] * MACE_SCALE; r_tip = r_body
gx, gz = mp["grip_xz"]
vs = np.asarray(body.data.vertices[i].co[:] for i in range(0)) if False else None
co = np.array([v.co[:] for v in body.data.vertices])
near = co[(abs(co[:, 0] - gx) < 0.10) & (abs(co[:, 2] - gz) < 0.12)]
by = float(near[:, 1].mean()) if len(near) else -0.05           # mace sits in the hand's depth plane
print("mace y", round(by, 3), "ball", bx, bz, "r", r_body, r_tip)
parts = []
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=r_body, location=(bx, by, bz)); parts.append(bpy.context.object)
for sp in mp["spikes"]:                                              # one cone per spike drawn on the sheet, in the view plane
    ang = math.radians(sp["angle_deg"]); dv = Vector((math.cos(ang), 0.0, math.sin(ang))); L_ = sp["tip_r"] * MACE_SCALE - r_body
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=max(L_ * 0.55, 0.012), radius2=0.004, depth=L_ * 1.25, location=Vector((bx, by, bz)) + dv * (r_body + L_ * 0.42))
    o = bpy.context.object; o.rotation_euler = dv.to_track_quat("Z", "Y").to_euler(); parts.append(o)
a, b = Vector((bx, by, bz)) + (Vector((gx, by, gz)) - Vector((bx, by, bz))).normalized() * r_body * 0.9, Vector((gx + 0.03, by, gz + 0.04))
bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.032, depth=(b - a).length, location=(a + b) / 2)
o = bpy.context.object; o.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler(); parts.append(o)
for o in parts: o.name = "Mace_part"
bpy.ops.object.select_all(action="DESELECT")
for o in parts: o.select_set(True)
bpy.context.view_layer.objects.active = parts[0]; bpy.ops.object.join(); mace = bpy.context.object; mace.name = "Aruun_Mace"
for p in mace.data.polygons: p.use_smooth = True
bpy.ops.object.select_all(action="DESELECT"); body.select_set(True); mace.select_set(True)
bpy.context.view_layer.objects.active = body; bpy.ops.object.join(); body.name = "Aruun"
body.location = (0, 0, 0)

# ------------------------------------------------------------------ triplanar projection of the original art
def load(name):
    im = bpy.data.images.load(os.path.join(REF, name)); im.alpha_mode = "STRAIGHT"; return im
IMG = {k: load(f"aruun_{k}.png") for k in ("front", "back", "side")}

def triplanar_emission(mat):
    mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear(); N, L = nt.nodes.new, nt.links.new
    tc = N("ShaderNodeTexCoord"); sep = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep.inputs[0])
    geo = N("ShaderNodeNewGeometry"); ns = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Normal"], ns.inputs[0])
    def madd(inp, mul, add):
        n = N("ShaderNodeMath"); n.operation = "MULTIPLY_ADD"; L(inp, n.inputs[0]); n.inputs[1].default_value = mul; n.inputs[2].default_value = add; return n.outputs[0]
    def math(op, a, b=None, clamp=False):
        n = N("ShaderNodeMath"); n.operation = op
        if isinstance(a, (int, float)): n.inputs[0].default_value = a
        else: L(a, n.inputs[0])
        if b is not None:
            if isinstance(b, (int, float)): n.inputs[1].default_value = b
            else: L(b, n.inputs[1])
        n.use_clamp = clamp; return n.outputs[0]
    z_v = madd(sep.outputs["Z"], 1 / H, -Z0 / H)
    uv = dict(front=(madd(sep.outputs["X"], 1 / W, 0.5), z_v), back=(madd(sep.outputs["X"], -1 / W, 0.5), z_v), side=(madd(sep.outputs["Y"], -1 / W, 0.5), z_v))
    nyneg = math("MAXIMUM", math("MULTIPLY", ns.outputs["Y"], -1.0), 0.0); nypos = math("MAXIMUM", ns.outputs["Y"], 0.0); nxa = math("ABSOLUTE", ns.outputs["X"])
    w = dict(front=math("ADD", math("MULTIPLY", math("POWER", nyneg, 3.0), 2.0), 0.01), back=math("MULTIPLY", math("POWER", nypos, 3.0), 2.0), side=math("POWER", nxa, 10.0))
    csum = None; wsum = None
    for k in ("front", "back", "side"):
        comb = N("ShaderNodeCombineXYZ"); L(uv[k][0], comb.inputs[0]); L(uv[k][1], comb.inputs[1])
        tex = N("ShaderNodeTexImage"); tex.image = IMG[k]; tex.extension = "CLIP"; tex.interpolation = "Linear"; L(comb.outputs[0], tex.inputs[0])
        ww = math("MULTIPLY", w[k], tex.outputs["Alpha"])
        sc_ = N("ShaderNodeVectorMath"); sc_.operation = "SCALE"; L(tex.outputs["Color"], sc_.inputs[0]); L(ww, sc_.inputs["Scale"])
        if csum is None: csum, wsum = sc_.outputs[0], ww
        else:
            va = N("ShaderNodeVectorMath"); va.operation = "ADD"; L(csum, va.inputs[0]); L(sc_.outputs[0], va.inputs[1]); csum = va.outputs[0]; wsum = math("ADD", wsum, ww)
    inv = math("DIVIDE", 1.0, math("MAXIMUM", wsum, 1e-4)); fin = N("ShaderNodeVectorMath"); fin.operation = "SCALE"; L(csum, fin.inputs[0]); L(inv, fin.inputs["Scale"])
    mix = N("ShaderNodeMix"); mix.data_type = "RGBA"; mix.inputs[6].default_value = (0.02, 0.018, 0.04, 1)
    L(math("MULTIPLY", wsum, 40.0, clamp=True), mix.inputs[0]); L(fin.outputs[0], mix.inputs[7])
    em = N("ShaderNodeEmission"); out = N("ShaderNodeOutputMaterial"); L(mix.outputs[2], em.inputs["Color"]); L(em.outputs[0], out.inputs[0])
    return nt

mat = bpy.data.materials.new("Aruun_Projected"); triplanar_emission(mat); body.data.materials.clear(); body.data.materials.append(mat)

# ------------------------------------------------------------------ cameras / render helpers
def cam_ortho(name, loc, rot):
    cd = bpy.data.cameras.new(name); cd.type = "ORTHO"; cd.ortho_scale = W; cd.sensor_fit = "HORIZONTAL"
    o = bpy.data.objects.new(name, cd); o.location = loc; o.rotation_euler = tuple(math.radians(a) for a in rot); sc.collection.objects.link(o); return o
CAM = dict(front=cam_ortho("cF", (0, -8, Z0 + H / 2), (90, 0, 0)), left=cam_ortho("cS", (-8, 0, Z0 + H / 2), (90, 0, -90)), back=cam_ortho("cB", (0, 8, Z0 + H / 2), (90, 0, 180)))
sc.render.engine = "BLENDER_EEVEE"; sc.render.film_transparent = True; sc.render.resolution_x, sc.render.resolution_y = 1600, 1300
sc.view_settings.view_transform = "Standard"

def render(name, cam, path_dir=PREV):
    sc.camera = cam; sc.render.filepath = os.path.join(path_dir, name + ".png"); bpy.ops.render.render(write_still=True)

if "--no-render" not in sys.argv:
    os.makedirs(PREV, exist_ok=True)
    for k in ("front", "left", "back"): render(f"traced_proj_{k}", CAM[k])

# ------------------------------------------------------------------ UV + bake the projection into one texture
if "--no-bake" not in sys.argv:
    bpy.ops.object.select_all(action="DESELECT"); body.select_set(True); bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002); bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("Aruun_BaseColor", TEX, TEX, alpha=False); img.colorspace_settings.name = "sRGB"
    node = mat.node_tree.nodes.new("ShaderNodeTexImage"); node.image = img; mat.node_tree.nodes.active = node
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 1; sc.cycles.use_denoising = False
    sc.render.bake.margin = 8; sc.render.bake.use_clear = True
    print("baking...", flush=True); bpy.ops.object.bake(type="EMIT")
    os.makedirs(MODELS, exist_ok=True); img.filepath_raw = os.path.join(MODELS, "aruun_traced_basecolor.png"); img.file_format = "PNG"; img.save()
    # final lit material: baked colour on a plain principled shader (what Godot/glTF will see)
    pm = bpy.data.materials.new("Aruun"); pm.use_nodes = True; n = pm.node_tree; b = n.nodes["Principled BSDF"]
    t = n.nodes.new("ShaderNodeTexImage"); t.image = img; n.links.new(t.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.55
    body.data.materials.clear(); body.data.materials.append(pm)
    sc.render.engine = "BLENDER_EEVEE"
    if "--no-render" not in sys.argv:
        def sun(name, rot, col, e):
            ld = bpy.data.lights.new(name, "SUN"); ld.energy = e; ld.color = col
            o = bpy.data.objects.new(name, ld); o.rotation_euler = tuple(math.radians(a) for a in rot); sc.collection.objects.link(o); return o
        sun("Key", (55, 0, -35), (1, 0.93, 0.82), 3.0); sun("Rim", (65, 0, 150), (0.7, 0.8, 1), 2.0); sun("Fill", (80, 0, 60), (0.9, 0.85, 1), 0.6)
        w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.52, 0.5, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.6
        for k in ("front", "left", "back"): render(f"traced_lit_{k}", CAM[k])
        cq = bpy.data.cameras.new("q"); cq.lens = 60; q = bpy.data.objects.new("q", cq); q.location = (-4.2, -5.2, 1.6); sc.collection.objects.link(q)
        q.rotation_euler = (Vector((0, 0, 1.15)) - q.location).to_track_quat("-Z", "Y").to_euler(); sc.render.resolution_x, sc.render.resolution_y = 1000, 1250
        render("traced_lit_3q", q)

# ------------------------------------------------------------------ export
for o in [o for o in sc.objects if o.type in ("CAMERA", "LIGHT")]: bpy.data.objects.remove(o, do_unlink=True)
os.makedirs(MODELS, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=os.path.join(MODELS, "aruun_traced.glb"), export_format="GLB")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(MODELS, "aruun_traced.blend"))
print("OK")
