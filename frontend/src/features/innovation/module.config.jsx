/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { Lightbulb } from 'lucide-react'

/* ============================================================================
   Groupe NTIDE — Config du module Innovation (boîte à idées interne, auto-
   enregistrée). Collectée par le registre ``router/moduleRoutes.jsx`` via glob
   (nav Sidebar, routes.meta, fil d'Ariane, route lazy).

   Liste/détail : ouverts à TOUT utilisateur connecté (« logged-in users
   only », NTIDE4/NTIDE5 — aucun ``roles`` déclaré ⇒ authLoader seul).
   ========================================================================== */

const IdeesPage = lazy(() => import('./IdeesPage'))
const IdeeDetail = lazy(() => import('./IdeeDetail'))

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
    ],
  },
  titles: [
    ['/innovation/idees', 'Boîte à idées'],
  ],
  sectionLabels: { innovation: 'Innovation' },
  routes: [
    { path: '/innovation/idees', component: IdeesPage },
    { path: '/innovation/idees/:id', component: IdeeDetail },
  ],
}

export default config
