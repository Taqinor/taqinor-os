/**
 * ENF19 — légendes de la galerie « chantiers » de l'accueil (fr/en/ar) : ville, puissance et
 * production viennent TOUJOURS de lib/realisations (jamais saisies à la main). `cityName` /
 * `prodLabel` ne servent qu'à traduire l'affichage (ville arabe, unité « /an »).
 * (2026-09) `kwc` peut être vide (chantier filmé avant tout relevé de puissance, ex. Bouskoura) :
 * jointures filtrées plutôt qu'un séparateur qui pend sur rien.
 */
import { realisationBySlug } from './realisations';

export function buildGallery<T extends { slug: string; showProd: boolean }>(
  galleryRaw: T[],
  opts: { cityName?: (ville: string) => string; prodLabel?: (production: string) => string } = {},
) {
  const { cityName = (v: string) => v, prodLabel = (p: string) => p } = opts;
  return galleryRaw.map((g) => {
    const r = realisationBySlug(g.slug);
    const ville = cityName(r?.ville ?? '');
    const kwc = r?.kwc ?? '';
    const prod = g.showProd && r?.production != null ? prodLabel(r.production) : null;
    return {
      ...g,
      ville,
      kwc,
      prod,
      caption: [ville, kwc, prod].filter(Boolean).join(' · '),
      ariaLabel: [ville, kwc, prod].filter(Boolean).join(', '),
    };
  });
}
