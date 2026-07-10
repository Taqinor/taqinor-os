/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC54 — Migration des routes legacy Chantiers / Installations / Production
   vers le registre (phase 2, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only (aucune section `nav` : Sidebar.jsx garde son menu Chantiers
   hard-codé, non touché — `buildModuleRoutes` traite `nav` comme optionnel via
   `.filter(Boolean)`, donc « Sidebar sans doublon » tient trivialement ici).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const InstallationsPage = lazy(() => import('../../pages/installations/InstallationsPage'))
const DemandesAchatList = lazy(() => import('../../pages/installations/DemandesAchatList'))
const InterventionsPage = lazy(() => import('../../pages/interventions/InterventionsPage'))
const PlanificationPage = lazy(() => import('../../pages/installations/PlanificationPage'))
const MaJourneePage = lazy(() => import('../../pages/interventions/MaJourneePage'))
const ParcInstallePage = lazy(() => import('../../pages/installations/ParcInstallePage'))
const AteliersPage = lazy(() => import('../../pages/installations/AteliersPage'))
const ProductionPage = lazy(() => import('../../pages/monitoring/ProductionPage'))
const FleetPage = lazy(() => import('../../pages/monitoring/FleetPage'))
const OmAnalyticsPage = lazy(() => import('../../pages/monitoring/OmAnalyticsPage'))
const WarrantiesPage = lazy(() => import('../../pages/monitoring/WarrantiesPage'))
const Co2Page = lazy(() => import('../../pages/monitoring/Co2Page'))
const CleaningsPage = lazy(() => import('../../pages/monitoring/CleaningsPage'))
const OmReportPage = lazy(() => import('../../pages/monitoring/OmReportPage'))
const ClientPortalPage = lazy(() => import('../../pages/monitoring/ClientPortalPage'))
const OutillagePage = lazy(() => import('../../pages/outillage/OutillagePage'))

const config = {
  key: 'installations',
  order: 60,
  routes: [
    { path: '/chantiers', component: InstallationsPage },
    { path: '/chantiers/demandes-achat', component: DemandesAchatList },
    { path: '/interventions', component: InterventionsPage },
    { path: '/planification', component: PlanificationPage },
    { path: '/ma-journee', component: MaJourneePage },
    { path: '/parc', component: ParcInstallePage },
    { path: '/atelier', component: AteliersPage },
    { path: '/production', component: ProductionPage },
    { path: '/production/parc', component: FleetPage },
    { path: '/production/analytique', component: OmAnalyticsPage },
    { path: '/production/garanties', component: WarrantiesPage },
    { path: '/production/co2', component: Co2Page },
    { path: '/production/nettoyages', component: CleaningsPage },
    { path: '/production/rapports', component: OmReportPage },
    { path: '/production/portail-client', component: ClientPortalPage },
    { path: '/outillage', component: OutillagePage },
  ],
}

export default config
