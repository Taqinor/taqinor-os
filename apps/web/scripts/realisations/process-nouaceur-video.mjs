/**
 * Réalisation Nouaceur (réf. NC-10/25, 2026-09) — vidéo de chantier 16:9,
 * publiée sous /videos/nouaceur-chantier.mp4 (+ poster), lue via
 * LiteVideo.astro sur /realisations/nouaceur-4-kwc.
 *
 * ASSEMBLAGE de 3 plans réels du MÊME chantier (jamais mélangés avec une
 * autre installation), choisis après revue image par image de la totalité
 * des 22 MP4 + 1 MOV du dossier source :
 *   1. 20251018_104855000_iOS.MOV (18/10/2025, 0-7s) — natif 1920x1080 16:9,
 *      la meilleure qualité technique du lot (HEVC) : les deux installateurs
 *      mesurent l'implantation des blocs de lestage au sol.
 *   2. 20251020_133535000_iOS.MP4 (20/10/2025, portrait 720x1280, 1-7s) — un
 *      installateur fixe un panneau à la perceuse, gilet Taqinor visible.
 *      Recadrage centré 720x405 (16:9) puis mise à l'échelle 720p — AUCUN
 *      flip : le logo au dos de CE vêtement précis est imprimé à l'envers en
 *      usine (défaut de flocage, vérifié en comparant avec d'autres plans du
 *      même lot où le logo Taqinor est net) ; retourner l'image entière
 *      aurait inversé la casquette et la main du geste, un défaut pire que le
 *      petit logo illisible.
 *   3. 20251020_133438000_iOS.MP4 (20/10/2025, portrait 720x1280, 1-6s) — la
 *      rangée de six panneaux terminée, lumière dorée, palmiers en fond.
 *      Même recadrage centré 720x405 → 720p.
 * Durée totale ≈ 18 s. Audio d'ambiance conservé sur les trois plans.
 *
 * Ré-encodage : H.264 720p, faststart, ≤ 20 Mo (mêmes réglages que
 * process-bouskoura-video.mjs : crf 23 preset slow, maxrate 2.3M).
 *
 * Le dossier source (OneDrive, hors dépôt) n'est JAMAIS écrit — lecture
 * seule. Aucun fichier brut n'est committé.
 *
 *   node scripts/realisations/process-nouaceur-video.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import sharp from 'sharp';
import { execFileSync } from 'node:child_process';
import { statSync, unlinkSync } from 'node:fs';
import { mkdir as mkdirP } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const outDir = path.join(root, 'public', 'videos');

const SRC = 'C:\\Users\\kasri\\OneDrive - Atlencia\\TAQINOR\\Marketing\\Pictures';
const clip1 = path.join(SRC, '20251018_104855000_iOS.MOV');
const clip2 = path.join(SRC, '20251020_133535000_iOS.MP4');
const clip3 = path.join(SRC, '20251020_133438000_iOS.MP4');
const out = path.join(outDir, 'nouaceur-chantier.mp4');

await mkdirP(outDir, { recursive: true });

// Recadrage centré portrait(720x1280) -> 16:9 (720x405), mesuré à l'écran sur
// des frames extraites de chaque clip (garde le sujet + la scène, coupe
// surtout du ciel/sol excédentaire).
const CROP = 'crop=720:405:0:437';
const CROP2 = 'crop=720:405:0:380';

const filterComplex =
  `[0:v]scale=1280:720:flags=lanczos,format=yuv420p,setsar=1[v0];` +
  `[1:v]${CROP},scale=1280:720:flags=lanczos,format=yuv420p,setsar=1[v1];` +
  `[2:v]${CROP2},scale=1280:720:flags=lanczos,format=yuv420p,setsar=1[v2];` +
  `[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];` +
  `[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];` +
  `[2:a]aresample=48000,aformat=channel_layouts=stereo[a2];` +
  `[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[vout][aout]`;

execFileSync(
  ffmpegPath,
  [
    '-ss', '0', '-t', '7.0', '-i', clip1,
    '-ss', '1', '-t', '6', '-i', clip2,
    '-ss', '1', '-t', '5', '-i', clip3,
    '-filter_complex', filterComplex,
    '-map', '[vout]', '-map', '[aout]',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-maxrate', '2.3M', '-bufsize', '4.6M',
    '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
    '-movflags', '+faststart',
    '-y', out,
  ],
  { stdio: 'pipe' },
);

const mb = statSync(out).size / 1e6;
console.log(`nouaceur-chantier.mp4 : ${mb.toFixed(1)} Mo (budget <= 20 Mo)`);
if (mb > 20) throw new Error(`nouaceur-chantier.mp4 ${mb.toFixed(1)} Mo > budget 20 Mo`);

// ── Poster (LiteVideo lit UNIQUEMENT {poster}.avif / {poster}.webp — sans
//    suffixe de largeur). Pris à t=15s, dans le plan de clôture (rangée de
//    panneaux terminée, lumière dorée) — le meilleur cadre du montage. ──────
const tmp = path.join(outDir, 'nouaceur-poster-tmp.jpg');
execFileSync(ffmpegPath, ['-y', '-ss', '15', '-i', out, '-frames:v', '1', '-update', '1', '-q:v', '2', tmp], { stdio: 'pipe' });
const base = await sharp(tmp).resize(1600, 900, { fit: 'cover' }).png().toBuffer();
await sharp(base).webp({ quality: 78 }).toFile(path.join(outDir, 'nouaceur-chantier-poster.webp'));
await sharp(base).avif({ quality: 55 }).toFile(path.join(outDir, 'nouaceur-chantier-poster.avif'));
unlinkSync(tmp);
console.log('poster: nouaceur-chantier-poster.{webp,avif} (1600x900)');
