/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Network, Columns3 } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   NTADM4/30 — Configuration du module « Entités » (structure organisationnelle
   intra-tenant). Nav gatée Administrateur ; écran de gestion de l'arbre +
   assistant guidé de création.
   NTADM25 — s'y ajoute la vue consolidée « Groupe » (lecture seule) : une
   colonne de KPI par entité active + un total.
   ========================================================================== */

const ROLES = ['admin']

const EntitesPage = lazy(() => import('./EntitesPage'))
const GroupePage = lazy(() => import('./GroupePage'))

const NW = <Network size={17} strokeWidth={1.75} aria-hidden="true" />
const GR = <Columns3 size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'entites',
  order: 92,
  nav: {
    label: 'ENTITÉS',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Network),
    accent: 'lune',
    items: [
      { to: '/parametres/entites', label: 'Entités', icon: NW, roles: ROLES },
      { to: '/admin/groupe', label: 'Vue Groupe', icon: GR, roles: ROLES },
    ],
  },
  titles: [
    ['/parametres/entites', 'Entités (structure)'],
    ['/admin/groupe', 'Vue Groupe (consolidée)'],
  ],
  sectionLabels: { entites: 'Entités' },
  routes: [
    { path: '/parametres/entites', component: EntitesPage, roles: ROLES },
    { path: '/admin/groupe', component: GroupePage, roles: ROLES },
  ],
}
