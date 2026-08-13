/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `moduleRoutes.jsx` via glob — pas un module de composants : la règle
   fast-refresh ne s'y applique pas (cf. `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  LayoutDashboard, Users, CalendarDays, Clock,
  GraduationCap, Briefcase, ShieldAlert, UserCircle,
  Car, FileText, CalendarPlus, ClipboardCheck, ListChecks,
  Calculator, LogOut, Wallet, Clock3, CalendarOff, Milestone,
  DoorClosed, Gift, SlidersHorizontal,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX21–UX28 — Registre du module RH (ressources humaines).
   ----------------------------------------------------------------------------
   Un seul fichier déposé dans `src/features/rh/` : `moduleRoutes.jsx` le
   collecte automatiquement (glob) et construit nav + routes gatées, sans
   toucher au routeur ni à la Sidebar. Tout le back-office RH est réservé
   Responsable/Administrateur ; SEUL le portail self-service (UX28) est ouvert à
   tous les rôles (aucune clé `roles` → route authentifiée simple).

   PACT81-94 (07/08/2026) — 14 « écrans manquants » : le backend existait déjà
   (modèles/vues/services testés) mais aucun écran ne l'appelait. Chacun gagne
   ici sa propre route + entrée de nav (jamais un onglet caché dans un autre
   écran non listé dans les fichiers de la tâche) — cohérent avec le reste du
   module (Compétences, HSE…) qui suit le même patron un-écran-par-domaine.
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
// PACT81-94 — écrans manquants (backend testé, jamais consommé).
const VehiculesPermis = lazy(() => import('./VehiculesPermis.jsx'))
const DepotsBulletinsPaie = lazy(() => import('./DepotsBulletinsPaie.jsx'))
const DemandesAllocation = lazy(() => import('./DemandesAllocation.jsx'))
const DemandesRh = lazy(() => import('./DemandesRh.jsx'))
const ModelesIntegration = lazy(() => import('./ModelesIntegration.jsx'))
const ElementsVariablesPaie = lazy(() => import('./ElementsVariablesPaie.jsx'))
const EntretiensSortie = lazy(() => import('./EntretiensSortie.jsx'))
const GrillesSalariales = lazy(() => import('./GrillesSalariales.jsx'))
const HorairesTravail = lazy(() => import('./HorairesTravail.jsx'))
const JoursBloquesConge = lazy(() => import('./JoursBloquesConge.jsx'))
const ParcoursEmploye = lazy(() => import('./ParcoursEmploye.jsx'))
const FermeturesCollectives = lazy(() => import('./FermeturesCollectives.jsx'))
const PrimesIndemnites = lazy(() => import('./PrimesIndemnites.jsx'))
const ReglagesRh = lazy(() => import('./ReglagesRh.jsx'))

// Rôles autorisés pour le back-office RH.
const RH = ['responsable', 'admin']

export default {
  key: 'rh',
  order: 40,
  nav: {
    label: 'RH',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Users),
    accent: 'azur', // VX8 — RH/paie = accent azur (dérivé)
    items: [
      { to: '/rh', label: 'Cockpit RH', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/employes', label: 'Employés', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/conges', label: 'Congés & absences', icon: <CalendarDays size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/temps', label: 'Temps & présence', icon: <Clock size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/competences', label: 'Compétences', icon: <GraduationCap size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/recrutement', label: 'EPI & recrutement', icon: <Briefcase size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/hse', label: 'HSE', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      // PACT81-94 — écrans manquants (backend déjà testé).
      { to: '/rh/vehicules-permis', label: 'Véhicules & permis', icon: <Car size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/bulletins-paie', label: 'Bulletins de paie', icon: <FileText size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/demandes-allocation', label: 'Demandes d’allocation', icon: <CalendarPlus size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/demandes-rh', label: 'Demandes RH (attestations)', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/modeles-integration', label: 'Modèles d’intégration', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/elements-variables-paie', label: 'Éléments variables de paie', icon: <Calculator size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/entretiens-sortie', label: 'Entretiens de sortie', icon: <LogOut size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/grilles-salariales', label: 'Grilles salariales', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/horaires-travail', label: 'Horaires de travail', icon: <Clock3 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/jours-bloques-conge', label: 'Jours bloqués (congés)', icon: <CalendarOff size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/parcours-employes', label: 'Parcours des employés', icon: <Milestone size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/fermetures-collectives', label: 'Fermetures collectives', icon: <DoorClosed size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/primes-indemnites', label: 'Primes & indemnités', icon: <Gift size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
      { to: '/rh/reglages', label: 'Réglages RH', icon: <SlidersHorizontal size={17} strokeWidth={1.75} aria-hidden="true" />, roles: RH },
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
    ['/rh/vehicules-permis', 'Véhicules & permis'],
    ['/rh/bulletins-paie', 'Bulletins de paie'],
    ['/rh/demandes-allocation', 'Demandes d’allocation'],
    ['/rh/demandes-rh', 'Demandes RH (attestations)'],
    ['/rh/modeles-integration', 'Modèles d’intégration'],
    ['/rh/elements-variables-paie', 'Éléments variables de paie'],
    ['/rh/entretiens-sortie', 'Entretiens de sortie'],
    ['/rh/grilles-salariales', 'Grilles salariales'],
    ['/rh/horaires-travail', 'Horaires de travail'],
    ['/rh/jours-bloques-conge', 'Jours bloqués (congés)'],
    ['/rh/parcours-employes', 'Parcours des employés'],
    ['/rh/fermetures-collectives', 'Fermetures collectives'],
    ['/rh/primes-indemnites', 'Primes & indemnités'],
    ['/rh/reglages', 'Réglages RH'],
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
    // PACT81-94 — écrans manquants (backend déjà testé).
    { path: '/rh/vehicules-permis', component: VehiculesPermis, roles: RH },
    { path: '/rh/bulletins-paie', component: DepotsBulletinsPaie, roles: RH },
    { path: '/rh/demandes-allocation', component: DemandesAllocation, roles: RH },
    { path: '/rh/demandes-rh', component: DemandesRh, roles: RH },
    { path: '/rh/modeles-integration', component: ModelesIntegration, roles: RH },
    { path: '/rh/elements-variables-paie', component: ElementsVariablesPaie, roles: RH },
    { path: '/rh/entretiens-sortie', component: EntretiensSortie, roles: RH },
    { path: '/rh/grilles-salariales', component: GrillesSalariales, roles: RH },
    { path: '/rh/horaires-travail', component: HorairesTravail, roles: RH },
    { path: '/rh/jours-bloques-conge', component: JoursBloquesConge, roles: RH },
    { path: '/rh/parcours-employes', component: ParcoursEmploye, roles: RH },
    { path: '/rh/fermetures-collectives', component: FermeturesCollectives, roles: RH },
    { path: '/rh/primes-indemnites', component: PrimesIndemnites, roles: RH },
    { path: '/rh/reglages', component: ReglagesRh, roles: RH },
    // UX28 — portail self-service : tous rôles (authLoader simple).
    { path: '/rh/portail', component: Portail },
  ],
}
