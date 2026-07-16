/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { Lightbulb } from 'lucide-react'

/* ============================================================================
   Groupe NTIDE — Config du module Innovation (boîte à idées interne, auto-
   enregistrée). Collectée par le registre ``router/moduleRoutes.jsx`` via glob
   (nav Sidebar, routes.meta, fil d'Ariane, route lazy).

   Liste/détail/proposer : ouverts à TOUT utilisateur connecté (« logged-in
   users only », NTIDE4/NTIDE5/NTIDE8 — aucun ``roles`` déclaré ⇒ authLoader
   seul). Tableau de bord : palier Directeur/Responsable (NTIDE6, gaté aussi
   côté serveur par ``IsAdminOrResponsableTier``).
   ========================================================================== */

const IdeesPage = lazy(() => import('./IdeesPage'))
const IdeeDetail = lazy(() => import('./IdeeDetail'))
const ProposerIdeePage = lazy(() => import('./ProposerIdeePage'))
const InnovationDashboard = lazy(() => import('./InnovationDashboard'))

const ADMIN_RESPONSABLE = ['responsable', 'admin']

const config = {
  key: 'innovation',
  order: 92,
  nav: {
    label: 'INNOVATION',
    accent: 'primary',
    items: [
      {
        to: '/innovation/idees',
        label: 'Boîte à idées',
        icon: <Lightbulb size={17} strokeWidth={1.75} aria-hidden="true" />,
      },
      {
        to: '/innovation/tableau-bord',
        label: 'Tableau de bord',
        icon: <Lightbulb size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ADMIN_RESPONSABLE,
      },
    ],
  },
  titles: [
    ['/innovation/idees', 'Boîte à idées'],
    ['/innovation/proposer', 'Proposer une idée'],
    ['/innovation/tableau-bord', 'Tableau de bord — Idées'],
  ],
  sectionLabels: { innovation: 'Innovation' },
  routes: [
    { path: '/innovation/idees', component: IdeesPage },
    { path: '/innovation/idees/:id', component: IdeeDetail },
    { path: '/innovation/proposer', component: ProposerIdeePage },
    { path: '/innovation/tableau-bord', component: InnovationDashboard, roles: ADMIN_RESPONSABLE },
  ],
}

export default config
