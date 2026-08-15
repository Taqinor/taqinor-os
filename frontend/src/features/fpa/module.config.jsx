/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  Table2, TrendingUp, GitCompareArrows, Scale, LayoutDashboard, CheckCircle2,
  Settings2,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   NTFPA30 — Configuration du module ERP « FP&A » (budgets & prévisions).
   ----------------------------------------------------------------------------
   Un seul fichier auto-enregistré par `router/moduleRoutes.jsx` (glob) : nav
   Sidebar gatée, titres de page (routes.meta), et routes lazy. Aucune édition
   du routeur / de la Sidebar / de routes.meta.

   Budget MACRO par société/département/période — DISTINCT du budget micro par
   chantier (module Gestion de projet). Accès gaté au palier Directeur/FP&A
   (mêmes rôles que le backend : responsable/admin ; le périmètre par
   département est appliqué côté serveur, NTFPA26).
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const DashboardPage = lazy(() => import('../../pages/fpa/DashboardPage'))
const SaisiePage = lazy(() => import('../../pages/fpa/SaisiePage'))
const PrevisionsPage = lazy(() => import('../../pages/fpa/PrevisionsPage'))
const ScenariosPage = lazy(() => import('../../pages/fpa/ScenariosPage'))
const VariancePage = lazy(() => import('../../pages/fpa/VariancePage'))
// PACT53 — le workflow de validation d'un budget de département (NTFPA5)
// n'avait aucun écran : la saisie fonctionnait, son statut de validation
// formel restait invisible.
const SoumissionsBudgetPage = lazy(() => import('../../pages/fpa/SoumissionsBudgetPage'))
// WIR199 — administration (départements en arbre + cycles budgétaires) :
// jusqu'ici créables SEULEMENT en admin Django, la saisie ne pouvait pas
// s'amorcer sans ça.
const AdministrationPage = lazy(() => import('../../pages/fpa/AdministrationPage'))

const LD = <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />
const TB = <Table2 size={17} strokeWidth={1.75} aria-hidden="true" />
const TU = <TrendingUp size={17} strokeWidth={1.75} aria-hidden="true" />
const GC = <GitCompareArrows size={17} strokeWidth={1.75} aria-hidden="true" />
const SC = <Scale size={17} strokeWidth={1.75} aria-hidden="true" />
const CC = <CheckCircle2 size={17} strokeWidth={1.75} aria-hidden="true" />
const AD = <Settings2 size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'fpa',
  order: 75,
  nav: {
    label: 'FP&A',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(TrendingUp),
    accent: 'lune',
    items: [
      { to: '/fpa/dashboard', label: 'Tableau de bord', icon: LD, roles: ROLES },
      { to: '/fpa/saisie', label: 'Saisie budgétaire', icon: TB, roles: ROLES },
      { to: '/fpa/soumissions', label: 'Soumissions', icon: CC, roles: ROLES },
      { to: '/fpa/previsions', label: 'Prévisions glissantes', icon: TU, roles: ROLES },
      { to: '/fpa/scenarios', label: 'Scénarios', icon: GC, roles: ROLES },
      { to: '/fpa/variance', label: 'Analyse des écarts', icon: SC, roles: ROLES },
      { to: '/fpa/administration', label: 'Administration', icon: AD, roles: ROLES },
    ],
  },
  titles: [
    ['/fpa/dashboard', 'Tableau de bord FP&A'],
    ['/fpa/saisie', 'Saisie budgétaire'],
    ['/fpa/soumissions', 'Soumissions budgétaires'],
    ['/fpa/previsions', 'Prévisions glissantes'],
    ['/fpa/scenarios', 'Scénarios what-if'],
    ['/fpa/variance', 'Analyse des écarts'],
    ['/fpa/administration', 'Administration FP&A'],
  ],
  sectionLabels: { fpa: 'FP&A' },
  routes: [
    { path: '/fpa/dashboard', component: DashboardPage, roles: ROLES },
    { path: '/fpa/saisie', component: SaisiePage, roles: ROLES },
    { path: '/fpa/soumissions', component: SoumissionsBudgetPage, roles: ROLES },
    { path: '/fpa/previsions', component: PrevisionsPage, roles: ROLES },
    { path: '/fpa/scenarios', component: ScenariosPage, roles: ROLES },
    { path: '/fpa/variance', component: VariancePage, roles: ROLES },
    { path: '/fpa/administration', component: AdministrationPage, roles: ROLES },
  ],
}
