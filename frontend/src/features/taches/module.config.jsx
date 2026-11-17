import { lazy } from 'react'
import { Navigate } from 'react-router-dom'

/* ============================================================================
   TCH43 — Module frontend « Tâches » (apps.taches) : routes déclarées, AUCUNE nav.
   ----------------------------------------------------------------------------
   Clé `taches` IDENTIQUE au manifeste backend (`apps/taches/apps.py`, vérifiée par
   `scripts/check_modules.py`). Le module est INVISIBLE jusqu'à l'activation (TCH131) :
   ni `nav` (donc aucune entrée de menu, aucune tuile d'app), ni libellé de section.
   Les écrans restent atteignables par URL directe, comme les notifications (`plan_matin`,
   `bilan_soir`, rappel…) les ouvriront ; chaque route porte `// contextuelle: …` pour la
   garde `scripts/check_ecrans_atteignables.py` (route sans entrée de nav).

   Table des routes : docs/taches/reference/api.md §7 (13 routes). `/taches/projets/archive`
   et `/taches/projets/modeles` sont statiques : elles passent avant `/taches/projets/:id`.
   Gating STRICT : palier ET `taches_voir` (activation par étapes, donnees.md inv. 28) —
   jamais le repli WIR171 des comptes sans rôle fin, que le serveur refuse aussi.
   ========================================================================== */

const Aujourdhui = lazy(() => import('../../pages/taches/Aujourdhui'))
const ATrier = lazy(() => import('../../pages/taches/ATrier'))
const Projets = lazy(() => import('../../pages/taches/Projets'))
const Projet = lazy(() => import('../../pages/taches/Projet'))
const ProjetsArchive = lazy(() => import('../../pages/taches/ProjetsArchive'))
const ProjetsModeles = lazy(() => import('../../pages/taches/ProjetsModeles'))
const Agenda = lazy(() => import('../../pages/taches/Agenda'))
const Revue = lazy(() => import('../../pages/taches/Revue'))
const Rythme = lazy(() => import('../../pages/taches/Rythme'))
const Recherche = lazy(() => import('../../pages/taches/Recherche'))
const Supprimees = lazy(() => import('../../pages/taches/Supprimees'))
const Reglages = lazy(() => import('../../pages/taches/Reglages'))

/** `/taches` mène à `/taches/aujourdhui` (api.md §7), en remplaçant l'entrée d'historique. */
function AllerAAujourdhui() {
  return <Navigate to="/taches/aujourdhui" replace />
}

const ROLES = ['normal', 'responsable', 'admin']
const GARDE = { roles: ROLES, perm: 'taches_voir' }

const config = {
  key: 'taches',
  order: 60,
  titles: [
    ['/taches/reglages', 'Tâches — Réglages'],
    ['/taches/supprimees', 'Tâches — Supprimées récemment'],
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
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches', component: AllerAAujourdhui, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/aujourdhui', component: Aujourdhui, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/a-trier', component: ATrier, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/projets', component: Projets, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/projets/archive', component: ProjetsArchive, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/projets/modeles', component: ProjetsModeles, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/projets/:id', component: Projet, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/agenda', component: Agenda, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/revue', component: Revue, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/rythme', component: Rythme, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/recherche', component: Recherche, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/supprimees', component: Supprimees, ...GARDE },
    // contextuelle: module invisible jusqu'à TCH131
    { path: '/taches/reglages/:rubrique?', component: Reglages, ...GARDE },
  ],
}

export default config
