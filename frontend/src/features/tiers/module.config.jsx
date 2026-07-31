/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — même dérogation que
   `features/agriculture/module.config.jsx`. */
import { lazy } from 'react'
import { Users } from 'lucide-react'

/* ============================================================================
   WIR152 — configuration du module « Tiers » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/tiers/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar
   ni à routes.meta (patron UX1). Écran répertoire en `src/pages/tiers/*`
   chargé en lazy (code-splitting préservé). « Doublons tiers » (ARC20,
   admin-only côté backend) vit sous Paramètres — voir
   `features/parametres/module.config.jsx` (même patron que Territoires/
   Playbooks/Achats : les sous-routes `/parametres/*` restent toutes
   déclarées dans CE fichier unique, jamais dupliquées ailleurs).
   ========================================================================== */

const TiersPage = lazy(() => import('../../pages/tiers/TiersPage'))

const ROLES = ['responsable', 'admin', 'normal']

const config = {
  key: 'tiers',
  order: 65,
  nav: {
    label: 'TIERS',
    items: [
      { to: '/tiers', label: 'Répertoire', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/tiers', 'Tiers'],
  ],
  sectionLabels: { tiers: 'Tiers' },
  routes: [
    { path: '/tiers', component: TiersPage, roles: ROLES },
  ],
}

export default config
