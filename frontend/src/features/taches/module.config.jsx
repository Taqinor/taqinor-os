import { createElement } from 'react'
import { Navigate } from 'react-router-dom'
import { Calendar, Folder, Inbox, ListTodo, Sun } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'
import Aujourdhui from './ecrans/Aujourdhui'
import ATrier from './ecrans/ATrier'
import Projets from './ecrans/Projets'
import Projet from './ecrans/Projet'
import ProjetsArchive from './ecrans/ProjetsArchive'
import ProjetsModeles from './ecrans/ProjetsModeles'
import Agenda from './ecrans/Agenda'
import Revue from './ecrans/Revue'
import Rythme from './ecrans/Rythme'
import Recherche from './ecrans/Recherche'
import Supprimees from './ecrans/Supprimees'
import Reglages from './ecrans/Reglages'
/* ============================================================================
   TCH43 — Module frontend « Tâches » (apps.taches) : routes déclarées.
   ----------------------------------------------------------------------------
   Clé `taches` IDENTIQUE au manifeste backend (`apps/taches/apps.py`, vérifiée par
   `scripts/check_modules.py`). TCH131 — activation : `nav` à 4 onglets (spec-7 §2,
   maquette `coque.js`), chacun gardé par `taches_voir` comme les routes — le lanceur,
   la barre latérale, la barre d'onglets et les épinglés ne montrent le module qu'à un
   compte qui porte le droit (l'Administrateur seul en F2, donnees.md inv. 28). Les
   autres écrans s'ouvrent depuis ces onglets (menu « Plus » de la coquille, liens).

   Table des routes : docs/taches/reference/api.md §7 (13 routes). `/taches/projets/archive`
   et `/taches/projets/modeles` sont statiques : elles passent avant `/taches/projets/:id`.
   Gating STRICT : palier ET `taches_voir` (activation par étapes, donnees.md inv. 28) —
   jamais le repli WIR171 des comptes sans rôle fin, que le serveur refuse aussi.
   ========================================================================== */

/* R4-41 — chaque écran vit dans `ecrans/` : son morceau chargé à la demande, SA frontière de chargement dans le module
   (`Frontiere`, repli = la coquille et un squelette) et son chargeur de préchargement (`precharger.js`). Les routes
   ci-dessous nomment ces écrans par un import par défaut, lisible statiquement (garde `check_ecrans_atteignables.py`). */
export { CHARGEURS, prechargerEcrans, reinitialiserPrechargement } from './ecrans/precharger'

/** `/taches` mène à `/taches/aujourdhui` (api.md §7), en remplaçant l'entrée d'historique. */
function AllerAAujourdhui() {
  return <Navigate to="/taches/aujourdhui" replace />
}

const ROLES = ['normal', 'responsable', 'admin']
const GARDE = { roles: ROLES, perm: 'taches_voir' }

const navIcon = (Comp) => createElement(Comp, { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' })

const config = {
  key: 'taches',
  order: 60,
  nav: {
    label: 'Tâches', labelKey: 'nav.section.taches',
    // Glyphe d'APP unique (ODY34, `lib/apps/appGlyph.test.jsx`) ; les onglets gardent ceux de la maquette.
    icon: appGlyph(ListTodo),
    items: [
      { to: '/taches/aujourdhui', label: "Aujourd'hui", k: 'nav.taches_aujourdhui', icon: navIcon(Sun), ...GARDE },
      { to: '/taches/a-trier', label: 'À trier', k: 'nav.taches_a_trier', icon: navIcon(Inbox), ...GARDE },
      { to: '/taches/projets', label: 'Projets', k: 'nav.taches_projets', icon: navIcon(Folder), ...GARDE },
      { to: '/taches/agenda', label: 'Agenda', k: 'nav.taches_agenda', icon: navIcon(Calendar), ...GARDE },
    ],
  },
  titles: [
    ['/taches/reglages', 'Tâches — Réglages'],
    ['/taches/supprimees', 'Tâches — Supprimées'],
    ['/taches/recherche', 'Tâches — Recherche'],
    ['/taches/rythme', 'Tâches — Mon rythme'],
    ['/taches/revue', 'Tâches — Revue de la semaine'],
    ['/taches/agenda', 'Tâches — Agenda'],
    ['/taches/projets/archive', 'Tâches — Archive'],
    ['/taches/projets/modeles', 'Tâches — Modèles'],
    ['/taches/projets', 'Tâches — Projets'],
    ['/taches/a-trier', 'Tâches — À trier'],
    ['/taches', 'Tâches — Aujourd\'hui'],
  ],
  sectionLabels: { taches: 'Tâches' },
  routes: [
    { path: '/taches', component: AllerAAujourdhui, ...GARDE },
    { path: '/taches/aujourdhui', component: Aujourdhui, ...GARDE },
    { path: '/taches/a-trier', component: ATrier, ...GARDE },
    { path: '/taches/projets', component: Projets, ...GARDE },
    { path: '/taches/projets/archive', component: ProjetsArchive, ...GARDE },
    { path: '/taches/projets/modeles', component: ProjetsModeles, ...GARDE },
    { path: '/taches/projets/:id', component: Projet, ...GARDE },
    { path: '/taches/agenda', component: Agenda, ...GARDE },
    { path: '/taches/revue', component: Revue, ...GARDE },
    { path: '/taches/rythme', component: Rythme, ...GARDE },
    { path: '/taches/recherche', component: Recherche, ...GARDE },
    { path: '/taches/supprimees', component: Supprimees, ...GARDE },
    { path: '/taches/reglages/:rubrique?', component: Reglages, ...GARDE },
  ],
}

export default config
