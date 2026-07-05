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

const ROLES = ['normal', 'responsable', 'admin']

const config = {
  key: 'pos',
  order: 15,
  nav: {
    label: 'CAISSE',
    items: [
      { to: '/pos', label: 'Caisse', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/pos', 'Caisse'],
  ],
  sectionLabels: { pos: 'Caisse' },
  routes: [
    { path: '/pos', component: CaisseScreen, roles: ROLES },
  ],
}

export default config
