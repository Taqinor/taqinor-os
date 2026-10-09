#!/usr/bin/env node
/**
 * Images Open Graph 1200×630 (YBW45) — une par page du registre (`pages.ts`)
 * et par langue ACTIVE construite, SANS photo : nom de marque inversé (logo
 * dérivé, jamais redessiné) sur encre opaque, le titre de la page, et le
 * trait-flèche du motif (proportions du logo, YBW40).
 *
 * Source des titres : le `og:title` des pages CONSTRUITES (lui-même tiré du
 * dictionnaire de la page par le Layout, YBW60) — donc toujours le texte
 * réellement publié. Rendu : Chromium (Playwright, déjà en devDependencies)
 * avec la police d'affichage RETENUE auto-hébergée (`public/fonts/outfit-*.woff2`,
 * OFL) : le navigateur lit le woff2, aucun TTF ni téléchargement n'est
 * nécessaire. Le rendu n'a pas lieu dans le build Cloudflare (pas de
 * navigateur là-bas) : les PNG sont générés ici puis committés, et
 * `tests/og.test.ts` rougit si une image manque, est périmée (titre changé)
 * ou si son titre sort de la zone sûre.
 *
 * Fichiers : `public/og/<page>-<langue>-<empreinte>.png` (nom versionné →
 * cache immuable d'un an, worker/cache.mjs) + `src/data/og.json` (registre lu
 * par le Layout). Les anciennes images sont supprimées.
 *
 * Usage : npm run build && node scripts/generate-og.mjs && npm run build
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const RACINE = fileURLToPath(new URL('../', import.meta.url));
export const DOSSIER_OG = join(RACINE, 'public', 'og');
export const REGISTRE_OG = join(RACINE, 'src', 'data', 'og.json');
const DIST = join(RACINE, 'dist', 'client');

export const LARGEUR = 1200;
export const HAUTEUR = 630;
/** Zone sûre : marge de 80 px (recadrages des réseaux, coins arrondis). */
export const ZONE_SURE = { x: 80, y: 80, l: LARGEUR - 160, h: HAUTEUR - 160 };
/** Version du gabarit : la changer régénère toutes les images (empreinte). */
export const GABARIT = 'og-1';

/**
 * Le rectangle `r` est-il entièrement dans la zone sûre ?
 * @param {{ x: number, y: number, l: number, h: number }} r
 */
export function dansZoneSure(r, zone = ZONE_SURE) {
  return r.x >= zone.x && r.y >= zone.y && r.x + r.l <= zone.x + zone.l && r.y + r.h <= zone.y + zone.h;
}

/**
 * Largeur et hauteur d'un PNG (en-tête IHDR).
 * @param {Buffer} png
 */
export function taillePng(png) {
  if (png.toString('latin1', 1, 4) !== 'PNG' || png.toString('latin1', 12, 16) !== 'IHDR') throw new Error('pas un PNG');
  return { largeur: png.readUInt32BE(16), hauteur: png.readUInt32BE(20) };
}

/**
 * Empreinte courte d'une image (titre + gabarit).
 * @param {string} titre
 */
export function empreinte(titre) {
  return createHash('sha256').update(`${GABARIT}\n${titre}`).digest('hex').slice(0, 10);
}

/**
 * Valeur hex d'un jeton brut de tokens.css (aucune couleur écrite ici).
 * @param {string} nom
 */
function jeton(nom) {
  const css = readFileSync(join(RACINE, 'src', 'styles', 'tokens.css'), 'utf-8');
  const m = new RegExp(`${nom}:\\s*(#[0-9A-Fa-f]{6})`).exec(css);
  if (!m) throw new Error(`jeton ${nom} introuvable dans tokens.css`);
  return m[1];
}

/** Pages du registre construites, avec leur titre publié (og:title). */
function pagesConstruites() {
  const registre = lireRegistreTs();
  const out = [];
  for (const [id, chemins] of Object.entries(registre)) {
    for (const [langue, url] of Object.entries(chemins)) {
      const fichier = join(DIST, ...url.split('/').filter(Boolean), 'index.html');
      if (!existsSync(fichier)) continue;
      const html = readFileSync(fichier, 'utf-8');
      const titre = /<meta property="og:title" content="([^"]*)"/.exec(html)?.[1];
      if (!titre) continue;
      out.push({ id, langue, titre: decoder(titre) });
    }
  }
  return out;
}

/** Lecture du registre des pages sans exécuter TypeScript (objets littéraux simples). */
export function lireRegistreTs() {
  const src = readFileSync(join(RACINE, 'src', 'i18n', 'pages.ts'), 'utf-8');
  const bloc = /export const PAGES = \{([\s\S]*?)\} as const/.exec(src)?.[1] ?? '';
  /** @type {Record<string, Record<string, string>>} */
  const out = {};
  for (const m of bloc.matchAll(/(\w+):\s*\{\s*fr:\s*'([^']+)',\s*en:\s*'([^']+)'\s*\}/g)) out[m[1]] = { fr: m[2], en: m[3] };
  return out;
}

