#!/usr/bin/env node
/**
 * Variantes web du logo (YBW36) — DÉRIVÉES du pack de Reda (src/brand/svg/),
 * jamais redessinées. Pour chacun des 17 SVG, écrit src/brand/derived/<nom>.svg :
 *  1. retire SEULEMENT le rectangle encre des fichiers `reversed` (sinon une
 *     boîte visible sur tout fond sombre autre que #1B1B1B) ;
 *  2. resserre la viewBox sur la boîte englobante EXACTE des tracés (extrema
 *     des courbes de Bézier, translation du groupe appliquée) — les marges
 *     intégrées au pack disparaissent ; aucune largeur/hauteur fixe ;
 *  3. expose les couleurs en propriétés CSS : chaque tracé garde son attribut
 *     `fill` d'origine (repli) et reçoit `style="fill:var(--logo-ink|--logo-arrow, <origine>)"`
 *     (`--logo-arrow` = la flèche orange, `--logo-ink` = tout le reste).
 * Les attributs `d` sont recopiés TELS QUELS (garde : tests/logoDerived.test.ts).
 *
 * Usage : node scripts/derive-logo-variants.mjs [--check]
 *   --check : n'écrit rien, échoue si un fichier dérivé est absent ou différent.
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const SOURCE = fileURLToPath(new URL('../src/brand/svg/', import.meta.url));
const SORTIE = fileURLToPath(new URL('../src/brand/derived/', import.meta.url));
const ORANGE = '#C8762B';

/**
 * Tokenise un `d` absolu (M, L, C, Z — seules commandes du pack).
 * @param {string} d
 * @returns {{ lettre: string, nombres: number[] }[]}
 */
function commandes(d) {
  const out = [];
  const re = /([MLCZ])([^MLCZ]*)/gi;
  let m;
  while ((m = re.exec(d))) {
    const lettre = m[1];
    if (lettre !== lettre.toUpperCase()) throw new Error(`commande relative inattendue « ${lettre} » : le dériveur ne gère que M L C Z absolus`);
    const nombres = (m[2].match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
    out.push({ lettre, nombres });
  }
  return out;
}

/**
 * Extrema d'une cubique sur un axe (valeurs de t dans ]0,1[).
 * @param {number} p0 @param {number} p1 @param {number} p2 @param {number} p3
 * @returns {number[]}
 */
function extremaCubique(p0, p1, p2, p3) {
  const a = -p0 + 3 * p1 - 3 * p2 + p3;
  const b = 2 * (p0 - 2 * p1 + p2);
  const c = p1 - p0;
  const ts = [];
  if (Math.abs(a) < 1e-12) {
    if (Math.abs(b) > 1e-12) ts.push(-c / b);
  } else {
    const disc = b * b - 4 * a * c;
    if (disc >= 0) {
      const r = Math.sqrt(disc);
      ts.push((-b + r) / (2 * a), (-b - r) / (2 * a));
    }
  }
  return ts.filter((t) => t > 0 && t < 1).map((t) => (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3);
}

/**
 * Boîte englobante exacte d'un `d`.
 * @param {string} d
 * @returns {{ x0: number, y0: number, x1: number, y1: number }}
 */
export function boiteDuTrace(d) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  /** @param {number} x @param {number} y */
  const ajoute = (x, y) => {
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  };
  let cx = 0, cy = 0, sx = 0, sy = 0;
  for (const { lettre, nombres: n } of commandes(d)) {
    if (lettre === 'M' || lettre === 'L') {
      for (let i = 0; i + 1 < n.length; i += 2) {
        cx = n[i]; cy = n[i + 1]; ajoute(cx, cy);
        if (lettre === 'M' && i === 0) { sx = cx; sy = cy; }
      }
    } else if (lettre === 'C') {
      for (let i = 0; i + 5 < n.length; i += 6) {
        const [ax, ay, bx, by, ex, ey] = n.slice(i, i + 6);
        ajoute(ex, ey);
        for (const x of extremaCubique(cx, ax, bx, ex)) ajoute(x, cy);
        for (const y of extremaCubique(cy, ay, by, ey)) ajoute(cx, y);
        // Les extrema d'un axe se combinent avec n'importe quelle valeur de l'autre :
        // on n'ajoute que la coordonnée concernée (la boîte reste exacte).
        cx = ex; cy = ey;
      }
    } else if (lettre === 'Z') {
      cx = sx; cy = sy;
    }
  }
  return { x0, y0, x1, y1 };
}

/** @param {number} v */
const arrondi = (v) => Math.round(v * 100) / 100;

/**
 * Dérive UN fichier ; renvoie le texte du SVG dérivé.
 * @param {string} svg
 * @returns {string}
 */
export function deriver(svg) {
  const translate = /<g transform="translate\(([-\d.]+) ([-\d.]+)\)">/.exec(svg);
  const tx = translate ? Number(translate[1]) : 0;
  const ty = translate ? Number(translate[2]) : 0;
  const chemins = [...svg.matchAll(/<path fill="(#[0-9A-Fa-f]{6})" d="([^"]+)"\/>/g)];
  if (!chemins.length) throw new Error('aucun tracé trouvé');
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [, , d] of chemins) {
    const b = boiteDuTrace(d);
    x0 = Math.min(x0, b.x0 + tx); y0 = Math.min(y0, b.y0 + ty); x1 = Math.max(x1, b.x1 + tx); y1 = Math.max(y1, b.y1 + ty);
  }
  // Arrondi VERS L'EXTÉRIEUR au centième : rien n'est rogné.
  const vx = Math.floor(x0 * 100) / 100, vy = Math.floor(y0 * 100) / 100;
  const vw = arrondi(Math.ceil(x1 * 100) / 100 - vx), vh = arrondi(Math.ceil(y1 * 100) / 100 - vy);
  const paths = chemins
    .map(([, fill, d]) => {
      const role = fill.toUpperCase() === ORANGE ? 'arrow' : 'ink';
      return `<path class="logo-${role}" fill="${fill}" style="fill:var(--logo-${role},${fill})" d="${d}"/>`;
    })
    .join('');
  const corps = translate ? `<g transform="translate(${translate[1]} ${translate[2]})">${paths}</g>` : paths;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vx} ${vy} ${vw} ${vh}">${corps}</svg>`;
}

function principal() {
  const verifier = process.argv.includes('--check');
  mkdirSync(SORTIE, { recursive: true });
  const ecarts = [];
  for (const nom of readdirSync(SOURCE).filter((n) => n.endsWith('.svg')).sort()) {
    const derive = deriver(readFileSync(SOURCE + nom, 'utf-8'));
    const cible = SORTIE + nom;
    if (verifier) {
      if (!existsSync(cible) || readFileSync(cible, 'utf-8') !== derive) ecarts.push(nom);
    } else {
      writeFileSync(cible, derive);
    }
  }
  if (ecarts.length) {
    console.error(`Dérivés absents ou périmés : ${ecarts.join(', ')} — relancer node scripts/derive-logo-variants.mjs`);
    process.exit(1);
  }
  console.log(verifier ? 'dérivés à jour' : 'dérivés écrits dans src/brand/derived/');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) principal();
