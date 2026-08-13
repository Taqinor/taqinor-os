/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { BarChart3, Inbox, Tv, ScrollText } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   ARC54 — Migration des routes legacy Reporting vers le registre (phase 2,
   après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes migrées ici (section `nav` ajoutée depuis par ODX7, voir plus bas).
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

   ODX7 — la section `nav` ci-dessous est le littéral ANALYSE (« RAPPORTS ») qui
   vivait dans `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE
   (regroupement fonctionnel only, zéro changement visuel, y compris le badge
   d'approbations en attente géré par Sidebar sur `to === '/approbations'`).
   Sidebar lit désormais cette section par clé (`navFor('reporting')`), à la
   même place dans l'ordre d'affichage.

   ODY23 — « Reporting/Rapports/Journal → app Rapports » : ajoute l'entrée de
   menu Journal d'activité (route ET gating INCHANGÉS, `roles`+`perm` copiés
   à l'identique) — elle vivait jusqu'ici UNIQUEMENT dans la section
   ADMINISTRATION codée en dur de `Sidebar.jsx` (extraite par la lane ODY4).
   La ROUTE elle-même reste déclarée dans `features/parametres/module.config.jsx`
   (`Journal`, inchangé) : un item de nav peut pointer vers une route déclarée
   par un AUTRE module.config, exactement comme `navFor('reporting')` pointe
   déjà vers `/approbations` géré ailleurs — aucune duplication de route ici.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const Reporting = lazy(() => import('../../pages/Reporting').then((m) => ({ default: m.Component })))
const Rapports = lazy(() => import('../../pages/Rapports').then((m) => ({ default: m.Component })))
const BalanceAgeePage = lazy(() => import('../../pages/reporting/BalanceAgeePage'))
const CommercialDashboard = lazy(() => import('../../pages/reporting/CommercialDashboard'))
const CohortsPage = lazy(() => import('../../pages/reporting/CohortsPage'))
const DashboardConfigPage = lazy(() => import('../../pages/reporting/DashboardConfigPage'))
// XPLT10 — partage de dashboard (liens publics tokenisés, créer/révoquer).
const DashboardSharePage = lazy(() => import('../../pages/reporting/DashboardSharePage'))
// PACT144 — rapport d'activité périodique (métriques serveur + narratif
// éditable ; un narratif citant un chiffre absent est refusé côté serveur).
const RapportPeriodePage = lazy(() => import('./RapportPeriodePage'))
// PACT146 — générateur de rapports croisés (définitions NTEXT10 rejouables).
const RapportBuilderPage = lazy(() => import('./RapportBuilderPage'))
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
// WIR84 — consommateur des agrégateurs Quote-to-Cash de `apps/ventes`
// (FG45 `/ventes/dashboard/`, FG47 `/ventes/insights/cash-flow/`,
// ZFAC10 `/ventes/etats/analyse-facturation/`), jusqu'ici sans appelant.
const QuoteToCashPage = lazy(() => import('../../pages/reporting/QuoteToCashPage'))

const RESPONSABLE_ADMIN = ['responsable', 'admin']

const config = {
  key: 'reporting',
  order: 70,
  nav: {
    label: 'ANALYSE', labelKey: 'nav.section.analyse',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(BarChart3),
    accent: 'warning',
    items: [
      { to: '/reporting',            label: 'Reporting',        k: 'nav.reporting',  icon: navIcon(BarChart3),    roles: ['responsable','admin'] },
      { to: '/rapports',             label: 'Rapports',         k: 'nav.rapports',   icon: navIcon(BarChart3),    roles: ['responsable','admin'] },
      { to: '/reporting/balance-agee', label: 'Balance âgée',   k: 'nav.balance_agee', icon: navIcon(BarChart3),  roles: ['responsable','admin'] },
      { to: '/reporting/commercial', label: 'Tableau commercial', k: 'nav.tableau_commercial', icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      // WIR84 — écran consommateur des agrégateurs Quote-to-Cash de `ventes`.
      { to: '/reporting/quote-to-cash', label: 'Quote-to-Cash', k: 'nav.quote_to_cash', icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      // WIR17/FG98 — cohortes de rétention/CA (route déjà enregistrée
      // ci-dessous, jusqu'ici sans entrée de menu).
      { to: '/reporting/cohortes',   label: 'Cohortes',         k: 'nav.cohortes',   icon: navIcon(BarChart3),    roles: ['responsable','admin'] },
      // XKB1/ZCTR7-9 — boîte d'approbations centralisée, ouverte à tout rôle
      // (chacun peut avoir des demandes en attente sur son périmètre).
      { to: '/approbations',         label: 'Approbations',     k: 'nav.approbations', icon: navIcon(Inbox), roles: ['normal','responsable','admin'] },
      // XPLT22 — classeurs (mini-tableurs BI avec données live).
      { to: '/reporting/classeurs',  label: 'Classeurs',        k: 'nav.classeurs',  icon: navIcon(BarChart3),    roles: ['responsable','admin'] },
      // XSAV8 — conformité SLA + KPI SAV avancés.
      { to: '/reporting/sav-sla',    label: 'SLA SAV',          k: 'nav.sav_sla',    icon: navIcon(BarChart3),    roles: ['responsable','admin'] },
      // XFSM16 — analytics field service consolidés (FTF, MTTR, ponctualité…).
      { to: '/reporting/field-service', label: 'Analytics terrain', k: 'nav.field_service', icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      // XFSM17 — scorecard coaching par technicien vs moyenne équipe.
      { to: '/reporting/scorecard-technicien', label: 'Scorecard technicien', k: 'nav.scorecard_technicien', icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      // XPLT10 — kiosque TV plein écran des dashboards partagés.
      { to: '/dashboards-tv',        label: 'Dashboards TV',    k: 'nav.dashboards_tv', icon: navIcon(Tv), roles: ['responsable','admin'] },
      // XPLT10 — gestion des liens de partage (créer/révoquer).
      { to: '/reporting/dashboards/partage', label: 'Partage de dashboards', k: 'nav.dashboards_partage', icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      // PACT144 — rapport d'activité périodique (chiffres serveur + narratif).
      { to: '/reporting/rapport-periode', label: 'Rapport de période', k: 'nav.rapport_periode', icon: navIcon(ScrollText), roles: ['responsable','admin'] },
      // PACT146 — générateur de rapports croisés (définitions rejouables).
      { to: '/reporting/rapport-builder', label: 'Rapports croisés', k: 'nav.rapport_builder', icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      // ODY23 — Journal d'activité rejoint l'app Rapports (route inchangée,
      // déclarée dans features/parametres/module.config.jsx). Gating IDENTIQUE
      // au littéral ADMINISTRATION historique de Sidebar.jsx : ouvert à tout
      // rôle, réservé par la permission dédiée (Directeur par défaut).
      { to: '/journal', label: "Journal d'activité", k: 'nav.journal', icon: navIcon(ScrollText), roles: ['normal','responsable','admin'], perm: 'journal_activite_voir' },
    ],
  },
  // PACT144 — titre de page du seul chemin AJOUTÉ par ce module (les autres
  // restent déclarés dans `components/layout/routes.meta.js`, non dupliqués).
  titles: [
    ['/reporting/rapport-periode', 'Rapport d’activité périodique'],
    ['/reporting/rapport-builder', 'Générateur de rapports croisés'],
  ],
  routes: [
    { path: '/reporting', component: Reporting, roles: RESPONSABLE_ADMIN },
    { path: '/rapports', component: Rapports },
    { path: '/reporting/balance-agee', component: BalanceAgeePage },
    { path: '/reporting/commercial', component: CommercialDashboard, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/quote-to-cash', component: QuoteToCashPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/cohortes', component: CohortsPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/dashboards', component: DashboardConfigPage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/dashboards/partage', component: DashboardSharePage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/rapport-periode', component: RapportPeriodePage, roles: RESPONSABLE_ADMIN },
    { path: '/reporting/rapport-builder', component: RapportBuilderPage, roles: RESPONSABLE_ADMIN },
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
