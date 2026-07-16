/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Workflow, CalendarClock } from 'lucide-react'

/* ============================================================================
   WORKFLOW (XPLT8) — configuration du module « Workflows & tâches planifiées »
   (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/workflow/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Câble FG366/368/369 (moteur BPM + jobs Beat + bibliothèque de
   modèles) côté écran, tous deux backend-only jusqu'ici. Gaté admin/responsable
   (feature d'administration). Écrans chargés en lazy (code-splitting préservé).

   Chemins DÉDIÉS `/workflow/*` (et non `/parametres/*`) : `PAGE_TITLES` est
   `[...BASE_PAGE_TITLES, ...moduleTitles]` et résout par le PREMIER préfixe
   correspondant (`routes.meta.js`) — nicher sous `/parametres/*` ferait
   matcher l'entrée générale `/parametres` de BASE (plus générale, mais placée
   AVANT nos entrées de module) avant nos titres spécifiques. `/workflow` est
   un premier segment libre : aucun autre module ne le prend.
   ========================================================================== */

const TachesPlanifieesScreen = lazy(() => import('./TachesPlanifieesScreen'))
const WorkflowsScreen = lazy(() => import('./WorkflowsScreen'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'workflow',
  order: 55,
  nav: {
    label: 'WORKFLOW',
    accent: 'warning', // VX8 — pilotage/process = accent warning (dérivé)
    items: [
      {
        to: '/workflow/taches-planifiees',
        label: 'Tâches planifiées',
        icon: <CalendarClock size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/workflow',
        label: 'Workflows',
        icon: <Workflow size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  // routes.meta — du plus spécifique au plus général (le préfixe /workflow en dernier).
  titles: [
    ['/workflow/taches-planifiees', 'Tâches planifiées'],
    ['/workflow', 'Workflows'],
  ],
  sectionLabels: { workflow: 'Workflow' },
  routes: [
    { path: '/workflow/taches-planifiees', component: TachesPlanifieesScreen, roles: ROLES },
    { path: '/workflow', component: WorkflowsScreen, roles: ROLES },
  ],
}

export default config
