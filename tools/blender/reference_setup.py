"""Build a Blender reference scene from references/aruun/*.png (see tools/reference/extract_refs.py).

Conventions (match tools/blender/aruun.py): metres, +Z up, character faces -Y, feet on z=0.
  front plane  : behind the character at +Y, seen from the FRONT camera (looking +Y)  numpad 1
  back plane   : in front of the character at -Y, seen from the BACK camera (looking -Y)  ctrl+numpad 1
  side plane   : at +X, seen from the LEFT camera (looking +X, character faces screen-right)  ctrl+numpad 3
Each plane is back-face culled, so it only shows from its own side and never blocks the other views.
Image scale is 1 px = 2 mm, so a 2.40 m figure = 1200 px; the ground line is at z=0.

Run:  python3 tools/blender/reference_setup.py            -> references/aruun/aruun_reference.blend (+ check renders)
      python3 tools/blender/reference_setup.py --no-render
Inside Blender's Scripting tab you can also run it directly (it only uses bpy).
"""
import bpy, os, sys, json, math
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath or __file__), "..", "..")) if "__file__" not in globals() else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "references", "aruun")
OUT_BLEND = os.path.join(REF, "aruun_reference.blend")
CHECK = os.path.join(ROOT, "evidence", "models")

PX = 0.002                       # metres per pixel
CW, CH, MB = 1600, 1300, 50      # canvas px and bottom margin px (must match extract_refs.py)
W, H = CW * PX, CH * PX          # 3.2 m x 2.6 m
Z0 = -MB * PX                    # plane bottom edge, so the ground line lands on z=0
DIST = 1.6                       # how far the planes sit from the origin

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
col = bpy.data.collections.new("REFERENCE"); sc.collection.children.link(col)

def image_plane(name, png, verts, uvs=((0, 0), (1, 0), (1, 1), (0, 1)), opacity=1.0):
    img = bpy.data.images.load(os.path.join(REF, png)); img.alpha_mode = "STRAIGHT"
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UV")
    for loop, p in zip(me.loops, uvs): uv.data[loop.index].uv = p
    m = bpy.data.materials.new(name); m.use_nodes = True; m.use_backface_culling = True
    m.surface_render_method = "DITHERED"
    nt = m.node_tree; nt.nodes.clear(); N, L = nt.nodes.new, nt.links.new
    tex = N("ShaderNodeTexImage"); tex.image = img; tex.interpolation = "Linear"
    em = N("ShaderNodeEmission"); tr = N("ShaderNodeBsdfTransparent"); mix = N("ShaderNodeMixShader"); out = N("ShaderNodeOutputMaterial")
    mulv = N("ShaderNodeMath"); mulv.operation = "MULTIPLY"; mulv.inputs[1].default_value = opacity
    L(tex.outputs["Color"], em.inputs["Color"]); L(tex.outputs["Alpha"], mulv.inputs[0]); L(mulv.outputs[0], mix.inputs[0])
    L(tr.outputs[0], mix.inputs[1]); L(em.outputs[0], mix.inputs[2]); L(mix.outputs[0], out.inputs[0])
    me.materials.append(m)
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    o.hide_select = True            # click-through while modelling; unlock in the outliner to move them
    o.visible_shadow = False
    return o

hw = W / 2
# FRONT: image right = +X, plane at +Y, normal -Y
image_plane("Ref_Front", "aruun_front.png", [(-hw, DIST, Z0), (hw, DIST, Z0), (hw, DIST, Z0 + H), (-hw, DIST, Z0 + H)])
# BACK: image right = -X, plane at -Y, normal +Y
image_plane("Ref_Back", "aruun_back.png", [(hw, -DIST, Z0), (-hw, -DIST, Z0), (-hw, -DIST, Z0 + H), (hw, -DIST, Z0 + H)])
# SIDE (left view from -X): image right = -Y, plane at +X, normal -X
image_plane("Ref_Side", "aruun_side.png", [(DIST, hw, Z0), (DIST, -hw, Z0), (DIST, -hw, Z0 + H), (DIST, hw, Z0 + H)])

# detail boards (head, mace, expressions...) laid out flat to the right of the front plane, same 1 px = 2 mm * 1/3 (they are 3x upscaled)
x = hw + 0.3
for nm, png in (("detail_head", "detail_head.png"), ("detail_mace", "detail_mace.png"), ("detail_expressions", "detail_expressions.png"), ("detail_wing_sketch", "detail_wing_sketch.png"), ("detail_beetle_ref", "detail_beetle_ref.png")):
    p = os.path.join(REF, png)
    if not os.path.exists(p): continue
    iw, ih = bpy.data.images.load(p).size
    w, h = iw * PX * 2, ih * PX * 2          # panels are 3x the sheet, the figures were scaled ~2.0-2.6x: close to the same scale
    image_plane("Ref_" + nm, png, [(x, DIST, 0), (x + w, DIST, 0), (x + w, DIST, h), (x, DIST, h)])
    x += w + 0.2

# 2.4 m ruler + 10 cm ground marks so scale is verifiable in the viewport
rb = bpy.data.objects.new("Ruler_2.4m", None); rb.empty_display_type = "SINGLE_ARROW"; rb.empty_display_size = 2.4; rb.location = (-1.2, 0, 0); col.objects.link(rb)
meta = json.load(open(os.path.join(REF, "measurements.json")))
print("palette:", [p["hex"] for p in meta["palette"]])

# cameras
def cam(name, loc, rot, ortho=3.4):
    d = bpy.data.cameras.new(name); d.type = "ORTHO"; d.ortho_scale = ortho
    o = bpy.data.objects.new(name, d); o.location = loc; o.rotation_euler = tuple(math.radians(a) for a in rot); sc.collection.objects.link(o); return o
cams = dict(front=cam("Cam_Front", (0, -6, 1.2), (90, 0, 0)),
            left=cam("Cam_Left", (-6, 0, 1.2), (90, 0, -90)),
            back=cam("Cam_Back", (0, 6, 1.2), (90, 0, 180)))
sc.render.engine = "BLENDER_EEVEE"; sc.render.resolution_x, sc.render.resolution_y = 1000, 1250
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.045, 0.047, 0.055, 1)
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

if "--no-render" not in sys.argv:
    os.makedirs(CHECK, exist_ok=True)
    for k, c in cams.items():
        sc.camera = c; c.data.shift_y = 0.0; c.data.shift_x = -0.12 if k == "front" else 0.0
        sc.render.filepath = os.path.join(CHECK, f"ref_check_{k}.png"); bpy.ops.render.render(write_still=True)
print("OK", OUT_BLEND)
