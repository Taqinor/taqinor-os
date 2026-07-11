/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { createElement, lazy } from 'react'
import {
  LayoutDashboard, BookOpen, PencilLine, FileBarChart2,
  Landmark, ReceiptText, Building2, Scale, Receipt, HandCoins, ShieldCheck,
} from 'lucide-react'

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
    accent: 'nuit', // VX8 — finance = accent nuit (dérivé, cf. tokens.css)
    items: [
      { to: '/comptabilite', label: 'Cockpit', icon: icon(LayoutDashboard), roles: ROLES },
      { to: '/comptabilite/plan', label: 'Plan comptable', icon: icon(BookOpen), roles: ROLES },
      { to: '/comptabilite/ecritures', label: 'Écritures', icon: icon(PencilLine), roles: ROLES },
      { to: '/comptabilite/etats', label: 'États CGNC', icon: icon(FileBarChart2), roles: ROLES },
      { to: '/comptabilite/tresorerie', label: 'Trésorerie', icon: icon(Landmark), roles: ROLES },
      { to: '/comptabilite/fiscalite', label: 'Fiscalité', icon: icon(ReceiptText), roles: ROLES },
      { to: '/comptabilite/immobilisations', label: 'Immobilisations', icon: icon(Building2), roles: ROLES },
      { to: '/comptabilite/rapprochements', label: 'Rapprochements', icon: icon(Scale), roles: ROLES },
      { to: '/comptabilite/notes-de-frais', label: 'Notes de frais', icon: icon(Receipt), roles: ROLES },
      { to: '/comptabilite/effets', label: 'Effets & règlements', icon: icon(HandCoins), roles: ROLES },
      { to: '/comptabilite/engagements', label: 'Engagements', icon: icon(ShieldCheck), roles: ROLES },
    ],
  },
  // Titres de page : du plus spécifique au plus général (routes.meta).
  titles: [
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
  ],
}

export default config
