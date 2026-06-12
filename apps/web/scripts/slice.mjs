/**
 * Outil de session : découpe une capture pleine page en tranches lisibles
 * pour la revue visuelle (la lecture directe écrase trop l'image).
 *
 *   node scripts/slice.mjs <capture.png> <nbTranches> [prefixeSortie]
 */
import sharp from 'sharp';
import path from 'node:path';

const [file, nArg, prefix] = process.argv.slice(2);
const n = Number(nArg ?? 4);
const img = sharp(file);
const { width, height } = await img.metadata();
const base = prefix ?? file.replace(/\.png$/, '');
const sliceH = Math.ceil(height / n);
for (let i = 0; i < n; i++) {
  const top = i * sliceH;
  const h = Math.min(sliceH, height - top);
  if (h <= 0) break;
  await sharp(file).extract({ left: 0, top, width, height: h }).png().toFile(`${base}-s${i + 1}.png`);
}
console.log(`${n} tranches de ${width}x${sliceH}`);
