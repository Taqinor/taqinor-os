/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { BookOpen, GraduationCap } from 'lucide-react'

/* ============================================================================
   UX43 — Config du module Base de connaissances (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée telle quelle : le registre ``router/moduleRoutes.jsx`` la collecte via
   glob (nav Sidebar gatée, routes.meta, fil d'Ariane, route lazy). Lecture
   ouverte à tous les rôles ; l'édition/publication est gatée dans l'écran.

   XKB22 — /kb/parcours (KbParcoursPage) : séquences d'onboarding assignées
   nominativement, gaté responsable/admin (création/assignation) comme le
   reste de la gestion KB.
   ========================================================================== */

const KbPage = lazy(() => import('./KbPage'))
const KbParcoursPage = lazy(() => import('./KbParcoursPage'))

const config = {
  key: 'kb',
  order: 85,
  nav: {
    label: 'BASE DE CONNAISSANCES',
    accent: 'lune', // VX8 — documentaire = accent lune (dérivé)
    items: [
      {
        to: '/kb',
        label: 'Base de connaissances',
        icon: <BookOpen size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
      {
        to: '/kb/parcours',
        label: 'Parcours',
        icon: <GraduationCap size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['responsable', 'admin'],
      },
    ],
  },
  titles: [
    ['/kb', 'Base de connaissances'],
    ['/kb/parcours', 'Parcours'],
  ],
  sectionLabels: { kb: 'Base de connaissances' },
  routes: [
    { path: '/kb', component: KbPage, roles: ['normal', 'responsable', 'admin'] },
    { path: '/kb/parcours', component: KbParcoursPage, roles: ['responsable', 'admin'] },
  ],
}

export default config
