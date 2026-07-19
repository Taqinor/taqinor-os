/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Truck, ClipboardList, ArrowLeftRight, Undo2 } from 'lucide-react'

/* ============================================================================
   LOGISTIQUE (XSTK2) — configuration du module « Logistique » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/logistique/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Toutes les routes/entrées de menu sont gatées
   `['responsable','admin']`. Écrans chargés en lazy (code-splitting préservé).
   ========================================================================== */

const LogistiqueCockpit = lazy(() => import('./LogistiqueCockpit'))
const LivraisonsPlanningScreen = lazy(() => import('./LivraisonsPlanningScreen'))
const ComptageCyclesScreen = lazy(() => import('./ComptageCyclesScreen'))
const TransfertsScreen = lazy(() => import('./TransfertsScreen'))
// WIR111 — consultation des retours (matériel + livraison), backend-only.
const RetoursScreen = lazy(() => import('./RetoursScreen'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'logistique',
  order: 51,
  nav: {
    label: 'LOGISTIQUE',
    accent: 'success', // VX8 — terrain/opérations = accent success (dérivé)
    items: [
      { to: '/logistique', label: 'Cockpit', icon: <Truck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/logistique/livraisons', label: 'Livraisons', icon: <Truck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/logistique/comptages', label: 'Comptages cycliques', icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/logistique/transferts', label: 'Transferts', icon: <ArrowLeftRight size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/logistique/retours', label: 'Retours', icon: <Undo2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général (le préfixe /logistique en dernier).
  titles: [
    ['/logistique/livraisons', 'Livraisons'],
    ['/logistique/comptages', 'Comptages cycliques'],
    ['/logistique/transferts', 'Transferts'],
    ['/logistique/retours', 'Retours'],
    ['/logistique', 'Logistique'],
  ],
  sectionLabels: { logistique: 'Logistique' },
  routes: [
    { path: '/logistique', component: LogistiqueCockpit, roles: ROLES },
    { path: '/logistique/livraisons', component: LivraisonsPlanningScreen, roles: ROLES },
    { path: '/logistique/comptages', component: ComptageCyclesScreen, roles: ROLES },
    { path: '/logistique/transferts', component: TransfertsScreen, roles: ROLES },
    { path: '/logistique/retours', component: RetoursScreen, roles: ROLES },
  ],
}

export default config
