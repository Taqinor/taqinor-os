/**
 * ACAL99 — RÉPARTITION DE LA CIBLE VENDUE À LA RÉOUVERTURE (C-ACAL-108, ANON-03, ATL-12).
 *
 * Un calepinage lié à un devis de 12 panneaux, enregistré à 8, se rouvrait à 12 : le boot
 * ré-imposait la cible du devis au pan actif et écrasait la conception ENREGISTRÉE ; sur un
 * site à deux pans (20/20, cible 40) il imposait même le TOTAL (40) au seul pan actif.
 *
 * Règles (PURES) :
 *  - un document dont des pans portent une pose ENREGISTRÉE garde ses objectifs par pan
 *    (l'écart « posés / au devis » se lit au niveau du site ; le devis ne bouge qu'à
 *    « Resynchroniser ») ;
 *  - plusieurs pans : jamais le total au pan actif — chacun garde son objectif ;
 *  - un pan unique sans compte enregistré : la cible vendue lui est imposée (comportement
 *    d'aujourd'hui).
 */

/** Un pan, vu de la répartition. */
export interface PanCible {
  id: string;
  neededPanels: number;
  neededAuto: boolean;
  /** La pose enregistrée du pan (`zones[].geometry`), si le document en porte une. */
  geometrieEnregistree?: { count?: number } | null;
}

/** Ce que la répartition décide : `imposer` = la cible va au pan actif (cas d'aujourd'hui) ;
 *  `objectifs` = l'objectif GARDÉ de chaque pan. */
export type RepartitionCible =
  | { mode: 'imposer'; cible: number }
  | { mode: 'conserver'; objectifs: Record<string, number> };

/** Le compte ENREGISTRÉ d'un pan : son objectif choisi, sinon le nombre de modules posés. */
function compteEnregistre(pan: PanCible): number | null {
  if (!pan.neededAuto && Number.isFinite(pan.neededPanels) && pan.neededPanels > 0) return Math.round(pan.neededPanels);
  const n = pan.geometrieEnregistree?.count;
  return typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.round(n) : null;
}

export function repartirCibleVendue(entree: {
  cibleVendue: number;
  zones: readonly PanCible[];
  activeAreaId: string | null;
}): RepartitionCible {
  const { cibleVendue, zones } = entree;
  const poses = zones.some((z) => (z.geometrieEnregistree?.count ?? 0) > 0);
  if (zones.length > 1 || poses) {
    const objectifs: Record<string, number> = {};
    for (const z of zones) {
      const n = compteEnregistre(z);
      if (n != null) objectifs[z.id] = n;
    }
    if (Object.keys(objectifs).length) return { mode: 'conserver', objectifs };
    // Plusieurs pans sans AUCUN compte : on n'impose toujours pas le total au pan actif —
    // chaque pan reste piloté par son propre besoin (aucun objectif inventé).
    if (zones.length > 1) return { mode: 'conserver', objectifs: {} };
  }
  return { mode: 'imposer', cible: cibleVendue };
}
