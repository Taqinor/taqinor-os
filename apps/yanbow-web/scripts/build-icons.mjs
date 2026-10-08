#!/usr/bin/env node
/**
 * Favicon et icônes (YBW37) — tous générés depuis UNE source : la coupe
 * favicon INVERSÉE du pack (`src/brand/svg/*-favicon16-reversed.svg` : B blanc
 * + flèche orange sur une tuile encre OPAQUE). Une tuile opaque reste visible
 * sur un onglet clair comme sombre (les PNG transparents du pack, eux,
 * disparaissent sur un onglet sombre).
 *
 * Écrit dans public/ :
 *   favicon.svg                       — copie à l'octet de la source
 *   favicon.ico                       — PNG 16/32/48 empaquetés (ICO à PNG)
 *   icons/icon-16.png, -32, -48       — favicons PNG
 *   icons/apple-touch-icon-180.png    — iOS
 *   icons/icon-192.png, icon-512.png  — PWA
 *   icons/icon-maskable-512.png       — PWA maskable : B dans la zone sûre (cercle de 40 %)
 *   site.webmanifest                  — nom lu dans src/lib/brand.ts
 *
 * Usage : node scripts/build-icons.mjs
 */
import { copyFileSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const RACINE = new URL('../', import.meta.url);
const PACK = fileURLToPath(new URL('src/brand/svg/', RACINE));
const PUBLIC = fileURLToPath(new URL('public/', RACINE));
const ENCRE = '#1B1B1B';

/** La source unique (repérée par son suffixe, sans écrire la marque ici). */
export const SOURCE = PACK + readdirSync(PACK).find((n) => n.endsWith('-favicon16-reversed.svg'));

export const TAILLES_FAVICON = [16, 32, 48];
export const ICONES = {
  'apple-touch-icon-180.png': 180,
  'icon-192.png': 192,
  'icon-512.png': 512,
};
export const MASQUABLE = { nom: 'icon-maskable-512.png', taille: 512 };

/**
 * @param {number} taille
 * @returns {Promise<Buffer>}
 */
function png(taille) {
  return sharp(SOURCE, { density: Math.max(72, (72 * taille) / 16) }).resize(taille, taille).png().toBuffer();
}

/**
 * Boîte du glyphe dans la source (unités de la viewBox 800 × 800) — mesurée par
 * scripts/derive-logo-variants.mjs (viewBox resserrée « 100 50 600 700 »).
 */
export const GLYPHE = { x0: 100, y0: 50, x1: 700, y1: 750, cote: 800 };

/**
 * Icône masquable : tuile encre pleine, glyphe mis à l'échelle pour que les
 * COINS de sa boîte tiennent dans le cercle sûr (rayon 40 % du côté).
 * @param {number} taille
 */
async function masquable(taille) {
  const demiDiagonale = Math.hypot((GLYPHE.x1 - GLYPHE.x0) / 2, (GLYPHE.y1 - GLYPHE.y0) / 2);
  const rendu = Math.floor((0.4 * taille * GLYPHE.cote) / demiDiagonale) - 2;
  const image = await sharp(SOURCE, { density: 300 }).resize(rendu, rendu).png().toBuffer();
  const decalage = Math.round((taille - rendu) / 2);
  return sharp({ create: { width: taille, height: taille, channels: 4, background: ENCRE } })
    .composite([{ input: image, left: decalage, top: decalage }])
    .png()
    .toBuffer();
}

/**
 * Fichier .ico contenant des PNG (format admis par tous les navigateurs actuels).
 * @param {{ taille: number, donnees: Buffer }[]} images
 */
export function ico(images) {
  const entete = Buffer.alloc(6);
  entete.writeUInt16LE(0, 0);
  entete.writeUInt16LE(1, 2);
  entete.writeUInt16LE(images.length, 4);
  const repertoire = Buffer.alloc(16 * images.length);
  let decalage = 6 + 16 * images.length;
  images.forEach(({ taille, donnees }, i) => {
    const o = i * 16;
    repertoire.writeUInt8(taille >= 256 ? 0 : taille, o);
    repertoire.writeUInt8(taille >= 256 ? 0 : taille, o + 1);
    repertoire.writeUInt8(0, o + 2);
    repertoire.writeUInt8(0, o + 3);
    repertoire.writeUInt16LE(1, o + 4);
    repertoire.writeUInt16LE(32, o + 6);
    repertoire.writeUInt32LE(donnees.length, o + 8);
    repertoire.writeUInt32LE(decalage, o + 12);
    decalage += donnees.length;
  });
  return Buffer.concat([entete, repertoire, ...images.map((x) => x.donnees)]);
}

/** Nom de la marque lu dans src/lib/brand.ts (source unique des noms). */
export function marque() {
  const src = readFileSync(fileURLToPath(new URL('src/lib/brand.ts', RACINE)), 'utf-8');
  const m = /export const MARQUE = '([^']+)'/.exec(src);
  if (!m) throw new Error('MARQUE introuvable dans src/lib/brand.ts');
  return m[1];
}

async function principal() {
  mkdirSync(PUBLIC + 'icons', { recursive: true });
  copyFileSync(SOURCE, PUBLIC + 'favicon.svg');
  const favicons = [];
  for (const t of TAILLES_FAVICON) {
    const donnees = await png(t);
    writeFileSync(PUBLIC + `icons/icon-${t}.png`, donnees);
    favicons.push({ taille: t, donnees });
  }
  writeFileSync(PUBLIC + 'favicon.ico', ico(favicons));
  for (const [nom, t] of Object.entries(ICONES)) writeFileSync(PUBLIC + `icons/${nom}`, await png(t));
  writeFileSync(PUBLIC + `icons/${MASQUABLE.nom}`, await masquable(MASQUABLE.taille));
  const nom = marque();
  const manifeste = {
    name: nom,
    short_name: nom,
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: `/icons/${MASQUABLE.nom}`, sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    theme_color: ENCRE,
    background_color: ENCRE,
    display: 'browser',
  };
  writeFileSync(PUBLIC + 'site.webmanifest', JSON.stringify(manifeste, null, 2) + '\n');
  console.log('icônes écrites dans public/');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await principal();
