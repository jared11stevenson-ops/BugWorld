# Aruun – Blender-ready reference set

Every pixel here comes from `../aruun_sheet.png`. Nothing is redrawn or restyled; the figures are cut out of
the paper (text, labels, height bracket and ground shadow removed), uniformly scaled and placed on a shared canvas.

| file | what |
|---|---|
| `aruun_front.png` / `aruun_side.png` / `aruun_back.png` | transparent 1600x1300 planes, **1 px = 2 mm**, ground line y=1250, body axis x=800, horn tip→foot = 1200 px = **2.40 m** |
| `aruun_turnaround_guides.png` | the three views on a 10 cm grid with shared landmark lines (horn tip, eye, shoulder, hip, knee, ankle, ground) |
| `detail_*.png` | head, mace (retracted / extended / floating), five expressions, ability art, wing sketch, beetle photo – unmodified crops, 3x |
| `measurements.json` | per-view source box and scale factor, plus the five palette swatches (sRGB hex and linear) |
| `aruun_reference.blend` | planes, cameras and a 2.4 m ruler already set up (`tools/blender/reference_setup.py` rebuilds it) |

Blender axes: +Z up, character faces −Y. Front plane sits at +Y (use numpad 1), back plane at −Y (ctrl+numpad 1),
side plane at +X (ctrl+numpad 3, character faces screen-right). Planes are back-face culled and click-through.

## Caveats (they are properties of the source art, not of the extraction)
* The sheet's 240 cm bracket and human silhouette do not match the drawn figure, so scale is set by an assumed 2.40 m
  total height (horns included). Change `H_MM` in `tools/reference/extract_refs.py` for another height.
* The three drawings are not perfect orthographics: the front is a leaning 3/4 stance with the mace and is drawn larger,
  and landmark heights differ by roughly ±5 % between views (knee: front ≈0.27, side ≈0.33 of height). Use the guides sheet
  to see where they disagree and decide which view wins per body part.
* Body axes were set at the midpoint of the feet (front/back) and at the ankle (side); nudge the planes if needed.
