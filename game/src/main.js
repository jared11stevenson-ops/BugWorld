import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { initAudio, sfx, setIntensity } from './audio.js';

const $ = id => document.getElementById(id);
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
let seed = 1337; const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
const rr = (a, b) => a + rnd() * (b - a);

// ---------- value noise terrain ----------
const hash = (x, y) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };
const vnoise = (x, y) => { const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  return lerp(lerp(hash(xi, yi), hash(xi + 1, yi), u), lerp(hash(xi, yi + 1), hash(xi + 1, yi + 1), u), v); };
const fbm = (x, y) => { let a = 0.5, f = 1, s = 0; for (let i = 0; i < 4; i++) { s += a * vnoise(x * f, y * f); f *= 2; a *= 0.5; } return s; };
const WORLD_R = 92;
function terrainH(x, z) {
  const r = Math.hypot(x, z);
  return (fbm(x * 0.03 + 9, z * 0.03 + 4) - 0.45) * 9 * smooth(26, 60, r) + smooth(WORLD_R - 6, WORLD_R + 20, r) * 14;
}

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
const LOW = new URLSearchParams(location.search).get('q') === 'low';
renderer.setPixelRatio(LOW ? 1 : Math.min(devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = !LOW; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.0;
document.body.prepend(renderer.domElement);
const scene = new THREE.Scene();
const FOG = 0x1a2230;
scene.fog = new THREE.FogExp2(FOG, 0.02);
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 400);
scene.add(camera);

const moon = new THREE.DirectionalLight(0xaec4ff, 2.3);
moon.position.set(-30, 30, 20); moon.castShadow = true;
moon.shadow.mapSize.set(2048, 2048); moon.shadow.bias = -0.0004; moon.shadow.normalBias = 0.04;
moon.castShadow = !LOW;
Object.assign(moon.shadow.camera, { left: -38, right: 38, top: 38, bottom: -38, near: 1, far: 140 });
scene.add(moon, moon.target);
scene.add(new THREE.HemisphereLight(0x6a7fa8, 0x2a2018, 1.0));
const lantern = new THREE.PointLight(0xffa24a, 22, 22, 2); lantern.castShadow = false; scene.add(lantern);

// post: bloom + grade (vignette, grain, desaturation, cool shadows / warm highlights)
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.45, 0.8, 0.82); if (!LOW) composer.addPass(bloom);
const grade = new ShaderPass({
  uniforms: { tDiffuse: { value: null }, time: { value: 0 }, hurt: { value: 0 } },
  vertexShader: 'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader: `uniform sampler2D tDiffuse;uniform float time,hurt;varying vec2 vUv;
  float h(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
  void main(){vec2 uv=vUv,c=uv-.5;float d=dot(c,c);
    vec2 o=c*d*.012;vec3 col=vec3(texture2D(tDiffuse,uv+o).r,texture2D(tDiffuse,uv).g,texture2D(tDiffuse,uv-o).b);
    float l=dot(col,vec3(.299,.587,.114));col=mix(vec3(l),col,.82);
    col=mix(col*vec3(.9,.98,1.12),col*vec3(1.08,1.0,.9),smoothstep(.1,.7,l));
    col*=1.-d*1.35;col+=(h(uv*vec2(1920.,1080.)+time)-.5)*.035;col=mix(col,col*vec3(1.6,.4,.4),hurt*.6);
    gl_FragColor=vec4(col,1.);}`
});
composer.addPass(grade); composer.addPass(new OutputPass());
addEventListener('resize', () => { renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight); camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); });

// ---------- loading ----------
const gl = new GLTFLoader(); const texL = new THREE.TextureLoader();
const models = {}; let loaded = 0;
const MODEL_NAMES = ['gothic_statue', 'marble_bust_01', 'chess_set', 'wooden_candlestick', 'fern_02', 'grass_medium_01', 'dandelion_01', 'tree_stump_01',
  'dead_tree_trunk', 'boulder_01', 'rock_moss_set_01', 'wooden_barrels_01', 'tea_set_01', 'vintage_oil_lamp', 'treasure_chest', 'root_cluster_01',
  'garden_gnome', 'painted_wooden_chair_01', 'vintage_grandfather_clock_01'];
const TOTAL = MODEL_NAMES.length + 7;
const tick = () => { $('load').firstElementChild.style.width = (++loaded / TOTAL * 100) + '%'; };
const loadTex = (name, srgb, rep) => new Promise(res => texL.load(`assets/tex/${name}.jpg`, t => {
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(rep, rep); t.anisotropy = 8; if (srgb) t.colorSpace = THREE.SRGBColorSpace; tick(); res(t); }));
const pbr = async (id, rep) => new THREE.MeshStandardMaterial({ map: await loadTex(id + '_diff', true, rep), normalMap: await loadTex(id + '_nor', false, rep), roughnessMap: await loadTex(id + '_arm', false, rep), roughness: 1, metalness: 0 });

async function loadAll() {
  const hdrP = new Promise(res => new RGBELoader().load('assets/hdri/dark_autumn_forest.hdr', t => {
    t.mapping = THREE.EquirectangularReflectionMapping; scene.environment = t; scene.background = t;
    scene.environmentIntensity = 0.6; scene.backgroundIntensity = 0.3; scene.backgroundBlurriness = 0.15; tick(); res(); }));
  const mp = MODEL_NAMES.map(n => new Promise((res, rej) => gl.load(`assets/models/${n}/${n}.gltf`, g => { models[n] = g.scene; tick(); res(); }, undefined, rej)));
  const mats = {};
  await Promise.all([hdrP, ...mp, (async () => { mats.ground = await pbr('forest_ground_04', 220); })(), (async () => { mats.marble = await pbr('marble_tiles', 3); })(),
    (async () => { mats.brick = await pbr('mossy_brick_floor', 5); })()]);
  return mats;
}

// ---------- helpers ----------
const bboxOf = o => new THREE.Box3().setFromObject(o);
function prepared(name, height, { cast = true, double = false } = {}) {
  const src = models[name].clone(true); const b = bboxOf(src); const sz = b.getSize(V3()); const s = height / Math.max(0.001, Math.max(sz.x, sz.y, sz.z));
  const wrap = new THREE.Group(); src.scale.setScalar(s); src.position.set(-(b.min.x + b.max.x) / 2 * s, -b.min.y * s, -(b.min.z + b.max.z) / 2 * s);
  wrap.add(src);
  src.traverse(m => { if (m.isMesh) { m.castShadow = cast; m.receiveShadow = true; m.material = m.material.clone(); if (double) m.material.side = THREE.DoubleSide; } });
  wrap.userData.height = height; return wrap;
}
// instanced scatter of a loaded model (one InstancedMesh per sub-mesh)
function scatter(name, height, placements, { double = false, cast = true, maxDim = false } = {}) {
  const src = models[name]; const b = bboxOf(src); const sz = b.getSize(V3()); const s = height / Math.max(0.001, maxDim ? Math.max(sz.x, sz.y, sz.z) : sz.y);
  const base = new THREE.Matrix4().makeScale(s, s, s).setPosition(-(b.min.x + b.max.x) / 2 * s, -b.min.y * s, -(b.min.z + b.max.z) / 2 * s);
  src.updateMatrixWorld(true); const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  src.traverse(mesh => {
    if (!mesh.isMesh) return;
    instCells(mesh.geometry, double ? Object.assign(mesh.material.clone(), { side: THREE.DoubleSide }) : mesh.material, base.clone().multiply(mesh.matrixWorld), placements, cast, true);
  });
}
function instCells(geometry, mat, local, placements, cast, receive) {
  const q = new THREE.Quaternion(), e = new THREE.Euler(), m4 = new THREE.Matrix4(); const cells = new Map(); // 36m cells: per-cell frustum culling
  placements.forEach(p => { const key = Math.floor(p.x / 36) + ',' + Math.floor(p.z / 36); (cells.get(key) || cells.set(key, []).get(key)).push(p); });
  for (const list of cells.values()) {
    const inst = new THREE.InstancedMesh(geometry, mat, list.length); inst.castShadow = cast; inst.receiveShadow = receive;
    list.forEach((p, i) => { q.setFromEuler(e.set(p.tilt || 0, p.rot || 0, 0)); m4.compose(V3(p.x, terrainH(p.x, p.z) - 0.05, p.z), q, V3(p.s || 1, p.s || 1, p.s || 1)); m4.multiply(local); inst.setMatrixAt(i, m4); });
    inst.computeBoundingSphere(); scene.add(inst);
  }
}
const colliders = []; // {x,z,r}
const addCol = (x, z, r) => colliders.push({ x, z, r });
function place(obj, x, z, rot = 0, y = null) { obj.position.set(x, y ?? terrainH(x, z), z); obj.rotation.y = rot; scene.add(obj); return obj; }
function flame(parent, y, color = 0xffb060, intensity = 14, dist = 14) {
  const l = new THREE.PointLight(color, intensity, dist, 2); l.position.set(0, y, 0); parent.add(l);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  sp.scale.setScalar(1.6); sp.position.set(0, y, 0); parent.add(sp); (flames ||= []).push({ l, sp, base: intensity, ph: Math.random() * 9 }); return l;
}
let flames;
const glowTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'); const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.25, 'rgba(255,255,255,.35)'); g.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = g; x.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); })();

// ---------- game state ----------
const G = { started: false, paused: false, over: false, shards: 0, hp: 100, st: 100, respawn: V3(0, 0, 40), bossAwake: false, bossDead: false, time: 0, shake: 0, hurt: 0 };
const input = { keys: {}, mdx: 0, mdy: 0, click: false };
const player = { pos: V3(0, 0, 40), vel: V3(), yaw: Math.PI, face: Math.PI, rollT: 0, rollDir: V3(), atkT: 0, atkHit: new Set(), combo: 0, iframes: 0, stepT: 0, group: null };
const enemies = []; const shrines = []; const chests = []; const pickups = [];
let camYaw = 0, camPitch = 0.28, boss = null, objT = '';

// ---------- world build ----------
function buildTerrain(mats) {
  const geo = new THREE.PlaneGeometry(520, 520, 260, 260); geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position, col = new Float32Array(p.count * 3);
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i); p.setY(i, terrainH(x, z));
    const v = 0.3 + fbm(x * 0.09, z * 0.09) * 0.5, r = Math.hypot(x, z); const tint = smooth(24, 34, r);
    col[i * 3] = v * lerp(0.7, 1, tint); col[i * 3 + 1] = v * lerp(0.75, 1.05, tint); col[i * 3 + 2] = v * lerp(0.8, 0.95, tint);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3)); geo.computeVertexNormals();
  const m = mats.ground.clone(); m.vertexColors = true; const ter = new THREE.Mesh(geo, m); ter.receiveShadow = true; scene.add(ter);
  // manor courtyard: marble disc with brick ring
  const ring = new THREE.Mesh(new THREE.RingGeometry(21, 27, 64, 1), mats.brick); ring.rotation.x = -Math.PI / 2; ring.position.y = 0.04; ring.receiveShadow = true; scene.add(ring);
  ring.geometry.attributes.uv.array.forEach((_, i, a) => { a[i] *= 0.5; });
  mats.marble.color.setScalar(0.45); mats.brick.color.setScalar(0.55);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(21, 64), mats.marble); disc.rotation.x = -Math.PI / 2; disc.position.y = 0.05; disc.receiveShadow = true; scene.add(disc);
  const uv = disc.geometry.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) - 0.5) * 3, (uv.getY(i) - 0.5) * 3);
  // approach path from south gate: brick strip
  const path = new THREE.Mesh(new THREE.PlaneGeometry(5, 40, 1, 1), mats.brick); path.rotation.x = -Math.PI / 2; path.position.set(0, 0.04, 47);
  for (let i = 0; i < 4; i++) path.geometry.attributes.uv.setXY(i, path.geometry.attributes.uv.getX(i) * 2, path.geometry.attributes.uv.getY(i) * 16);
  path.receiveShadow = true; scene.add(path);
}

function buildScatter() {
  const R = () => { const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()) * (WORLD_R + 8); return { x: Math.cos(a) * r, z: Math.sin(a) * r }; };
  const out = (n, minR = 24, maxR = WORLD_R + 8, extra = () => ({})) => { const a = []; let g = 0; while (a.length < n && g++ < n * 20) { const p = R(), r = Math.hypot(p.x, p.z); if (r > minR && r < maxR && !(Math.abs(p.x) < 5 && p.z > 20)) a.push({ ...p, rot: rnd() * 6.28, s: rr(0.7, 1.3), ...extra() }); } return a; };
  scatter('fern_02', 1.0, out(170), { double: true, cast: false });
  scatter('grass_medium_01', 0.7, out(320, 22), { double: true, cast: false });
  scatter('dandelion_01', 0.4, out(70), { double: true, cast: false });
  scatter('root_cluster_01', 2.2, out(14, 30), { maxDim: true });
  const stumps = out(26, 30); scatter('tree_stump_01', 1.3, stumps, { maxDim: true }); stumps.forEach(p => addCol(p.x, p.z, 0.7 * p.s));
  const rocks = out(30, 28); scatter('boulder_01', 2.6, rocks, { maxDim: true }); rocks.forEach(p => addCol(p.x, p.z, 1.3 * p.s));
  scatter('rock_moss_set_01', 2.0, out(40, 28), { maxDim: true });
  // fallen logs (scanned) as ground debris
  const logs = out(26, 30); scatter('dead_tree_trunk', 5.5, logs, { maxDim: true }); logs.forEach(p => addCol(p.x, p.z, 0.9));
  // standing dead forest: procedural gnarled trunks wearing the scanned bark material
  const bark = (() => { let m; models.dead_tree_trunk.traverse(o => { if (o.isMesh && !m) m = o.material; }); return m.clone(); })(); bark.side = THREE.DoubleSide;
  const parts = []; const trunk = new THREE.CylinderGeometry(0.28, 0.75, 13, 9, 7, true);
  const tp = trunk.attributes.position; for (let i = 0; i < tp.count; i++) { const y = tp.getY(i); tp.setX(i, tp.getX(i) + Math.sin(y * 0.7) * 0.25); tp.setZ(i, tp.getZ(i) + Math.cos(y * 0.5) * 0.25); }
  trunk.translate(0, 6.5, 0); parts.push(trunk);
  for (let i = 0; i < 6; i++) { const len = 2.2 + (i % 3) * 1.1, br = new THREE.CylinderGeometry(0.03, 0.14, len, 5, 1, true); br.translate(0, len / 2, 0);
    br.rotateZ(1.0 + (i % 2) * 0.3); br.rotateY(i * 1.05); br.translate(0, 5 + i * 1.3, 0); parts.push(br); }
  const treeGeo = mergeGeometries(parts.map(g => g.index ? g.toNonIndexed() : g));
  const trees = out(170, 34, WORLD_R + 14, () => ({ s: rr(0.8, 1.5) })).filter(p => Math.hypot(p.x, p.z) > 56 || rnd() < 0.3);
  instCells(treeGeo, bark, new THREE.Matrix4(), trees, true, false); trees.forEach(p => addCol(p.x, p.z, 0.7 * p.s));
  const rim = []; for (let i = 0; i < 110; i++) { const a = i / 110 * Math.PI * 2, r = WORLD_R + rr(-2, 12); rim.push({ x: Math.cos(a) * r, z: Math.sin(a) * r, rot: rnd() * 6, s: rr(1.3, 2.0) }); }
  instCells(treeGeo, bark, new THREE.Matrix4(), rim, true, false);
}

function buildCourtyard() {
  // statues ring (decor, towering) + busts + set pieces
  for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2 + 0.2, r = 19.5;
    const s = prepared('gothic_statue', 4.2); place(s, Math.cos(a) * r, Math.sin(a) * r, -a - Math.PI / 2); addCol(Math.cos(a) * r, Math.sin(a) * r, 1);
    if (i % 2) { const b = prepared('marble_bust_01', 1.1); place(b, Math.cos(a + 0.2) * 23, Math.sin(a + 0.2) * 23, rr(0, 6)); } }
  const chess = prepared('chess_set', 2.4); place(chess, -12, 11, 0.6); addCol(-12, 11, 1.8);
  const tea = prepared('tea_set_01', 1.1); place(tea, -9.5, 13.5, 0.2);
  const chair = prepared('painted_wooden_chair_01', 1.8); place(chair, -15, 13, 2.2); addCol(-15, 13, 0.8);
  for (let i = 0; i < 5; i++) { const b = prepared('wooden_barrels_01', 1.3); const p = { x: 14 + rr(-2, 2), z: 10 + i * 1.6 }; place(b, p.x, p.z, rr(0, 6)); addCol(p.x, p.z, 1); }
  const gn = prepared('garden_gnome', 0.9); place(gn, 4, 44, 3.3); gn.userData.gnome = true; interacts.push({ obj: gn, r: 2.2, text: 'E · Examine the gnome', act: () => say('Someone has painted his eyes shut. He seems pleased about it.') });
  // boss: the Master Clock
  const clock = prepared('vintage_grandfather_clock_01', 9); place(clock, 0, -2, 0); addCol(0, -2, 2.8); clock.userData.base = clock.position.clone();
  boss = { obj: clock, hp: 40, max: 40, t: 0, tollT: 6, summonT: 12, rings: [], dead: false };
  const glow = new THREE.PointLight(0x8fb8ff, 0, 22, 2); glow.position.set(0, 6.5, 1.5); clock.add(glow); boss.glow = glow;
}

function buildZones() {
  const zones = [
    { name: 'the Weeping Garden', x: -58, z: 14, n: 4, kinds: 'sssb' },
    { name: 'the Deadwood', x: 60, z: -22, n: 5, kinds: 'ssbbs' },
    { name: 'the Barrow', x: 4, z: -68, n: 5, kinds: 'sbsbs' },
  ];
  // shrine at start, one per zone
  makeShrine(0, 36, 'the Gate');
  zones.forEach((z, zi) => {
    makeShrine(z.x + 7, z.z + 7, z.name);
    const c = prepared('treasure_chest', 1.0); place(c, z.x, z.z, rr(0, 6)); addCol(z.x, z.z, 0.8);
    chests.push({ obj: c, open: false, zone: z.name, i: zi });
    interacts.push({ obj: c, r: 2.2, text: 'E · Open the chest', cond: () => !chests[zi].open && enemiesNear(z.x, z.z, 18) === 0, deny: 'Something still stirs nearby…',
      act: () => { chests[zi].open = true; G.shards++; sfx.pickup(); sfx.bell(0.25); say(`You find a Hand of the Master Clock. (${G.shards}/3)`); burst(c.position.clone().add(V3(0, 0.8, 0)), 0xffd070, 60, 3); if (G.shards === 3) say('The Hands are whole. The Master Clock stirs in the courtyard.', 5); updObj(); } });
    for (let i = 0; i < z.n; i++) { const a = i / z.n * 6.28 + rnd(), r = rr(7, 12); spawnEnemy(z.kinds[i] === 's' ? 'statue' : 'bust', z.x + Math.cos(a) * r, z.z + Math.sin(a) * r); }
    // landmark: great statue and a few lamps
    const big = prepared('gothic_statue', 7); place(big, z.x - 4, z.z - 5, rr(0, 6)); addCol(z.x - 4, z.z - 5, 1.6);
  });
}

const interacts = [];
function makeShrine(x, z, name) {
  const c = prepared('wooden_candlestick', 2.0); place(c, x, z, 0); addCol(x, z, 0.5);
  const l = new THREE.PointLight(0xffa04a, 0, 20, 2); l.position.set(0, 2.1, 0); c.add(l);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0xffb060, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0 })); sp.scale.setScalar(1.6); sp.position.set(0, 2.1, 0); c.add(sp);
  const sh = { obj: c, l, sp, lit: false, name, x, z }; shrines.push(sh);
  interacts.push({ obj: c, r: 2.4, text: () => sh.lit ? 'E · Rest at the candle' : 'E · Light the candle',
    act: () => { sh.lit = true; G.respawn.set(x + 1.2, 0, z + 1.2); G.hp = 100; G.st = 100; sfx.bell(0.2); say(`You rest at the candle of ${name}. Wounds knit; the hour holds.`);
      enemies.forEach(e => { if (e.state === 'dead') return; }); } });
}
const enemiesNear = (x, z, r) => enemies.filter(e => e.state !== 'dead' && Math.hypot(e.obj.position.x - x, e.obj.position.z - z) < r).length;

function spawnEnemy(type, x, z) {
  const o = type === 'statue' ? prepared('gothic_statue', 2.5) : prepared('marble_bust_01', 1.0);
  place(o, x, z, rr(0, 6)); const e = { type, obj: o, hp: type === 'statue' ? 4 : 2, state: 'dormant', t: 0, vel: V3(), home: V3(x, 0, z), flash: 0, cd: rr(1, 3), ph: rr(0, 6), hit: false };
  o.traverse(m => { if (m.isMesh) { m.material.emissive = new THREE.Color(0); } });
  if (type === 'bust') o.position.y = terrainH(x, z) + 1.5;
  if (type === 'statue') addCol(x, z, 0.0);
  enemies.push(e);
}

// ---------- player ----------
function buildPlayer() {
  const g = new THREE.Group(); const cloth = new THREE.MeshStandardMaterial({ color: 0x1b1d26, roughness: 0.9 });
  const cloak = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.58, 1.55, 18, 4, true), cloth); cloak.material.side = THREE.DoubleSide; cloak.position.y = 0.85; cloak.castShadow = true; g.add(cloak);
  const pos = cloak.geometry.attributes.position; for (let i = 0; i < pos.count; i++) { const a = Math.atan2(pos.getZ(i), pos.getX(i)); const y = pos.getY(i); const k = 1 + Math.sin(a * 5) * 0.07 * (0.5 - y / 1.55); pos.setX(i, pos.getX(i) * k); pos.setZ(i, pos.getZ(i) * k); }
  cloak.geometry.computeVertexNormals();
  const hood = new THREE.Mesh(new THREE.SphereGeometry(0.25, 20, 16), cloth); hood.scale.set(1, 1.15, 1.1); hood.position.set(0, 1.78, 0); hood.castShadow = true; g.add(hood);
  const face = new THREE.Mesh(new THREE.SphereGeometry(0.19, 16, 12), new THREE.MeshBasicMaterial({ color: 0x020203 })); face.position.set(0, 1.76, 0.1); face.scale.set(1, 1.1, 0.8); g.add(face);
  for (const sx of [-1, 1]) { const eye = new THREE.Mesh(new THREE.SphereGeometry(0.02, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffd9a0 })); eye.position.set(sx * 0.07, 1.78, 0.25); g.add(eye); }
  const sword = new THREE.Group(); sword.position.set(0.5, 1.25, 0.1);
  const blade = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.15, 0.015), new THREE.MeshStandardMaterial({ color: 0xc8d0dc, metalness: 1, roughness: 0.25 })); blade.position.y = 0.65; blade.castShadow = true;
  const guard = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.05, 0.06), new THREE.MeshStandardMaterial({ color: 0x8a6a2d, metalness: 1, roughness: 0.4 }));
  const grip = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.2, 8), cloth); grip.position.y = -0.12;
  sword.add(blade, guard, grip); sword.rotation.x = Math.PI / 2 + 0.3; g.add(sword);
  const lamp = prepared('vintage_oil_lamp', 0.42); lamp.position.set(-0.5, 0.95, 0.25); g.add(lamp);
  g.userData = { cloak, sword, hood }; scene.add(g); player.group = g;
  const arc = new THREE.Mesh(new THREE.RingGeometry(1.0, 2.5, 24, 1, -1.0, 2.0), new THREE.MeshBasicMaterial({ color: 0xcfe0ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false }));
  arc.rotation.x = -Math.PI / 2; arc.rotation.z = Math.PI / 2; arc.position.y = 1.1; g.add(arc); g.userData.arc = arc;
}

// ---------- particles ----------
const PN = 400; const pGeo = new THREE.BufferGeometry(); const pPos = new Float32Array(PN * 3), pCol = new Float32Array(PN * 3); const pVel = new Float32Array(PN * 3), pLife = new Float32Array(PN);
pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3)); pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3));
const pPts = new THREE.Points(pGeo, new THREE.PointsMaterial({ size: 0.16, map: glowTex, vertexColors: true, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true })); pPts.frustumCulled = false; scene.add(pPts);
let pHead = 0;
function burst(p, color, n = 24, speed = 4) {
  const c = new THREE.Color(color);
  for (let i = 0; i < n; i++) { const k = pHead++ % PN; pPos.set([p.x, p.y, p.z], k * 3); const v = V3(rr(-1, 1), rr(-0.2, 1.2), rr(-1, 1)).normalize().multiplyScalar(rr(0.3, 1) * speed); pVel.set([v.x, v.y, v.z], k * 3); pCol.set([c.r, c.g, c.b], k * 3); pLife[k] = rr(0.5, 1.2); }
}
function updParticles(dt) {
  for (let i = 0; i < PN; i++) { if (pLife[i] <= 0) { pPos[i * 3 + 1] = -999; continue; } pLife[i] -= dt; pVel[i * 3 + 1] -= 6 * dt; for (let a = 0; a < 3; a++) pPos[i * 3 + a] += pVel[i * 3 + a] * dt; pCol[i * 3] *= 0.985; pCol[i * 3 + 1] *= 0.985; pCol[i * 3 + 2] *= 0.985; }
  pGeo.attributes.position.needsUpdate = true; pGeo.attributes.color.needsUpdate = true;
}
// fireflies / motes
const FN = 220; const fGeo = new THREE.BufferGeometry(); const fPos = new Float32Array(FN * 3); const fSeed = [];
for (let i = 0; i < FN; i++) { const a = rnd() * 6.28, r = rnd() * 80; fPos.set([Math.cos(a) * r, rr(0.4, 4), Math.sin(a) * r], i * 3); fSeed.push(rnd() * 100); }
fGeo.setAttribute('position', new THREE.BufferAttribute(fPos, 3));
const flies = new THREE.Points(fGeo, new THREE.PointsMaterial({ size: 0.22, map: glowTex, color: 0xc8ff90, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true })); flies.frustumCulled = false; scene.add(flies);

// ---------- ui ----------
let subT = 0;
function say(t, d = 4) { $('sub').textContent = t; $('sub').style.opacity = 1; subT = d; }
function updObj() {
  const nxt = G.bossDead ? 'The hour has ended.' : G.shards < 3 ? `Recover the Hands of the Master Clock (${G.shards}/3)` : 'Destroy the Master Clock in the courtyard';
  $('objt').textContent = nxt;
}
function objectivePos() {
  if (G.bossDead) return null; if (G.shards >= 3) return V3(0, 0, -2);
  const open = chests.filter(c => !c.open).sort((a, b) => a.obj.position.distanceTo(player.pos) - b.obj.position.distanceTo(player.pos))[0]; return open ? open.obj.position : null;
}

// ---------- input ----------
addEventListener('keydown', e => { input.keys[e.code] = true; if (e.code === 'Space') e.preventDefault(); if (e.code === 'KeyE') interactNow = true;
  if (e.code === 'Escape' && G.started && !G.over) { G.paused = !G.paused; if (G.paused) document.exitPointerLock?.(); say(G.paused ? 'Paused — click to continue' : '', G.paused ? 999 : 0); } });
addEventListener('keyup', e => { input.keys[e.code] = false; });
addEventListener('mousemove', e => { if (document.pointerLockElement || e.buttons) { input.mdx += e.movementX; input.mdy += e.movementY; } });
addEventListener('mousedown', e => { if (!G.started) return; if (G.paused) { G.paused = false; say('', 0); } if (e.button === 0) { input.click = true; if (!document.pointerLockElement) renderer.domElement.requestPointerLock?.(); } });
let interactNow = false;

// ---------- combat ----------
function hurtPlayer(dmg, from) {
  if (player.iframes > 0 || G.over) return; G.hp -= dmg; player.iframes = 0.7; G.hurt = 1; G.shake = 0.5; sfx.hurt(); burst(player.pos.clone().add(V3(0, 1.2, 0)), 0xb02020, 22, 3);
  if (from) { const k = player.pos.clone().sub(from).setY(0).normalize().multiplyScalar(6); player.vel.add(k); }
  if (G.hp <= 0) die();
}
function die() {
  G.over = true; $('flash').style.opacity = 0.9; say('The hour claims you…', 3.2); sfx.bell(0.4);
  setTimeout(() => { player.pos.copy(G.respawn); player.vel.set(0, 0, 0); G.hp = 100; G.st = 100; G.over = false; $('flash').style.opacity = 0; enemies.forEach(e => { if (e.state !== 'dead' && e.state !== 'dormant') { e.state = 'dormant'; e.obj.position.x = e.home.x; e.obj.position.z = e.home.z; e.hp = e.type === 'statue' ? 4 : 2; } }); say('You wake at the last candle.'); }, 2800);
}
function damageEnemy(e, dmg, dir) {
  if (e.state === 'dead') return; e.hp -= dmg; e.flash = 1; e.vel.copy(dir).setY(0).multiplyScalar(7); e.state = e.state === 'dormant' ? 'chase' : e.state; if (e.state === 'strike' || e.state === 'windup') e.state = 'recover', e.t = 0.5;
  sfx.hit(); G.shake = 0.25; burst(e.obj.position.clone().add(V3(0, 1, 0)), 0xcfe0ff, 18, 4);
  if (e.hp <= 0) { e.state = 'dead'; e.t = 0; burst(e.obj.position.clone().add(V3(0, 1, 0)), 0xffd070, 40, 5); sfx.bell(0.15); }
}

function updatePlayer(dt) {
  const k = input.keys; const fwd = (k.KeyW ? 1 : 0) - (k.KeyS ? 1 : 0), side = (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0);
  const dir = V3(side, 0, -fwd); if (dir.lengthSq()) dir.normalize().applyAxisAngle(V3(0, 1, 0), camYaw);
  const moving = dir.lengthSq() > 0 && player.rollT <= 0 && player.atkT <= 0.12;
  const run = (k.ShiftLeft || k.ShiftRight) && G.st > 1 && moving;
  const speed = player.atkT > 0 ? 1.2 : run ? 7.2 : 4.2;
  if (player.iframes > 0) player.iframes -= dt;
  // roll
  if (k.Space && player.rollT <= 0 && G.st >= 25 && !G.over) { player.rollT = 0.45; player.iframes = Math.max(player.iframes, 0.42); G.st -= 25; player.rollDir.copy(dir.lengthSq() ? dir : V3(Math.sin(player.face), 0, Math.cos(player.face))); sfx.roll(); k.Space = false; }
  if (player.rollT > 0) { player.rollT -= dt; player.vel.copy(player.rollDir).multiplyScalar(9.5); player.face = Math.atan2(player.rollDir.x, player.rollDir.z); }
  else { const tv = dir.clone().multiplyScalar(moving ? speed : player.atkT > 0 ? 0 : 0); player.vel.x = lerp(player.vel.x, tv.x, 1 - Math.exp(-14 * dt)); player.vel.z = lerp(player.vel.z, tv.z, 1 - Math.exp(-14 * dt)); if (moving) player.face = lerp2(player.face, Math.atan2(dir.x, dir.z), 12 * dt); }
  if (run) G.st -= 14 * dt; else if (player.rollT <= 0) G.st = Math.min(100, G.st + (player.atkT > 0 ? 6 : 22) * dt);
  G.st = Math.max(0, G.st);
  // attack
  if (input.click && player.atkT <= 0 && player.rollT <= 0 && G.st >= 12 && !G.over) {
    const tgt = nearestEnemy(5.5); if (tgt) player.face = Math.atan2(tgt.obj.position.x - player.pos.x, tgt.obj.position.z - player.pos.z);
    player.atkT = 0.55; player.atkHit.clear(); player.combo ^= 1; G.st -= 12; sfx.swing(); player.group.userData.arc.material.opacity = 0.55;
  }
  input.click = false;
  if (player.atkT > 0) {
    const prev = player.atkT; player.atkT -= dt; const ph = 1 - player.atkT / 0.55;
    if (ph > 0.25 && ph < 0.6) { const fv = V3(Math.sin(player.face), 0, Math.cos(player.face));
      for (const e of enemies) { if (e.state === 'dead' || player.atkHit.has(e)) continue; const d = e.obj.position.clone().sub(player.pos).setY(0); const dist = d.length(); if (dist < 3.2 && d.normalize().dot(fv) > 0.1) { player.atkHit.add(e); damageEnemy(e, 1, d); } }
      if (boss && !boss.dead && !player.atkHit.has(boss)) { const d = boss.obj.position.clone().sub(player.pos).setY(0); if (d.length() < 5.2) { player.atkHit.add(boss); hitBoss(); } } }
  }
  // integrate + collide
  player.pos.addScaledVector(player.vel, dt);
  for (const c of colliders) { const dx = player.pos.x - c.x, dz = player.pos.z - c.z, rr2 = c.r + 0.45; const d2 = dx * dx + dz * dz; if (c.r > 0 && d2 < rr2 * rr2) { const d = Math.sqrt(d2) || 0.001; player.pos.x = c.x + dx / d * rr2; player.pos.z = c.z + dz / d * rr2; } }
  const pr = Math.hypot(player.pos.x, player.pos.z); if (pr > WORLD_R) { player.pos.x *= WORLD_R / pr; player.pos.z *= WORLD_R / pr; }
  player.pos.y = lerp(player.pos.y, terrainH(player.pos.x, player.pos.z), 1 - Math.exp(-18 * dt));
  // footsteps
  if (moving && player.vel.length() > 1) { player.stepT -= dt * (run ? 2.4 : 1.6) * 1.0; if (player.stepT <= 0) { sfx.step(); player.stepT = 0.5; } }
  // visual
  const g = player.group, sp = player.vel.length(); g.position.copy(player.pos); g.rotation.y = player.face;
  const bob = Math.sin(G.time * (run ? 14 : 9)) * Math.min(1, sp / 4);
  g.userData.cloak.rotation.x = Math.min(0.3, sp * 0.035) + bob * 0.03; g.userData.cloak.rotation.z = Math.sin(G.time * 2) * 0.02; g.userData.hood.position.y = 1.78 + bob * 0.025;
  if (player.rollT > 0) { g.rotation.x = (1 - player.rollT / 0.45) * Math.PI * 2; g.position.y += 0.6 * Math.sin((1 - player.rollT / 0.45) * Math.PI); g.scale.setScalar(0.8); } else { g.rotation.x = 0; g.scale.setScalar(1); }
  const swing = player.atkT > 0 ? Math.sin((1 - player.atkT / 0.55) * Math.PI) : 0; const dirS = player.combo ? 1 : -1;
  g.userData.sword.rotation.set(Math.PI / 2 + 0.3 - swing * 1.5, 0, dirS * swing * 1.3 + 0.0); g.userData.sword.position.set(0.5 - dirS * swing * 0.4, 1.25, 0.1 + swing * 0.5);
  g.userData.arc.material.opacity = Math.max(0, g.userData.arc.material.opacity - dt * 1.6); g.userData.arc.rotation.z = Math.PI / 2 + (player.combo ? 0.3 : -0.3);
  lantern.position.copy(player.pos).add(V3(Math.cos(player.face) * -0.5, 1.5, -Math.sin(player.face) * -0.5).add(V3(Math.sin(player.face) * 0.3, 0, Math.cos(player.face) * 0.3)));
}
const lerp2 = (a, b, t) => { let d = ((b - a + Math.PI) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) - Math.PI; return a + d * clamp(t, 0, 1); };
function nearestEnemy(r) { let best = null, bd = r; for (const e of enemies) { if (e.state === 'dead') continue; const d = Math.hypot(e.obj.position.x - player.pos.x, e.obj.position.z - player.pos.z); if (d < bd) { bd = d; best = e; } } return best; }

function updateEnemies(dt) {
  let nearAwake = false;
  for (const e of enemies) {
    const o = e.obj, to = player.pos.clone().sub(o.position).setY(0), dist = to.length(), dn = to.clone().normalize();
    e.flash = Math.max(0, e.flash - dt * 4); o.traverse(m => { if (m.isMesh) m.material.emissive.setScalar(e.flash * 0.9); });
    e.vel.multiplyScalar(Math.exp(-6 * dt)); o.position.x += e.vel.x * dt; o.position.z += e.vel.z * dt;
    if (e.state === 'dead') { e.t += dt; o.rotation.x = Math.min(1.4, e.t * 2.5); o.position.y -= dt * (e.t > 0.8 ? 1.2 : 0); if (e.t > 3) { o.visible = false; } continue; }
    const gy = terrainH(o.position.x, o.position.z);
    if (e.type === 'statue') {
      o.position.y = gy;
      if (e.state === 'dormant') { if (dist < 11) { e.state = 'chase'; sfx.wake(); burst(o.position.clone().add(V3(0, 1.2, 0)), 0x8fb8ff, 20, 2); say('The stone remembers how to move.', 2.5); } continue; }
      nearAwake = true;
      if (e.state === 'chase') { o.rotation.y = lerp2(o.rotation.y, Math.atan2(dn.x, dn.z), 6 * dt); if (dist > 2.3) { o.position.addScaledVector(dn, 3.3 * dt); o.rotation.z = Math.sin(G.time * 7) * 0.05; } else { e.state = 'windup'; e.t = 0.55; } }
      else if (e.state === 'windup') { e.t -= dt; o.rotation.x = -0.35 * (1 - e.t / 0.55); o.rotation.y = lerp2(o.rotation.y, Math.atan2(dn.x, dn.z), 4 * dt); e.flash = Math.max(e.flash, 0.5); if (e.t <= 0) { e.state = 'strike'; e.t = 0.2; e.hit = false; } }
      else if (e.state === 'strike') { e.t -= dt; o.rotation.x = 0.5; o.position.addScaledVector(dn, 8 * dt); if (!e.hit && dist < 2.6) { e.hit = true; hurtPlayer(18, o.position); } if (e.t <= 0) { e.state = 'recover'; e.t = 0.8; } }
      else if (e.state === 'recover') { e.t -= dt; o.rotation.x = lerp(o.rotation.x, 0, 8 * dt); if (e.t <= 0) e.state = 'chase'; }
    } else { // bust: hovering skull-like menace
      o.position.y = lerp(o.position.y, gy + 1.6 + Math.sin(G.time * 2 + e.ph) * 0.2, 4 * dt);
      if (e.state === 'dormant') { if (dist < 12) { e.state = 'chase'; sfx.wake(); burst(o.position.clone(), 0x8fb8ff, 14, 2); } continue; }
      nearAwake = true; o.rotation.y = Math.atan2(dn.x, dn.z);
      if (e.state === 'chase') { const want = dist - 6; o.position.addScaledVector(dn, clamp(want, -1, 1) * 3 * dt); const perp = V3(-dn.z, 0, dn.x); o.position.addScaledVector(perp, 1.6 * dt); e.cd -= dt; if (e.cd <= 0) { e.state = 'windup'; e.t = 0.6; } }
      else if (e.state === 'windup') { e.t -= dt; e.flash = 0.6; o.position.y += dt * 0.8; if (e.t <= 0) { e.state = 'strike'; e.t = 0.7; e.hit = false; e.dive = dn.clone(); } }
      else if (e.state === 'strike') { e.t -= dt; o.position.addScaledVector(e.dive, 13 * dt); o.position.y = lerp(o.position.y, gy + 1.0, 6 * dt); if (!e.hit && Math.hypot(o.position.x - player.pos.x, o.position.z - player.pos.z) < 1.3) { e.hit = true; hurtPlayer(14, o.position); } if (e.t <= 0) { e.state = 'chase'; e.cd = rr(2, 3.5); } }
      else if (e.state === 'recover') { e.t -= dt; if (e.t <= 0) { e.state = 'chase'; e.cd = 2; } }
    }
  }
  setIntensity(nearAwake || (boss && G.bossAwake && !G.bossDead) ? 1 : 0);
}

// ---------- boss ----------
function hitBoss() {
  if (G.shards < 3) { sfx.hit(); burst(boss.obj.position.clone().add(V3(1, 3, 3)), 0x7090ff, 20, 5); say('The clock-face is sealed. It wants its Hands.', 3); return; }
  boss.hp -= 1; sfx.hit(); sfx.bell(0.2); G.shake = 0.4; burst(boss.obj.position.clone().add(V3(0, 5, 3)), 0xffd070, 24, 6);
  if (!G.bossAwake) { G.bossAwake = true; $('boss').style.opacity = 1; say('The Master Clock begins to toll.', 3); }
  if (boss.hp <= 0) { boss.dead = true; G.bossDead = true; boss.t = 0; $('boss').style.opacity = 0; sfx.bell(0.6); updObj(); setTimeout(() => finish(), 4200); }
}
function updateBoss(dt) {
  if (!boss) return; const o = boss.obj, d = Math.hypot(player.pos.x - o.position.x, player.pos.z - o.position.z);
  boss.glow.intensity = lerp(boss.glow.intensity, G.shards >= 3 ? (G.bossAwake ? 120 : 60) : 0, 2 * dt);
  if (!G.bossAwake && G.shards >= 3 && d < 16) { G.bossAwake = true; $('boss').style.opacity = 1; sfx.bell(0.5); say('The Master Clock begins to toll.', 3); }
  $('bossb').style.width = (boss.hp / boss.max * 100) + '%';
  if (boss.dead) { boss.t += dt; o.rotation.z = Math.min(0.6, boss.t * 0.15); o.position.y = boss.obj.userData.base.y - Math.min(3.5, boss.t * 0.8); o.position.x = boss.obj.userData.base.x + Math.sin(boss.t * 40) * 0.05 * Math.max(0, 3 - boss.t); }
  else if (G.bossAwake) {
    o.rotation.y = lerp2(o.rotation.y, Math.atan2(player.pos.x - o.position.x, player.pos.z - o.position.z), 0.8 * dt); o.rotation.z = Math.sin(G.time * 1.5) * 0.015;
    boss.tollT -= dt; boss.summonT -= dt;
    if (boss.tollT <= 0) { boss.tollT = boss.hp < boss.max / 2 ? 3.6 : 5; sfx.bell(0.7); G.shake = 0.5;
      const m = new THREE.Mesh(new THREE.RingGeometry(0.9, 1.1, 64), new THREE.MeshBasicMaterial({ color: 0x9cc0ff, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false }));
      m.rotation.x = -Math.PI / 2; m.position.set(o.position.x, 0.4, o.position.z); scene.add(m); boss.rings.push({ m, r: 1, hit: false }); }
    if (boss.summonT <= 0) { boss.summonT = boss.hp < boss.max / 2 ? 14 : 20; const alive = enemies.filter(e => e.state !== 'dead' && e.type === 'bust' && e.summoned).length;
      if (alive < 3) for (let i = 0; i < 2; i++) { const a = rnd() * 6.28; spawnEnemy('bust', Math.cos(a) * 14, Math.sin(a) * 14 - 2); const e = enemies[enemies.length - 1]; e.state = 'chase'; e.summoned = true; } say('The clock calls its servants.', 2.5); }
  }
  for (let i = boss.rings.length - 1; i >= 0; i--) { const R = boss.rings[i]; R.r += dt * 9; R.m.scale.setScalar(R.r); R.m.material.opacity = Math.max(0, 0.9 - R.r / 30);
    const pd = Math.hypot(player.pos.x - o.position.x, player.pos.z - o.position.z); if (!R.hit && Math.abs(pd - R.r) < 1.0) { R.hit = true; if (player.iframes <= 0) hurtPlayer(22, o.position); }
    if (R.r > 34) { scene.remove(R.m); boss.rings.splice(i, 1); } }
}
function finish() {
  G.over = true; document.exitPointerLock?.();
  $('endh').textContent = 'THE HOUR ENDS'; $('endp').textContent = 'The pendulum stills for the last time. Across the estate every stopped clock draws one long breath and ticks — once — and the fog lifts off Hollowmere like a held sigh. Nothing here will be young again. But, at last, nothing here will be waiting. You lower your lantern. Morning begins.';
  $('end').classList.remove('hide');
}

// ---------- camera ----------
const camPos = V3(0, 3, 50), camTarget = V3();
function updateCamera(dt) {
  camYaw -= input.mdx * 0.0028; camPitch = clamp(camPitch + input.mdy * 0.0025, -0.15, 1.1); input.mdx = input.mdy = 0;
  const dist = 5.4, tgt = player.pos.clone().add(V3(0, 1.7, 0));
  const off = V3(Math.sin(camYaw) * Math.cos(camPitch), Math.sin(camPitch), Math.cos(camYaw) * Math.cos(camPitch)).multiplyScalar(dist);
  const want = tgt.clone().add(off); want.y = Math.max(want.y, terrainH(want.x, want.z) + 0.6);
  camPos.lerp(want, 1 - Math.exp(-16 * dt)); camTarget.lerp(tgt, 1 - Math.exp(-20 * dt));
  camera.position.copy(camPos); if (G.shake > 0) { camera.position.add(V3(rr(-1, 1), rr(-1, 1), rr(-1, 1)).multiplyScalar(G.shake * 0.15)); G.shake = Math.max(0, G.shake - dt * 2); }
  camera.lookAt(camTarget);
  moon.position.set(player.pos.x - 30, 30, player.pos.z + 20); moon.target.position.copy(player.pos); moon.target.updateMatrixWorld();
}

// ---------- main loop ----------
const clock = new THREE.Clock();
function frame() {
  requestAnimationFrame(frame); const dt = Math.min(clock.getDelta(), 0.05); G.time += dt;
  grade.uniforms.time.value = G.time % 100; G.hurt = Math.max(0, G.hurt - dt * 2); grade.uniforms.hurt.value = G.hurt;
  if (G.started && !G.paused) {
    if (!G.over) updatePlayer(dt); else { player.vel.multiplyScalar(0.9); }
    updateEnemies(dt); updateBoss(dt); if (G.dbg) { camera.position.copy(G.dbg.p); camera.lookAt(G.dbg.l); } else updateCamera(dt);
    // interactions + hud
    let best = null, bd = 99; for (const it of interacts) { const d = it.obj.position.distanceTo(player.pos); if (d < it.r && d < bd && (!it.cond || it.cond() || it.deny)) { bd = d; best = it; } }
    const pr = $('prompt'); if (best && !G.over) { const ok = !best.cond || best.cond(); pr.textContent = ok ? (typeof best.text === 'function' ? best.text() : best.text) : best.deny; pr.style.opacity = 1; if (interactNow && ok) best.act(); } else pr.style.opacity = 0;
    interactNow = false;
    $('hp').firstElementChild.style.width = clamp(G.hp, 0, 100) + '%'; $('st').firstElementChild.style.width = G.st + '%';
    if (subT > 0 && (subT -= dt) <= 0) $('sub').style.opacity = 0;
  }
  if (flames) flames.forEach(f => { f.l.intensity = f.base * (0.85 + Math.sin(G.time * 11 + f.ph) * 0.1 + Math.sin(G.time * 23 + f.ph) * 0.05); });
  shrines.forEach(s => { s.l.intensity = lerp(s.l.intensity, s.lit ? 30 * (0.88 + Math.sin(G.time * 10 + s.x) * 0.1) : 0, 4 * (1 / 60)); s.sp.material.opacity = s.l.intensity / 30; s.sp.scale.setScalar(1.2 + Math.sin(G.time * 12 + s.x) * 0.12); });
  lantern.intensity = 22 + Math.sin(G.time * 9) * 2.5 + Math.sin(G.time * 17) * 3;
  for (let i = 0; i < FN; i++) { const s = fSeed[i]; fPos[i * 3] += Math.sin(G.time * 0.4 + s) * 0.01; fPos[i * 3 + 1] = 1.3 + Math.sin(G.time * 0.7 + s * 3) * 0.9 + terrainH(fPos[i * 3], fPos[i * 3 + 2]) * 0.5; fPos[i * 3 + 2] += Math.cos(G.time * 0.33 + s) * 0.01; }
  fGeo.attributes.position.needsUpdate = true; updParticles(dt);
  composer.render(); G.frames = (G.frames || 0) + 1;
}

// ---------- boot ----------
(async function boot() {
  const mats = await loadAll();
  buildTerrain(mats); buildScatter(); buildCourtyard(); buildZones(); buildPlayer(); updObj();
  player.pos.copy(V3(0, 0, 44)); camYaw = 0; camPos.set(0, 4, 50);
  for (const e of enemies) tickNoop();
  tick(); tick(); tick(); tick();
  const go = $('go'); go.disabled = false; go.textContent = 'ENTER';
  const start = () => { initAudio(); G.started = true; $('title').classList.add('hide'); $('hud').classList.add('on'); renderer.domElement.requestPointerLock?.();
    setTimeout(() => say('Find the three Hands. Follow the lantern-light. Light every candle you pass.', 6), 1200); sfx.bell(0.3); };
  go.onclick = start; $('again').onclick = () => location.reload();
  window.__hm = { fog: d => { scene.fog.density = d; }, cam: (p, l) => { G.dbg = p ? { p: V3(...p), l: V3(...l) } : null; }, G, player, enemies, chests, shrines, boss, camera, start, THREE, terrainH, tp: (x, z, yaw = 0, pitch = 0.28) => { player.pos.set(x, terrainH(x, z), z); camYaw = yaw; camPitch = pitch; camPos.set(x + Math.sin(yaw) * 5, terrainH(x, z) + 3, z + Math.cos(yaw) * 5); camTarget.set(x, terrainH(x, z) + 1.7, z); } };
  frame();
})().catch(e => { console.error(e); $('go').textContent = 'ERROR: ' + e.message; });
function tickNoop() {}
