/**
 * YBW42 — tour design : trois accueils candidats `/_design/a|b|c`.
 *
 * Sur le HTML RENDU : routes privées (noindex, nofollow), hors registre des
 * pages (donc hors sitemap), liées nulle part depuis le site ; même
 * dictionnaire neutre pour les trois ; aucune image hors captures produit ;
 * logo aux tailles minimales (YBW36), slogan jamais dans l'en-tête ; chaque
 * capture porte sa légende dans la langue de la page.
 * Sur les jetons : contrastes CALCULÉS (règles YBW38) pour chaque candidat,
 * chaque schéma rendu (C : clair seulement) et chaque portée locale
 * (`.nuit`, `.aplat`) ; règles propres au candidat C (sarcelle en aplat
 * seulement, jamais sur le bleu nuit ; ambre en grands titres seulement).
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { LEGENDE } from '../src/data/productScreens';
import { toutesLesUrl } from '../src/i18n/pages';
import { fr } from '../src/i18n/pages/design.fr';
import { en } from '../src/i18n/pages/design.en';
import { typoFr } from '../src/lib/typo';
import { CANDIDATS, candidatDeUrl, cheminCandidat, FICHES, type Candidat } from '../src/styles/candidates/candidats';
import { DIST_CLIENT, pagesRendues, type PageRendue } from './builtHtml';

const CANDIDATES = fileURLToPath(new URL('../src/styles/candidates/', import.meta.url));
const ORANGE = '#C8762B';
const BLANC = '#FFFFFF';
const NUIT_C = '#16294A';
const SARCELLE_C = '#2E7D6B';

// ---------------------------------------------------------------- contraste WCAG 2.x
const lin = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const lum = (hex: string) => {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
};
const contraste = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// ---------------------------------------------------------------- lecture des jetons d'un candidat
type Decl = Record<string, string>;
const sansCommentaires = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '');

/** Extrait le corps de `@media (prefers-color-scheme: dark) { … }` (accolades équilibrées). */
function separerSombre(css: string): { base: string; sombre: string } {
  const debut = css.indexOf('@media (prefers-color-scheme: dark)');
  if (debut < 0) return { base: css, sombre: '' };
  const ouvre = css.indexOf('{', debut);
  let n = 0;
  for (let i = ouvre; i < css.length; i++) {
    if (css[i] === '{') n++;
    else if (css[i] === '}' && --n === 0) return { base: css.slice(0, debut) + css.slice(i + 1), sombre: css.slice(ouvre + 1, i) };
  }
  throw new Error('bloc sombre non fermé');
}

/** Blocs `sélecteur { déclarations }` → portée (`racine` ou nom de classe). */
function blocs(css: string): Record<string, Decl> {
  const out: Record<string, Decl> = {};
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const sel = m[1].trim();
    const portee = /^:root\[data-candidat='[a-z]'\]$/.test(sel) ? 'racine' : /^:root\[data-candidat='[a-z]'\]\s+\.([\w-]+)$/.exec(sel)?.[1];
    if (!portee) throw new Error(`sélecteur de jetons inattendu : ${sel}`);
    const decl: Decl = { ...(out[portee] ?? {}) };
    for (const d of m[2].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) decl[d[1]] = d[2].trim();
    out[portee] = decl;
  }
  return out;
}

export interface JetonsCandidat {
  /** Schéma → portée → déclarations résolues (racine fusionnée). */
  schemas: Record<string, Record<string, Decl>>;
  aSombre: boolean;
  source: string;
}

export function lireJetons(source: string, schemasRendus: readonly string[]): JetonsCandidat {
  const { base, sombre } = separerSombre(sansCommentaires(source));
  const clair = blocs(base);
  const nuit = sombre ? blocs(sombre) : {};
  const portees = new Set([...Object.keys(clair), ...Object.keys(nuit)]);
  const schemas: Record<string, Record<string, Decl>> = {};
  for (const schema of schemasRendus) {
    const racine = { ...clair.racine, ...(schema === 'sombre' ? nuit.racine : {}) };
    schemas[schema] = {};
    for (const p of portees) {
      schemas[schema][p] =
        p === 'racine' ? racine : { ...racine, ...(clair[p] ?? {}), ...(schema === 'sombre' ? (nuit[p] ?? {}) : {}) };
    }
  }
  return { schemas, aSombre: sombre !== '', source };
}

