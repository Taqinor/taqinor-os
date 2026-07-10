/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC54 — Migration des routes legacy Reporting vers le registre (phase 2,
   après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only (aucune section `nav` : Sidebar.jsx garde son menu Reporting
   hard-codé, non touché — `buildModuleRoutes` traite `nav` comme optionnel via
   `.filter(Boolean)`, donc « Sidebar sans doublon » tient trivialement ici).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.

   Gating préservé à l'identique (index.jsx:153-160 `roleLoader`) :
   - `/rapports`, `/reporting/balance-agee`, `/reporting/archive/client/:id`,
     `/reporting/archive/chantier/:id`, `/approbations`, `/reporting/classeurs`,
     `/reporting/classeurs/:id` : authLoader (aucun `roles` déclaré ci-dessous).
   - `/reporting`, `/reporting/commercial`, `/reporting/cohortes`,
     `/reporting/dashboards`, `/reporting/dashboards/partage`,
     `/reporting/sav-sla`, `/reporting/field-service`,
     `/reporting/scorecard-technicien` : `roles: ['responsable','admin']`,
     aucune `perm` — identique à `roleLoader(['responsable','admin'])`.
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const Reporting = lazy(() => import('../../pages/Reporting').then((m) => ({ default: m.Component })))
const Rapports = lazy(() => import('../../pages/Rapports').then((m) => ({ default: m.Component })))
const BalanceAgeePage = lazy(() => import('../../pages/reporting/BalanceAgeePage'))
const CommercialDashboard = lazy(() => import('../../pages/reporting/CommercialDashboard'))
const CohortsPage = lazy(() => import('../../pages/reporting/CohortsPage'))
const DashboardConfigPage = lazy(() => import('../../pages/reporting/DashboardConfigPage'))
// XPLT10 — partage de dashboard (liens publics tokenisés, créer/révoquer).
const DashboardSharePage = lazy(() => import('../../pages/reporting/DashboardSharePage'))
const ArchiveClientPage = lazy(() => import('../../pages/reporting/ArchiveClientPage'))
const ArchiveChantierPage = lazy(() => import('../../pages/reporting/ArchiveChantierPage'))
// XKB1/ZCTR7-9 — boîte d'approbations centralisée cross-app (5 sources).
const ApprobationsPage = lazy(() => import('../../pages/approbations/ApprobationsPage'))
// XPLT22 — classeur léger embarqué (mini-spreadsheet BI, données live).
const ClasseursListPage = lazy(() => import('../../pages/reporting/ClasseursListPage'))
const ClasseurPage = lazy(() => import('../../pages/reporting/ClasseurPage'))
// XSAV8 — conformité SLA + KPI SAV avancés.
const SavSlaPage = lazy(() => import('../../pages/reporting/SavSlaPage'))
// XFSM16 — analytics field service consolidés.
const FieldServiceReportPage = lazy(() => import('../../pages/reporting/FieldServiceReportPage'))
// XFSM17 — scorecard coaching par technicien vs moyenne équipe.
const TechnicienScorecardPage = lazy(() => import('../../pages/reporting/TechnicienScorecardPage'))

const RESPONSABLE_ADMIN = ['responsable', 'admin']

const config = {
  key: 'reporting',
  order: 70,
  routes: [
    { path: '/reporting', component: Reporting, roles: RESPONSABLE_ADMIN },
    { path: '/rapports', component: Rapports },
    { path: '/reporting/balance-agee', component: BalanceAgeePage },
    { path: '/reporting/commercial', component: CommercialDashboard, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/cohortes', component: CohortsPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/dashboards', component: DashboardConfigPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/dashboards/partage', component: DashboardSharePage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/archive/client/:id', component: ArchiveClientPage },
    { path: '/reporting/archive/chantier/:id', component: ArchiveChantierPage },
    { path: '/approbations', component: ApprobationsPage },
    { path: '/reporting/classeurs', component: ClasseursListPage },
    { path: '/reporting/classeurs/:id', component: ClasseurPage },
    { path: '/reporting/sav-sla', component: SavSlaPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/field-service', component: FieldServiceReportPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/scorecard-technicien', component: TechnicienScorecardPage, roles: RESPONSABLE_ADMIN },
  ],
}

export default config
