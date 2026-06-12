/**
 * Montage chantier v3 — un MONTAGE, pas un assemblage. Narration sur les
 * installations réelles (mapping EXIF → dossier entreprise) :
 *   portage (NC-10/25 Nouaceur) → pose du panneau (Ref 236 El Jadida) →
 *   écran onduleur/monitoring (NC-10/25) → REFLET DU SOLEIL sur les
 *   panneaux (Ref 468 El Jadida, IMG_2210 — le plan beauté) → révélation
 *   large avec échelle (Ref 468, IMG_2198).
 * Deux rythmes : A calme/premium ~31 s (défaut en prod, ≤ 3 Mo) ·
 * B énergique ~21 s. Étalonnure accordée aux photos.
 *
 *   node scripts/process-montages.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import { execFileSync } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, 'public', 'videos');
await mkdir(outDir, { recursive: true });

const GRADE = 'eq=contrast=1.04:saturation=1.1';
const FIT = (s = '') => `scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30,format=yuv420p,${GRADE}${s}`;
const FIT_V = `split=2[bg][fg];[bg]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,gblur=sigma=22[bgb];[fg]scale=-2:720[fgs];[bgb][fgs]overlay=(W-w)/2:0,fps=30,format=yuv420p,${GRADE}`;

const CLIPS = {
  portage: [path.join(rawDir, '20251020_134025000_iOS.MP4'), FIT()], // NC-10/25
  pose: [path.join(rawDir, 'IMG_1702.MOV'), FIT()], // Ref 236
  drill: [path.join(rawDir, '20251020_133535000_iOS.MP4'), FIT_V], // NC, vertical
  monitoring: [path.join(rawDir, '20251020_133423000_iOS.MP4'), FIT_V], // NC, vertical
  reflet: [path.join(rawDir, 'IMG_2210.MOV'), FIT()], // Ref 468 — plan beauté
  reveal: [path.join(rawDir, 'IMG_2198.MOV'), FIT()], // Ref 468 — large
};

/** cut = [clé, début s, durée s] — coupes sur le mouvement. */
function build(name, cuts, { crf, maxrate }) {
  const inputs = [];
  const filters = [];
  const labels = [];
  cuts.forEach(([key, ss, t], i) => {
    const [file, fit] = CLIPS[key];
    inputs.push('-ss', String(ss), '-t', String(t), '-i', file);
    filters.push(`[${i}:v]${fit}[v${i}]`, `[${i}:a]aresample=48000[a${i}]`);
    labels.push(`[v${i}][a${i}]`);
  });
  const out = path.join(outDir, name);
  execFileSync(
    ffmpegPath,
    [
      ...inputs,
      '-filter_complex', `${filters.join(';')};${labels.join('')}concat=n=${cuts.length}:v=1:a=1[v][a]`,
      '-map', '[v]', '-map', '[a]',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', String(crf), '-maxrate', maxrate, '-bufsize', '2M',
      '-c:a', 'aac', '-b:a', '64k', '-ac', '1',
      '-movflags', '+faststart',
      '-y', out,
    ],
    { stdio: 'pipe' },
  );
  const mb = statSync(out).size / 1e6;
  console.log(`${name}: ${mb.toFixed(1)} MB (${cuts.reduce((a, c) => a + c[2], 0)} s)`);
  return mb;
}

// A — calme/premium, ~31 s, plans posés. Fin sur le plan le plus fort
// (révélation large, coupée au moment où le champ entier est lisible).
const a = build('chantier-a.mp4', [
  ['portage', 4, 4],
  ['pose', 1, 8],
  ['monitoring', 2, 5],
  ['reflet', 3, 6],
  ['reveal', 2, 8],
], { crf: 28, maxrate: '620k' });
if (a > 3) throw new Error(`chantier-a.mp4 ${a.toFixed(1)} MB > budget 3 MB`);

// B — énergique, ~21 s, coupes courtes sur le mouvement.
const b = build('chantier-b.mp4', [
  ['portage', 4.5, 2.5],
  ['pose', 2, 4.5],
  ['drill', 3, 3],
  ['monitoring', 3, 2.5],
  ['reflet', 4, 4],
  ['reveal', 4, 4.5],
], { crf: 26, maxrate: '900k' });
if (b > 4) throw new Error(`chantier-b.mp4 ${b.toFixed(1)} MB > budget 4 MB`);
