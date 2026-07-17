/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  Table2, TrendingUp, GitCompareArrows, Scale, LayoutDashboard,
} from 'lucide-react'

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

const LD = <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />
const TB = <Table2 size={17} strokeWidth={1.75} aria-hidden="true" />
const TU = <TrendingUp size={17} strokeWidth={1.75} aria-hidden="true" />
const GC = <GitCompareArrows size={17} strokeWidth={1.75} aria-hidden="true" />
const SC = <Scale size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'fpa',
  order: 75,
  nav: {
    label: 'FP&A',
    accent: 'lune',
    items: [
      { to: '/fpa/dashboard', label: 'Tableau de bord', icon: LD, roles: ROLES },
      { to: '/fpa/saisie', label: 'Saisie budgétaire', icon: TB, roles: ROLES },
      { to: '/fpa/previsions', label: 'Prévisions glissantes', icon: TU, roles: ROLES },
      { to: '/fpa/scenarios', label: 'Scénarios', icon: GC, roles: ROLES },
      { to: '/fpa/variance', label: 'Analyse des écarts', icon: SC, roles: ROLES },
    ],
  },
  titles: [
    ['/fpa/dashboard', 'Tableau de bord FP&A'],
    ['/fpa/saisie', 'Saisie budgétaire'],
    ['/fpa/previsions', 'Prévisions glissantes'],
    ['/fpa/scenarios', 'Scénarios what-if'],
    ['/fpa/variance', 'Analyse des écarts'],
  ],
  sectionLabels: { fpa: 'FP&A' },
  routes: [
    { path: '/fpa/dashboard', component: DashboardPage, roles: ROLES },
    { path: '/fpa/saisie', component: SaisiePage, roles: ROLES },
    { path: '/fpa/previsions', component: PrevisionsPage, roles: ROLES },
    { path: '/fpa/scenarios', component: ScenariosPage, roles: ROLES },
    { path: '/fpa/variance', component: VariancePage, roles: ROLES },
  ],
}
