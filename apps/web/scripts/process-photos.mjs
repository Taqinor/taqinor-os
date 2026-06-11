/**
 * Transforme les photos brutes (photos-raw/, hors git) en assets web
 * optimisés dans public/photos/. Recadrages fixes pour écarter les éléments
 * de chantier (seau, vélo d'appartement) des cadrages publiés.
 *
 *   node scripts/process-photos.mjs
 */
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, 'public', 'photos');

const PHOTOS = [
  {
    // Rangée de panneaux sur toit-terrasse, skyline avec minaret — photo phare
    src: '6937f73c-df26-4b8e-ba40-838526e0f0d5.JPG',
    out: 'toit-terrasse-panneaux.webp',
    width: 1600,
    height: 900,
  },
  {
    // Équipe Taqinor (gilet logoté) posant la structure sur toiture plate
    src: '20251020_141446000_iOS.jpg',
    out: 'equipe-pose-structure.webp',
    width: 1000,
    height: 1000,
  },
  {
    // Installation au crépuscule, palmiers — recadrée à gauche (seau hors champ)
    src: '20251020_133405000_iOS.jpg',
    out: 'installation-crepuscule.webp',
    extractRatio: { left: 0, top: 0.18, width: 0.72, height: 0.66 },
    width: 1000,
    height: 760,
  },
  {
    // Mur technique : onduleur hybride + 2 batteries Dyness — recadré à droite
    src: 'E683BD27-5563-4790-AA09-556BBD4137DB.JPG',
    out: 'batteries-onduleur.webp',
    extractRatio: { left: 0.28, top: 0.08, width: 0.5, height: 0.88 },
    width: 1000,
    height: 940,
  },
];

await mkdir(outDir, { recursive: true });
for (const p of PHOTOS) {
  const input = sharp(path.join(rawDir, p.src)).rotate();
  const meta = await input.metadata();
  let img = input;
  if (p.extractRatio) {
    const r = p.extractRatio;
    img = img.extract({
      left: Math.round(meta.width * r.left),
      top: Math.round(meta.height * r.top),
      width: Math.round(meta.width * r.width),
      height: Math.round(meta.height * r.height),
    });
  }
  const file = path.join(outDir, p.out);
  await img.resize(p.width, p.height, { fit: 'cover' }).webp({ quality: 78 }).toFile(file);
  console.log(`photo: ${p.out}`);
}
