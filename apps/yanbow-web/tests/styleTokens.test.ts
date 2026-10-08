/**
 * YBW38 — jetons provisoires + garde de contraste WCAG CALCULÉE.
 * Texte normal < 4,5:1 = rouge ; graphique / grand texte (>= 24 px) < 3:1 = rouge.
 * Interdits : texte #C8762B < 24 px sur fond clair ; texte blanc sur #C8762B ;
 * tout hex brut hors tokens.css (le pack logo src/brand/ excepté).
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const SRC = fileURLToPath(new URL('../src/', import.meta.url));
const TOKENS = readFileSync(SRC + 'styles/tokens.css', 'utf-8');
const GLOBAL = readFileSync(SRC + 'styles/global.css', 'utf-8');
const ORANGE = '#C8762B';
const BLANC = '#FFFFFF';

// ---------------------------------------------------------------- contraste WCAG
const lin = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const lum = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
};
export const contraste = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// ---------------------------------------------------------------- lecture des jetons
const sansCommentaires = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '');
function declarations(bloc: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of bloc.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
const css = sansCommentaires(TOKENS);
const racineClaire = declarations(/^:root\s*\{([\s\S]*?)\n\}/m.exec(css)![1]);
const racineSombre = { ...racineClaire, ...declarations(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/.exec(css)![1]) };
export type Schema = Record<string, string>;
export const SCHEMAS: Record<'clair' | 'sombre', Schema> = { clair: racineClaire, sombre: racineSombre };

/** Résout une valeur (var(--x) en chaîne) jusqu'à un hex ou une longueur. */
export function resoudre(valeur: string, schema: Schema): string {
  let v = valeur.trim();
  for (let i = 0; i < 10; i++) {
    const m = /^var\((--[\w-]+)\)$/.exec(v);
    if (!m) break;
    if (!(m[1] in schema)) throw new Error(`jeton inconnu ${m[1]}`);
    v = schema[m[1]];
  }
  return v.toUpperCase().startsWith('#') ? v.toUpperCase() : v;
}
const px = (v: string) => (v.endsWith('rem') ? parseFloat(v) * 16 : v.endsWith('px') ? parseFloat(v) : NaN);

// ---------------------------------------------------------------- paires d'usage
type Paire = { premier: string; fond: string; seuil: 4.5 | 3; usage: string };
const PAIRES: Paire[] = [
  { premier: '--texte', fond: '--fond', seuil: 4.5, usage: 'texte courant' },
  { premier: '--texte', fond: '--fond-surface', seuil: 4.5, usage: 'texte sur surface (dont <option>)' },
  { premier: '--texte-attenue', fond: '--fond', seuil: 4.5, usage: 'texte atténué' },
  { premier: '--texte-attenue', fond: '--fond-surface', seuil: 4.5, usage: 'texte atténué sur surface' },
  { premier: '--accent-texte', fond: '--fond', seuil: 4.5, usage: 'liens / accent texte' },
  { premier: '--accent-texte', fond: '--fond-surface', seuil: 4.5, usage: 'accent texte sur surface' },
  { premier: '--bouton-texte', fond: '--bouton-fond', seuil: 4.5, usage: 'bouton' },
  { premier: '--accent-graphique', fond: '--fond', seuil: 3, usage: 'graphique / titre >= 24 px' },
  { premier: '--logo-arrow', fond: '--fond', seuil: 3, usage: 'flèche du logo' },
  { premier: '--logo-ink', fond: '--fond', seuil: 3, usage: 'logo' },
];

/** Violations de contraste d'un schéma. */
export function violationsContraste(schema: Schema, paires: Paire[] = PAIRES): string[] {
  return paires.flatMap((p) => {
    const a = resoudre(`var(${p.premier})`, schema);
    const b = resoudre(`var(${p.fond})`, schema);
    const r = contraste(a, b);
    return r + 1e-9 < p.seuil ? [`${p.usage} : ${a} sur ${b} = ${r.toFixed(2)}:1 < ${p.seuil}:1`] : [];
  });
}

/** Règles CSS interdites (évaluées dans le schéma clair). */
export function violationsRegles(feuille: string, schema: Schema = SCHEMAS.clair): string[] {
  const out: string[] = [];
  for (const m of sansCommentaires(feuille).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selecteur = m[1].trim();
    const decl: Record<string, string> = {};
    for (const d of m[2].matchAll(/([\w-]+)\s*:\s*([^;]+);?/g)) decl[d[1]] = d[2].trim();
    const couleur = decl.color ? resoudre(decl.color, schema) : null;
    const fond = decl['background-color'] ?? decl.background;
    const fondResolu = fond ? resoudre(fond, schema) : null;
    if (couleur === ORANGE) {
      const taille = decl['font-size'] ? px(resoudre(decl['font-size'], schema)) : NaN;
      if (!(taille >= 24)) out.push(`${selecteur} : texte ${ORANGE} sous 24 px`);
    }
    if (couleur === BLANC && fondResolu === ORANGE) out.push(`${selecteur} : blanc sur ${ORANGE}`);
  }
  return out;
}

