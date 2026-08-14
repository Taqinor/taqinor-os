/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants. */
import { lazy } from 'react'
import { TrendingUp, ShoppingCart } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   Groupe NTSCM — Planification supply chain (prévision de demande
   saisonnière, classification ABC, politiques de stock, tableau de bord de
   réappro consolidé, cycle S&OP). Clé backend `scm` (apps/scm/apps.py).
   ========================================================================== */

const ReapproPage = lazy(() => import('../../pages/scm/ReapproPage'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'scm',
  order: 64,
  nav: {
    label: 'Planification supply',
    icon: appGlyph(TrendingUp),
    accent: 'info',
    items: [
      { to: '/scm/reappro', label: 'Tableau de bord réappro', icon: <ShoppingCart size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/scm/reappro', 'Tableau de bord réappro'],
  ],
  sectionLabels: { scm: 'Planification supply chain' },
  routes: [
    { path: '/scm/reappro', component: ReapproPage, roles: ROLES },
  ],
}

export default config
