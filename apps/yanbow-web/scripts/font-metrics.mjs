/**
 * Lecture des métriques d'une police (YBW39) — WOFF2 (Brotli, zlib de Node) ou
 * TTF/OTF, sans dépendance. Sert au repli métrique (`size-adjust`,
 * `ascent-override`, `descent-override`, `line-gap-override`) qui évite le
 * décalage de mise en page (CLS) pendant le chargement de la police.
 *
 * Tables lues : head (unitsPerEm), hhea (ascender, descender, lineGap),
 * OS/2 (xAvgCharWidth) — aucune n'est transformée par WOFF2.
 */
import { brotliDecompressSync } from 'node:zlib';

const TAGS_CONNUS = ['cmap', 'head', 'hhea', 'hmtx', 'maxp', 'name', 'OS/2', 'post', 'cvt ', 'fpgm', 'glyf', 'loca', 'prep', 'CFF ', 'VORG', 'EBDT', 'EBLC', 'gasp', 'hdmx', 'kern', 'LTSH', 'PCLT', 'VDMX', 'vhea', 'vmtx', 'BASE', 'GDEF', 'GPOS', 'GSUB', 'EBSC', 'JSTF', 'MATH', 'CBDT', 'CBLC', 'COLR', 'CPAL', 'SVG ', 'sbix', 'acnt', 'avar', 'bdat', 'bloc', 'bsln', 'cvar', 'fdsc', 'feat', 'fmtx', 'fvar', 'gvar', 'hsty', 'just', 'lcar', 'mort', 'morx', 'opbd', 'prop', 'trak', 'Zapf', 'Silf', 'Glat', 'Gloc', 'Feat', 'Sill'];

/**
 * @param {Buffer} buf
 * @param {number} pos
 * @returns {[number, number]} valeur, position suivante
 */
function base128(buf, pos) {
  let v = 0;
  for (let i = 0; i < 5; i++) {
    const o = buf[pos++];
    v = v * 128 + (o & 0x7f);
    if (!(o & 0x80)) return [v, pos];
  }
  throw new Error('UIntBase128 invalide');
}

/**
 * Tables utiles d'un WOFF2.
 * @param {Buffer} buf
 * @returns {Record<string, Buffer>}
 */
function tablesWoff2(buf) {
  if (buf.toString('ascii', 0, 4) !== 'wOF2') throw new Error('pas un WOFF2');
  const n = buf.readUInt16BE(12);
  const tailleCompressee = buf.readUInt32BE(20);
  let pos = 48;
  /** @type {{ tag: string, longueur: number }[]} */
  const entrees = [];
  for (let i = 0; i < n; i++) {
    const drapeaux = buf[pos++];
    let tag = TAGS_CONNUS[drapeaux & 0x3f];
    if ((drapeaux & 0x3f) === 63) {
      tag = buf.toString('ascii', pos, pos + 4);
      pos += 4;
    }
    let origine;
    [origine, pos] = base128(buf, pos);
    const version = (drapeaux >> 6) & 3;
    const transforme = tag === 'glyf' || tag === 'loca' ? version === 0 : version !== 0;
    let longueur = origine;
    if (transforme) [longueur, pos] = base128(buf, pos);
    entrees.push({ tag, longueur });
  }
  const flux = brotliDecompressSync(buf.subarray(pos, pos + tailleCompressee));
  /** @type {Record<string, Buffer>} */
  const tables = {};
  let o = 0;
  for (const e of entrees) {
    tables[e.tag] = flux.subarray(o, o + e.longueur);
    o += e.longueur;
  }
  return tables;
}

/**
 * Tables d'un TTF/OTF.
 * @param {Buffer} buf
 * @returns {Record<string, Buffer>}
 */
function tablesSfnt(buf) {
  const n = buf.readUInt16BE(4);
  /** @type {Record<string, Buffer>} */
  const tables = {};
  for (let i = 0; i < n; i++) {
    const o = 12 + i * 16;
    const tag = buf.toString('ascii', o, o + 4);
    const debut = buf.readUInt32BE(o + 8);
    tables[tag] = buf.subarray(debut, debut + buf.readUInt32BE(o + 12));
  }
  return tables;
}

/** Caractères dont on moyenne l'avance (minuscules latines + espace, poids égaux). */
export const ECHANTILLON = 'abcdefghijklmnopqrstuvwxyz ';