function fichiers(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? fichiers(p) : [p];
  });
}
/** Fichiers de src/ (hors tokens.css et pack logo) contenant un hex brut. */
export function hexBruts(entrees: { rel: string; contenu: string }[]): string[] {
  return entrees
    .filter((f) => f.rel !== 'styles/tokens.css' && !f.rel.startsWith('brand/') && /\.(css|astro|ts|tsx|mjs|js)$/.test(f.rel))
    .filter((f) => /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?\b/.test(f.contenu))
    .map((f) => f.rel);
}

describe('YBW38 — valeurs connues', () => {
  it('#A6591A sur blanc = 5,17:1 ; encre sur #C8762B = 4,99:1', () => {
    expect(contraste('#A6591A', '#FFFFFF').toFixed(2)).toBe('5.17');
    expect(contraste('#1B1B1B', ORANGE).toFixed(2)).toBe('4.99');
    expect(contraste(ORANGE, '#FFFFFF').toFixed(2)).toBe('3.45');
  });

  it('palette du plan', () => {
    expect(racineClaire['--couleur-encre']).toBe('#1B1B1B');
    expect(racineClaire['--couleur-orange']).toBe(ORANGE);
    expect(racineClaire['--couleur-orange-texte']).toBe('#A6591A');
    expect(racineClaire['--couleur-papier']).toBe('#FAF7F2');
    expect(racineClaire['--couleur-gris-texte']).toBe('#6B6B6B');
    expect(racineClaire['--couleur-gris-sur-sombre']).toBe('#A3A3A3');
  });
});

describe('YBW38 — contrastes calculés, chaque schéma', () => {
  for (const [nom, schema] of Object.entries(SCHEMAS)) {
    it(`schéma ${nom} : aucune paire sous son seuil`, () => expect(violationsContraste(schema)).toEqual([]));
  }

  it('cas négatif : un gris trop clair planté rougit', () => {
    const piege = { ...SCHEMAS.clair, '--texte-attenue': '#8A8A8A' };
    expect(violationsContraste(piege).join('\n')).toMatch(/texte atténué/);
  });

  it('cas négatif : un texte orange #C8762B planté comme accent texte rougit', () => {
    const piege = { ...SCHEMAS.clair, '--accent-texte': 'var(--couleur-orange)' };
    expect(violationsContraste(piege).join('\n')).toMatch(/liens/);
  });
});

describe('YBW38 — règles interdites (feuilles réelles + pièges plantés)', () => {
  it('global.css : aucune violation', () => expect(violationsRegles(GLOBAL)).toEqual([]));

  it('piège : texte #C8762B à 16 px sur clair', () => {
    expect(violationsRegles('.x { color: var(--couleur-orange); font-size: 1rem; }')).toEqual(['.x : texte #C8762B sous 24 px']);
    expect(violationsRegles('.x { color: var(--couleur-orange); }')).toHaveLength(1);
    expect(violationsRegles('.x { color: var(--couleur-orange); font-size: var(--texte-xl); }')).toEqual([]);
  });

  it('piège : blanc sur #C8762B', () => {
    expect(violationsRegles('.b { background-color: var(--couleur-orange); color: var(--couleur-blanc); }')).toEqual(['.b : blanc sur #C8762B']);
  });

  it('<option> stylé : fond et texte depuis les jetons (vaut pour les deux schémas)', () => {
    const regles = [...sansCommentaires(GLOBAL).matchAll(/([^{}]+)\{([^{}]*)\}/g)];
    const corps = regles.find((r) => r[1].split(',').some((s) => s.trim() === 'option'))?.[2] ?? '';
    expect(corps).toMatch(/background-color:\s*var\(--fond-surface\)/);
    expect(corps).toMatch(/color:\s*var\(--texte\)/);
  });
});

describe('YBW38 — aucun hex brut hors tokens.css', () => {
  it('src/ (pack logo excepté)', () => {
    const entrees = fichiers(SRC).map((p) => ({ rel: relative(SRC, p).split(sep).join('/'), contenu: readFileSync(p, 'utf-8') }));
    expect(hexBruts(entrees)).toEqual([]);
  });

  it('cas négatif : un hex planté dans un composant est détecté', () => {
    expect(hexBruts([{ rel: 'components/X.astro', contenu: '<style>.x{color:#C8762B}</style>' }])).toEqual(['components/X.astro']);
    expect(hexBruts([{ rel: 'styles/tokens.css', contenu: '--a:#fff;' }])).toEqual([]);
  });
});
