/**
 * Tour design (YBW42) — registre des TROIS accueils candidats, routes privées
 * `/_design/a|b|c` (FR) et `/_design/a|b|c/en/` (EN).
 *
 * Routes PRIVÉES : `noindex, nofollow`, hors registre `pages.ts` (donc hors
 * sitemap, YBW75), liées nulle part depuis le site (testé sur le rendu,
 * tests/designCandidates.test.ts). Injectées par `astro.config.mjs` tant que
 * leur fichier existe ; YBW44 supprime les routes et les feuilles non retenues.
 *
 * Même dictionnaire NEUTRE pour les trois (`i18n/pages/design.*.ts`) : seuls
 * les jetons (`<id>.tokens.css`) et la mise en page (`<id>.css` + gabarit)
 * diffèrent.
 */
import type { Locale } from '../../i18n/config';
import { t } from '../../i18n/utils';
import { typoFr } from '../../lib/typo';
import { fr } from '../../i18n/pages/design.fr';
import { en } from '../../i18n/pages/design.en';

export const CANDIDATS = ['a', 'b', 'c'] as const;
export type Candidat = (typeof CANDIDATS)[number];

export interface FicheCandidat {
  id: Candidat;
  /** Schémas rendus : A et B suivent le système (clair + sombre), C est clair seulement. */
  schemas: readonly ('clair' | 'sombre')[];
  /** Les 2 fichiers de police critiques préchargés (versionnés, public/fonts/). */
  polices: readonly [string, string];
}

export const FICHES: Record<Candidat, FicheCandidat> = {
  a: {
    id: 'a',
    schemas: ['clair', 'sombre'],
    polices: ['/fonts/outfit-latin-wght-5.3.0.woff2', '/fonts/instrument-sans-latin-wght-5.3.0.woff2'],
  },
  b: {
    id: 'b',
    schemas: ['clair', 'sombre'],
    polices: ['/fonts/urbanist-latin-wght-5.3.0.woff2', '/fonts/geist-latin-wght-5.3.0.woff2'],
  },
  c: {
    id: 'c',
    schemas: ['clair'],
    polices: ['/fonts/fraunces-latin-wght-5.3.0.woff2', '/fonts/plus-jakarta-sans-latin-wght-5.3.0.woff2'],
  },
};

/** Chemin d'un candidat dans une langue (forme canonique, barre finale). */
export function cheminCandidat(id: Candidat, locale: Locale): string {
  return locale === 'en' ? `/_design/${id}/en/` : `/_design/${id}/`;
}

/** Candidat d'une URL rendue (`/_design/b/en/` → `b`), sinon `null`. */
export function candidatDeUrl(url: string): Candidat | null {
  const m = /^\/_design\/([abc])\/(?:en\/)?$/.exec(url);
  return m ? (m[1] as Candidat) : null;
}

/** `getStaticPaths` commun : la route FR (`[...langue]` vide) et la route EN. */
export function cheminsStatiques() {
  return [
    { params: { langue: undefined }, props: { locale: 'fr' as Locale } },
    { params: { langue: 'en' }, props: { locale: 'en' as Locale } },
  ];
}

/**
 * Lecteur du dictionnaire neutre dans une langue — sans repli (`t` lève sur
 * une clé absente) ; typographie française appliquée au français.
 */
export function textes(locale: Locale): (cle: string) => string {
  const dict = locale === 'en' ? en : fr;
  return (cle) => (locale === 'fr' ? typoFr(t(dict, cle, locale)) : t(dict, cle, locale));
}
