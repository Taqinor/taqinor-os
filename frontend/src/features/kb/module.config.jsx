/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { BookOpen, GraduationCap } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX43 — Config du module Base de connaissances (auto-enregistrée).
   ----------------------------------------------------------------------------
   Déposée telle quelle : le registre ``router/moduleRoutes.jsx`` la collecte via
   glob (nav Sidebar gatée, routes.meta, fil d'Ariane, route lazy). Lecture
   ouverte à tous les rôles ; l'édition/publication est gatée dans l'écran.

   XKB22 — /kb/parcours (KbParcoursPage) : séquences d'onboarding assignées
   nominativement ; la CRÉATION/ASSIGNATION reste gatée `kb_gerer` côté serveur
   et dans l'écran.

   WIR171 — les deux entrées reflètent désormais la garde serveur réelle
   (`_KbBaseViewSet` : `kb_voir` en lecture, `kb_gerer` en écriture, via
   `HasPermissionOrLegacy`) : `perm: 'kb_voir'` + `permRepliPalier`. Deux
   effets : `/kb/parcours`, jusque-là réservé au palier responsable/admin,
   s'ouvre en LECTURE à tout porteur de `kb_voir` (Commercial, Technicien,
   Viewer — exactement ce que le serveur autorise), et `/kb` cesse d'être
   proposé à un compte LÉGACY de palier 'normal' que le serveur refuse déjà.
   ========================================================================== */

const KbPage = lazy(() => import('./KbPage'))
const KbParcoursPage = lazy(() => import('./KbParcoursPage'))

const ROLES = ['normal', 'responsable', 'admin']
// WIR171 — gate commun aux entrées/routes du module (étalé par `...`).
const GATE = { roles: ROLES, perm: 'kb_voir', permRepliPalier: true }

const config = {
  key: 'kb',
  order: 85,
  nav: {
    label: 'BASE DE CONNAISSANCES',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(BookOpen),
    accent: 'lune', // VX8 — documentaire = accent lune (dérivé)
    items: [
      {
        to: '/kb',
        label: 'Base de connaissances',
        icon: <BookOpen size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GATE,
      },
      {
        to: '/kb/parcours',
        label: 'Parcours',
        icon: <GraduationCap size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GATE,
      },
    ],
  },
  titles: [
    ['/kb', 'Base de connaissances'],
    ['/kb/parcours', 'Parcours'],
  ],
  sectionLabels: { kb: 'Base de connaissances' },
  routes: [
    { path: '/kb', component: KbPage, ...GATE },
    { path: '/kb/parcours', component: KbParcoursPage, ...GATE },
  ],
}

export default config
