# Credits & licensing

Everything here is public domain / CC0, MIT-licensed, or written for this project. CC0 needs no attribution; it is given anyway.

| What | Source | License |
|---|---|---|
| 19 3D models (gothic statue, marble bust, chess set, candlestick, tea set, treasure chest, grandfather clock, oil lamp, garden gnome, chair, barrels, fern, grass, dandelion, stump, fallen logs, boulder, mossy rocks, roots) | [Poly Haven](https://polyhaven.com) | CC0 |
| Ground / marble / mossy-brick PBR textures (three more fetched but unused) | Poly Haven | CC0 |
| Environment lighting + sky (`dark_autumn_forest` HDRI) | Poly Haven | CC0 |
| three.js r170 + loader/post-processing add-ons (`vendor/three`) | [mrdoob/three.js](https://github.com/mrdoob/three.js) | MIT (`vendor/three/LICENSE`) |
| glTF-Transform, meshoptimizer (dev-time decimation only, `tools/optimize.mjs`) | donmccurdy / zeux | MIT |
| Music + SFX | Synthesised live in WebAudio (`src/audio.js`) | Original |
| Hero, enemy behaviour, engine, UI, world layout | This repo | Original |
| Lore inspiration | E. A. Poe, *The Fall of the House of Usher* (1839) | Public domain |

Models were decimated from scan grade (up to 225k tris) to 1-14k tris by `tools/optimize.mjs`; textures are the 1k versions.
`tools/fetch_assets.py` re-downloads the originals.
