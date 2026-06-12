/**
 * Boucle héro : extrait ~11 s du panorama IMG_2198.MOV (grand champ +
 * ville blanche), muet, 720p, très compressé (~2 Mo) pour lecture
 * automatique en arrière-plan du héro. Affiche (poster) assortie,
 * débrumée comme les photos.
 *
 *   node scripts/process-hero-video.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import { execFileSync } from 'node:child_process';
import { statSync, unlinkSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const input = path.join(root, 'photos-raw', 'IMG_2198.MOV');
const outDir = path.join(root, 'public', 'videos');
const out = path.join(outDir, 'hero.mp4');

execFileSync(
  ffmpegPath,
  [
    '-ss', '2', '-t', '11', '-i', input,
    '-vf', 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=24,format=yuv420p,eq=saturation=1.1:contrast=1.05',
    '-an',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '28', '-maxrate', '1.6M', '-bufsize', '3M',
    '-movflags', '+faststart',
    '-y', out,
  ],
  { stdio: 'pipe' },
);
console.log(`video: hero.mp4 ${(statSync(out).size / 1e6).toFixed(1)} MB`);

const tmp = path.join(outDir, 'hero-tmp.jpg');
execFileSync(ffmpegPath, ['-ss', '2', '-i', input, '-frames:v', '1', '-q:v', '3', '-y', tmp], { stdio: 'pipe' });
const img = sharp(tmp).resize(1600, 900, { fit: 'cover' });
const meta = await img.metadata();
const treated = img.clahe({ width: 200, height: 200, maxSlope: 2 }).normalise({ lower: 0.6, upper: 99.6 }).modulate({ saturation: 1.12 });
await treated.clone().webp({ quality: 75 }).toFile(path.join(outDir, 'hero-poster.webp'));
await treated.clone().avif({ quality: 52 }).toFile(path.join(outDir, 'hero-poster.avif'));
unlinkSync(tmp);
console.log('poster: hero-poster.webp/avif');
