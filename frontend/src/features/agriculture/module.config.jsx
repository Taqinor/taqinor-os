/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — même dérogation que
   `features/flotte/module.config.jsx`. */
import { lazy } from 'react'
import { Sprout, Beaker } from 'lucide-react'

/* ============================================================================
   NTAGR4/NTAGR8 — configuration du module « Agriculture » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/agriculture/` ; le registre
   `router/moduleRoutes.jsx` la collecte via `import.meta.glob` — SANS toucher
   au routeur, à la Sidebar ni à routes.meta (patron UX1/ODX7). Écrans en
   `src/pages/agriculture/*` chargés en lazy (code-splitting préservé).
   NTAGR35 (hors périmètre ici) étendra ce fichier avec les écrans P2/P3
   restants et le gating par ModuleToggle (`core.ModuleToggle`).
   ========================================================================== */

const ParcellesPage = lazy(() => import('../../pages/agriculture/ParcellesPage'))
const IntrantsPage = lazy(() => import('../../pages/agriculture/IntrantsPage'))

const ROLES = ['responsable', 'admin', 'normal']

const config = {
  key: 'agriculture',
  order: 60,
  nav: {
    label: 'AGRICULTURE',
    accent: 'success',
    items: [
      { to: '/agriculture/parcelles', label: 'Parcelles', icon: <Sprout size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/agriculture/intrants', label: 'Intrants', icon: <Beaker size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/agriculture/parcelles', 'Parcelles'],
    ['/agriculture/intrants', 'Intrants'],
  ],
  sectionLabels: { agriculture: 'Agriculture' },
  routes: [
    { path: '/agriculture/parcelles', component: ParcellesPage, roles: ROLES },
    { path: '/agriculture/intrants', component: IntrantsPage, roles: ROLES },
  ],
}

export default config
