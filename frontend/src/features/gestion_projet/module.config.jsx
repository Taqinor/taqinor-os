/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (voir moduleRoutes.jsx). */
import { lazy } from 'react'
import {
  FolderKanban, CalendarRange, Users, Wallet, ShieldAlert, Clock3, ListChecks,
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
const TempsPage = lazy(() => import('./pages/TempsPage'))
const TachesPage = lazy(() => import('./pages/TachesPage'))
const MesTachesPage = lazy(() => import('./pages/TachesPage').then((mod) => {
  const TachesPageComponent = mod.default
  return { default: () => <TachesPageComponent mesTaches /> }
}))

export default {
  key: 'gestion_projet',
  order: 55,
  nav: {
    label: 'PROJETS',
    accent: 'warning', // VX8 — pilotage/reporting = accent warning (dérivé)
    items: [
      { to: '/projets', label: 'Projets', icon: <FolderKanban size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/planning', label: 'Planning', icon: <CalendarRange size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/taches', label: 'Tâches', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/taches/mes-taches', label: 'Mes tâches', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/temps', label: 'Temps', icon: <Clock3 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/ressources', label: 'Ressources', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/budget', label: 'Budget & P&L', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/projets/risques', label: 'Risques & CR', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta : du plus SPÉCIFIQUE au plus général.
  titles: [
    ['/projets/planning', 'Planning'],
    ['/projets/taches/mes-taches', 'Mes tâches'],
    ['/projets/taches', 'Tâches'],
    ['/projets/temps', 'Saisie des temps'],
    ['/projets/ressources', 'Ressources & capacité'],
    ['/projets/budget', 'Budget & P&L'],
    ['/projets/risques', 'Risques, actions & CR'],
    ['/projets', 'Projets'],
  ],
  sectionLabels: { projets: 'Projets' },
  routes: [
    // Les sous-routes fixes AVANT la route de détail paramétrée.
    { path: '/projets/planning', component: PlanningPage, roles: ROLES },
    { path: '/projets/taches/mes-taches', component: MesTachesPage, roles: ROLES },
    { path: '/projets/taches', component: TachesPage, roles: ROLES },
    { path: '/projets/temps', component: TempsPage, roles: ROLES },
    { path: '/projets/ressources', component: RessourcesPage, roles: ROLES },
    { path: '/projets/budget', component: BudgetPage, roles: ROLES },
    { path: '/projets/risques', component: RisquesPage, roles: ROLES },
    { path: '/projets/:id', component: ProjetDetailPage, roles: ROLES },
    { path: '/projets', component: ProjetsPage, roles: ROLES },
  ],
}
