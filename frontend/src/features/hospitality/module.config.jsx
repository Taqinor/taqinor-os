/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { LayoutDashboard, BedDouble, CalendarDays, ClipboardList, Sparkles } from 'lucide-react'

/* ============================================================================
   WIR57 — Config du module Hôtellerie (auto-enregistrée).
   ----------------------------------------------------------------------------
   Les 5 écrans (`features/hospitality/`) étaient construits mais sans registre :
   aucune route ni entrée de nav ne les atteignait. Cette config est collectée
   par `router/moduleRoutes.jsx` via `import.meta.glob` (nav Sidebar, routes.meta,
   fil d'Ariane, routes lazy) — sans toucher au routeur ni à la Sidebar. Backend
   `apps/hospitality` prêt et company-scopé, aucun changement backend. Gaté comme
   les autres modules internes (normal/responsable/admin) en attendant un RBAC fin.
   ========================================================================== */

const Dashboard = lazy(() => import('./Dashboard'))
const PlanChambres = lazy(() => import('./PlanChambres'))
const CalendrierReservations = lazy(() => import('./CalendrierReservations'))
const MainCourante = lazy(() => import('./MainCourante'))
const Menage = lazy(() => import('./Menage'))

const ROLES = ['normal', 'responsable', 'admin']

const config = {
  key: 'hospitality',
  order: 96,
  nav: {
    label: 'HÔTELLERIE',
    accent: 'primary',
    items: [
      {
        to: '/hospitality',
        label: 'Tableau de bord',
        icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/hospitality/chambres',
        label: 'Plan des chambres',
        icon: <BedDouble size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/hospitality/reservations',
        label: 'Réservations',
        icon: <CalendarDays size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/hospitality/main-courante',
        label: 'Main courante',
        icon: <ClipboardList size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
      {
        to: '/hospitality/menage',
        label: 'Ménage',
        icon: <Sparkles size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [
    ['/hospitality', 'Tableau de bord (Hôtellerie)'],
    ['/hospitality/chambres', 'Plan des chambres'],
    ['/hospitality/reservations', 'Réservations'],
    ['/hospitality/main-courante', 'Main courante'],
    ['/hospitality/menage', 'Ménage'],
  ],
  sectionLabels: { hospitality: 'Hôtellerie' },
  routes: [
    { path: '/hospitality', component: Dashboard, roles: ROLES },
    { path: '/hospitality/chambres', component: PlanChambres, roles: ROLES },
    { path: '/hospitality/reservations', component: CalendrierReservations, roles: ROLES },
    { path: '/hospitality/main-courante', component: MainCourante, roles: ROLES },
    { path: '/hospitality/menage', component: Menage, roles: ROLES },
  ],
}

export default config
