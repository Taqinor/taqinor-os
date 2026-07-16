/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Warehouse, MapPin, PackageCheck, ClipboardList, Boxes } from 'lucide-react'

/* ============================================================================
   MAGASIN (XSTK1) — configuration du module « Magasin » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/magasin/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Toutes les routes/entrées de menu sont gatées
   `['responsable','admin']` (même gating que flotte/ged/qhse — opérations
   d'entrepôt, pas un écran grand public). Écrans chargés en lazy.
   ========================================================================== */

const MagasinCockpit = lazy(() => import('./MagasinCockpit'))
const BinTreeScreen = lazy(() => import('./BinTreeScreen'))
const PutAwayScreen = lazy(() => import('./PutAwayScreen'))
const PickListScreen = lazy(() => import('./PickListScreen'))
const ColisageScreen = lazy(() => import('./ColisageScreen'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'magasin',
  order: 51,
  nav: {
    label: 'MAGASIN',
    accent: 'success', // VX8 — terrain/opérations = accent success (dérivé)
    items: [
      { to: '/magasin', label: 'Cockpit', icon: <Warehouse size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/casiers', label: 'Casiers', icon: <MapPin size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/rangement', label: 'Rangement (put-away)', icon: <PackageCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/prelevements', label: 'Prélèvements', icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/magasin/colisage', label: 'Colisage', icon: <Boxes size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général (le préfixe /magasin en dernier).
  titles: [
    ['/magasin/casiers', 'Casiers'],
    ['/magasin/rangement', 'Rangement (put-away)'],
    ['/magasin/prelevements', 'Prélèvements'],
    ['/magasin/colisage', 'Colisage'],
    ['/magasin', 'Magasin'],
  ],
  sectionLabels: { magasin: 'Magasin' },
  routes: [
    { path: '/magasin', component: MagasinCockpit, roles: ROLES },
    { path: '/magasin/casiers', component: BinTreeScreen, roles: ROLES },
    { path: '/magasin/rangement', component: PutAwayScreen, roles: ROLES },
    { path: '/magasin/prelevements', component: PickListScreen, roles: ROLES },
    { path: '/magasin/colisage', component: ColisageScreen, roles: ROLES },
  ],
}

export default config
