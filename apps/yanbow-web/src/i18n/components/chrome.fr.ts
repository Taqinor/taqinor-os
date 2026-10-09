/**
 * Gabarit commun (YBW60) — en-tête, navigation, pied de page, emplacement de
 * capture. Textes d'interface seulement (aucune affirmation : celles-ci
 * viennent du registre `src/lib/claims.ts`). Les noms de produits viennent de
 * `src/lib/brand.ts`.
 */
export const fr = {
  evitement: 'Aller au contenu',
  accueil: 'YanBow, accueil',
  nav: {
    aria: 'Navigation principale',
    ariaMobile: 'Navigation',
    menu: 'Menu',
    surMesure: 'Sur-mesure',
    societe: 'Société',
    rdv: 'Prendre rendez-vous',
  },
  pied: {
    aria: 'Pied de page',
    nav: 'Plan du site',
  },
  capture: {
    attente: 'Capture d’écran en préparation',
    note: 'Vrai écran du logiciel, société fictive, recadré sur la zone utile.',
  },
} as const;