/** Résout `var(--x)` en chaîne jusqu'à un hex ; `null` si le jeton n'existe pas. */
export function resoudre(valeur: string | undefined, d: Decl): string | null {
  let v = valeur?.trim();
  for (let i = 0; v && i < 12; i++) {
    const m = /^var\((--[\w-]+)\)$/.exec(v);
    if (!m) break;
    v = d[m[1]];
  }
  return v && /^#[0-9a-f]{6}$/i.test(v) ? v.toUpperCase() : null;
}

type Paire = [premier: string, fond: string, seuil: 4.5 | 3, usage: string];
const PAIRES: Paire[] = [
  ['--texte', '--fond', 4.5, 'texte courant'],
  ['--texte', '--fond-surface', 4.5, 'texte sur surface'],
  ['--texte', '--fond-alt', 4.5, 'texte sur fond alterné'],
  ['--texte-titre', '--fond', 4.5, 'titres'],
  ['--texte-titre', '--fond-alt', 4.5, 'titres sur fond alterné'],
  ['--texte-attenue', '--fond', 4.5, 'texte atténué'],
  ['--texte-attenue', '--fond-surface', 4.5, 'texte atténué sur surface'],
  ['--texte-attenue', '--fond-alt', 4.5, 'texte atténué sur fond alterné'],
  ['--accent-texte', '--fond', 4.5, 'accent texte'],
  ['--accent-texte', '--fond-surface', 4.5, 'accent texte sur surface'],
  ['--bouton-texte', '--bouton-fond', 4.5, 'texte du bouton'],
  ['--bouton-fond', '--fond', 3, 'bouton sur le fond'],
  ['--accent-graphique', '--fond', 3, 'graphique'],
  ['--titre-grand', '--fond', 3, 'grand titre (>= 24 px)'],
  ['--logo-ink', '--fond', 3, 'logo (encre)'],
  ['--logo-arrow', '--fond', 3, 'logo (flèche)'],
  ['--focus', '--fond', 3, 'anneau de focus'],
  ['--ruban-texte', '--ruban-fond', 4.5, 'ruban privé'],
  ['--capture-texte', '--capture-fond', 4.5, 'emplacement de capture'],
  ['--bande-texte', '--bande-fond', 4.5, 'bande finale'],
  ['--bande-attenue', '--bande-fond', 4.5, 'bande finale, texte atténué'],
  ['--bouton-fond', '--bande-fond', 3, 'bouton sur la bande'],
  ['--bande-logo-ink', '--bande-fond', 3, 'logo sur la bande'],
];

/** Violations de contraste de tous les schémas et portées d'un candidat. */
export function violationsJetons(j: JetonsCandidat): string[] {
  const out: string[] = [];
  for (const [schema, portees] of Object.entries(j.schemas)) {
    for (const [portee, d] of Object.entries(portees)) {
      for (const [a, b, seuil, usage] of PAIRES) {
        const x = resoudre(`var(${a})`, d);
        const y = resoudre(`var(${b})`, d);
        if (!x || !y) continue;
        const r = contraste(x, y);
        if (r + 1e-9 < seuil) out.push(`${schema}/${portee} — ${usage} : ${x} sur ${y} = ${r.toFixed(2)}:1 < ${seuil}:1`);
      }
    }
  }
  return out;
}

