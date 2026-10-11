"""Cut the Aruun character sheet into Blender-ready reference planes.

Nothing is redrawn: every output pixel is a pixel of references/aruun_sheet.png
(only uniformly scaled and placed on a transparent canvas). The background paper,
label text, height bracket and ground shadow are removed; the design is untouched.

Run:  python3 -I tools/reference/extract_refs.py
Out:  references/aruun/*.png  +  references/aruun/measurements.json
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "references", "aruun_sheet.png")
OUT = os.path.join(ROOT, "references", "aruun")
os.makedirs(OUT, exist_ok=True)

sheet = Image.open(SRC).convert("RGB")
A = np.asarray(sheet).astype(np.int32)

# ---- paper colour: median of empty margins ----
PAPER = np.median(np.concatenate([A[300:330, 480:495].reshape(-1, 3), A[600:610, 5:18].reshape(-1, 3), A[130:150, 640:660].reshape(-1, 3)]), axis=0)
print("paper RGB", PAPER)

# ---- views: crop box (x0,y0,x1,y1) in sheet px, boxes to blank out (labels/text/bracket), ground-axis x ----
VIEWS = {
    "front": dict(box=(0, 0, 476, 612), blank=[], axis=350, shadow_y=535),
    "back":  dict(box=(458, 118, 640, 600), blank=[], axis=554, shadow_y=545),
    "side":  dict(box=(636, 118, 768, 600), blank=[(702, 430, 716, 566), (655, 588, 700, 606), (760, 100, 768, 600)], axis=672, shadow_y=550),
}
H_MM, PX_PER_MM = 2400, 0.5            # 1 px = 2 mm, figure 2.4 m = 1200 px tall
CANVAS_W, CANVAS_H, MARGIN_BOTTOM = 1600, 1300, 50

def bfs_label(mask, min_area=0):
    """4-connected labelling of True pixels; returns (labels, areas)."""
    h, w = mask.shape; lab = np.zeros((h, w), np.int32); areas = [0]; cur = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]: continue
        cur += 1; lab[y0, x0] = cur; q = deque([(y0, x0)]); n = 0
        while q:
            y, x = q.popleft(); n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = cur; q.append((yy, xx))
        areas.append(n)
    return lab, areas

def erode(m, n=1):
    for _ in range(n):
        p = np.pad(m, 1, constant_values=True)
        m = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m
def dilate(m, n=1):
    for _ in range(n):
        p = np.pad(m, 1, constant_values=False)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m

def cutout(box, blank, shadow_y):
    x0, y0, x1, y1 = box
    crop = A[y0:y1, x0:x1].copy()
    for bx0, by0, bx1, by1 in blank:                       # paint labels with paper so they drop out
        crop[max(0, by0 - y0):max(0, by1 - y0), max(0, bx0 - x0):max(0, bx1 - x0)] = PAPER.astype(np.int32)
    d = np.sqrt(((crop - PAPER) ** 2).sum(-1))
    loose = d < 34                                         # paper + soft ground shadow
    tight = d < 14                                         # paper only (for enclosed holes)
    # background = loose paper connected to the crop border (via a 1px-eroded mask so ink gaps can't leak)
    er = erode(loose, 1)
    lab, areas = bfs_label(er)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    bg = dilate(bg, 2) & loose
    # enclosed holes between limbs: big tight-paper regions not already background
    lab2, areas2 = bfs_label(erode(tight, 1) & ~bg)
    for i, a in enumerate(areas2):
        if i and a > 300: bg |= dilate(lab2 == i, 2) & tight
    # soft ground shadow: darker-but-proportional paper tone, only in the ground band, reachable from background
    ratio = crop / np.maximum(PAPER, 1); k = ratio.mean(-1)
    shadowlike = (k > 0.66) & (k < 1.02) & (np.abs(ratio - k[..., None]).max(-1) < 0.06)
    band = np.zeros_like(bg); band[max(0, shadow_y - y0):, :] = True
    shadowlike &= band
    grow = bg & band
    for _ in range(80):
        nxt = dilate(grow, 1) & (shadowlike | bg)
        if (nxt == grow).all(): break
        grow = nxt
    bg |= grow
    fg = erode(~bg, 1)                                   # shave the 1px paper-coloured fringe off the cut edge
    # drop detached specks (stray text bits, bracket ticks)
    lab3, areas3 = bfs_label(fg)
    main = int(np.argmax(areas3[1:])) + 1            # the figure itself = largest connected drawing
    near = dilate(lab3 == main, 7)                    # plus anything that touches/almost touches it (loose fingers, tassels)
    keep = np.isin(lab3, [i for i in np.unique(lab3[near]) if i and areas3[i] >= 20])
    alpha = Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    rgba = Image.fromarray(crop.astype(np.uint8)).convert("RGBA"); rgba.putalpha(alpha)
    return rgba

meta = {"units": "1 px = 2 mm; figure height 2400 mm; canvas 1600x1300 px; ground line at y=1250; axis x=800", "views": {}}
placed = {}
for name, v in VIEWS.items():
    im = cutout(v["box"], v["blank"], v["shadow_y"])
    bb = im.getchannel("A").point(lambda p: 255 if p > 40 else 0).getbbox()
    im = im.crop(bb)                                          # tight to the figure
    top, bottom = bb[1], bb[3]
    h_src = im.height
    s = (H_MM * PX_PER_MM) / h_src                            # uniform scale: horn tip -> lowest foot = 2.4 m
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    axis_in_crop = (v["axis"] - v["box"][0] - bb[0]) * s       # ground-axis x inside the tight crop
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    px, py = round(CANVAS_W / 2 - axis_in_crop), CANVAS_H - MARGIN_BOTTOM - im.height
    canvas.alpha_composite(im, (px, py))
    canvas.save(os.path.join(OUT, f"aruun_{name}.png"))
    placed[name] = canvas
    meta["views"][name] = dict(source_box=v["box"], source_height_px=h_src, scale_factor=round(s, 3), axis_sheet_x=v["axis"], figure_top_y=py, ground_y=py + im.height)
    print(name, "src h", h_src, "scale", round(s, 2), "->", im.size)

# ---- detail panels cut straight from the sheet (unmodified, upscaled 3x, paper kept: they are framed panels) ----
PANELS = {
    "detail_head":        (636, 12, 764, 118),
    "detail_beetle_ref":  (418, 24, 556, 118),
    "detail_mace":        (14, 628, 385, 790),
    "detail_expressions": (392, 628, 766, 792),
    "detail_wing_sketch": (585, 140, 660, 292),
    "detail_abilities":   (8, 812, 764, 1010),
}
for k, b in PANELS.items():
    c = sheet.crop(b); c = c.resize((c.width * 3, c.height * 3), Image.LANCZOS); c.save(os.path.join(OUT, k + ".png"))

# ---- palette: sample the five swatches on the sheet ----
pal = []
for i, (cx, cy) in enumerate([(32, 210), (32, 247), (32, 283), (32, 318), (32, 355)]):
    px = A[cy - 8:cy + 9, cx - 8:cx + 9].reshape(-1, 3); r, g, b = np.median(px, axis=0).astype(int)
    pal.append(dict(index=i + 1, hex="#%02x%02x%02x" % (r, g, b), srgb=[int(r), int(g), int(b)],
                    linear=[round(float(((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92), 4) for c in (r, g, b)]))
meta["palette"] = pal
json.dump(meta, open(os.path.join(OUT, "measurements.json"), "w"), indent=2)

# ---- guide sheet: the three views on a 10 cm / 50 cm grid with shared horizontal landmarks ----
LM = [("horn tip", 1.0), ("eye", 0.80), ("shoulder", 0.74), ("hip joint", 0.48), ("knee", 0.30), ("ankle", 0.10), ("ground", 0.0)]
SC = 0.5
GW, GH = int(CANVAS_W * SC), int(CANVAS_H * SC)
G = Image.new("RGBA", (GW * 3 + 80, GH + 90), (236, 233, 226, 255)); d = ImageDraw.Draw(G)
try: font = ImageFont.truetype("DejaVuSans.ttf", 13)
except Exception: font = ImageFont.load_default()
for i, name in enumerate(("front", "side", "back")):
    ox = 20 + i * (GW + 20); oy = 50
    d.rectangle((ox, oy, ox + GW, oy + GH), fill=(246, 244, 238, 255), outline=(150, 150, 150, 255))
    step = int(100 * PX_PER_MM * SC)                     # 10 cm
    gx0 = ox + GW // 2
    for k in range(-GW // step // 2 - 1, GW // step // 2 + 2):
        x = gx0 + k * step; major = (k % 5 == 0)
        d.line((x, oy, x, oy + GH), fill=(190, 200, 215, 255) if not major else (140, 160, 195, 255), width=1)
    ground = oy + GH - int(MARGIN_BOTTOM * SC)
    for k in range(0, int(GH / step) + 2):
        y = ground - k * step; major = (k % 5 == 0)
        if y >= oy: d.line((ox, y, ox + GW, y), fill=(190, 200, 215, 255) if not major else (140, 160, 195, 255), width=1)
    d.line((gx0, oy, gx0, oy + GH), fill=(60, 120, 220, 255), width=1)       # ground axis
    small = placed[name].resize((GW, GH), Image.LANCZOS); G.alpha_composite(small, (ox, oy))
    d = ImageDraw.Draw(G)
    for lab, f in LM:
        y = ground - int(f * H_MM * PX_PER_MM * SC)
        d.line((ox, y, ox + GW, y), fill=(220, 40, 120, 255), width=1)
        d.text((ox + 4, y - 14), lab, fill=(200, 20, 100, 255), font=font)
    d.text((ox, 18), name.upper() + "  (1 square = 10 cm, heavy line = 50 cm, 2.40 m total)", fill=(30, 30, 30, 255), font=font)
G.convert("RGB").save(os.path.join(OUT, "aruun_turnaround_guides.png"))
print("done ->", OUT)
