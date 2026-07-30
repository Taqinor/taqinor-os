/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté
   par `router/moduleRoutes.jsx` via glob — même dérogation que
   `features/agriculture/module.config.jsx` / `features/sante/module.config.jsx`. */
import { lazy } from 'react'
import {
  CalendarCheck, CalendarDays, ClipboardCheck, GraduationCap, School,
  ShieldAlert, Users, Utensils, Wallet,
} from 'lucide-react'

/* ============================================================================
   WIR143 — Configuration du module « Éducation » (école/établissement
   scolaire), auto-enregistrée. Backend NTEDU complet et testé ; ce lot pose
   le PREMIER frontend (aucun fichier n'existait avant). Écrans en
   `src/pages/education/*` chargés en lazy (patron agriculture/flotte).
   ----------------------------------------------------------------------------
   P1 : structure classes, familles/élèves + inscriptions, échéancier
   scolarité, présences bulk, notes, emploi du temps, cantine, discipline.
   Certificat/export sont des actions DANS les écrans P1 (pas d'écran dédié).
   Le cycle FACTUREE/PAYEE et ses écrans restent hors périmètre (NTEDU9/11,
   ouverts). Gaté comme les autres modules internes (normal/responsable/
   admin) en attendant un grain RBAC dédié.
   ========================================================================== */

const StructurePage = lazy(() => import('../../pages/education/StructurePage'))
const FamillesElevesPage = lazy(() => import('../../pages/education/FamillesElevesPage'))
const InscriptionsPage = lazy(() => import('../../pages/education/InscriptionsPage'))
const EcheancierPage = lazy(() => import('../../pages/education/EcheancierPage'))
const PresencesPage = lazy(() => import('../../pages/education/PresencesPage'))
const NotesPage = lazy(() => import('../../pages/education/NotesPage'))
const EmploiDuTempsPage = lazy(() => import('../../pages/education/EmploiDuTempsPage'))
const CantinePage = lazy(() => import('../../pages/education/CantinePage'))
const DisciplinePage = lazy(() => import('../../pages/education/DisciplinePage'))

const ROLES = ['normal', 'responsable', 'admin']

const config = {
  key: 'education',
  order: 96,
  nav: {
    label: 'ÉDUCATION',
    accent: 'primary',
    items: [
      { to: '/education/structure', label: 'Structure', icon: <School size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ['responsable', 'admin'] },
      { to: '/education/familles-eleves', label: 'Familles & élèves', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/inscriptions', label: 'Inscriptions', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/echeancier', label: 'Échéancier scolarité', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/presences', label: 'Présences', icon: <CalendarCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/notes', label: 'Notes', icon: <GraduationCap size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/emploi-du-temps', label: 'Emploi du temps', icon: <CalendarDays size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/cantine', label: 'Cantine', icon: <Utensils size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/education/discipline', label: 'Discipline', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  titles: [
    ['/education/structure', 'Structure de l’établissement'],
    ['/education/familles-eleves', 'Familles & élèves'],
    ['/education/inscriptions', 'Inscriptions'],
    ['/education/echeancier', 'Échéancier scolarité'],
    ['/education/presences', 'Présences'],
    ['/education/notes', 'Notes'],
    ['/education/emploi-du-temps', 'Emploi du temps'],
    ['/education/cantine', 'Cantine'],
    ['/education/discipline', 'Discipline'],
  ],
  sectionLabels: { education: 'Éducation' },
  routes: [
    { path: '/education/structure', component: StructurePage, roles: ['responsable', 'admin'] },
    { path: '/education/familles-eleves', component: FamillesElevesPage, roles: ROLES },
    { path: '/education/inscriptions', component: InscriptionsPage, roles: ROLES },
    { path: '/education/echeancier', component: EcheancierPage, roles: ROLES },
    { path: '/education/presences', component: PresencesPage, roles: ROLES },
    { path: '/education/notes', component: NotesPage, roles: ROLES },
    { path: '/education/emploi-du-temps', component: EmploiDuTempsPage, roles: ROLES },
    { path: '/education/cantine', component: CantinePage, roles: ROLES },
    { path: '/education/discipline', component: DisciplinePage, roles: ROLES },
  ],
}

export default config
