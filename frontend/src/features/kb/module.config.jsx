/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { BookOpen } from 'lucide-react'

/* ============================================================================
   UX43 — Config du module Base de connaissances (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée telle quelle : le registre ``router/moduleRoutes.jsx`` la collecte via
   glob (nav Sidebar gatée, routes.meta, fil d'Ariane, route lazy). Lecture
   ouverte à tous les rôles ; l'édition/publication est gatée dans l'écran.
   ========================================================================== */

const KbPage = lazy(() => import('./KbPage'))

const config = {
  key: 'kb',
  order: 85,
  nav: {
    label: 'BASE DE CONNAISSANCES',
    items: [
      {
        to: '/kb',
        label: 'Base de connaissances',
        icon: <BookOpen size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
    ],
  },
  titles: [['/kb', 'Base de connaissances']],
  sectionLabels: { kb: 'Base de connaissances' },
  routes: [
    { path: '/kb', component: KbPage, roles: ['normal', 'responsable', 'admin'] },
  ],
}

export default config
