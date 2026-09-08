/**
 * Réalisation Bouskoura (2026-09) — photos optimisées dans public/photos/,
 * même convention que scripts/process-photos.mjs (AVIF q55 + WebP q80, mêmes
 * largeurs déclarées dans src/lib/realisations.ts).
 *
 * Sources : 3 JPG natifs (BH8A75xx.JPG) + 5 frames extraites des meilleurs
 * plans du montage brut (BH8A75xx.MOV), toutes tournées le 09/07/2026 sur le
 * MÊME chantier (villa de Bouskoura) — jamais mélangées avec une autre
 * installation. `bouskoura-batterie-dyness` est tournée à 180° dans le brut
 * (la caméra filmait l'étiquette DYNESS depuis en dessous) : `.rotate(180)`
 * la remet à l'endroit.
 *
 * Le dossier source (OneDrive, hors dépôt) n'est JAMAIS écrit — lecture
 * seule. Aucun fichier brut n'est committé (règle photos-raw/ du .gitignore).
 *
 *   node scripts/realisations/process-bouskoura-photos.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import sharp from 'sharp';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const outDir = path.join(root, 'public', 'photos');

// Dossier source réel (lecture seule, jamais copié dans le dépôt — trop
// volumineux : 46 clips 1080p + 2 montages ≈ 330 Mo au total).
const SRC = 'C:\\Users\\kasri\\OneDrive - Atlencia\\TAQINOR\\Marketing\\Pictures\\boukoura-07-26';
const RAW_DIR = path.join(SRC, '2026-07-09_Raw_Footage');

/**
 * Une entrée par photo publiée. `src` = JPG natif (chemin direct) OU
 * `{ clip, atSeconds }` = frame extraite d'un .MOV à l'instant choisi (le
 * meilleur plan identifié à l'écran, cf. rapport de repérage).
 */
const PHOTOS = [
  {
    out: 'bouskoura-toit',
    src: path.join(RAW_DIR, 'BH8A7558.JPG'),
    widths: [2000, 1280, 768, 480],
    ratio: 16 / 9,
  },
  {
    out: 'bouskoura-toit-large',
    clip: path.join(RAW_DIR, 'BH8A7560.MOV'),
    atSeconds: 2.0,
    widths: [1600, 1024, 640],
    ratio: 16 / 9,
  },
  {
    out: 'bouskoura-panneaux',
    clip: path.join(RAW_DIR, 'BH8A7556.MOV'),
    atSeconds: 3.0,
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
  },
  {
    out: 'bouskoura-gilet-taqinor',
    clip: path.join(RAW_DIR, 'BH8A7569.MOV'),
    atSeconds: 1.5,
    widths: [1600, 1024, 640],
    ratio: 1,
  },
  {
    out: 'bouskoura-cablage-onduleur',
    clip: path.join(RAW_DIR, 'BH8A7549.MOV'),
    atSeconds: 2.0,
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
  },
  {
    out: 'bouskoura-coffret-technicien',
    src: path.join(RAW_DIR, 'BH8A7577.JPG'),
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
  },
  {
    out: 'bouskoura-equipe-mur-technique',
    clip: path.join(RAW_DIR, 'BH8A7585.MOV'),
    atSeconds: 2.0,
    widths: [1600, 1024, 640],
    ratio: 3 / 2,
  },
  {
    out: 'bouskoura-batterie-dyness',
    clip: path.join(RAW_DIR, 'BH8A7545.MOV'),
    atSeconds: 2.5,
    widths: [1600, 1024, 640],
    ratio: 4 / 3,
    rotate180: true, // caméra filmait l'étiquette DYNESS depuis en dessous.
  },
];

/** Extrait UNE frame JPEG (qualité quasi-lossless) d'un clip, en mémoire — jamais de fichier temporaire. */
function extractFrame(clip, atSeconds) {
  return execFileSync(
    ffmpegPath,
    ['-ss', String(atSeconds), '-i', clip, '-frames:v', '1', '-q:v', '2', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'],
    { stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 1024 * 1024 * 64 },
  );
}

/** Même étalonnure commune que process-photos.mjs (« cinéma du chantier ») —
 *  contraste doux + voile chaud, jamais de tint() (garde la vraie couleur). */
function unifyGrade(img) {
  return img.linear([1.09, 1.06, 1.02], [-8, -8, -6]);
}

await mkdir(outDir, { recursive: true });
const manifest = {};

for (const p of PHOTOS) {
  const buf = p.src ? undefined : extractFrame(p.clip, p.atSeconds);
  let img = sharp(p.src ?? buf).rotate(); // .rotate() sans argument : applique l'EXIF s'il y en a.
  if (p.rotate180) img = img.rotate(180);
  img = unifyGrade(img);
  const base = await img.png().toBuffer();
  manifest[p.out] = { widths: p.widths, ratio: p.ratio };

  for (const w of p.widths) {
    const h = Math.round(w / p.ratio);
    const resized = sharp(base).resize(w, h, { fit: 'cover', withoutEnlargement: false });
    await resized.clone().avif({ quality: 55 }).toFile(path.join(outDir, `${p.out}-${w}.avif`));
    await resized.clone().webp({ quality: 80 }).toFile(path.join(outDir, `${p.out}-${w}.webp`));
  }
  console.log(`photo: ${p.out} (${p.widths.join('/')})${p.src ? ' [JPG natif]' : ` [frame @${p.atSeconds}s]`}`);
}

// (2026-09) Fusionné dans le manifeste PARTAGÉ (public/photos/manifest.json,
// lu par tests/photos-assets.test.ts) plutôt qu'un fichier séparé : les 8
// photos Bouskoura héritent ainsi du même garde-fou anti-404 que le reste du
// site. NOTE pour un futur mainteneur : re-lancer process-photos.mjs seul
// écrase ce fichier avec SA SEULE sélection (comportement préexistant,
// inchangé) — relancer aussi ce script après pour réintégrer ces 8 entrées.
const manifestPath = path.join(outDir, 'manifest.json');
let existing = {};
try {
  existing = JSON.parse(await readFile(manifestPath, 'utf8'));
} catch {
  // Premier run / manifeste absent : on part d'un objet vide.
}
await writeFile(manifestPath, JSON.stringify({ ...existing, ...manifest }, null, 2));
console.log('OK — photos Bouskoura écrites dans public/photos/, manifest.json fusionné');
