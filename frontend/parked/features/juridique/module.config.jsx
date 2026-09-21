/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
// ODY34 — le glyphe d'APP doit être UNIQUE sur tout le portail (garanti par
// `lib/apps/appGlyph.test.jsx`) : `Scale` est déjà pris par `fiscal`, d'où
// `Landmark` (le palais de justice) pour les affaires juridiques.
import { Landmark } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   NTJUR — Config du module « Affaires juridiques » (auto-enregistrée).
   ----------------------------------------------------------------------------
   Collectée par le registre ``router/moduleRoutes.jsx`` via glob (nav Sidebar,
   routes.meta, fil d'Ariane, route lazy). Sans cette entrée, l'écran existerait
   sur le disque sans jamais pouvoir être ouvert.

   Gating aligné sur le serveur (YRBAC3) : la LECTURE du module est gardée par
   ``juridique_voir`` côté API, avec repli sur le palier responsable/admin pour
   les seuls comptes LÉGACY sans rôle fin — d'où ``perm`` +
   ``permRepliPalier``. Le filtrage de CONFIDENTIALITÉ est une garde SERVEUR
   supplémentaire (les dossiers confidentiels sont absents du queryset d'un
   rôle non autorisé) : la nav n'a rien à en savoir.
   ========================================================================== */

const JuridiquePage = lazy(() => import('./JuridiquePage'))

const ROLES = ['normal', 'responsable', 'admin']
const GATE = { roles: ROLES, perm: 'juridique_voir', permRepliPalier: true }

const config = {
  key: 'juridique',
  order: 91,
  nav: {
    label: 'JURIDIQUE',
    icon: appGlyph(Landmark),
    accent: 'destructive',
    items: [
      {
        to: '/juridique',
        label: 'Affaires juridiques',
        icon: <Landmark size={17} strokeWidth={1.75} aria-hidden="true" />,
        ...GATE,
      },
    ],
  },
  titles: [['/juridique', 'Affaires juridiques']],
  sectionLabels: { juridique: 'Juridique' },
  routes: [
    {
      path: '/juridique',
      component: JuridiquePage,
      ...GATE,
    },
  ],
}

export default config
