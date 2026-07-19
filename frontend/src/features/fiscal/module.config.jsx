/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants. */
import { lazy } from 'react'
import { ShieldCheck } from 'lucide-react'

/* ============================================================================
   WIR106 — Module Conformité fiscale (NTMAR). Écran « Calendrier fiscal /
   Conformité » (feu tricolore NTMAR16 + échéances). NE DUPLIQUE PAS la gestion
   des obligations fiscales, qui reste dans le module Comptabilité (XACC9) — cet
   écran est une vue conformité en lecture seule (réconciliation WIR106).
   ========================================================================== */

const ConformiteFiscale = lazy(() => import('../../pages/fiscal/ConformiteFiscale'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'fiscal',
  order: 63,
  nav: {
    label: 'Conformité fiscale',
    accent: 'warning',
    items: [
      { to: '/fiscal/conformite', label: 'Conformité fiscale', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/fiscal/conformite', 'Conformité fiscale'],
  ],
  sectionLabels: { fiscal: 'Conformité fiscale' },
  routes: [
    { path: '/fiscal/conformite', component: ConformiteFiscale, roles: ROLES },
  ],
}

export default config
