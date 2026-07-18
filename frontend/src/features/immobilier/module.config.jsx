/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Building2 } from 'lucide-react'

/* ============================================================================
   IMMOBILIER (Groupe NTPRO) — configuration du module « Immobilier »
   (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/immobilier/` ; le registre
   `router/moduleRoutes.jsx` la collecte via `import.meta.glob` — SANS toucher
   au routeur, à la Sidebar ni à routes.meta. Les écrans vivent dans
   `src/pages/immobilier/` (chargés en lazy, code-splitting préservé).
   ========================================================================== */

const PatrimoineTree = lazy(() => import('../../pages/immobilier/PatrimoineTree'))
const RentabiliteActif = lazy(() => import('../../pages/immobilier/RentabiliteActif'))
const ChargesPage = lazy(() => import('../../pages/immobilier/ChargesPage'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'immobilier',
  order: 60,
  nav: {
    label: 'IMMOBILIER',
    items: [
      {
        to: '/immobilier',
        label: 'Patrimoine',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/rentabilite',
        label: 'Rentabilité',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/immobilier/charges',
        label: 'Charges',
        icon: <Building2 size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/immobilier/rentabilite', 'Rentabilité'],
    ['/immobilier/charges', 'Charges'],
    ['/immobilier', 'Immobilier'],
  ],
  sectionLabels: { immobilier: 'Immobilier' },
  routes: [
    { path: '/immobilier', component: PatrimoineTree, roles: ROLES },
    { path: '/immobilier/rentabilite', component: RentabiliteActif, roles: ROLES },
    { path: '/immobilier/charges', component: ChargesPage, roles: ROLES },
  ],
}

export default config
