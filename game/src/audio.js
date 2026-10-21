// Fully synthesised audio (WebAudio) - no sample files, so nothing to license.
let ctx, master, noiseBuf;
export function initAudio() {
  if (ctx) { ctx.resume(); return; }
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  master = ctx.createGain(); master.gain.value = 0.8; master.connect(ctx.destination);
  noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
  const d = noiseBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  wind(); drone(); musicLoop();
}
const noise = () => { const s = ctx.createBufferSource(); s.buffer = noiseBuf; s.loop = true; return s; };
function wind() {
  const n = noise(), f = ctx.createBiquadFilter(), g = ctx.createGain(), l = ctx.createOscillator(), lg = ctx.createGain();
  f.type = 'bandpass'; f.frequency.value = 420; f.Q.value = 0.7; g.gain.value = 0.07;
  l.frequency.value = 0.07; lg.gain.value = 0.05; l.connect(lg); lg.connect(g.gain);
  n.connect(f); f.connect(g); g.connect(master); n.start(); l.start();
}
function drone() {
  const g = ctx.createGain(), f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 220; g.gain.value = 0.05;
  for (const fr of [55, 55.4, 82.4]) { const o = ctx.createOscillator(); o.type = 'sawtooth'; o.frequency.value = fr; o.connect(f); o.start(); }
  f.connect(g); g.connect(master);
}
const SCALE = [0, 2, 3, 5, 7, 8, 10]; // A natural minor
function note(freq, t, dur, vol, type = 'triangle') {
  const o = ctx.createOscillator(), g = ctx.createGain(); o.type = type; o.frequency.value = freq;
  g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g); g.connect(master); o.start(t); o.stop(t + dur + 0.05);
}
let step = 0, intensity = 0;
export const setIntensity = v => { intensity = v; };
function musicLoop() {
  const t = ctx.currentTime + 0.05, root = 110;
  const deg = [0, 4, 2, 5, 0, 4, 6, 3][step % 8];
  const f = root * 2 ** (SCALE[deg % 7] / 12) * (step % 16 < 8 ? 1 : 1);
  note(f * 2, t, 3.2, 0.05 + intensity * 0.03); if (step % 4 === 0) note(f / 2, t, 4, 0.08, 'sine');
  if (intensity > 0.3) note(f * 4, t + 0.5, 1.2, 0.025 * intensity);
  step++; setTimeout(musicLoop, intensity > 0.3 ? 900 : 1800);
}
function burst(dur, freq, q, vol, type = 'bandpass', sweepTo) {
  if (!ctx) return; const t = ctx.currentTime, n = noise(), f = ctx.createBiquadFilter(), g = ctx.createGain();
  f.type = type; f.frequency.setValueAtTime(freq, t); if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, t + dur); f.Q.value = q;
  g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  n.connect(f); f.connect(g); g.connect(master); n.start(t); n.stop(t + dur);
}
export const sfx = {
  swing: () => burst(0.22, 600, 1.2, 0.35, 'bandpass', 3200),
  hit: () => { burst(0.18, 900, 0.8, 0.5); if (ctx) note(90, ctx.currentTime, 0.25, 0.4, 'sine'); },
  hurt: () => { burst(0.3, 300, 0.6, 0.6, 'lowpass'); if (ctx) note(70, ctx.currentTime, 0.4, 0.5, 'sawtooth'); },
  step: () => burst(0.07, 250 + Math.random() * 120, 0.5, 0.12, 'lowpass'),
  roll: () => burst(0.35, 400, 0.5, 0.25, 'bandpass', 150),
  pickup: () => { if (!ctx) return; [0, 4, 7, 12].forEach((s, i) => note(440 * 2 ** (s / 12), ctx.currentTime + i * 0.08, 0.9, 0.12, 'sine')); },
  bell: (v = 0.3) => { if (!ctx) return; const t = ctx.currentTime; [1, 2.76, 5.4, 8.9].forEach((m, i) => note(130 * m, t, 4 / (i + 1), v / (i + 1), 'sine')); },
  wake: () => { burst(0.8, 150, 2, 0.5, 'lowpass'); if (ctx) note(55, ctx.currentTime, 0.9, 0.35, 'sawtooth'); },
};
