/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (même contrat que
   `router/moduleRoutes.jsx`). */
import { lazy } from 'react'
import {
  FileSignature, LibraryBig, BellRing, Wallet, PackageOpen, LayoutDashboard,
  CreditCard,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   UX34–UX37 — Configuration du module ERP « Contrats » (CLM).
   ----------------------------------------------------------------------------
   Un seul fichier auto-enregistré par `router/moduleRoutes.jsx` (glob) : nav
   Sidebar gatée, titres de page (routes.meta), libellé de fil d'Ariane, et
   routes lazy. Aucune édition du routeur / de la Sidebar / de routes.meta.

   NB : `/contrats` (ce module CLM) est DISTINCT de `/sav/contrats` (page de
   maintenance SAV) — deux modules séparés.

   WIR171 — la LECTURE n'est pas gatée « responsable/admin » côté serveur : les
   viewsets contrats exposent `read_permission = 'contrat_voir'`
   (`HasPermissionOrLegacy`), permission accordée aux 7 rôles. Les écrans de
   consultation portent donc `...LECTURE` (palier élargi + permission + repli
   palier pour les comptes hérités) ; seuls les écrans de CONFIGURATION restent
   au palier `ROLES`. Règle unique : `router/navPermission.js`.
   ========================================================================== */

const ROLES = ['responsable', 'admin']
// WIR171 — sémantique serveur `HasPermissionOrLegacy('contrat_voir')`.
const LECTURE = {
  roles: ['normal', 'responsable', 'admin'],
  perm: 'contrat_voir',
  permLegacyRoles: ROLES,
}

const ContratsList = lazy(() => import('./ContratsList'))
const ContratDetail = lazy(() => import('./ContratDetail'))
const ModelesPage = lazy(() => import('./ModelesPage'))
const EcheancesPage = lazy(() => import('./EcheancesPage'))
const FinancesPage = lazy(() => import('./FinancesPage'))
const LocationPage = lazy(() => import('./LocationPage'))
const DashboardPage = lazy(() => import('./DashboardPage'))
const ConfigLocationPage = lazy(() => import('./ConfigLocationPage'))
// PACT138 — catalogue « revenus récurrents » (NTSUB1-4) : plans, options,
// paliers d'usage, compteurs — jusque-là sans aucun écran.
const AbonnementsPage = lazy(() => import('./AbonnementsPage'))
// PACT139 — séquences/étapes de relance d'impayé (NTSUB8) — jusque-là sans
// aucun écran.
const DunningPage = lazy(() => import('./DunningPage'))

const FS = <FileSignature size={17} strokeWidth={1.75} aria-hidden="true" />
const LB = <LibraryBig size={17} strokeWidth={1.75} aria-hidden="true" />
const BR = <BellRing size={17} strokeWidth={1.75} aria-hidden="true" />
const WL = <Wallet size={17} strokeWidth={1.75} aria-hidden="true" />
const PO = <PackageOpen size={17} strokeWidth={1.75} aria-hidden="true" />
const LD = <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />
const CC = <CreditCard size={17} strokeWidth={1.75} aria-hidden="true" />

export default {
  key: 'contrats',
  order: 70,
  nav: {
    label: 'CONTRATS',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(FileSignature),
    accent: 'lune', // VX8 — documentaire/juridique = accent lune (dérivé)
    items: [
      { to: '/contrats/tableau-de-bord', label: 'Tableau de bord', icon: LD, ...LECTURE },
      { to: '/contrats', label: 'Contrats', icon: FS, ...LECTURE },
      { to: '/contrats/location', label: 'Location matériel', icon: PO, ...LECTURE },
      { to: '/contrats/modeles', label: 'Modèles & clauses', icon: LB, ...LECTURE },
      { to: '/contrats/echeances', label: 'Échéances & alertes', icon: BR, ...LECTURE },
      { to: '/contrats/finances', label: 'Finances', icon: WL, ...LECTURE },
      { to: '/contrats/abonnements', label: 'Abonnements', icon: CC, ...LECTURE },
      { to: '/contrats/relances-impayes', label: 'Relances impayés', icon: BR, ...LECTURE },
      // Écran de CONFIGURATION : reste au palier responsable/admin.
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
    ['/contrats/abonnements', 'Abonnements'],
    ['/contrats/relances-impayes', 'Relances impayés'],
    ['/contrats', 'Contrats'],
  ],
  sectionLabels: { contrats: 'Contrats' },
  routes: [
    { path: '/contrats/tableau-de-bord', component: DashboardPage, ...LECTURE },
    { path: '/contrats', component: ContratsList, ...LECTURE },
    { path: '/contrats/location', component: LocationPage, ...LECTURE },
    { path: '/contrats/config-location', component: ConfigLocationPage, roles: ROLES },
    { path: '/contrats/modeles', component: ModelesPage, ...LECTURE },
    { path: '/contrats/echeances', component: EcheancesPage, ...LECTURE },
    { path: '/contrats/finances', component: FinancesPage, ...LECTURE },
    { path: '/contrats/abonnements', component: AbonnementsPage, ...LECTURE },
    { path: '/contrats/relances-impayes', component: DunningPage, ...LECTURE },
    { path: '/contrats/:id', component: ContratDetail, ...LECTURE },
  ],
}