/** @param {string} s */
function decoder(s) {
  return s.replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n))).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16))).replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
}

/** @param {string} s */
const echapper = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/**
 * HTML du gabarit (polices en data: URL, logo dérivé en ligne).
 * @param {string} titre
 * @param {string} langue
 */
export function gabarit(titre, langue) {
  const police = readFileSync(join(RACINE, 'public', 'fonts', 'outfit-latin-wght-5.3.0.woff2')).toString('base64');
  const logo = readFileSync(join(RACINE, 'src', 'brand', 'derived', 'yanbow-wordmark-reversed.svg'), 'utf-8').replace(
    '<svg ',
    '<svg width="300" aria-hidden="true" ',
  );
  const encre = jeton('--couleur-encre');
  const papier = jeton('--couleur-papier');
  const orange = jeton('--couleur-orange');
  // Trait-flèche aux proportions du logo (src/components/motif/mesures.ts) : fût 36, pointe 98,01, dos 75,32.
  const e = 36;
  const L = 22 * e;
  const pointe = 98.01;
  const demi = 75.32 / 2;
  return `<!doctype html><html lang="${langue}"><head><meta charset="utf-8"><style>
@font-face { font-family: 'Outfit'; font-weight: 100 900; src: url(data:font/woff2;base64,${police}) format('woff2'); }
html, body { margin: 0; inline-size: ${LARGEUR}px; block-size: ${HAUTEUR}px; overflow: hidden; background: ${encre}; }
.carte { position: relative; inline-size: ${LARGEUR}px; block-size: ${HAUTEUR}px; --logo-ink: ${papier}; --logo-arrow: ${orange}; }
.logo { position: absolute; left: ${ZONE_SURE.x}px; top: ${ZONE_SURE.y}px; line-height: 0; }
.fleche { position: absolute; left: 0; top: 268px; inline-size: 360px; color: ${orange}; }
#titre { position: absolute; left: ${ZONE_SURE.x}px; top: 300px; inline-size: ${ZONE_SURE.l}px; margin: 0;
  font-family: 'Outfit', sans-serif; font-weight: 450; font-size: 64px; line-height: 1.08; letter-spacing: -0.02em; color: ${papier};
  display: -webkit-box; -webkit-box-orient: vertical; overflow: hidden; }
</style></head><body><div class="carte">
<div class="logo">${logo}</div>
<svg class="fleche" viewBox="0 ${-demi} ${L + pointe} ${2 * demi}" aria-hidden="true"><path d="M0 0H${L}" stroke="currentColor" stroke-width="${e}"/><path d="M${L - 0.5} ${-demi}L${L + pointe} 0L${L - 0.5} ${demi}Z" fill="currentColor"/></svg>
<h1 id="titre">${echapper(titre)}</h1>
</div></body></html>`;
}

async function principal() {
  const pages = pagesConstruites();
  const { chromium } = await import('@playwright/test');
  const navigateur = await chromium.launch();
  const page = await navigateur.newPage({ viewport: { width: LARGEUR, height: HAUTEUR }, deviceScaleFactor: 1 });
  mkdirSync(DOSSIER_OG, { recursive: true });
  /** @type {Record<string, { fichier: string, titre: string, largeur: number, hauteur: number, zone: { x: number, y: number, l: number, h: number }, tient: boolean }>} */
  const registre = {};
  const gardes = new Set();
  try {
    for (const p of pages) {
      await page.setContent(gabarit(p.titre, p.langue));
      await page.evaluate(() => document.fonts.ready);
      const zone = await page.evaluate(() => {
        const el = /** @type {HTMLElement} */ (document.getElementById('titre'));
        const r = el.getBoundingClientRect();
        return { x: Math.round(r.x), y: Math.round(r.y), l: Math.round(r.width), h: Math.round(el.scrollHeight), deborde: el.scrollWidth > el.clientWidth };
      });
      const fichier = `${p.id}-${p.langue}-${empreinte(p.titre)}.png`;
      await page.screenshot({ path: join(DOSSIER_OG, fichier), type: 'png' });
      gardes.add(fichier);
      registre[`${p.id}.${p.langue}`] = {
        fichier,
        titre: p.titre,
        largeur: LARGEUR,
        hauteur: HAUTEUR,
        zone: { x: zone.x, y: zone.y, l: zone.l, h: zone.h },
        tient: !zone.deborde && dansZoneSure(zone),
      };
      console.log(`${fichier}  ${registre[`${p.id}.${p.langue}`].tient ? 'OK' : 'HORS ZONE SÛRE'}  « ${p.titre} »`);
    }
  } finally {
    await navigateur.close();
  }
  for (const f of readdirSync(DOSSIER_OG)) if (f.endsWith('.png') && !gardes.has(f)) rmSync(join(DOSSIER_OG, f));
  writeFileSync(REGISTRE_OG, JSON.stringify({ gabarit: GABARIT, images: registre }, null, 2) + '\n');
  console.log(`[generate-og] ${pages.length} image(s) — registre ${REGISTRE_OG}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  principal().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
