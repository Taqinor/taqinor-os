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

   WIR171 — le commentaire d'origine annonçait un backing viewset « gaté
   ``IsResponsableOrAdmin`` » : c'est FAUX depuis YRBAC3. ``_LitigesBaseViewSet``
   (apps/litiges/views.py) gate la LECTURE par ``litige_voir`` — permission
   accordée aux 7 rôles (core/rbac_matrix.py) — avec repli palier pour les
   comptes hérités sans rôle fin. L'écran, lui, restait gaté responsable/admin :
   un Commercial recevait 200 du serveur et ne voyait ni le menu ni la route.
   D'où les ``roles`` élargis + ``perm``/``permLegacyRoles`` ci-dessous (règle
   unique dans ``router/navPermission.js``).
   ========================================================================== */

const LitigesPage = lazy(() => import('./LitigesPage'))

// WIR171 — sémantique serveur `HasPermissionOrLegacy('litige_voir')`.
const ROLES_LECTURE = ['normal', 'responsable', 'admin']
const PERM_LECTURE = 'litige_voir'
const LEGACY_LECTURE = ['responsable', 'admin']

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
        roles: ROLES_LECTURE,
        perm: PERM_LECTURE,
        permLegacyRoles: LEGACY_LECTURE,
      },
    ],
  },
  titles: [['/litiges', 'Litiges & réclamations']],
  sectionLabels: { litiges: 'Litiges' },
  routes: [
    {
      path: '/litiges',
      component: LitigesPage,
      roles: ROLES_LECTURE,
      perm: PERM_LECTURE,
      permLegacyRoles: LEGACY_LECTURE,
    },
  ],
}

export default config
