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
   page, libellés de fil d'Ariane et routes lazy.

   WIR171 — tout était gaté « responsable / admin » alors que le serveur gate
   les projets par `projet_voir` / `projet_gerer` (YRBAC3) via
   `HasPermissionOrLegacy` : un Commercial / Technicien / Viewer porte
   `projet_voir` tout en relevant du palier 'normal' — le serveur lui répondait
   200 pendant que la coquille le renvoyait en 403. Chaque entrée déclare donc
   la permission de LECTURE + `permRepliPalier` (sémantique serveur exacte, cf.
   `router/moduleGating.js`) ; le palier élargi ne sert plus que de repli
   documentaire (comptes LÉGACY sans rôle fin).
   ========================================================================== */

const ROLES = ['normal', 'responsable', 'admin']
// WIR171 — gate commun à toutes les entrées/routes du module (étalé par `...`).
const GATE = { roles: ROLES, perm: 'projet_voir', permRepliPalier: true }

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
      { to: '/projets', label: 'Projets', icon: <FolderKanban size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/planning', label: 'Planning', icon: <CalendarRange size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/taches', label: 'Tâches', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/taches/mes-taches', label: 'Mes tâches', icon: <ListChecks size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/temps', label: 'Temps', icon: <Clock3 size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/ressources', label: 'Ressources', icon: <Users size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/budget', label: 'Budget & P&L', icon: <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/risques', label: 'Risques & CR', icon: <ShieldAlert size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
      { to: '/projets/parametres', label: 'Paramètres avancés', icon: <Settings2 size={17} strokeWidth={1.75} aria-hidden="true" />, ...GATE },
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
    { path: '/projets/planning', component: PlanningPage, ...GATE },
    { path: '/projets/taches/mes-taches', component: MesTachesPage, ...GATE },
    { path: '/projets/taches', component: TachesPage, ...GATE },
    { path: '/projets/temps', component: TempsPage, ...GATE },
    { path: '/projets/ressources', component: RessourcesPage, ...GATE },
    { path: '/projets/budget', component: BudgetPage, ...GATE },
    { path: '/projets/risques', component: RisquesPage, ...GATE },
    { path: '/projets/parametres', component: ParametresAvances, ...GATE },
    { path: '/projets/:id', component: ProjetDetailPage, ...GATE },
    { path: '/projets', component: ProjetsPage, ...GATE },
  ],
}
