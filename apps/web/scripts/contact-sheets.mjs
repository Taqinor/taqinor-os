/**
 * Outil de curation (session redesign) : génère des planches-contacts
 * numérotées de toutes les photos de photos-raw/ dans .curation/ (hors git)
 * pour la revue visuelle, + un index JSON numéro -> fichier.
 *
 *   node scripts/contact-sheets.mjs
 */
import sharp from 'sharp';
import decodeHeic from 'heic-decode';
import { mkdir, writeFile, readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, '.curation');

const CELL = 360;
const COLS = 4;
const ROWS = 3;
const LABEL_H = 26;

/** sharp si possible, sinon décodage HEIC (HEVC) via WASM. */
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

const files = (await readdir(rawDir))
  .filter((f) => /\.(heic|jpg|jpeg)$/i.test(f))
  .sort();

await mkdir(outDir, { recursive: true });
const index = {};

let sheetNo = 0;
for (let i = 0; i < files.length; i += COLS * ROWS) {
  const batch = files.slice(i, i + COLS * ROWS);
  const composites = [];
  for (let j = 0; j < batch.length; j++) {
    const n = i + j + 1;
    index[n] = batch[j];
    let cell;
    try {
      cell = await loadImage(path.join(rawDir, batch[j]))
        .then((img) =>
          img
            .resize(CELL, CELL - LABEL_H, { fit: 'contain', background: '#222' })
            .jpeg({ quality: 60 })
            .toBuffer()
        );
    } catch (e) {
      cell = await sharp({
        create: { width: CELL, height: CELL - LABEL_H, channels: 3, background: '#800' },
      }).jpeg().toBuffer();
    }
    const label = Buffer.from(
      `<svg width="${CELL}" height="${LABEL_H}"><rect width="100%" height="100%" fill="#000"/><text x="6" y="19" font-family="Arial" font-size="16" fill="#fff">#${n}</text></svg>`
    );
    const col = j % COLS;
    const row = Math.floor(j / COLS);
    composites.push(
      { input: cell, left: col * CELL, top: row * CELL },
      { input: label, left: col * CELL, top: row * CELL + (CELL - LABEL_H) }
    );
  }
  sheetNo++;
  const sheet = path.join(outDir, `sheet-${String(sheetNo).padStart(2, '0')}.jpg`);
  await sharp({
    create: { width: COLS * CELL, height: ROWS * CELL, channels: 3, background: '#222' },
  })
    .composite(composites)
    .jpeg({ quality: 70 })
    .toFile(sheet);
  console.log(sheet);
}
await writeFile(path.join(outDir, 'index.json'), JSON.stringify(index, null, 2));
console.log(`${files.length} photos sur ${sheetNo} planches`);
