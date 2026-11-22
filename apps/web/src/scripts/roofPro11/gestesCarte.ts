/**
 * ACAL952 — gestes de la carte de l'atelier au toucher.
 *
 * Au toucher, un doigt fait défiler la page et deux doigts déplacent la carte
 * (`cooperativeGestures`), avec le message de MapLibre en français. Pendant un
 * tracé ou un glissé de sommet / d'obstacle, le doigt appartient au geste :
 * l'événement DOM est annulé pour que la page ne défile pas.
 */

/** Libellés MapLibre du mode coopératif : clés relues dans maplibre-gl 6.12.0
 *  (`CooperativeGesturesHandler.*HelpText`). */
const LIBELLES_COOPERATIFS = {
  'CooperativeGesturesHandler.WindowsHelpText': 'Ctrl + molette pour zoomer la carte',
  'CooperativeGesturesHandler.MacHelpText': '⌘ + molette pour zoomer la carte',
  'CooperativeGesturesHandler.MobileHelpText': 'Utilisez deux doigts pour déplacer la carte',
};

/** Options de carte : gestes coopératifs sur pointeur tactile seulement. */
export function optionsGestesCarte(fenetre: {
  matchMedia?: (requete: string) => { matches: boolean };
}): { cooperativeGestures: boolean; locale?: Record<string, string> } {
  const tactile = Boolean(fenetre.matchMedia?.('(pointer: coarse)').matches);
  return tactile
    ? { cooperativeGestures: true, locale: LIBELLES_COOPERATIFS }
    : { cooperativeGestures: false };
}

/**
 * Annule le défilement de la page (événement DOM) quand un geste est actif ; garde
 * aussi l'annulation côté carte (le doigt ne déplace pas la carte pendant le geste).
 */
export function geleDefilementPendantGeste(
  e: { preventDefault?: () => void; originalEvent?: { preventDefault?: () => void } | null },
  actif: boolean,
): void {
  if (!actif) return;
  e.preventDefault?.();
  e.originalEvent?.preventDefault?.();
}
