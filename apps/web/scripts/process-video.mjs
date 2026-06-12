/**
 * Montage chantier (tri approfondi : 4 moments distincts sur 30 clips
 * inventoriés — .curation/inventory.json) :
 *   1. IMG_1702.MOV  — pose : deux installateurs fixent un panneau (8,5 s)
 *   2. ...134025.MP4 — portage : panneau porté, gilets TAQINOR (6 s)
 *   3. ...133423.MP4 — monitoring : écran onduleur, vertical sur fond
 *                      flouté (mêmes pixels, aucun ajout) (5,5 s)
 *   4. IMG_2198.MOV  — révélation large : pano du champ + ville (10 s)
 * Étalonnure commune accordée aux photos (contraste doux, saturation).
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

const GRADE = 'eq=contrast=1.04:saturation=1.1';
const FIT = `scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p,${GRADE}`;
// Vertical : le clip entier sur son propre fond agrandi flouté (pillarbox
// non génératif — uniquement les pixels du clip).
const FIT_VERTICAL =
  `split=2[bg][fg];[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,gblur=sigma=24[bgb];` +
  `[fg]scale=-2:1080[fgs];[bgb][fgs]overlay=(W-w)/2:0,fps=30,format=yuv420p,${GRADE}`;

const out = path.join(outDir, 'chantier.mp4');
execFileSync(
  ffmpegPath,
  [
    '-ss', '1', '-t', '8.5', '-i', path.join(rawDir, 'IMG_1702.MOV'),
    '-ss', '4', '-t', '6', '-i', path.join(rawDir, '20251020_134025000_iOS.MP4'),
    '-ss', '2', '-t', '5.5', '-i', path.join(rawDir, '20251020_133423000_iOS.MP4'),
    '-ss', '2', '-t', '10', '-i', path.join(rawDir, 'IMG_2198.MOV'),
    '-filter_complex',
    `[0:v]${FIT}[v0];[1:v]${FIT}[v1];[2:v]${FIT_VERTICAL}[v2];[3:v]${FIT}[v3];` +
      '[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[2:a]aresample=48000[a2];[3:a]aresample=48000[a3];' +
      '[v0][a0][v1][a1][v2][a2][v3][a3]concat=n=4:v=1:a=1[v][a]',
    '-map', '[v]', '-map', '[a]',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '24', '-maxrate', '2.2M', '-bufsize', '4M',
    '-c:a', 'aac', '-b:a', '96k', '-ac', '1',
    '-movflags', '+faststart',
    '-y', out,
  ],
  { stdio: 'pipe' },
);
console.log(`video: chantier.mp4 ${(statSync(out).size / 1e6).toFixed(1)} MB (4 moments, ~30 s)`);

// Affiche du montage : geste de pose, étalonnée comme les photos
const posterTmp = path.join(outDir, 'poster-tmp.jpg');
execFileSync(ffmpegPath, ['-ss', '2', '-i', path.join(rawDir, 'IMG_1702.MOV'), '-frames:v', '1', '-q:v', '3', '-y', posterTmp], { stdio: 'pipe' });
const poster = sharp(posterTmp)
  .resize(1600, 900, { fit: 'cover' })
  .clahe({ width: 200, height: 200, maxSlope: 2 })
  .normalise({ lower: 0.6, upper: 99.6 })
  .modulate({ saturation: 1.08 })
  .linear(1.02, -3)
  .tint({ r: 255, g: 252, b: 246 });
await poster.clone().webp({ quality: 78 }).toFile(path.join(outDir, 'chantier-poster.webp'));
await poster.clone().avif({ quality: 55 }).toFile(path.join(outDir, 'chantier-poster.avif'));
execFileSync(process.platform === 'win32' ? 'cmd' : 'rm', process.platform === 'win32' ? ['/c', 'del', posterTmp] : [posterTmp]);
console.log('poster: chantier-poster.webp/avif');
