/**
 * Transforme les photos brutes (photos-raw/, hors git) en assets web
 * optimisés dans public/photos/ : recadrage éditorial (écarte sacs, flaques,
 * climatiseurs des cadrages publiés), correction non destructive
 * (exposition/contraste via courbe linéaire douce + normalisation), sorties
 * responsives AVIF + WebP. Jamais de retouche générative.
 *
 * Sélection éditoriale 2026-06 : 14 photos retenues sur 162 brutes.
 *
 *   node scripts/process-photos.mjs
 */
import sharp from 'sharp';
import decodeHeic from 'heic-decode';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, 'public', 'photos');

/**
 * widths : tailles responsives générées (toutes en AVIF + WebP).
 * ratio  : cadrage final (w/h) appliqué en "cover".
 * extractRatio : pré-recadrage proportionnel pour sortir le hors-sujet.
 * tune   : { exposure: gain linéaire (1 = neutre), saturation }.
 */
const PHOTOS = [
  {
    // Photo phare — rangée de panneaux, skyline avec minaret, lumière dorée
    src: '6937f73c-df26-4b8e-ba40-838526e0f0d5.JPG',
    out: 'hero-skyline',
    widths: [2000, 1280, 768, 480],
    ratio: 16 / 9,
    tune: { exposure: 1.04, saturation: 1.06 },
  },
  {
    // Crépuscule, penthouse blanc + chauffe-eau solaire — sac de chantier
    // recadré (bord gauche), ciel chaud préservé
    src: 'IMG_1988.HEIC',
    out: 'crepuscule-penthouse',
    extractRatio: { left: 0.1, top: 0.04, width: 0.9, height: 0.92 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    tune: { exposure: 1.06, saturation: 1.05 },
  },
  {
    // Champ noir sur toit plat, ciel bleu, verdure — bord bas droit (bâche)
    // recadré
    src: 'IMG_1780.HEIC',
    out: 'champ-villa',
    extractRatio: { left: 0, top: 0, width: 1, height: 0.9 },
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    tune: { exposure: 1.02, saturation: 1.04 },
  },
  {
    // Villa marocaine, toiture pyramidale en zellige turquoise + panneaux
    src: 'IMG_1841.HEIC',
    out: 'villa-zellige',
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    tune: { exposure: 1.08, saturation: 1.05 },
  },
  {
    // Rangée de 7 panneaux, toit-terrasse en terre cuite — clim recadrée à droite
    src: 'IMG_2288.HEIC',
    out: 'terrasse-terre-cuite',
    extractRatio: { left: 0, top: 0.04, width: 0.93, height: 0.96 },
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    tune: { exposure: 1.0, saturation: 1.04 },
  },
  {
    // Graphique : panneau + chauffe-eau en silhouette sur acrotère blanc
    src: 'IMG_2300.HEIC',
    out: 'silhouette-acrotere',
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    tune: { exposure: 1.0, saturation: 1.05 },
  },
  {
    // Nettoyage au jet d'un champ — geste d'entretien, palmiers
    src: '20251020_133441000_iOS.jpg',
    out: 'entretien-jet',
    widths: [1600, 1024, 640],
    ratio: 1,
    tune: { exposure: 1.0, saturation: 1.03 },
  },
  {
    // Gilet TAQINOR au premier plan, pose de rails — la marque au travail
    src: '20251020_141418000_iOS.jpg',
    out: 'equipe-gilet-taqinor',
    widths: [1600, 1024, 640],
    ratio: 1,
    tune: { exposure: 1.02, saturation: 1.02 },
  },
  {
    // Traçage et mesure des rails au mètre — la précision du geste
    src: '20251018_104911817_iOS.heic',
    out: 'mesure-rails',
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    tune: { exposure: 1.02, saturation: 1.02 },
  },
  {
    // Chantier industriel au couchant, double rangée, ciel dramatique
    src: 'IMG_2184.HEIC',
    out: 'industriel-couchant',
    widths: [2000, 1280, 768, 480],
    ratio: 16 / 9,
    tune: { exposure: 1.14, saturation: 1.04 },
  },
  {
    // Équipe de trois devant la longue rangée — fierté de chantier
    src: 'IMG_2199.HEIC',
    out: 'equipe-trois',
    extractRatio: { left: 0, top: 0, width: 0.88, height: 1 },
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    tune: { exposure: 1.06, saturation: 1.03 },
  },
  {
    // Mur technique : onduleur hybride, 2 batteries Dyness, borne de recharge
    src: '6a46ce14-7f71-4768-910c-a8b438f37853.JPG',
    out: 'mur-technique-dyness',
    extractRatio: { left: 0.05, top: 0.02, width: 0.92, height: 0.93 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    tune: { exposure: 1.1, saturation: 1.0 },
  },
  {
    // Installation au crépuscule, palmiers — recadrée (seau hors champ)
    src: '20251020_133405000_iOS.jpg',
    out: 'installation-crepuscule',
    extractRatio: { left: 0, top: 0.18, width: 0.72, height: 0.66 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    tune: { exposure: 1.04, saturation: 1.05 },
  },
  {
    // Équipe posant la structure sur toiture plate (gilet logoté)
    src: '20251020_141446000_iOS.jpg',
    out: 'equipe-pose-structure',
    widths: [1600, 1024, 640],
    ratio: 1,
    tune: { exposure: 1.02, saturation: 1.02 },
  },
];

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

await mkdir(outDir, { recursive: true });
const manifest = {};

for (const p of PHOTOS) {
  let img = await loadImage(path.join(rawDir, p.src));
  const meta = await img.metadata();
  if (p.extractRatio) {
    const r = p.extractRatio;
    img = img.extract({
      left: Math.round(meta.width * r.left),
      top: Math.round(meta.height * r.top),
      width: Math.round(meta.width * r.width),
      height: Math.round(meta.height * r.height),
    });
  }
  // Correction non destructive : gain d'exposition linéaire + saturation douce
  const t = p.tune ?? {};
  if (t.exposure && t.exposure !== 1) img = img.linear(t.exposure, 0);
  if (t.saturation && t.saturation !== 1) img = img.modulate({ saturation: t.saturation });
  img = img.normalise({ lower: 0.3, upper: 99.7 });

  const base = await img.png().toBuffer();
  manifest[p.out] = { widths: p.widths, ratio: p.ratio };

  for (const w of p.widths) {
    const h = Math.round(w / p.ratio);
    const resized = sharp(base).resize(w, h, { fit: 'cover', withoutEnlargement: false });
    await resized.clone().avif({ quality: 55 }).toFile(path.join(outDir, `${p.out}-${w}.avif`));
    await resized.clone().webp({ quality: 80 }).toFile(path.join(outDir, `${p.out}-${w}.webp`));
  }
  console.log(`photo: ${p.out} (${p.widths.join('/')})`);
}

await writeFile(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
