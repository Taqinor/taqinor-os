/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { Gavel } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX44 — Config du module Litiges & réclamations (auto-enregistrée).
   ----------------------------------------------------------------------------
   Collectée par le registre ``router/moduleRoutes.jsx`` via glob (nav Sidebar,
   routes.meta, fil d'Ariane, route lazy).

   WIR171 — le commentaire « le backing viewset est déjà gaté
   ``IsResponsableOrAdmin`` côté serveur » était PÉRIMÉ : depuis YRBAC3 le
   serveur gate les litiges par ``litige_voir`` (lecture) / ``litige_gerer``
   (écriture) via ``HasPermissionOrLegacy``, avec repli sur le palier
   responsable/admin pour les seuls comptes LÉGACY sans rôle fin. La nav et la
   route reflètent désormais cette sémantique (``perm`` + ``permRepliPalier``,
   cf. ``router/moduleGating.js``) : un Commercial/Technicien/Viewer, qui porte
   ``litige_voir`` tout en relevant du palier 'normal', voit et ouvre l'écran —
   il recevait un 403 côté client alors que le serveur lui répondait 200.
   ========================================================================== */

const LitigesPage = lazy(() => import('./LitigesPage'))

// Paliers ÉLARGIS : la permission fine décide pour un rôle fin, ce tableau ne
// sert plus que de repli documentaire (et aux surfaces sans permission).
const ROLES = ['normal', 'responsable', 'admin']
// WIR171 — gate commun à l'entrée de nav et à la route (étalé par `...`).
const GATE = { roles: ROLES, perm: 'litige_voir', permRepliPalier: true }

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
        ...GATE,
      },
    ],
  },
  titles: [['/litiges', 'Litiges & réclamations']],
  sectionLabels: { litiges: 'Litiges' },
  routes: [
    {
      path: '/litiges',
      component: LitigesPage,
      ...GATE,
    },
  ],
}

export default config
