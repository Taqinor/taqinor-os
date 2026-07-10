/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC54 — Migration des routes legacy CRM vers le registre (phase 2, après les
   pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only (aucune section `nav` : Sidebar.jsx garde son menu CRM hard-codé,
   non touché — `buildModuleRoutes` traite `nav` comme optionnel via
   `.filter(Boolean)`, donc « Sidebar sans doublon » tient trivialement ici).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const ClientList = lazy(() => import('../../pages/crm/ClientList'))
const LeadsPage = lazy(() => import('../../pages/crm/leads/LeadsPage'))
const MesActivitesPage = lazy(() => import('../../pages/activities/MesActivitesPage'))
const CalendarPage = lazy(() => import('../../pages/CalendarPage'))
const CartePage = lazy(() => import('../../pages/CartePage'))
const ParrainagePage = lazy(() => import('../../pages/crm/ParrainagePage'))

const config = {
  key: 'crm',
  order: 40,
  routes: [
    { path: '/crm', component: ClientList },
    { path: '/crm/leads', component: LeadsPage },
    { path: '/activites', component: MesActivitesPage },
    { path: '/calendrier', component: CalendarPage },
    { path: '/carte', component: CartePage },
    { path: '/crm/parrainage', component: ParrainagePage },
  ],
}

export default config
