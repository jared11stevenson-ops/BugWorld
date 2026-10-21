// Decimate the high-poly CC0 scans to a console-class triangle budget (PS3-era).
// Deps (dev only, MIT): npm i @gltf-transform/core @gltf-transform/functions meshoptimizer
// Usage: node tools/optimize.mjs
import { NodeIO } from '@gltf-transform/core';
import { weld, simplify } from '@gltf-transform/functions';
import { MeshoptSimplifier } from 'meshoptimizer';
import fs from 'node:fs';
const TARGET = { boulder_01: 4500, chess_set: 9000, dandelion_01: 2500, dead_tree_trunk: 7000, fern_02: 6300, garden_gnome: 7000, gothic_statue: 14000,
  grass_medium_01: 3000, marble_bust_01: 9000, painted_wooden_chair_01: 800, rock_moss_set_01: 4500, root_cluster_01: 6000, tea_set_01: 6000,
  treasure_chest: 9000, tree_stump_01: 4500, vintage_grandfather_clock_01: 9000, vintage_oil_lamp: 7300, wooden_barrels_01: 6000, wooden_candlestick: 9000 };
await MeshoptSimplifier.ready;
const io = new NodeIO();
for (const [name, target] of Object.entries(TARGET)) {
  const path = `assets/models/${name}/${name}.gltf`; const doc = await io.read(path);
  const count = () => doc.getRoot().listMeshes().flatMap(m => m.listPrimitives()).reduce((a, p) => a + (p.getIndices()?.getCount() ?? 0) / 3, 0);
  const before = count(); if (before <= target * 1.05) { console.log(name, before, 'ok'); continue; }
  await doc.transform(weld(), simplify({ simplifier: MeshoptSimplifier, ratio: target / before, error: name === "boulder_01" ? 0.2 : 0.02, lockBorder: false }));
  await io.write(path, doc); console.log(name, before, '->', Math.round(count()));
}
