/**
 * Réalisation Bouskoura (2026-09) — vidéo de chantier 16:9, publiée sous
 * /videos/bouskoura-chantier.mp4 (+ poster), lue via LiteVideo.astro sur
 * /realisations/bouskoura-villa-2026.
 *
 * RÈGLE FONDATEUR ABSOLUE (08/09/2026) : le montage source contient une
 * étiquette de datalogger (n° de série + MOT DE PASSE + QR code) filmée en
 * gros plan. Repérage image par image (fps=5 contact sheet + frames isolées) :
 * dans CE montage 16:9, elle est nette et lisible d'environ t=37,4 s à
 * t=39,0 s (transition floue avant/après ≈36,8-39,6 s) — position STABLE dans
 * le cadre (caméra fixe sur ce plan), rectangle mesuré sur plusieurs frames :
 * x=730 y=0 largeur=320 hauteur=700 (résolution source 1920×1080). Le filtre
 * ci-dessous floute CETTE zone, UNIQUEMENT sur cette fenêtre temporelle
 * (marge de sécurité ajoutée aux deux bords), AVANT le redimensionnement en
 * 720p — jamais l'inverse (les coordonnées mesurées sont en 1080p natif).
 * Une vérification post-encodage (3 frames extraites du fichier FINAL, dans
 * le dossier temp OS) permet de confirmer visuellement l'illisibilité avant
 * toute publication — jamais supprimées automatiquement.
 *
 * Ré-encodage : H.264 720p, faststart, ≤ 20 Mo (limite Cloudflare Pages :
 * 25 MiB/fichier — marge gardée). Audio conservé (narration/ambiance),
 * ré-encodé en AAC 128k pour tenir le budget.
 *
 *   node scripts/realisations/process-bouskoura-video.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import sharp from 'sharp';
import { execFileSync } from 'node:child_process';
import { statSync, unlinkSync } from 'node:fs';
import { mkdir as mkdirP } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const outDir = path.join(root, 'public', 'videos');

const SRC = 'C:\\Users\\kasri\\OneDrive - Atlencia\\TAQINOR\\Marketing\\Pictures\\boukoura-07-26';
const input = path.join(SRC, 'Videos', 'Taqinor.mp4');
const out = path.join(outDir, 'bouskoura-chantier.mp4');

await mkdirP(outDir, { recursive: true });

// Zone de l'étiquette datalogger (1080p natif, mesurée sur frames à
// t=37.6/38.0/38.8 — position stable), fenêtre temporelle avec marge.
const BLUR = { x: 730, y: 0, w: 320, h: 700 };
const BLUR_START = 36.8;
const BLUR_END = 39.6;

const filterComplex =
  `[0:v]split=2[main][tmp];` +
  `[tmp]crop=${BLUR.w}:${BLUR.h}:${BLUR.x}:${BLUR.y},boxblur=24:3[blurred];` +
  `[main][blurred]overlay=${BLUR.x}:${BLUR.y}:enable='between(t,${BLUR_START},${BLUR_END})'[boxed];` +
  `[boxed]scale=1280:720:flags=lanczos,format=yuv420p[vout]`;

execFileSync(
  ffmpegPath,
  [
    '-i', input,
    '-filter_complex', filterComplex,
    '-map', '[vout]', '-map', '0:a?',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-maxrate', '2.3M', '-bufsize', '4.6M',
    '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
    '-movflags', '+faststart',
    '-y', out,
  ],
  { stdio: 'pipe' },
);

const mb = statSync(out).size / 1e6;
console.log(`bouskoura-chantier.mp4 : ${mb.toFixed(1)} Mo (budget <= 20 Mo)`);
if (mb > 20) throw new Error(`bouskoura-chantier.mp4 ${mb.toFixed(1)} Mo > budget 20 Mo`);

// ── Vérification post-encodage : l'étiquette ne doit PLUS être lisible ──────
// Extrait 3 frames dans la fenêtre floutée du fichier FINAL, dans le dossier
// temp OS (jamais dans le dépôt) — contrôle visuel avant publication.
const checkDir = path.join(tmpdir(), 'bouskoura-blur-check');
await mkdirP(checkDir, { recursive: true });
for (const t of [37.6, 38.2, 38.8]) {
  execFileSync(
    ffmpegPath,
    ['-y', '-ss', String(t), '-i', out, '-frames:v', '1', '-q:v', '2', path.join(checkDir, `blur-check-${t}.jpg`)],
    { stdio: 'pipe' },
  );
}
console.log(`Vérification : frames extraites dans ${checkDir} (à inspecter avant publication)`);

// ── Poster (LiteVideo lit UNIQUEMENT {poster}.avif / {poster}.webp — sans
//    suffixe de largeur, pas de srcset responsive pour l'affiche). ──────────
const tmp = path.join(outDir, 'bouskoura-poster-tmp.jpg');
execFileSync(ffmpegPath, ['-y', '-ss', '2', '-i', out, '-frames:v', '1', '-q:v', '2', tmp], { stdio: 'pipe' });
const base = await sharp(tmp).resize(1600, 900, { fit: 'cover' }).png().toBuffer();
await sharp(base).webp({ quality: 78 }).toFile(path.join(outDir, 'bouskoura-chantier-poster.webp'));
await sharp(base).avif({ quality: 55 }).toFile(path.join(outDir, 'bouskoura-chantier-poster.avif'));
unlinkSync(tmp);
console.log('poster: bouskoura-chantier-poster.{webp,avif} (1600x900)');
