/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { ShoppingCart } from 'lucide-react'

/* ============================================================================
   POS (XPOS2) — configuration du module « Caisse » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/pos/` ; le registre `router/moduleRoutes.jsx` la
   collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni à
   routes.meta. Accessible à tout utilisateur pouvant vendre (normal/
   responsable/admin), comme les autres écrans de vente courante.
   ========================================================================== */

const CaisseScreen = lazy(() => import('./CaisseScreen'))
const SessionScreen = lazy(() => import('./SessionScreen'))
const DashboardScreen = lazy(() => import('./DashboardScreen'))
const RetraitsScreen = lazy(() => import('./RetraitsScreen'))
const ConfigMaterielScreen = lazy(() => import('./ConfigMaterielScreen'))

const ROLES = ['normal', 'responsable', 'admin']
// XPOS4 — l'ouverture/clôture de caisse est réservée aux responsables/admin
// (même palier que le backend SessionCaisseViewSet : IsResponsableOrAdmin).
const ROLES_CAISSE = ['responsable', 'admin']

const config = {
  key: 'pos',
  order: 15,
  nav: {
    label: 'CAISSE',
    accent: 'brass', // VX8 — commercial/vente = accent brass (dérivé)
    items: [
      { to: '/pos', label: 'Caisse', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/pos/session', label: 'Sessions de caisse', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_CAISSE },
      { to: '/pos/dashboard', label: 'Tableau de bord', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_CAISSE },
      { to: '/pos/retraits', label: 'Retraits magasin', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_CAISSE },
      { to: '/pos/config-materiel', label: 'Matériel de caisse', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_CAISSE },
    ],
  },
  titles: [
    ['/pos', 'Caisse'],
    ['/pos/session', 'Sessions de caisse'],
    ['/pos/dashboard', 'Tableau de bord'],
    ['/pos/retraits', 'Retraits magasin'],
    ['/pos/config-materiel', 'Matériel de caisse'],
  ],
  sectionLabels: { pos: 'Caisse' },
  routes: [
    { path: '/pos', component: CaisseScreen, roles: ROLES },
    { path: '/pos/session', component: SessionScreen, roles: ROLES_CAISSE },
    { path: '/pos/dashboard', component: DashboardScreen, roles: ROLES_CAISSE },
    { path: '/pos/retraits', component: RetraitsScreen, roles: ROLES_CAISSE },
    { path: '/pos/config-materiel', component: ConfigMaterielScreen, roles: ROLES_CAISSE },
  ],
}

export default config
