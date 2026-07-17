/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Network } from 'lucide-react'

/* ============================================================================
   NTADM4/30 — Configuration du module « Entités » (structure organisationnelle
   intra-tenant). Nav gatée Administrateur ; écran de gestion de l'arbre +
   assistant guidé de création.
   ========================================================================== */

const ROLES = ['admin']

const EntitesPage = lazy(() => import('./EntitesPage'))

const NW = <Network size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'entites',
  order: 92,
  nav: {
    label: 'ENTITÉS',
    accent: 'lune',
    items: [
      { to: '/parametres/entites', label: 'Entités', icon: NW, roles: ROLES },
    ],
  },
  titles: [
    ['/parametres/entites', 'Entités (structure)'],
  ],
  sectionLabels: { entites: 'Entités' },
  routes: [
    { path: '/parametres/entites', component: EntitesPage, roles: ROLES },
  ],
}
