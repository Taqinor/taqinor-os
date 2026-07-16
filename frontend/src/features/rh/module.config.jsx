/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `moduleRoutes.jsx` via glob — pas un module de composants : la règle
   fast-refresh ne s'y applique pas (cf. `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  LayoutDashboard, Users, CalendarDays, Clock,
  GraduationCap, Briefcase, ShieldAlert, UserCircle,
} from 'lucide-react'

/* ============================================================================
   UX21–UX28 — Registre du module RH (ressources humaines).
   ----------------------------------------------------------------------------
   Un seul fichier déposé dans `src/features/rh/` : `moduleRoutes.jsx` le
   collecte automatiquement (glob) et construit nav + routes gatées, sans
   toucher au routeur ni à la Sidebar. Tout le back-office RH est réservé
   Responsable/Administrateur ; SEUL le portail self-service (UX28) est ouvert à
   tous les rôles (aucune clé `roles` → route authentifiée simple).
   ========================================================================== */

const RhCockpit = lazy(() => import('./RhCockpit.jsx'))
const EmployeList = lazy(() => import('./EmployeList.jsx'))
const EmployeDetail = lazy(() => import('./EmployeDetail.jsx'))
const Conges = lazy(() => import('./Conges.jsx'))
const Temps = lazy(() => import('./Temps.jsx'))
const Competences = lazy(() => import('./Competences.jsx'))
const Recrutement = lazy(() => import('./Recrutement.jsx'))
const Hse = lazy(() => import('./Hse.jsx'))
const Portail = lazy(() => import('./Portail.jsx'))

// Rôles autorisés pour le back-office RH.
const RH = ['responsable', 'admin']

export default {
  key: 'rh',
  order: 40,
  nav: {
    label: 'RH',
    accent: 'azur', // VX8 — RH/paie = accent azur (dérivé)
    items: [
      { to: '/rh', label: 'Cockpit RH', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/employes', label: 'Employés', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/conges', label: 'Congés & absences', icon: <CalendarDays size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/temps', label: 'Temps & présence', icon: <Clock size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/competences', label: 'Compétences', icon: <GraduationCap size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/recrutement', label: 'EPI & recrutement', icon: <Briefcase size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/hse', label: 'HSE', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      // UX28 — portail self-service : tous rôles. La Sidebar filtre via
      // `it.roles.includes(role)` → chaque item DOIT porter `roles` (sinon crash).
      { to: '/rh/portail', label: 'Mon portail', icon: <UserCircle size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['normal', 'responsable', 'admin'] },
    ],
  },
  titles: [
    ['/rh/employes', 'Employés'],
    ['/rh/conges', 'Congés & absences'],
    ['/rh/temps', 'Temps & présence'],
    ['/rh/competences', 'Compétences & habilitations'],
    ['/rh/recrutement', 'EPI, recrutement & évaluations'],
    ['/rh/hse', 'HSE'],
    ['/rh/portail', 'Mon portail RH'],
    ['/rh', 'Cockpit RH'],
  ],
  sectionLabels: { rh: 'RH' },
  routes: [
    { path: '/rh', component: RhCockpit, roles: RH },
    { path: '/rh/employes', component: EmployeList, roles: RH },
    { path: '/rh/employes/:id', component: EmployeDetail, roles: RH },
    { path: '/rh/conges', component: Conges, roles: RH },
    { path: '/rh/temps', component: Temps, roles: RH },
    { path: '/rh/competences', component: Competences, roles: RH },
    { path: '/rh/recrutement', component: Recrutement, roles: RH },
    { path: '/rh/hse', component: Hse, roles: RH },
    // UX28 — portail self-service : tous rôles (authLoader simple).
    { path: '/rh/portail', component: Portail },
  ],
}
