/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (voir moduleRoutes.jsx). */
import { lazy } from 'react'
import {
  FolderKanban, CalendarRange, Users, Wallet, ShieldAlert,
} from 'lucide-react'

/* ============================================================================
   UX38–UX42 — Configuration du module « Gestion de projet ».
   ----------------------------------------------------------------------------
   Fichier UNIQUE d'enregistrement (auto-collecté par
   `src/router/moduleRoutes.jsx` via import.meta.glob) : nav Sidebar, titres de
   page, libellés de fil d'Ariane et routes lazy. Aucun autre fichier partagé
   n'est touché. Tout est gaté « responsable / admin ».
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const ProjetsPage = lazy(() => import('./pages/ProjetsPage'))
const ProjetDetailPage = lazy(() => import('./pages/ProjetDetailPage'))
const PlanningPage = lazy(() => import('./pages/PlanningPage'))
const RessourcesPage = lazy(() => import('./pages/RessourcesPage'))
const BudgetPage = lazy(() => import('./pages/BudgetPage'))
const RisquesPage = lazy(() => import('./pages/RisquesPage'))

export default {
  key: 'gestion_projet',
  order: 55,
  nav: {
    label: 'PROJETS',
    items: [
      { to: '/projets', label: 'Projets', icon: <FolderKanban size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/planning', label: 'Planning', icon: <CalendarRange size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/ressources', label: 'Ressources', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/budget', label: 'Budget & P&L', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/risques', label: 'Risques & CR', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta : du plus SPÉCIFIQUE au plus général.
  titles: [
    ['/projets/planning', 'Planning'],
    ['/projets/ressources', 'Ressources & capacité'],
    ['/projets/budget', 'Budget & P&L'],
    ['/projets/risques', 'Risques, actions & CR'],
    ['/projets', 'Projets'],
  ],
  sectionLabels: { projets: 'Projets' },
  routes: [
    // Les sous-routes fixes AVANT la route de détail paramétrée.
    { path: '/projets/planning', component: PlanningPage, roles: ROLES },
    { path: '/projets/ressources', component: RessourcesPage, roles: ROLES },
    { path: '/projets/budget', component: BudgetPage, roles: ROLES },
    { path: '/projets/risques', component: RisquesPage, roles: ROLES },
    { path: '/projets/:id', component: ProjetDetailPage, roles: ROLES },
    { path: '/projets', component: ProjetsPage, roles: ROLES },
  ],
}
