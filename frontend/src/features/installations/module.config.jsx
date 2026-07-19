/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { CalendarClock, HardHat, ClipboardList, Wrench, Boxes, BarChart3 } from 'lucide-react'

/* ============================================================================
   ARC54 — Migration des routes legacy Chantiers / Installations / Production
   vers le registre (phase 2, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes migrées ici (section `nav` ajoutée depuis par ODX7, voir plus bas).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).

   ODX7 — la section `nav` ci-dessous est le littéral CHANTIERS qui vivait dans
   `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE (regroupement
   fonctionnel only, zéro changement visuel). Sidebar lit désormais cette
   section par clé (`navFor('installations')`), à la même place dans l'ordre
   d'affichage.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const InstallationsPage = lazy(() => import('../../pages/installations/InstallationsPage'))
const DemandesAchatList = lazy(() => import('../../pages/installations/DemandesAchatList'))
// WIR110 — consultation approvisionnement avancé (6 familles FG310-318).
const ApprovisionnementPage = lazy(() => import('../../pages/installations/ApprovisionnementPage'))
// WIR114 — astreintes / indisponibilités / récurrences (FG302, ZFSM3).
const AstreintesPage = lazy(() => import('../../pages/installations/AstreintesPage'))
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
  nav: {
    label: 'CHANTIERS', labelKey: 'nav.section.chantiers',
    accent: 'success',
    items: [
      { to: '/ma-journee',           label: 'Ma journée',       k: 'nav.ma_journee', icon: navIcon(CalendarClock),       roles: ['normal','responsable','admin'] },
      { to: '/chantiers',            label: 'Chantiers',        k: 'nav.chantiers',  icon: navIcon(HardHat),    roles: ['normal','responsable','admin'] },
      { to: '/chantiers/demandes-achat', label: "Demandes d'achat", k: 'nav.demandes_achat', icon: navIcon(ClipboardList), roles: ['normal','responsable','admin'] },
      { to: '/chantiers/approvisionnement', label: 'Approvisionnement', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/interventions',        label: 'Interventions',    k: 'nav.interventions', icon: navIcon(Wrench), roles: ['normal','responsable','admin'] },
      { to: '/planification',        label: 'Planification',    k: 'nav.planification', icon: navIcon(CalendarClock),    roles: ['normal','responsable','admin'] },
      { to: '/planification/astreintes', label: 'Astreintes',   icon: navIcon(CalendarClock), roles: ['responsable','admin'] },
      { to: '/parc',                 label: 'Parc installé',    k: 'nav.parc',       icon: navIcon(Boxes),  roles: ['normal','responsable','admin'] },
      { to: '/atelier',              label: 'Atelier',          k: 'nav.atelier',    icon: navIcon(Wrench),    roles: ['normal','responsable','admin'] },
      { to: '/production',           label: 'Production',       k: 'nav.production', icon: navIcon(BarChart3),   roles: ['normal','responsable','admin'] },
      { to: '/outillage',            label: 'Outillage',        k: 'nav.outillage',  icon: navIcon(Wrench),  roles: ['normal','responsable','admin'] },
    ],
  },
  routes: [
    { path: '/chantiers', component: InstallationsPage },
    { path: '/chantiers/demandes-achat', component: DemandesAchatList },
    { path: '/chantiers/approvisionnement', component: ApprovisionnementPage, roles: ['responsable', 'admin'] },
    { path: '/interventions', component: InterventionsPage },
    { path: '/planification', component: PlanificationPage },
    { path: '/planification/astreintes', component: AstreintesPage, roles: ['responsable', 'admin'] },
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