/**
 * Glyphe d'un point de code (cmap format 4, plan multilingue de base).
 * @param {Buffer} cmap
 * @param {number} code
 */
function glyphe(cmap, code) {
  const n = cmap.readUInt16BE(2);
  for (let i = 0; i < n; i++) {
    const plateforme = cmap.readUInt16BE(4 + i * 8);
    const encodage = cmap.readUInt16BE(6 + i * 8);
    const o = cmap.readUInt32BE(8 + i * 8);
    if (!((plateforme === 3 && encodage === 1) || plateforme === 0) || cmap.readUInt16BE(o) !== 4) continue;
    const segX2 = cmap.readUInt16BE(o + 6);
    const fins = o + 14;
    const debuts = fins + segX2 + 2;
    const deltas = debuts + segX2;
    const decalages = deltas + segX2;
    for (let s = 0; s < segX2 / 2; s++) {
      if (cmap.readUInt16BE(fins + 2 * s) < code) continue;
      const debut = cmap.readUInt16BE(debuts + 2 * s);
      if (debut > code) return 0;
      const delta = cmap.readInt16BE(deltas + 2 * s);
      const ro = cmap.readUInt16BE(decalages + 2 * s);
      if (ro === 0) return (code + delta) & 0xffff;
      const g = cmap.readUInt16BE(decalages + 2 * s + ro + 2 * (code - debut));
      return g === 0 ? 0 : (g + delta) & 0xffff;
    }
  }
  return 0;
}

/**
 * @typedef {{ unitsPerEm: number, ascender: number, descender: number, lineGap: number, avanceMoyenne: number }} Metriques
 */

/**
 * @param {Buffer} buf police WOFF2 ou TTF/OTF
 * @returns {Metriques}
 */
export function metriques(buf) {
  const t = buf.toString('ascii', 0, 4) === 'wOF2' ? tablesWoff2(buf) : tablesSfnt(buf);
  for (const tag of ['head', 'hhea', 'cmap', 'hmtx']) if (!t[tag]) throw new Error(`table ${tag} absente`);
  const nbMetriques = t.hhea.readUInt16BE(34);
  const avance = (/** @type {number} */ g) => t.hmtx.readUInt16BE(4 * Math.min(g, nbMetriques - 1));
  const avances = [...ECHANTILLON].map((c) => {
    const g = glyphe(t.cmap, c.codePointAt(0) ?? 0);
    if (!g) throw new Error(`glyphe absent : « ${c} »`);
    return avance(g);
  });
  return {
    unitsPerEm: t.head.readUInt16BE(18),
    ascender: t.hhea.readInt16BE(4),
    descender: t.hhea.readInt16BE(6),
    lineGap: t.hhea.readInt16BE(8),
    avanceMoyenne: avances.reduce((a, b) => a + b, 0) / avances.length,
  };
}

/**
 * Métriques d'Arial, police de repli : lues dans `C:\Windows\Fonts\arial.ttf`
 * (Windows 11, 07/10/2026) avec `metriques()` ci-dessus — figées ici pour que
 * le calcul soit reproductible sur la CI Linux (où Arial n'est pas installée).
 * @type {Metriques}
 */
export const ARIAL = { unitsPerEm: 2048, ascender: 1854, descender: -434, lineGap: 67, avanceMoyenne: 26636 / 27 };

const pct = (/** @type {number} */ v) => `${(Math.round(v * 10000) / 100).toFixed(2)}%`;

/**
 * Surcharges du repli métrique : le repli Arial est mis à l'échelle de
 * l'avance moyenne (minuscules + espace), puis ses hauteurs sont recalées sur
 * celles de la police (formule des outils de référence, ex. next/font).
 * @param {Metriques} m
 * @param {Metriques} [repli]
 */
export function surcharges(m, repli = ARIAL) {
  const taille = m.avanceMoyenne / m.unitsPerEm / (repli.avanceMoyenne / repli.unitsPerEm);
  return {
    sizeAdjust: pct(taille),
    ascentOverride: pct(m.ascender / m.unitsPerEm / taille),
    descentOverride: pct(Math.abs(m.descender) / m.unitsPerEm / taille),
    lineGapOverride: pct(m.lineGap / m.unitsPerEm / taille),
  };
}
