/**
 * Outil de curation vidéo (session redesign) : extrait 3 vignettes + durée
 * de chaque clip de photos-raw/ vers .curation/video/ pour revue visuelle.
 *
 *   node scripts/video-sheets.mjs
 */
import ffmpegPath from 'ffmpeg-static';
import { execFileSync } from 'node:child_process';
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const rawDir = path.join(root, 'photos-raw');
const outDir = path.join(root, '.curation', 'video');

const files = (await readdir(rawDir)).filter((f) => /\.(mp4|mov)$/i.test(f)).sort();
await mkdir(outDir, { recursive: true });

const index = {};
let n = 0;
for (const f of files) {
  n++;
  index[n] = f;
  const input = path.join(rawDir, f);
  // Durée via ffmpeg (stderr) — pas de ffprobe dans ffmpeg-static
  let meta = '';
  try {
    execFileSync(ffmpegPath, ['-i', input], { stdio: 'pipe' });
  } catch (e) {
    meta = String(e.stderr);
  }
  const dur = (meta.match(/Duration: (\d+:\d+:\d+\.\d+)/) || [])[1] ?? '?';
  const dim = (meta.match(/, (\d{3,5}x\d{3,5})/) || [])[1] ?? '?';
  index[n] = { file: f, duration: dur, dim };

  const secs = dur === '?' ? 0 : dur.split(':').reduce((a, v) => a * 60 + parseFloat(v), 0);
  const stamps = [0.1, 0.5, 0.85].map((r) => Math.max(0, secs * r));
  const cells = [];
  for (let i = 0; i < 3; i++) {
    const tmp = path.join(outDir, `tmp-${n}-${i}.jpg`);
    try {
      execFileSync(ffmpegPath, ['-ss', String(stamps[i]), '-i', input, '-frames:v', '1', '-q:v', '5', '-y', tmp], { stdio: 'pipe' });
      cells.push(await sharp(tmp).resize(360, 300, { fit: 'contain', background: '#222' }).jpeg().toBuffer());
    } catch {
      cells.push(await sharp({ create: { width: 360, height: 300, channels: 3, background: '#800' } }).jpeg().toBuffer());
    }
  }
  const label = Buffer.from(
    `<svg width="1080" height="30"><rect width="100%" height="100%" fill="#000"/><text x="6" y="21" font-family="Arial" font-size="17" fill="#fff">#V${n} — ${dur} — ${dim} — ${f}</text></svg>`
  );
  await sharp({ create: { width: 1080, height: 330, channels: 3, background: '#222' } })
    .composite([
      { input: cells[0], left: 0, top: 0 },
      { input: cells[1], left: 360, top: 0 },
      { input: cells[2], left: 720, top: 0 },
      { input: label, left: 0, top: 300 },
    ])
    .jpeg({ quality: 70 })
    .toFile(path.join(outDir, `v-${String(n).padStart(2, '0')}.jpg`));
  console.log(`#V${n} ${f} ${dur}`);
}
await writeFile(path.join(outDir, 'index.json'), JSON.stringify(index, null, 2));
