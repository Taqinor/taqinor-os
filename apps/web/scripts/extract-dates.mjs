/**
 * Outil de session (passe preuve) : extrait la date de prise de vue
 * (EXIF DateTimeOriginal, parseur TIFF minimal) + mtime de chaque fichier
 * de photos-raw/ → .curation/dates.json. Sert à rattacher chaque média à
 * l'une des 5 installations du dossier entreprise.
 *
 *   node scripts/extract-dates.mjs
 */
import sharp from 'sharp';
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const rawDir = 'photos-raw';

/** DateTimeOriginal (0x9003) depuis un buffer EXIF (TIFF). */
function exifDate(buf) {
  try {
    // Préambule "Exif\0\0" éventuel
    if (buf.slice(0, 4).toString() === 'Exif') buf = buf.subarray(6);
    const le = buf.readUInt16LE(0) === 0x4949;
    const r16 = (o) => (le ? buf.readUInt16LE(o) : buf.readUInt16BE(o));
    const r32 = (o) => (le ? buf.readUInt32LE(o) : buf.readUInt32BE(o));
    let ifd = r32(4);
    // IFD0 : cherche ExifIFDPointer (0x8769)
    let exifOff = 0;
    const n0 = r16(ifd);
    for (let i = 0; i < n0; i++) {
      const e = ifd + 2 + i * 12;
      if (r16(e) === 0x8769) exifOff = r32(e + 8);
    }
    if (!exifOff) return null;
    const n1 = r16(exifOff);
    for (let i = 0; i < n1; i++) {
      const e = exifOff + 2 + i * 12;
      if (r16(e) === 0x9003) {
        const off = r32(e + 8);
        return buf.subarray(off, off + 19).toString();
      }
    }
  } catch {}
  return null;
}

const out = {};
for (const f of readdirSync(rawDir)) {
  const full = path.join(rawDir, f);
  const st = statSync(full);
  let date = null;
  if (/\.(heic|jpg|jpeg)$/i.test(f)) {
    try {
      const meta = await sharp(full).metadata();
      if (meta.exif) date = exifDate(meta.exif);
    } catch {}
  }
  out[f] = { exif: date, mtime: st.mtime.toISOString().slice(0, 16) };
}
writeFileSync('.curation/dates.json', JSON.stringify(out, null, 1));
const withExif = Object.values(out).filter((v) => v.exif).length;
console.log(`dates: ${Object.keys(out).length} fichiers, ${withExif} avec EXIF`);
