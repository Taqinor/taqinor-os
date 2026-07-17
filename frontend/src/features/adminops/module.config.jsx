/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas. */
import { createElement, lazy } from 'react'
import { HeartPulse, FlaskConical, Package, BarChart3, Settings, Stethoscope } from 'lucide-react'

/* ============================================================================
   NTADM6/12/15/17/23/33 — Configuration du module « Administration ». Nav gatée
   Administrateur : health score, sandbox, packages de config, adoption,
   diagnostic, réglages.
   ========================================================================== */

const ROLES = ['admin']

const HealthScorePage = lazy(() => import('./HealthScorePage'))
const SandboxPage = lazy(() => import('./SandboxPage'))
const ConfigPackagesPage = lazy(() => import('./ConfigPackagesPage'))
const AdoptionPage = lazy(() => import('./AdoptionPage'))
const DiagnosticPage = lazy(() => import('./DiagnosticPage'))
const AdminSettingsPage = lazy(() => import('./AdminSettingsPage'))

// createElement pour ne PAS déclarer de « composant » dans un fichier de config.
const icon = (Comp) =>
  createElement(Comp, { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' })

export default {
  key: 'adminops',
  order: 93,
  nav: {
    label: 'ADMINISTRATION',
    accent: 'lune',
    items: [
      { to: '/admin/sante', label: 'Santé du compte', icon: icon(HeartPulse), roles: ROLES },
      { to: '/admin/sandbox', label: 'Sandbox', icon: icon(FlaskConical), roles: ROLES },
      { to: '/admin/config-packages', label: 'Packages config', icon: icon(Package), roles: ROLES },
      { to: '/admin/adoption', label: 'Adoption', icon: icon(BarChart3), roles: ROLES },
      { to: '/admin/diagnostic', label: 'Diagnostic', icon: icon(Stethoscope), roles: ROLES },
      { to: '/admin/reglages-admin', label: 'Réglages admin', icon: icon(Settings), roles: ROLES },
    ],
  },
  titles: [
    ['/admin/sante', 'Santé du compte'],
    ['/admin/sandbox', 'Environnements sandbox'],
    ['/admin/config-packages', 'Packages de configuration'],
    ['/admin/adoption', "Analytics d'adoption"],
    ['/admin/diagnostic', 'Diagnostic tenant'],
    ['/admin/reglages-admin', 'Réglages Administration'],
  ],
  sectionLabels: { admin: 'Administration' },
  routes: [
    { path: '/admin/sante', component: HealthScorePage, roles: ROLES },
    { path: '/admin/sandbox', component: SandboxPage, roles: ROLES },
    { path: '/admin/config-packages', component: ConfigPackagesPage, roles: ROLES },
    { path: '/admin/adoption', component: AdoptionPage, roles: ROLES },
    { path: '/admin/diagnostic', component: DiagnosticPage, roles: ROLES },
    { path: '/admin/reglages-admin', component: AdminSettingsPage, roles: ROLES },
  ],
}
