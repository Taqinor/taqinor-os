/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants : le
   fast-refresh ne s'y applique pas. */
import { lazy } from 'react'
import { Leaf } from 'lucide-react'

/* ============================================================================
   NTESG6 — Configuration du module ESG / RSE (reporting ESG/durabilité
   consolidé). Déposé ici, collecté automatiquement par
   `router/moduleRoutes.jsx` (glob) — AUCUNE modification du routeur/Sidebar.
   Distinct de `/qhse/environnement` (saisie environnement QHSE) : ce module
   consolide la COUCHE reporting (périodes figées, agrégation cross-app,
   catalogue GRI-lite) — voir `apps/esg` côté backend.
   ========================================================================== */

const EsgCockpit = lazy(() => import('../../pages/esg/EsgCockpit'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'esg',
  order: 62,
  nav: {
    label: 'ESG / RSE',
    accent: 'success',
    items: [
      { to: '/esg', label: 'Cockpit ESG', icon: <Leaf size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/esg', 'Cockpit ESG'],
  ],
  sectionLabels: { esg: 'ESG / RSE' },
  routes: [
    { path: '/esg', component: EsgCockpit, roles: ROLES },
  ],
}

export default config
