// ODY34 — Le GLYPHE D'APP d'un module, déclaré une fois, au même endroit.
// ----------------------------------------------------------------------------
// Constat (fondateur, 2026-08-02, capture du portail à l'appui) : 43 des 44
// module.config ne déclaraient PAS d'icône d'app. `useInstalledApps()` et
// `iconNodeForApp()` retombaient donc sur `nav.items[0].icon` — l'icône du
// PREMIER ÉCRAN du module, pas de l'app. Résultat à l'écran : une dizaine de
// collisions (cinq apps portaient le carré 2×2 de `LayoutDashboard` parce que
// leur premier écran est un cockpit ; Flotte et Logistique le même camion ;
// QHSE et Conformité le même bouclier ; Workflow et Chantiers le même
// calendrier-horloge…). Un portail où cinq tuiles portent le même dessin ne se
// lit plus.
//
// Le CONTRAT existait déjà — `nav.icon` (APX1), prioritaire sur
// `nav.items[0].icon` dans les DEUX résolveurs (`useInstalledApps.js:142` et
// `lib/apps/appIcon.js:31`) : seul le CRM le remplissait. Cette passe le
// remplit pour les 42 apps, avec un glyphe métier UNIQUE par module
// (`lib/apps/appGlyph.test.jsx` interdit tout doublon).
//
// Ce module n'existe que pour que ces 42 déclarations soient rigoureusement
// IDENTIQUES : mêmes props, une seule ligne à changer si le kit bouge. Il
// n'importe QUE `react` — surtout pas `lib/apps/appIcon.js` ni
// `router/moduleRoutes`, ce qui refermerait le cycle
// module.config → … → module.config.
import { createElement } from 'react'

/* Props du kit de nav (UX1) : la taille et l'épaisseur sont de toute façon
   réécrites par `.app-icon-glyph > svg` (index.css) sur les quatre surfaces
   ODY9 — elles servent aux rendus HORS tuile (repli, tests). */
export const APP_GLYPH_PROPS = { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' }

/**
 * appGlyph — nœud d'icône d'app à poser dans `nav.icon` d'un `module.config`.
 * `createElement` plutôt que du JSX : un fichier de config n'est pas un module
 * de composants (cf. l'en-tête `react-refresh/only-export-components` de
 * chaque config).
 *
 * @param {import('react').ElementType} Composant  icône lucide (ex. `Calculator`)
 */
export function appGlyph(Composant) {
  return createElement(Composant, APP_GLYPH_PROPS)
}

export default appGlyph
