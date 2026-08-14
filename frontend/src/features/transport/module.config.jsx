/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { LayoutDashboard, Plus, Route } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   Transport (Groupe SUPPLY, NTLOG1-20) — configuration du module « Transport »
   (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/transport/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta. Un seul écran pour l'instant : la liste des ordres de
   transport (`/transport/ordres`), qui monte les composants NTLOG7 (comparateur
   d'affrètement) et NTLOG8 (timeline) sur la ligne sélectionnée.
   ========================================================================== */

const OrdresTransportScreen = lazy(() => import('./OrdresTransportScreen'))
// NTLOG24 — tableau de bord logistique (KPI + répartition flotte propre/
// affrètement), nav ET route déclarées ensemble (motif PACT150).
const TableauBordLogistique = lazy(() => import('../../pages/transport/TableauBordLogistique'))
// NTLOG32 — wizard « Créer un ordre de transport » en 3 étapes, nav ET
// route déclarées ensemble (motif PACT150) ; atteint aussi depuis le bouton
// « Nouvel ordre » de l'écran `/transport/ordres`.
const CreerOrdreTransportWizard = lazy(() => import('../../pages/transport/CreerOrdreTransportWizard'))

const ROLES = ['normal', 'responsable', 'admin']

const config = {
  key: 'transport',
  order: 46,
  nav: {
    label: 'TRANSPORT',
    // Glyphe d'APP (contrat APX1 `nav.icon`) — unique sur tout le portail,
    // garanti par `lib/apps/appGlyph.test.jsx` (aucun autre module.config
    // n'utilise `Route`, contrairement à `Truck` déjà pris par `logistique`).
    icon: appGlyph(Route),
    accent: 'brass', // VX8 — supply chain/logistique = accent brass (dérivé)
    items: [
      { to: '/transport/ordres', label: 'Ordres de transport', icon: <Route size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/transport/tableau-bord', label: 'Tableau de bord', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/transport/ordres/nouveau', label: 'Nouvel ordre', icon: <Plus size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/transport/ordres', 'Ordres de transport'],
    ['/transport/tableau-bord', 'Tableau de bord logistique'],
    ['/transport/ordres/nouveau', 'Créer un ordre de transport'],
  ],
  sectionLabels: { transport: 'Transport' },
  routes: [
    { path: '/transport/ordres', component: OrdresTransportScreen, roles: ROLES },
    { path: '/transport/tableau-bord', component: TableauBordLogistique, roles: ROLES },
    { path: '/transport/ordres/nouveau', component: CreerOrdreTransportWizard, roles: ROLES },
  ],
}

export default config
