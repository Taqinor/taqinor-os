/**
 * Transforme les photos brutes (photos-raw/, hors git) en assets web
 * optimisés dans public/photos/. Tri approfondi 2026-06 (16 retenues sur
 * 162, inventaire scoré : .curation/inventory.json) :
 *  1. traitement INDIVIDUEL par photo — débrumage dosé (pente CLAHE),
 *     exposition, balance, recadrage composé pour l'emplacement exact ;
 *  2. puis UNE étalonnure légère commune (contraste doux + blanc chaud)
 *     pour que tout le site lise comme une seule prise de vue.
 * Jamais de retouche générative — rien d'ajouté, rien d'effacé.
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
 * slope : intensité du débrumage CLAHE (1,4 doux → 2,6 fort, contre-jour).
 * exposure : gain linéaire post-débrumage. sat : récupération de couleur.
 * extractRatio : recadrage composé pour l'emplacement (héros ≠ galerie).
 */
const PHOTOS = [
  {
    // Rangée + skyline + minaret, heure dorée — OG accueil + galerie (ville)
    src: '6937f73c-df26-4b8e-ba40-838526e0f0d5.JPG',
    out: 'hero-skyline',
    widths: [2000, 1280, 768, 480],
    ratio: 16 / 9,
    treat: { slope: 2, exposure: 1.0, sat: 1.1 },
  },
  {
    // Penthouse + chauffe-eau au crépuscule — en-tête /résidentiel.
    // Recadrage héros : sac de chantier sorti à gauche, ciel préservé.
    src: 'IMG_1988.HEIC',
    out: 'crepuscule-penthouse',
    extractRatio: { left: 0.1, top: 0.04, width: 0.9, height: 0.92 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 2, exposure: 1.04, sat: 1.1 },
  },
  {
    // Champ noir villa — galerie. Bâche sortie du bord bas.
    src: 'IMG_1780.HEIC',
    out: 'champ-villa',
    extractRatio: { left: 0, top: 0, width: 1, height: 0.9 },
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    treat: { slope: 2, exposure: 1.0, sat: 1.14 },
  },
  {
    // Villa pavillon zellige turquoise — galerie + illustration /résidentiel.
    // Contre-jour : débrumage appuyé.
    src: 'IMG_1841.HEIC',
    out: 'villa-zellige',
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 3, exposure: 1.08, sat: 1.12 },
  },
  {
    // Longue pente + pyramide zellige + palmiers — galerie (diagonale).
    src: 'IMG_1838.HEIC',
    out: 'pente-zellige',
    extractRatio: { left: 0, top: 0.12, width: 1, height: 0.84 },
    widths: [1024, 640],
    ratio: 4 / 5,
    treat: { slope: 3, exposure: 1.06, sat: 1.12 },
  },
  {
    // Rangée de 7 sur terre cuite — galerie. Clim sortie à droite.
    src: 'IMG_2288.HEIC',
    out: 'terrasse-terre-cuite',
    extractRatio: { left: 0, top: 0.04, width: 0.93, height: 0.96 },
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    treat: { slope: 2, exposure: 1.0, sat: 1.12 },
  },
  {
    // Panneau + chauffe-eau sur acrotère — /équipement + galerie (graphique)
    src: 'IMG_2300.HEIC',
    out: 'silhouette-acrotere',
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 2, exposure: 1.0, sat: 1.1 },
  },
  {
    // Nettoyage au jet — galerie (entretien, geste)
    src: '20251020_133441000_iOS.jpg',
    out: 'entretien-jet',
    widths: [1600, 1024, 640],
    ratio: 1,
    treat: { slope: 2, exposure: 1.0, sat: 1.08 },
  },
  {
    // Gilet TAQINOR net, pose des rails — galerie (marque au travail)
    src: '20251020_141418000_iOS.jpg',
    out: 'equipe-gilet-taqinor',
    widths: [1600, 1024, 640],
    ratio: 1,
    treat: { slope: 2, exposure: 1.02, sat: 1.06 },
  },
  {
    // Traçage et mesure des rails — galerie + /professionnel (précision)
    src: '20251018_104911817_iOS.heic',
    out: 'mesure-rails',
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 2, exposure: 1.02, sat: 1.06 },
  },
  {
    // Double rangée industrielle au couchant — en-tête /professionnel.
    // Contre-jour appuyé : débrumage fort + gain.
    src: 'IMG_2184.HEIC',
    out: 'industriel-couchant',
    widths: [2000, 1280, 768, 480],
    ratio: 16 / 9,
    treat: { slope: 3, exposure: 1.08, sat: 1.08 },
  },
  {
    // Équipe de trois + longue rangée — /professionnel + OG contact.
    // Clim YORK sortie à droite.
    src: 'IMG_2199.HEIC',
    out: 'equipe-trois',
    extractRatio: { left: 0, top: 0, width: 0.88, height: 1 },
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    treat: { slope: 2, exposure: 1.06, sat: 1.08 },
  },
  {
    // Mur technique Dyness + borne — /équipement. Intérieur : débrumage
    // doux (bruit), correction de la dominante froide.
    src: '6a46ce14-7f71-4768-910c-a8b438f37853.JPG',
    out: 'mur-technique-dyness',
    extractRatio: { left: 0.05, top: 0.02, width: 0.92, height: 0.93 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 2, exposure: 1.1, sat: 1.0 },
  },
  {
    // Bornes Dyness + coffret Güneş, gros plan câblage — /équipement
    // (détail du geste). Sol de chantier sorti du bas.
    src: 'IMG_2226.HEIC',
    out: 'detail-cablage',
    extractRatio: { left: 0.02, top: 0, width: 0.96, height: 0.8 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 2, exposure: 1.08, sat: 1.0 },
  },
  {
    // Installation au crépuscule, palmiers — galerie (hérité, seau hors champ)
    src: '20251020_133405000_iOS.jpg',
    out: 'installation-crepuscule',
    extractRatio: { left: 0, top: 0.18, width: 0.72, height: 0.66 },
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    treat: { slope: 2, exposure: 1.04, sat: 1.1 },
  },
  {
    // Équipe posant la structure — galerie (hérité)
    src: '20251020_141446000_iOS.jpg',
    out: 'equipe-pose-structure',
    widths: [1600, 1024, 640],
    ratio: 1,
    treat: { slope: 2, exposure: 1.02, sat: 1.06 },
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

/** Traitement individuel : CLAHE dosé + point noir + exposition + couleur. */
function treatIndividual(img, meta, t) {
  const tile = Math.max(64, Math.round(Math.min(meta.width, meta.height) / 8));
  let out = img
    .clahe({ width: tile, height: tile, maxSlope: t.slope })
    .normalise({ lower: 0.6, upper: 99.6 });
  if (t.exposure !== 1) out = out.linear(t.exposure, 0);
  if (t.sat !== 1) out = out.modulate({ saturation: t.sat });
  return out;
}

/** Étalonnure commune : contraste doux + blanc légèrement chaud — la même
 * pour toutes les photos, pour une lecture « une seule prise de vue ». */
function unifyGrade(img) {
  return img.linear(1.02, -3).tint({ r: 255, g: 252, b: 246 });
}

await mkdir(outDir, { recursive: true });
const manifest = {};

for (const p of PHOTOS) {
  let img = await loadImage(path.join(rawDir, p.src));
  const meta = await img.metadata();
  img = treatIndividual(img, meta, p.treat);
  if (p.extractRatio) {
    const r = p.extractRatio;
    img = img.extract({
      left: Math.round(meta.width * r.left),
      top: Math.round(meta.height * r.top),
      width: Math.round(meta.width * r.width),
      height: Math.round(meta.height * r.height),
    });
  }
  const base = await unifyGrade(img).png().toBuffer();
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
