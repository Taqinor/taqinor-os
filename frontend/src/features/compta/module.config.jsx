/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { createElement, lazy } from 'react'
import {
  LayoutDashboard, BookOpen, PencilLine, FileBarChart2,
  Landmark, ReceiptText, Building2, Scale, Receipt, HandCoins, ShieldCheck,
  ListChecks, Repeat, BadgeCheck, CalendarClock, PieChart,
  Calculator, Percent, Layers3, UserCheck, GitBranch, Split, Network, TrendingUp,
  UploadCloud, GitCompare, Tag, Wand2, Link2, FileStack, CalendarRange,
  ClipboardCheck,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX2–UX9 — Enregistrement du module « Comptabilité » (coquille ERP).
   ----------------------------------------------------------------------------
   Un SEUL fichier dépose tout le module dans le registre (router/moduleRoutes) :
   navigation Sidebar, titres de page (routes.meta) et routes react-router, sans
   toucher au routeur, à la Sidebar ni à routes.meta. Toutes les routes sont
   gatées « responsable / admin » comme le reste de la comptabilité.
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const CockpitPage = lazy(() => import('./pages/CockpitPage.jsx'))
const PlanComptablePage = lazy(() => import('./pages/PlanComptablePage.jsx'))
const EcrituresPage = lazy(() => import('./pages/EcrituresPage.jsx'))
const EtatsPage = lazy(() => import('./pages/EtatsPage.jsx'))
const TresoreriePage = lazy(() => import('./pages/TresoreriePage.jsx'))
const FiscalitePage = lazy(() => import('./pages/FiscalitePage.jsx'))
const ImmobilisationsPage = lazy(() => import('./pages/ImmobilisationsPage.jsx'))
const RapprochementsPage = lazy(() => import('./pages/RapprochementsPage.jsx'))
const NotesDeFraisPage = lazy(() => import('./pages/NotesDeFraisPage.jsx'))
const EffetsPage = lazy(() => import('./pages/EffetsPage.jsx'))
const EngagementsPage = lazy(() => import('./pages/EngagementsPage.jsx'))
// WIR107 — cockpit de clôture (NTFIN26-34) et écritures récurrentes (XACC8).
const CloturePage = lazy(() => import('./pages/CloturePage.jsx'))
const EcrituresRecurrentesPage = lazy(
  () => import('./pages/EcrituresRecurrentesPage.jsx'))
// PACT160 — file d'approbation des changements de RIB fournisseur (XACC24).
const ApprobationsRibPage = lazy(() => import('./pages/ApprobationsRibPage.jsx'))
// PACT163 — charges constatées d'avance (XACC15) et budgets (XACC22).
const ChargesAvancePage = lazy(() => import('./pages/ChargesAvancePage.jsx'))
const BudgetsPage = lazy(() => import('./pages/BudgetsPage.jsx'))
// PACT28 — fiscalité avancée (acomptes IS, conventions fiscales, TVA non
// déductible) : trois référentiels sans écran (NTMAR12/18, XACC11).
const FiscaliteAvanceePage = lazy(() => import('./pages/FiscaliteAvanceePage.jsx'))
// PACT29 — immobilisations avancées (composants, dépréciation, mutations,
// encours CIP) : 5 ressources NTFIN40-43 greffées sur le module existant.
const ImmobilisationsAvanceesPage = lazy(
  () => import('./pages/ImmobilisationsAvanceesPage.jsx'))
// PACT30 — rapprochements de comptes de bilan (NTFIN35-37, contrôle 4 yeux) :
// distinct du rapprochement bancaire déjà écranté (homonymie de nom).
const RapprochementsComptePage = lazy(
  () => import('./pages/RapprochementsComptePage.jsx'))
// PACT31 — référentiels comptables parallèles & analytique multi-axes
// (NTFIN13/15-17), jusqu'ici « API-only » dans comptaApi.js.
const ReferentielsAnalytiquePage = lazy(
  () => import('./pages/ReferentielsAnalytiquePage.jsx'))
// PACT32 — clés de répartition & engagements comptables (NTFIN20-24) : le
// backend /compta/engagements/ est un HOMONYME sans rapport avec la page
// « Engagements & clôtures avancées » (retenues de garantie…) déjà existante.
const AllocationsEngagementsPage = lazy(
  () => import('./pages/AllocationsEngagementsPage.jsx'))
// PACT33 — consolidation groupe multi-sociétés (NTFIN1-9). EntiteConsolidation
// (périmètre de filiales, mécanisme séparé et plus ancien) reste hors écran.
const ConsolidationGroupePage = lazy(
  () => import('./pages/ConsolidationGroupePage.jsx'))
// PACT34 — reconnaissance du revenu IFRS 15 (NTFIN46-48), utile pour les
// contrats pluriannuels (maintenance solaire, monitoring).
const RevenuIfrs15Page = lazy(() => import('./pages/RevenuIfrs15Page.jsx'))
// PACT35 — import guidé de la balance d'ouverture (COMPTA3, migration
// tooling) : gabarit CSV + import idempotent par exercice.
const BalanceOuverturePage = lazy(() => import('./pages/BalanceOuverturePage.jsx'))
// PACT36 — comparateurs commerciaux (FG212 versions de devis, FG221 cash vs
// financement) : calcul pur, aucun stockage.
const ComparateursPage = lazy(() => import('./pages/ComparateursPage.jsx'))
// PACT37 — codes promotionnels datés sur devis (FG209).
const CodesPromotionPage = lazy(() => import('./pages/CodesPromotionPage.jsx'))
// PACT38 — assistant de vente guidée (FG211), configurateur pas-à-pas.
const GuidedSellingPage = lazy(() => import('./pages/GuidedSellingPage.jsx'))
// PACT39 — catalogue public à jeton (FG214/XPOS14) : côté admin (le rendu
// public réel est servi par apps.ventes.public_views.ecatalogue_public).
const ECataloguePage = lazy(() => import('./pages/ECataloguePage.jsx'))
// PACT40 — bibliothèque d'annexes de proposition (FG215), purement additive.
const DocumentsPropositionPage = lazy(
  () => import('./pages/DocumentsPropositionPage.jsx'))
// PACT41 — échéanciers de paiement en tranches (FG220, type Tayssir).
const EcheanciersPaiementPage = lazy(
  () => import('./pages/EcheanciersPaiementPage.jsx'))
// PACT42 — approbation des configurations non standard (FG213).
const ApprobationsConfigPage = lazy(
  () => import('./pages/ApprobationsConfigPage.jsx'))

const ROLES = ['responsable', 'admin']

// Icône de navigation homogène (taille/épaisseur du kit UX1). On utilise
// createElement pour ne PAS déclarer de « composant » dans un fichier de config.
const icon = (Comp) =>
  createElement(Comp, { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' })

const config = {
  key: 'compta',
  order: 10,
  nav: {
    label: 'COMPTABILITÉ',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Calculator),
    accent: 'nuit', // VX8 — finance = accent nuit (dérivé, cf. tokens.css)
    items: [
      { to: '/comptabilite', label: 'Cockpit', icon: icon(LayoutDashboard), roles: ROLES },
      { to: '/comptabilite/plan', label: 'Plan comptable', icon: icon(BookOpen), roles: ROLES },
      { to: '/comptabilite/ecritures', label: 'Écritures', icon: icon(PencilLine), roles: ROLES },
      { to: '/comptabilite/ecritures-recurrentes', label: 'Écritures récurrentes', icon: icon(Repeat), roles: ROLES },
      { to: '/comptabilite/etats', label: 'États CGNC', icon: icon(FileBarChart2), roles: ROLES },
      { to: '/comptabilite/tresorerie', label: 'Trésorerie', icon: icon(Landmark), roles: ROLES },
      { to: '/comptabilite/fiscalite', label: 'Fiscalité', icon: icon(ReceiptText), roles: ROLES },
      { to: '/comptabilite/immobilisations', label: 'Immobilisations', icon: icon(Building2), roles: ROLES },
      { to: '/comptabilite/rapprochements', label: 'Rapprochements', icon: icon(Scale), roles: ROLES },
      { to: '/comptabilite/notes-de-frais', label: 'Notes de frais', icon: icon(Receipt), roles: ROLES },
      { to: '/comptabilite/effets', label: 'Effets & règlements', icon: icon(HandCoins), roles: ROLES },
      { to: '/comptabilite/engagements', label: 'Engagements', icon: icon(ShieldCheck), roles: ROLES },
      { to: '/comptabilite/cloture', label: 'Clôture', icon: icon(ListChecks), roles: ROLES },
      { to: '/comptabilite/approbations-rib', label: 'Approbations RIB', icon: icon(BadgeCheck), roles: ROLES },
      { to: '/comptabilite/charges-avance', label: 'Charges d’avance', icon: icon(CalendarClock), roles: ROLES },
      { to: '/comptabilite/budgets', label: 'Budgets', icon: icon(PieChart), roles: ROLES },
      { to: '/comptabilite/fiscalite-avancee', label: 'Fiscalité avancée', icon: icon(Percent), roles: ROLES },
      { to: '/comptabilite/immobilisations-avancees', label: 'Immobilisations avancées', icon: icon(Layers3), roles: ROLES },
      { to: '/comptabilite/rapprochements-compte', label: 'Rapprochements de comptes', icon: icon(UserCheck), roles: ROLES },
      { to: '/comptabilite/referentiels-analytique', label: 'Référentiels & analytique', icon: icon(GitBranch), roles: ROLES },
      { to: '/comptabilite/allocations-engagements', label: 'Allocations & engagements', icon: icon(Split), roles: ROLES },
      { to: '/comptabilite/consolidation-groupe', label: 'Consolidation groupe', icon: icon(Network), roles: ROLES },
      { to: '/comptabilite/revenu-ifrs15', label: 'Revenu (IFRS 15)', icon: icon(TrendingUp), roles: ROLES },
      { to: '/comptabilite/balance-ouverture', label: "Balance d'ouverture", icon: icon(UploadCloud), roles: ROLES },
      { to: '/comptabilite/comparateurs', label: 'Comparateurs', icon: icon(GitCompare), roles: ROLES },
      { to: '/comptabilite/codes-promotion', label: 'Codes promotion', icon: icon(Tag), roles: ROLES },
      { to: '/comptabilite/vente-guidee', label: 'Vente guidée', icon: icon(Wand2), roles: ROLES },
      { to: '/comptabilite/e-catalogue', label: 'Catalogue public', icon: icon(Link2), roles: ROLES },
      { to: '/comptabilite/documents-proposition', label: 'Annexes de proposition', icon: icon(FileStack), roles: ROLES },
      { to: '/comptabilite/echeanciers-paiement', label: 'Échéanciers de paiement', icon: icon(CalendarRange), roles: ROLES },
      { to: '/comptabilite/approbations-config', label: 'Approbations config', icon: icon(ClipboardCheck), roles: ROLES },
    ],
  },
  // Titres de page : du plus spécifique au plus général (routes.meta).
  titles: [
    // WIR107 — « ecritures-recurrentes » AVANT « ecritures » : la résolution
    // se fait par préfixe, l'entrée la plus spécifique doit passer d'abord.
    ['/comptabilite/ecritures-recurrentes', 'Écritures récurrentes — Comptabilité'],
    ['/comptabilite/approbations-rib', 'Approbations RIB — Comptabilité'],
    ['/comptabilite/charges-avance', 'Charges d’avance — Comptabilité'],
    ['/comptabilite/budgets', 'Budgets — Comptabilité'],
    ['/comptabilite/fiscalite-avancee', 'Fiscalité avancée — Comptabilité'],
    ['/comptabilite/immobilisations-avancees', 'Immobilisations avancées — Comptabilité'],
    ['/comptabilite/rapprochements-compte', 'Rapprochements de comptes — Comptabilité'],
    ['/comptabilite/referentiels-analytique', 'Référentiels & analytique — Comptabilité'],
    ['/comptabilite/allocations-engagements', 'Allocations & engagements — Comptabilité'],
    ['/comptabilite/consolidation-groupe', 'Consolidation groupe — Comptabilité'],
    ['/comptabilite/revenu-ifrs15', 'Revenu (IFRS 15) — Comptabilité'],
    ['/comptabilite/balance-ouverture', "Balance d'ouverture — Comptabilité"],
    ['/comptabilite/comparateurs', 'Comparateurs — Comptabilité'],
    ['/comptabilite/codes-promotion', 'Codes promotion — Comptabilité'],
    ['/comptabilite/vente-guidee', 'Vente guidée — Comptabilité'],
    ['/comptabilite/e-catalogue', 'Catalogue public — Comptabilité'],
    ['/comptabilite/documents-proposition', 'Annexes de proposition — Comptabilité'],
    ['/comptabilite/echeanciers-paiement', 'Échéanciers de paiement — Comptabilité'],
    ['/comptabilite/approbations-config', 'Approbations config — Comptabilité'],
    ['/comptabilite/cloture', 'Clôture — Comptabilité'],
    ['/comptabilite/engagements', 'Engagements — Comptabilité'],
    ['/comptabilite/effets', 'Effets & règlements — Comptabilité'],
    ['/comptabilite/notes-de-frais', 'Notes de frais — Comptabilité'],
    ['/comptabilite/rapprochements', 'Rapprochements — Comptabilité'],
    ['/comptabilite/immobilisations', 'Immobilisations — Comptabilité'],
    ['/comptabilite/fiscalite', 'Fiscalité — Comptabilité'],
    ['/comptabilite/tresorerie', 'Trésorerie — Comptabilité'],
    ['/comptabilite/etats', 'États CGNC — Comptabilité'],
    ['/comptabilite/ecritures', 'Écritures — Comptabilité'],
    ['/comptabilite/plan', 'Plan comptable — Comptabilité'],
    ['/comptabilite', 'Comptabilité'],
  ],
  sectionLabels: { comptabilite: 'Comptabilité' },
  routes: [
    { path: '/comptabilite', component: CockpitPage, roles: ROLES },
    { path: '/comptabilite/plan', component: PlanComptablePage, roles: ROLES },
    { path: '/comptabilite/ecritures', component: EcrituresPage, roles: ROLES },
    { path: '/comptabilite/etats', component: EtatsPage, roles: ROLES },
    { path: '/comptabilite/tresorerie', component: TresoreriePage, roles: ROLES },
    { path: '/comptabilite/fiscalite', component: FiscalitePage, roles: ROLES },
    { path: '/comptabilite/immobilisations', component: ImmobilisationsPage, roles: ROLES },
    { path: '/comptabilite/rapprochements', component: RapprochementsPage, roles: ROLES },
    { path: '/comptabilite/notes-de-frais', component: NotesDeFraisPage, roles: ROLES },
    { path: '/comptabilite/effets', component: EffetsPage, roles: ROLES },
    { path: '/comptabilite/engagements', component: EngagementsPage, roles: ROLES },
    { path: '/comptabilite/cloture', component: CloturePage, roles: ROLES },
    { path: '/comptabilite/ecritures-recurrentes', component: EcrituresRecurrentesPage, roles: ROLES },
    { path: '/comptabilite/approbations-rib', component: ApprobationsRibPage, roles: ROLES },
    { path: '/comptabilite/charges-avance', component: ChargesAvancePage, roles: ROLES },
    { path: '/comptabilite/budgets', component: BudgetsPage, roles: ROLES },
    { path: '/comptabilite/fiscalite-avancee', component: FiscaliteAvanceePage, roles: ROLES },
    { path: '/comptabilite/immobilisations-avancees', component: ImmobilisationsAvanceesPage, roles: ROLES },
    { path: '/comptabilite/rapprochements-compte', component: RapprochementsComptePage, roles: ROLES },
    { path: '/comptabilite/referentiels-analytique', component: ReferentielsAnalytiquePage, roles: ROLES },
    { path: '/comptabilite/allocations-engagements', component: AllocationsEngagementsPage, roles: ROLES },
    { path: '/comptabilite/consolidation-groupe', component: ConsolidationGroupePage, roles: ROLES },
    { path: '/comptabilite/revenu-ifrs15', component: RevenuIfrs15Page, roles: ROLES },
    { path: '/comptabilite/balance-ouverture', component: BalanceOuverturePage, roles: ROLES },
    { path: '/comptabilite/comparateurs', component: ComparateursPage, roles: ROLES },
    { path: '/comptabilite/codes-promotion', component: CodesPromotionPage, roles: ROLES },
    { path: '/comptabilite/vente-guidee', component: GuidedSellingPage, roles: ROLES },
    { path: '/comptabilite/e-catalogue', component: ECataloguePage, roles: ROLES },
    { path: '/comptabilite/documents-proposition', component: DocumentsPropositionPage, roles: ROLES },
    { path: '/comptabilite/echeanciers-paiement', component: EcheanciersPaiementPage, roles: ROLES },
    { path: '/comptabilite/approbations-config', component: ApprobationsConfigPage, roles: ROLES },
  ],
}

export default config
