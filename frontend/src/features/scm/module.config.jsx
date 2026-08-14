/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants. */
import { lazy } from 'react'
import { LineChart, ShoppingCart, CalendarClock, LayoutDashboard, ListPlus, Rocket } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   Groupe NTSCM — Planification supply chain (prévision de demande
   saisonnière, classification ABC, politiques de stock, tableau de bord de
   réappro consolidé, cycle S&OP). Clé backend `scm` (apps/scm/apps.py).
   ========================================================================== */

const ReapproPage = lazy(() => import('../../pages/scm/ReapproPage'))
const CyclesSopListPage = lazy(() => import('../../pages/scm/CyclesSopListPage'))
const CycleSopPage = lazy(() => import('../../pages/scm/CycleSopPage'))
// NTSCM28 — tableau de bord SCM exécutif (KPI de synthèse).
const ScmDashboardPage = lazy(() => import('../../pages/scm/ScmDashboardPage'))
// NTSCM30 — assistant guidé « Créer une politique de stock » en lot.
const PolitiqueStockWizardPage = lazy(
  () => import('../../pages/scm/PolitiqueStockWizardPage'))
// NTSCM31 — assistant guidé « Lancer un cycle S&OP ».
const CycleSopWizardPage = lazy(() => import('../../pages/scm/CycleSopWizardPage'))

const ROLES = ['responsable', 'admin']
// NTSCM15 — le cycle S&OP (Demande/Offre/Finance, dont le CA/marge en clair)
// reste visible au SEUL rôle Administrateur/Directeur — plus restreint que
// le reste du module.
const ROLES_SOP = ['admin']

const config = {
  key: 'scm',
  order: 64,
  nav: {
    label: 'Planification supply',
    icon: appGlyph(LineChart),
    // VX8 — supply chain/logistique = accent brass (dérivé), comme Transport ;
    // `accent: 'info'` n'existe pas dans tokens.css (cf. core/module.config.jsx)
    // et rendait une tuile SANS fond.
    accent: 'brass',
    items: [
      { to: '/scm/dashboard', label: 'Tableau de bord exécutif', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/scm/reappro', label: 'Tableau de bord réappro', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/scm/politiques-stock/nouveau', label: 'Nouvelle politique de stock', icon: <ListPlus size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/scm/sop', label: 'Cycle S&OP', icon: <CalendarClock size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_SOP },
      { to: '/scm/sop/nouveau', label: 'Lancer un cycle S&OP', icon: <Rocket size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_SOP },
    ],
  },
  titles: [
    ['/scm/dashboard', 'Tableau de bord SCM exécutif'],
    ['/scm/reappro', 'Tableau de bord réappro'],
    ['/scm/politiques-stock/nouveau', 'Nouvelle politique de stock'],
    ['/scm/sop', 'Cycles S&OP'],
    ['/scm/sop/nouveau', 'Lancer un cycle S&OP'],
    // Préfixe plus long (avec le slash final) : gagne sur `/scm/sop`
    // ci-dessus pour toute fiche `/scm/sop/<id>` (plus long préfixe l'emporte,
    // voir `titleFor` dans `routes.meta.js`).
    ['/scm/sop/', 'Cycle S&OP'],
  ],
  sectionLabels: { scm: 'Planification supply chain' },
  routes: [
    { path: '/scm/dashboard', component: ScmDashboardPage, roles: ROLES },
    { path: '/scm/reappro', component: ReapproPage, roles: ROLES },
    { path: '/scm/politiques-stock/nouveau', component: PolitiqueStockWizardPage, roles: ROLES },
    { path: '/scm/sop', component: CyclesSopListPage, roles: ROLES_SOP },
    { path: '/scm/sop/nouveau', component: CycleSopWizardPage, roles: ROLES_SOP },
    { path: '/scm/sop/:id', component: CycleSopPage, roles: ROLES_SOP },
  ],
}

export default config
