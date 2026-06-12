/**
 * Outil de revue (session redesign) : génère 3 paires avant/après du
 * débrumage dans .curation/dehaze/ pour jugement visuel de l'intensité.
 *
 *   node scripts/dehaze-pairs.mjs
 */
import sharp from 'sharp';
import decodeHeic from 'heic-decode';
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, '.curation', 'dehaze');

const SAMPLES = [
  { src: '6937f73c-df26-4b8e-ba40-838526e0f0d5.JPG', name: 'hero-skyline' },
  { src: 'IMG_1780.HEIC', name: 'champ-villa' },
  { src: 'IMG_2184.HEIC', name: 'industriel-couchant' },
];

async function loadImage(file) {
  const direct = sharp(file).rotate();
  try {
    await direct.stats();
    return direct;
  } catch {
    const { width, height, data } = await decodeHeic({ buffer: await readFile(file) });
    return sharp(Buffer.from(data), { raw: { width, height, channels: 4 } });
  }
}

const W = 640;
await mkdir(outDir, { recursive: true });
for (const s of SAMPLES) {
  const img = await loadImage(path.join(rawDir, s.src));
  const meta = await img.metadata();
  const before = await img.clone().resize(W).jpeg({ quality: 85 }).toBuffer();
  const tile = Math.max(64, Math.round(Math.min(meta.width, meta.height) / 8));
  // Débrumage en passe séparée (sharp réordonne sinon clahe après resize,
  // et la fenêtre CLAHE dépasserait l'image réduite)
  const dehazed = await img
    .clone()
    .clahe({ width: tile, height: tile, maxSlope: 2 })
    .normalise({ lower: 0.6, upper: 99.6 })
    .modulate({ saturation: 1.12 })
    .png()
    .toBuffer();
  const after = await sharp(dehazed).resize(W).jpeg({ quality: 85 }).toBuffer();
  const h = (await sharp(before).metadata()).height;
  const label = (t, x) =>
    Buffer.from(`<svg width="${W}" height="34"><rect width="100%" height="100%" fill="#0a1238"/><text x="${x}" y="24" font-family="Arial" font-weight="bold" font-size="19" fill="#fff">${t}</text></svg>`);
  await sharp({ create: { width: W * 2 + 8, height: h + 34, channels: 3, background: '#fff' } })
    .composite([
      { input: label('AVANT', 12), left: 0, top: 0 },
      { input: label('APRÈS (débrumage)', 12), left: W + 8, top: 0 },
      { input: before, left: 0, top: 34 },
      { input: after, left: W + 8, top: 34 },
    ])
    .jpeg({ quality: 85 })
    .toFile(path.join(outDir, `${s.name}.jpg`));
  console.log(`paire: ${s.name}.jpg`);
}
