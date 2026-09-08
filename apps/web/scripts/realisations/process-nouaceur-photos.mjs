/**
 * Réalisation Nouaceur (réf. NC-10/25, 2026-09) — enrichissement photo : 6
 * nouvelles photos optimisées dans public/photos/ (préfixe `nouaceur-`), même
 * convention que scripts/process-photos.mjs et
 * scripts/realisations/process-bouskoura-photos.mjs (AVIF q55 + WebP q80,
 * mêmes largeurs déclarées dans src/lib/realisations.ts).
 *
 * Sources : 6 JPG/HEIC natifs du chantier, tous tournés les 18-20/10/2025 sur
 * le MÊME chantier (l'unique installation de Nouaceur, 3,72 kWc, 6 × JA
 * Solar — faits fondateur 08/09/2026, jamais mélangés avec une autre
 * installation). Les 3 photos Nouaceur déjà publiées (`equipe-gilet-taqinor`,
 * `mesure-rails`, `entretien-jet`, sourcées par scripts/process-photos.mjs
 * depuis ce même dossier) restent inchangées — ce script ne fait qu'AJOUTER.
 *
 * `nouaceur-toit` réutilise le même fichier source que l'ancien
 * `installation-crepuscule` (scripts/process-photos.mjs) mais avec un
 * cadrage 16:9 plein cadre différent (héros de page, comme
 * `bouskoura-toit`) — l'ancien asset `installation-crepuscule` n'est
 * référencé par aucune page live et reste intact, non touché.
 *
 * Le dossier source (OneDrive, hors dépôt) n'est JAMAIS écrit — lecture
 * seule. Aucun fichier brut (HEIC/MOV) n'est committé.
 *
 *   node scripts/realisations/process-nouaceur-photos.mjs
 */
import sharp from 'sharp';
import decodeHeic from 'heic-decode';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const outDir = path.join(root, 'public', 'photos');

// Dossier source réel (lecture seule, jamais copié dans le dépôt).
const SRC = 'C:\\Users\\kasri\\OneDrive - Atlencia\\TAQINOR\\Marketing\\Pictures';

/**
 * Une entrée par photo publiée. `src` = fichier natif JPG/HEIC (chemin
 * direct, iPhone — le HEIC de ce lot n'est PAS décodable par le sharp/libheif
 * de cet environnement (« compression format has not been built in »),
 * `loadImage` retombe alors sur `heic-decode`, exactement comme
 * scripts/process-photos.mjs). `position` = ancre de recadrage sharp
 * (`cover`) — 'bottom' pour la source portrait (l'essentiel de la scène est
 * dans la moitié basse du cadre, le haut n'est que du ciel).
 */
const PHOTOS = [
  {
    // Héros de page (position 0 dans realisations.ts) — les six panneaux au
    // complet, lumière dorée, palmiers en arrière-plan. Même traitement que
    // le héros `bouskoura-toit` (ratio 16:9, mêmes largeurs).
    out: 'nouaceur-toit',
    src: path.join(SRC, '20251020_133405000_iOS.jpg'),
    widths: [2000, 1280, 768, 480],
    ratio: 16 / 9,
    position: 'centre',
  },
  {
    // Même rangée, 35 s plus tard — recadrage plus serré sur les panneaux.
    out: 'nouaceur-panneaux-couchant',
    src: path.join(SRC, '20251020_133440000_iOS.jpg'),
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    position: 'centre',
  },
  {
    // Avant pose : deux installateurs alignent les blocs de lestage et les
    // rails au sol (18/10/2025 matin) — source portrait, l'action est dans
    // la moitié basse du cadre.
    out: 'nouaceur-structure-lestage',
    src: path.join(SRC, '20251018_104851879_iOS.heic'),
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    position: 'bottom',
  },
  {
    // Gilet/veste Taqinor au dos, alignement de rail en cours — équipe au
    // travail (20/10/2025).
    out: 'nouaceur-equipe-rails',
    src: path.join(SRC, '20251020_141213000_iOS 1.jpg'),
    widths: [1600, 1024, 640],
    ratio: 1,
    position: 'centre',
  },
  {
    // Trois installateurs Taqinor mesurent l'implantation des rails.
    out: 'nouaceur-mesure-equipe',
    src: path.join(SRC, '20251020_141446000_iOS.jpg'),
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
    position: 'centre',
  },
  {
    // Onduleur MUST posé sur mur intérieur, à côté du coffret électrique
    // (19/10/2025) — seule photo de la sélection qui montre le matériel
    // électrique posé.
    out: 'nouaceur-onduleur-must',
    src: path.join(SRC, '20251019_191028410_iOS.jpg'),
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    position: 'centre',
  },
];

/** sharp si possible, sinon décodage HEIC (HEVC) via WASM — identique à
 *  scripts/process-photos.mjs (`loadImage`). */
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

/** Même étalonnure commune que process-photos.mjs / process-bouskoura-photos.mjs
 *  (« cinéma du chantier ») — contraste doux + voile chaud, jamais de tint()
 *  (garde la vraie couleur). */
function unifyGrade(img) {
  return img.linear([1.09, 1.06, 1.02], [-8, -8, -6]);
}

await mkdir(outDir, { recursive: true });
const manifest = {};

for (const p of PHOTOS) {
  let img = await loadImage(p.src);
  img = unifyGrade(img);
  const base = await img.png().toBuffer();
  manifest[p.out] = { widths: p.widths, ratio: p.ratio };

  for (const w of p.widths) {
    const h = Math.round(w / p.ratio);
    const resized = sharp(base).resize(w, h, { fit: 'cover', position: p.position, withoutEnlargement: false });
    await resized.clone().avif({ quality: 55 }).toFile(path.join(outDir, `${p.out}-${w}.avif`));
    await resized.clone().webp({ quality: 80 }).toFile(path.join(outDir, `${p.out}-${w}.webp`));
  }
  console.log(`photo: ${p.out} (${p.widths.join('/')}) [${path.basename(p.src)}]`);
}

// Fusionné dans le manifeste PARTAGÉ (public/photos/manifest.json, lu par
// tests/photos-assets.test.ts), même précaution que process-bouskoura-photos.mjs :
// re-lancer process-photos.mjs seul écraserait ce fichier avec SA SEULE
// sélection — relancer aussi ce script après pour réintégrer ces 6 entrées.
const manifestPath = path.join(outDir, 'manifest.json');
let existing = {};
try {
  existing = JSON.parse(await readFile(manifestPath, 'utf8'));
} catch {
  // Premier run / manifeste absent : on part d'un objet vide.
}
await writeFile(manifestPath, JSON.stringify({ ...existing, ...manifest }, null, 2));
console.log('OK — photos Nouaceur écrites dans public/photos/, manifest.json fusionné');
