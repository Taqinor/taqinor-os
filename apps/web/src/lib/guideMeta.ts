/**
 * WB12 — shared per-slug "verified on" date for the /guides guides.
 *
 * Before this file, all 12 guide pages + guides/index.astro each hardcoded
 * their own `const verifiedDate = new Date('2026-07-03')` — one global
 * literal duplicated 13x, so no single guide's review date could actually
 * diverge from the others. This map is now the single source of truth: each
 * guide's slug (its folder-relative filename, without the .astro extension)
 * maps to its own verified date, independently editable.
 *
 * Slugs match the file name under apps/web/src/pages/guides/*.astro.
 */
import { NAP } from './nap';

export const GUIDE_VERIFIED_DATES: Record<string, Date> = {
  'batterie-lithium-ou-gel': new Date('2026-07-03'),
  'combien-de-panneaux-pour-ma-maison': new Date('2026-07-03'),
  'electricite-pendant-les-coupures': new Date('2026-07-03'),
  'entretien-et-duree-de-vie-des-panneaux': new Date('2026-07-03'),
  'faut-il-des-batteries': new Date('2026-07-03'),
  'loi-82-21-expliquee': new Date('2026-10-05'),
  'mon-toit-peut-il-supporter-des-panneaux': new Date('2026-07-03'),
  'monocristallin-ou-polycristallin': new Date('2026-07-03'),
  'on-grid-off-grid-ou-hybride': new Date('2026-07-03'),
  'onduleur-hybride-ou-reseau': new Date('2026-07-03'),
  'orientation-inclinaison-ombrage': new Date('2026-07-03'),
  'quelle-taille-de-batterie': new Date('2026-07-03'),
};

export function getGuideVerifiedDate(slug: string): Date {
  const d = GUIDE_VERIFIED_DATES[slug];
  // WAUD50 — jamais de date de repli : un slug absent de la carte est une erreur de build.
  if (!d) throw new Error(`guideMeta: pas de date « vérifié le » pour ${slug}`);
  return d;
}

/** WAUD50 — dateModified JSON-LD = la date « Vérifié le » affichée (AAAA-MM-JJ). */
export function guideDateModified(slug: string): string {
  return getGuideVerifiedDate(slug).toISOString().slice(0, 10);
}

/** WAUD50 — champs Article communs aux guides traduits : auteur, éditeur, page. */
export function guideArticleCommun(url: string) {
  const organisation = { '@type': 'Organization', name: NAP.name, url: NAP.url };
  return { author: organisation, publisher: organisation, mainEntityOfPage: url };
}
