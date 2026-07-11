/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  FileSignature, LibraryBig, BellRing, Wallet, PackageOpen, LayoutDashboard,
} from 'lucide-react'

/* ============================================================================
   UX34–UX37 — Configuration du module ERP « Contrats » (CLM).
   ----------------------------------------------------------------------------
   Un seul fichier auto-enregistré par `router/moduleRoutes.jsx` (glob) : nav
   Sidebar gatée, titres de page (routes.meta), libellé de fil d'Ariane, et
   routes lazy. Aucune édition du routeur / de la Sidebar / de routes.meta.

   NB : `/contrats` (ce module CLM) est DISTINCT de `/sav/contrats` (page de
   maintenance SAV) — deux modules séparés.

   Accès gaté au palier responsable/admin (les mêmes rôles que le backend
   `IsResponsableOrAdmin`).
   ========================================================================== */

const ROLES = ['responsable', 'admin']

const ContratsList = lazy(() => import('./ContratsList'))
const ContratDetail = lazy(() => import('./ContratDetail'))
const ModelesPage = lazy(() => import('./ModelesPage'))
const EcheancesPage = lazy(() => import('./EcheancesPage'))
const FinancesPage = lazy(() => import('./FinancesPage'))
const LocationPage = lazy(() => import('./LocationPage'))
const DashboardPage = lazy(() => import('./DashboardPage'))
const ConfigLocationPage = lazy(() => import('./ConfigLocationPage'))

const FS = <FileSignature size={17} strokeWidth={1.75} aria-hidden="true" />
const LB = <LibraryBig size={17} strokeWidth={1.75} aria-hidden="true" />
const BR = <BellRing size={17} strokeWidth={1.75} aria-hidden="true" />
const WL = <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />
const PO = <PackageOpen size={17} strokeWidth={1.75} aria-hidden="true" />
const LD = <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'contrats',
  order: 70,
  nav: {
    label: 'CONTRATS',
    accent: 'lune', // VX8 — documentaire/juridique = accent lune (dérivé)
    items: [
      { to: '/contrats/tableau-de-bord', label: 'Tableau de bord', icon: LD, roles: ROLES },
      { to: '/contrats', label: 'Contrats', icon: FS, roles: ROLES },
      { to: '/contrats/location', label: 'Location matériel', icon: PO, roles: ROLES },
      { to: '/contrats/modeles', label: 'Modèles & clauses', icon: LB, roles: ROLES },
      { to: '/contrats/echeances', label: 'Échéances & alertes', icon: BR, roles: ROLES },
      { to: '/contrats/finances', label: 'Finances', icon: WL, roles: ROLES },
      { to: '/contrats/config-location', label: 'Réglages location', icon: PO, roles: ROLES },
    ],
  },
  // routes.meta : du plus spécifique au plus général.
  titles: [
    ['/contrats/tableau-de-bord', 'Tableau de bord'],
    ['/contrats/config-location', 'Réglages location'],
    ['/contrats/location', 'Location de matériel'],
    ['/contrats/modeles', 'Modèles & clauses'],
    ['/contrats/echeances', 'Échéances & alertes'],
    ['/contrats/finances', 'Finances de contrat'],
    ['/contrats', 'Contrats'],
  ],
  sectionLabels: { contrats: 'Contrats' },
  routes: [
    { path: '/contrats/tableau-de-bord', component: DashboardPage, roles: ROLES },
    { path: '/contrats', component: ContratsList, roles: ROLES },
    { path: '/contrats/location', component: LocationPage, roles: ROLES },
    { path: '/contrats/config-location', component: ConfigLocationPage, roles: ROLES },
    { path: '/contrats/modeles', component: ModelesPage, roles: ROLES },
    { path: '/contrats/echeances', component: EcheancesPage, roles: ROLES },
    { path: '/contrats/finances', component: FinancesPage, roles: ROLES },
    { path: '/contrats/:id', component: ContratDetail, roles: ROLES },
  ],
}
