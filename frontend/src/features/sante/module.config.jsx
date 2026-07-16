/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { Stethoscope } from 'lucide-react'

/* ============================================================================
   NTSAN — Config du module Santé (cabinet/clinique), auto-enregistrée.
   ----------------------------------------------------------------------------
   Collectée par le registre ``router/moduleRoutes.jsx`` via glob (nav Sidebar,
   routes.meta, fil d'Ariane, route lazy). Le grain RBAC fin (rôles
   secretaire_medicale/praticien/caissier_sante) est posé par NTSAN17 — en
   attendant, gaté comme les autres modules internes (normal/responsable/admin).
   ========================================================================== */

const SanteAgenda = lazy(() => import('./SanteAgenda'))

const config = {
  key: 'sante',
  order: 95,
  nav: {
    label: 'SANTÉ',
    accent: 'primary',
    items: [
      {
        to: '/sante/agenda',
        label: 'Agenda',
        icon: <Stethoscope size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['normal', 'responsable', 'admin'],
      },
    ],
  },
  titles: [['/sante/agenda', 'Agenda (Santé)']],
  sectionLabels: { sante: 'Santé' },
  routes: [
    {
      path: '/sante/agenda', component: SanteAgenda,
      roles: ['normal', 'responsable', 'admin'],
    },
  ],
}

export default config
