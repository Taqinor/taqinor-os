/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob — pas un module de composants. */
import { lazy } from 'react'
import { Activity, Calculator, Factory, Gauge, Wand2, Wrench } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   Groupe NTMFG — Production / MRP II. Moteur générique de production
   (postes de charge, gammes, ordres de fabrication capacitaires, MRP net,
   terminal atelier). DISTINCT de `/production` (monitoring photovoltaïque
   N51, déjà propriétaire de tout le préfixe `/production/*` côté module
   `installations`) — préfixe dédié `/mrp/*` (même racine que l'API
   `/api/django/mrp/…`) pour ÉVITER toute collision de route ou de libellé
   de fil d'Ariane avec ce module existant ; nommé « Atelier MRP » dans le
   menu pour la clarté (NTMFG9).
   ========================================================================== */

const OrdresFabricationPage = lazy(() => import('../../pages/mrp/OrdresFabricationPage'))
const GanttAtelier = lazy(() => import('../../pages/mrp/GanttAtelier'))
const TerminalAtelier = lazy(() => import('../../pages/mrp/TerminalAtelier'))
// NTMFG11 — rapport interne coût standard vs réel (admin/responsable).
const AnalyseCoutsPage = lazy(() => import('../../pages/mrp/AnalyseCoutsPage'))
// NTMFG12 — TRS/OEE par poste de charge.
const OeePage = lazy(() => import('../../pages/mrp/OeePage'))
// NTMFG26 — assistant guidé de création d'OF en 3 étapes.
const AssistantCreationOF = lazy(() => import('../../pages/mrp/AssistantCreationOF'))
// NTMFG27 — assistant guidé de création de gamme opératoire.
const AssistantCreationGamme = lazy(() => import('../../pages/mrp/AssistantCreationGamme'))

// 'normal' couvre le rôle Technicien de base (pas de rôle fin dédié dans le
// vocabulaire existant, cf. `installations/module.config.jsx`) — le terminal
// atelier (NTMFG8) doit rester accessible sans palier responsable/admin.
const ROLES = ['normal', 'responsable', 'admin']
const ROLES_ADMIN = ['responsable', 'admin']

const config = {
  key: 'mrp',
  order: 66,
  nav: {
    label: 'Atelier MRP',
    icon: appGlyph(Factory),
    // VX8 — production/atelier = accent success (dérivé), comme
    // Installations/BTP chantier/Flotte (terrain/opérations) ; `accent: 'info'`
    // n'existe pas dans tokens.css (cf. core/module.config.jsx) et rendait
    // une tuile SANS fond.
    accent: 'success',
    items: [
      { to: '/mrp/ordres-fabrication', label: 'Ordres de fabrication', icon: <Factory size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/mrp/assistant-creation-of', label: 'Assistant nouvel OF', icon: <Wand2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/mrp/assistant-nouvelle-gamme', label: 'Nouvelle gamme guidée', icon: <Wand2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/mrp/gantt', label: 'Gantt atelier', icon: <Gauge size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/mrp/terminal', label: 'Terminal atelier', icon: <Wrench size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/mrp/oee', label: 'TRS / OEE', icon: <Activity size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      // NTMFG11 — coût interne, jamais visible du rôle limité.
      { to: '/mrp/analyse-couts', label: 'Analyse des coûts', icon: <Calculator size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES_ADMIN },
    ],
  },
  titles: [
    ['/mrp/ordres-fabrication', 'Ordres de fabrication'],
    ['/mrp/assistant-creation-of', 'Assistant nouvel OF'],
    ['/mrp/assistant-nouvelle-gamme', 'Nouvelle gamme guidée'],
    ['/mrp/gantt', 'Gantt atelier'],
    ['/mrp/terminal', 'Terminal atelier'],
    ['/mrp/oee', 'TRS / OEE'],
    ['/mrp/analyse-couts', 'Analyse des coûts'],
  ],
  sectionLabels: { mrp: 'Atelier MRP' },
  routes: [
    { path: '/mrp/ordres-fabrication', component: OrdresFabricationPage, roles: ROLES },
    { path: '/mrp/assistant-creation-of', component: AssistantCreationOF, roles: ROLES },
    { path: '/mrp/assistant-nouvelle-gamme', component: AssistantCreationGamme, roles: ROLES },
    { path: '/mrp/gantt', component: GanttAtelier, roles: ROLES },
    { path: '/mrp/terminal', component: TerminalAtelier, roles: ROLES },
    { path: '/mrp/oee', component: OeePage, roles: ROLES },
    { path: '/mrp/analyse-couts', component: AnalyseCoutsPage, roles: ROLES_ADMIN },
  ],
}

export default config
