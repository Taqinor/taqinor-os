/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { Gavel } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX44 — Config du module Litiges & réclamations (auto-enregistrée).
   ----------------------------------------------------------------------------
   Collectée par le registre ``router/moduleRoutes.jsx`` via glob (nav Sidebar
   gatée responsable/admin, routes.meta, fil d'Ariane, route lazy). Le backing
   viewset est déjà gaté ``IsResponsableOrAdmin`` côté serveur.
   ========================================================================== */

const LitigesPage = lazy(() => import('./LitigesPage'))

const config = {
  key: 'litiges',
  order: 90,
  nav: {
    label: 'LITIGES',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Gavel),
    accent: 'destructive', // VX8 — risque/conflit = accent destructive (dérivé)
    items: [
      {
        to: '/litiges',
        label: 'Litiges & réclamations',
        icon: <Gavel size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ['responsable', 'admin'],
      },
    ],
  },
  titles: [['/litiges', 'Litiges & réclamations']],
  sectionLabels: { litiges: 'Litiges' },
  routes: [
    { path: '/litiges', component: LitigesPage, roles: ['responsable', 'admin'] },
  ],
}

export default config
