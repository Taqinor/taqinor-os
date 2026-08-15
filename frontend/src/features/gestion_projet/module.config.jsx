/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (voir moduleRoutes.jsx). */
import { lazy } from 'react'
import {
  FolderKanban, CalendarRange, Users, Wallet, ShieldAlert, Clock3, ListChecks,
  Settings2,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX38–UX42 — Configuration du module « Gestion de projet ».
   ----------------------------------------------------------------------------
   Fichier UNIQUE d'enregistrement (auto-collecté par
   `src/router/moduleRoutes.jsx` via import.meta.glob) : nav Sidebar, titres de
   page, libellés de fil d'Ariane et routes lazy. Aucun autre fichier partagé
   n'est touché. Tout est gaté « responsable / admin ».
   ========================================================================== */

const ROLES = ['responsable', 'admin']
// WIR171 — la LECTURE des projets est gatee serveur par `projet_voir`
// (`HasPermissionOrLegacy`, permission accordee aux 7 roles) : l ecran restait
// gate responsable/admin, invisible au Commercial malgre son 200. Regle unique :
// `router/navPermission.js`. Les Parametres avances restent au palier ROLES.
const LECTURE = {
  roles: ['normal', 'responsable', 'admin'],
  perm: 'projet_voir',
  permLegacyRoles: ROLES,
}

const ProjetsPage = lazy(() => import('./pages/ProjetsPage'))
const ProjetDetailPage = lazy(() => import('./pages/ProjetDetailPage'))
const PlanningPage = lazy(() => import('./pages/PlanningPage'))
const RessourcesPage = lazy(() => import('./pages/RessourcesPage'))
const BudgetPage = lazy(() => import('./pages/BudgetPage'))
const RisquesPage = lazy(() => import('./pages/RisquesPage'))
const TempsPage = lazy(() => import('./pages/TempsPage'))
const TachesPage = lazy(() => import('./pages/TachesPage'))
// PACT78 — paramètres avancés : verrous de mois (temps), lien de portail
// projet, gabarits de tâches récurrentes.
const ParametresAvances = lazy(() => import('./ParametresAvances'))
const MesTachesPage = lazy(() => import('./pages/TachesPage').then((mod) => {
  const TachesPageComponent = mod.default
  return { default: () => <TachesPageComponent mesTaches /> }
}))

export default {
  key: 'gestion_projet',
  order: 55,
  nav: {
    label: 'PROJETS',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(FolderKanban),
    accent: 'warning', // VX8 — pilotage/reporting = accent warning (dérivé)
    items: [
      { to: '/projets', label: 'Projets', icon: <FolderKanban size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/planning', label: 'Planning', icon: <CalendarRange size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/taches', label: 'Tâches', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/taches/mes-taches', label: 'Mes tâches', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/temps', label: 'Temps', icon: <Clock3 size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/ressources', label: 'Ressources', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/budget', label: 'Budget & P&L', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/risques', label: 'Risques & CR', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, ...LECTURE },
      { to: '/projets/parametres', label: 'Paramètres avancés', icon: <Settings2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta : du plus SPÉCIFIQUE au plus général.
  titles: [
    ['/projets/planning', 'Planning'],
    ['/projets/taches/mes-taches', 'Mes tâches'],
    ['/projets/taches', 'Tâches'],
    ['/projets/temps', 'Saisie des temps'],
    ['/projets/ressources', 'Ressources & capacité'],
    ['/projets/budget', 'Budget & P&L'],
    ['/projets/risques', 'Risques, actions & CR'],
    ['/projets/parametres', 'Paramètres avancés du module Projet'],
    ['/projets', 'Projets'],
  ],
  sectionLabels: { projets: 'Projets' },
  routes: [
    // Les sous-routes fixes AVANT la route de détail paramétrée.
    { path: '/projets/planning', component: PlanningPage, ...LECTURE },
    { path: '/projets/taches/mes-taches', component: MesTachesPage, ...LECTURE },
    { path: '/projets/taches', component: TachesPage, ...LECTURE },
    { path: '/projets/temps', component: TempsPage, ...LECTURE },
    { path: '/projets/ressources', component: RessourcesPage, ...LECTURE },
    { path: '/projets/budget', component: BudgetPage, ...LECTURE },
    { path: '/projets/risques', component: RisquesPage, ...LECTURE },
    { path: '/projets/parametres', component: ParametresAvances, roles: ROLES },
    { path: '/projets/:id', component: ProjetDetailPage, ...LECTURE },
    { path: '/projets', component: ProjetsPage, ...LECTURE },
  ],
}
