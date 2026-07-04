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
export const GUIDE_VERIFIED_DATES: Record<string, Date> = {
  'batterie-lithium-ou-gel': new Date('2026-07-03'),
  'combien-de-panneaux-pour-ma-maison': new Date('2026-07-03'),
  'electricite-pendant-les-coupures': new Date('2026-07-03'),
  'entretien-et-duree-de-vie-des-panneaux': new Date('2026-07-03'),
  'faut-il-des-batteries': new Date('2026-07-03'),
  'loi-82-21-expliquee': new Date('2026-07-03'),
  'mon-toit-peut-il-supporter-des-panneaux': new Date('2026-07-03'),
  'monocristallin-ou-polycristallin': new Date('2026-07-03'),
  'on-grid-off-grid-ou-hybride': new Date('2026-07-03'),
  'onduleur-hybride-ou-reseau': new Date('2026-07-03'),
  'orientation-inclinaison-ombrage': new Date('2026-07-03'),
  'quelle-taille-de-batterie': new Date('2026-07-03'),
};

/** Fallback used only if a slug is somehow missing from the map above. */
const DEFAULT_VERIFIED_DATE = new Date('2026-07-03');

export function getGuideVerifiedDate(slug: string): Date {
  return GUIDE_VERIFIED_DATES[slug] ?? DEFAULT_VERIFIED_DATE;
}