/** Règles YBW38 sur une feuille de mise en page, évaluées dans le schéma clair (racine). */
export function violationsRegles(feuille: string, d: Decl): string[] {
  const out: string[] = [];
  const px = (v: string): number => {
    const min = /^clamp\(\s*([\d.]+)rem/.exec(v)?.[1] ?? /^([\d.]+)rem$/.exec(v)?.[1];
    if (min) return parseFloat(min) * 16;
    const jeton = /^var\((--[\w-]+)\)$/.exec(v)?.[1];
    return jeton && d[jeton] ? px(d[jeton]) : NaN;
  };
  for (const m of sansCommentaires(feuille).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const decl: Decl = {};
    for (const x of m[2].matchAll(/([\w-]+)\s*:\s*([^;]+);?/g)) decl[x[1]] = x[2].trim();
    if (/#[0-9a-f]{3,8}\b/i.test(m[2])) out.push(`${m[1].trim()} : couleur brute hors jetons`);
    const couleur = decl.color ? resoudre(decl.color, d) : null;
    const fond = decl['background-color'] ? resoudre(decl['background-color'], d) : null;
    if (couleur === ORANGE && !(px(decl['font-size'] ?? '') >= 24)) out.push(`${m[1].trim()} : texte ${ORANGE} sous 24 px`);
    if (couleur === BLANC && fond === ORANGE) out.push(`${m[1].trim()} : blanc sur ${ORANGE}`);
    if (decl.color === 'var(--titre-grand)' && !(px(decl['font-size'] ?? '') >= 24)) out.push(`${m[1].trim()} : ambre sous 24 px`);
  }
  return out;
}

const fichier = (n: string) => readFileSync(CANDIDATES + n, 'utf-8');
/** Échelle typographique du site (tokens.css, :root) — pour lire `font-size: var(--texte-…)`. */
const ECHELLE: Decl = Object.fromEntries(
  [...readFileSync(fileURLToPath(new URL('../src/styles/tokens.css', import.meta.url)), 'utf-8').matchAll(/(--texte-[\w-]+)\s*:\s*([^;]+);/g)].map(
    (m) => [m[1], m[2].trim()],
  ),
);
const JETONS = Object.fromEntries(CANDIDATS.map((c) => [c, lireJetons(fichier(`${c}.tokens.css`), FICHES[c].schemas)])) as Record<
  Candidat,
  JetonsCandidat
>;

// ---------------------------------------------------------------- jetons
describe('YBW42 — jetons des candidats : contrastes calculés (règles YBW38)', () => {
  for (const c of CANDIDATS) {
    it(`candidat ${c} : aucune paire sous son seuil (${FICHES[c].schemas.join(' + ')})`, () => {
      expect(violationsJetons(JETONS[c])).toEqual([]);
    });

    it(`candidat ${c} : feuille de mise en page sans couleur brute ni règle interdite`, () => {
      expect(violationsRegles(fichier(`${c}.css`), { ...ECHELLE, ...JETONS[c].schemas.clair.racine })).toEqual([]);
    });
  }

  it('A et B suivent le système (clair + sombre) ; C est clair SEULEMENT', () => {
    expect(JETONS.a.aSombre && JETONS.b.aSombre).toBe(true);
    expect(JETONS.c.aSombre).toBe(false);
    expect(sansCommentaires(JETONS.c.source)).toMatch(/color-scheme:\s*light;/);
  });

  it('valeurs du plan : encre/orange, #141414/#1B1B1B (B), bleu nuit/sarcelle (C)', () => {
    expect(JETONS.a.schemas.clair.racine['--a-papier']).toBe('#FAF7F2');
    expect(JETONS.b.schemas.clair.racine['--b-nuit']).toBe('#141414');
    expect(JETONS.b.schemas.clair.racine['--b-nuit-2']).toBe('#1B1B1B');
    expect(JETONS.c.schemas.clair.racine['--c-nuit']).toBe(NUIT_C);
    expect(JETONS.c.schemas.clair.racine['--c-sarcelle']).toBe(SARCELLE_C);
    expect(contraste(SARCELLE_C, NUIT_C).toFixed(2)).toBe('2.94');
  });

  it('C : sarcelle en APLAT seulement, jamais dans une portée bleu nuit', () => {
    for (const [portee, d] of Object.entries(JETONS.c.schemas.clair)) {
      const sarcelles = Object.keys(d).filter((k) => k !== '--c-sarcelle' && resoudre(d[k], d) === SARCELLE_C);
      const permis = portee === 'aplat' ? ['--aplat', '--fond', '--fond-surface', '--fond-alt'] : ['--aplat'];
      expect(sarcelles.filter((k) => !permis.includes(k)), portee).toEqual([]);
      if (resoudre(d['--fond'], d) === NUIT_C) expect(sarcelles.filter((k) => k !== '--aplat'), portee).toEqual([]);
    }
    expect(fichier('c.css')).not.toMatch(/--c-sarcelle|--aplat/);
  });

  it('cas négatifs : un gris trop clair, un texte orange < 24 px, du blanc sur orange rougissent', () => {
    const piege = lireJetons(":root[data-candidat='z'] { --fond: #FAF7F2; --texte-attenue: #9A9A9A; }", ['clair']);
    expect(violationsJetons(piege).join('\n')).toMatch(/texte atténué/);
    const d = { '--o': ORANGE, '--b': BLANC };
    expect(violationsRegles('.x { color: var(--o); font-size: 1rem; }', d)).toHaveLength(1);
    expect(violationsRegles('.x { color: var(--o); font-size: clamp(2rem, 1rem + 2vw, 3rem); }', d)).toEqual([]);
    expect(violationsRegles('.x { background-color: var(--o); color: var(--b); }', d)).toEqual(['.x : blanc sur #C8762B']);
    expect(violationsRegles('.x { color: #123456; }', d)).toEqual(['.x : couleur brute hors jetons']);
    expect(violationsRegles('.x { color: var(--titre-grand); font-size: var(--texte-sm); }', { '--texte-sm': '0.9375rem' })).toEqual([
      '.x : ambre sous 24 px',
    ]);
  });
});

// ---------------------------------------------------------------- rendu
const PAGES = pagesRendues();
const candidates = (): { id: Candidat; locale: 'fr' | 'en'; page: PageRendue }[] =>
  CANDIDATS.flatMap((id) =>
    (['fr', 'en'] as const).map((locale) => {
      const page = PAGES.find((p) => p.url === cheminCandidat(id, locale));
      if (!page) throw new Error(`candidat non construit : ${cheminCandidat(id, locale)}`);
      return { id, locale, page };
    }),
  );

/** Toutes les chaînes du dictionnaire neutre (feuilles), telles que rendues. */
function feuilles(d: unknown, locale: 'fr' | 'en'): string[] {
  if (typeof d === 'string') return [locale === 'fr' ? typoFr(d) : d];
  return Object.values(d as Record<string, unknown>).flatMap((v) => feuilles(v, locale));
}

describe('YBW42 — candidats rendus (FR et EN)', () => {
  it('les six pages sont construites (3 candidats × 2 langues)', () => {
    expect(candidates()).toHaveLength(6);
    expect(PAGES.filter((p) => candidatDeUrl(p.url)).map((p) => p.url).sort()).toEqual(
      CANDIDATS.flatMap((c) => [cheminCandidat(c, 'en'), cheminCandidat(c, 'fr')]).sort(),
    );
  });

  for (const { id, locale, page } of candidates()) {
    describe(`${page.url}`, () => {
      const doc = page.document;
      it('privée : noindex, nofollow ; candidat et langue posés', () => {
        expect(doc.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, nofollow');
        expect(doc.documentElement.dataset.candidat).toBe(id);
        expect(doc.documentElement.lang).toBe(locale);
        expect(doc.querySelectorAll('h1')).toHaveLength(1);
        expect(doc.querySelector('link[rel="canonical"]')).toBeNull();
      });

      it('aucune image hors captures produit, aucune image de fond en ligne', () => {
        for (const img of doc.querySelectorAll('img, picture source')) {
          expect(img.closest('figure[data-capture]'), img.outerHTML).not.toBeNull();
        }
        expect(doc.querySelectorAll('[style*="background-image"], [style*="url("]')).toHaveLength(0);
      });

      it('logo : tailles minimales YBW36, slogan jamais dans l’en-tête', () => {
        const minima: Record<string, number> = { nom: 180, slogan: 420, symbole: 16 };
        const logos = [...doc.querySelectorAll<HTMLElement>('[data-logo]')];
        expect(logos.length).toBeGreaterThanOrEqual(2);
        for (const l of logos) {
          const svg = l.querySelector('svg')!;
          const v = l.dataset.logo!;
          const dim = Number(svg.getAttribute(v === 'symbole' ? 'height' : 'width'));
          expect(dim, v).toBeGreaterThanOrEqual(minima[v]);
          if (v === 'slogan') expect(l.closest('header')).toBeNull();
        }
        expect(doc.querySelector('header [data-logo="nom"]')).not.toBeNull();
      });

      it('chaque capture porte sa légende dans la langue de la page', () => {
        const figures = [...doc.querySelectorAll('figure[data-capture]')];
        expect(figures.length).toBeGreaterThan(0);
        for (const f of figures) expect(f.querySelector('figcaption')?.textContent?.trim()).toBe(LEGENDE[locale]);
      });

      it('ancres internes seulement (aucun lien mort vers une page non construite)', () => {
        const ids = new Set([...doc.querySelectorAll('[id]')].map((e) => e.id));
        for (const a of doc.querySelectorAll('a[href]')) {
          const href = a.getAttribute('href')!;
          if (href.startsWith('#')) expect(ids.has(href.slice(1)), href).toBe(true);
          else expect(candidatDeUrl(href), href).not.toBeNull();
        }
      });
    });
  }

  it('C : aucun aplat sarcelle dans (ni autour) d’une diapositive bleu nuit, aucun logo dans un aplat', () => {
    for (const { page } of candidates().filter((x) => x.id === 'c')) {
      expect(page.document.querySelectorAll('.nuit .aplat, .aplat .nuit, .aplat [data-logo]')).toHaveLength(0);
    }
  });

  it('même dictionnaire neutre : les trois candidats rendent les mêmes chaînes, par langue', () => {
    for (const locale of ['fr', 'en'] as const) {
      const attendues = feuilles(locale === 'fr' ? fr : en, locale).filter((s) => !/^(Candidat|Candidate) [ABC]/.test(s));
      const presentes = (id: Candidat) => {
        const doc = candidates().find((x) => x.id === id && x.locale === locale)!.page.document;
        const texte = `${doc.body.textContent ?? ''}\n${doc.title}\n${[...doc.querySelectorAll('[aria-label], meta[content]')]
          .map((e) => e.getAttribute('aria-label') ?? e.getAttribute('content'))
          .join('\n')}`;
        return attendues.filter((s) => texte.includes(s));
      };
      const a = presentes('a');
      expect(presentes('b')).toEqual(a);
      expect(presentes('c')).toEqual(a);
      // Le cœur de l'accueil est présent partout (titre, introduction, produits, sur mesure, société, appel).
      for (const cle of [fr.hero.titre, fr.produits.titre, fr.surMesure.titre, fr.societe.titre, fr.rdv.titre]) {
        if (locale === 'fr') expect(a).toContain(typoFr(cle));
      }
    }
  });
});

describe('YBW42 — routes privées : hors sitemap, liées nulle part', () => {
  it('aucune route /_design dans le registre des pages (source du sitemap, YBW75)', () => {
    expect(toutesLesUrl().filter((u) => u.includes('_design'))).toEqual([]);
  });

  it('aucun sitemap construit ne cite /_design', () => {
    const sitemaps = existsSync(DIST_CLIENT) ? readdirSync(DIST_CLIENT).filter((n) => /^sitemap.*\.xml$/.test(n)) : [];
    for (const s of sitemaps) expect(readFileSync(DIST_CLIENT + s, 'utf-8')).not.toContain('_design');
  });

  for (const p of PAGES.filter((x) => !candidatDeUrl(x.url))) {
    it(`${p.url} : aucun lien vers /_design`, () => {
      expect(p.html).not.toContain('/_design');
    });
  }
});
