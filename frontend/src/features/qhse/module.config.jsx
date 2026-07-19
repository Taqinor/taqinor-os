/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants : le
   fast-refresh ne s'y applique pas. */
import { lazy } from 'react'
import {
  ShieldCheck, AlertOctagon, ClipboardCheck, ShieldAlert, Leaf, UserCheck,
} from 'lucide-react'

/* ============================================================================
   UX29–UX33 — Configuration du module QHSE (Qualité · Hygiène · Sécurité ·
   Environnement). Déposé ici, il est collecté automatiquement par
   `router/moduleRoutes.jsx` (glob) — aucune modification du routeur/Sidebar.
   Toutes les routes et entrées de menu sont gatées `['responsable','admin']`.
   ========================================================================== */

const QhseCockpit = lazy(() => import('./QhseCockpit'))
const NonConformites = lazy(() => import('./NonConformites'))
const Inspections = lazy(() => import('./Inspections'))
const Risques = lazy(() => import('./Risques'))
const Environnement = lazy(() => import('./Environnement'))
// WIR115 — check-in sécurité (technicien seul sur site) + SCAR fournisseur.
const CheckinsSecurite = lazy(() => import('./CheckinsSecurite'))

const ROLES = ['responsable', 'admin']

const config = {
  key: 'qhse',
  order: 60,
  nav: {
    label: 'QHSE',
    accent: 'destructive', // VX8 — sécurité/risque = accent destructive (dérivé)
    items: [
      { to: '/qhse', label: 'Cockpit QHSE', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/qhse/non-conformites', label: 'Non-conformités', icon: <AlertOctagon size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/qhse/inspections', label: 'Inspections & audits', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/qhse/risques', label: 'Risques & permis', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/qhse/environnement', label: 'Environnement & ESG', icon: <Leaf size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/qhse/checkins-securite', label: 'Check-ins sécurité', icon: <UserCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général.
  titles: [
    ['/qhse/non-conformites', 'Non-conformités — QHSE'],
    ['/qhse/inspections', 'Inspections & audits — QHSE'],
    ['/qhse/risques', 'Risques & permis — QHSE'],
    ['/qhse/environnement', 'Environnement & ESG — QHSE'],
    ['/qhse/checkins-securite', 'Check-ins sécurité — QHSE'],
    ['/qhse', 'Cockpit QHSE'],
  ],
  sectionLabels: { qhse: 'QHSE' },
  routes: [
    { path: '/qhse', component: QhseCockpit, roles: ROLES },
    { path: '/qhse/non-conformites', component: NonConformites, roles: ROLES },
    { path: '/qhse/inspections', component: Inspections, roles: ROLES },
    { path: '/qhse/risques', component: Risques, roles: ROLES },
    { path: '/qhse/environnement', component: Environnement, roles: ROLES },
    { path: '/qhse/checkins-securite', component: CheckinsSecurite, roles: ROLES },
  ],
}

export default config
