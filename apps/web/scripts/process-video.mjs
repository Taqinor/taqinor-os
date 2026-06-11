/**
 * Montage chantier pour la page d'accueil : 2 clips retenus sur 30 bruts
 * (IMG_1702.MOV — pose d'un panneau par l'équipe ; IMG_2198.MOV — panorama
 * d'un grand champ). Concaténés, ~35 s, H.264 1080p compressé pour
 * auto-hébergement Worker + affiche (poster) WebP/AVIF.
 *
 *   node scripts/process-video.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import { execFileSync } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, 'public', 'videos');

await mkdir(outDir, { recursive: true });

const CLIP_A = path.join(rawDir, 'IMG_1702.MOV'); // équipe — pose d'un panneau (18 s)
const CLIP_B = path.join(rawDir, 'IMG_2198.MOV'); // panorama grand champ (17 s utiles)
const out = path.join(outDir, 'chantier.mp4');

execFileSync(
  ffmpegPath,
  [
    '-i', CLIP_A,
    '-t', '17', '-i', CLIP_B,
    '-filter_complex',
    '[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p[v0];' +
      '[1:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p[v1];' +
      '[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];' +
      '[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]',
    '-map', '[v]', '-map', '[a]',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-maxrate', '2.2M', '-bufsize', '4M',
    '-c:a', 'aac', '-b:a', '96k', '-ac', '1',
    '-movflags', '+faststart',
    '-y', out,
  ],
  { stdio: 'pipe' },
);
console.log(`video: chantier.mp4 ${(statSync(out).size / 1e6).toFixed(1)} MB`);

// Affiche : image du clip A à 2 s (geste de pose bien lisible)
const posterTmp = path.join(outDir, 'poster-tmp.jpg');
execFileSync(ffmpegPath, ['-ss', '2', '-i', CLIP_A, '-frames:v', '1', '-q:v', '3', '-y', posterTmp], { stdio: 'pipe' });
for (const [ext, make] of [
  ['webp', (s) => s.webp({ quality: 78 })],
  ['avif', (s) => s.avif({ quality: 55 })],
]) {
  await make(
    sharp(posterTmp).resize(1600, 900, { fit: 'cover' }).linear(1.05, 0).modulate({ saturation: 1.05 }),
  ).toFile(path.join(outDir, `chantier-poster.${ext}`));
}
execFileSync(process.platform === 'win32' ? 'cmd' : 'rm', process.platform === 'win32' ? ['/c', 'del', posterTmp] : [posterTmp]);
console.log('poster: chantier-poster.webp/avif');
