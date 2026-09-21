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

   WIR171 — l'accès n'était gaté QUE par le palier responsable/admin, sur la
   foi d'un `IsResponsableOrAdmin` serveur qui n'a plus cours : depuis YRBAC3
   le backend gate les contrats par `contrat_voir` / `contrat_gerer` via
   `HasPermissionOrLegacy`. Un Commercial / Technicien / Viewer porte
   `contrat_voir` tout en relevant du palier 'normal' : le serveur lui
   répondait 200 pendant que la coquille le renvoyait en 403. Chaque entrée
   déclare donc la permission de LECTURE + `permRepliPalier` (sémantique
   serveur exacte, cf. `router/moduleGating.js`) ; le palier élargi ne sert
   plus que de repli documentaire (comptes LÉGACY sans rôle fin).
   ========================================================================== */

const ROLES = ['normal', 'responsable', 'admin']
// WIR171 — gate commun à toutes les entrées/routes du module (étalé par `...`).
const GATE = { roles: ROLES, perm: 'contrat_voir', permRepliPalier: true }

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
      { to: '/contrats/tableau-de-bord', label: 'Tableau de bord', icon: LD, ...GATE },
      { to: '/contrats', label: 'Contrats', icon: FS, ...GATE },
      { to: '/contrats/location', label: 'Location matériel', icon: PO, ...GATE },
      { to: '/contrats/modeles', label: 'Modèles & clauses', icon: LB, ...GATE },
      { to: '/contrats/echeances', label: 'Échéances & alertes', icon: BR, ...GATE },
      { to: '/contrats/finances', label: 'Finances', icon: WL, ...GATE },
      { to: '/contrats/abonnements', label: 'Abonnements', icon: CC, ...GATE },
      { to: '/contrats/relances-impayes', label: 'Relances impayés', icon: BR, ...GATE },
      { to: '/contrats/config-location', label: 'Réglages location', icon: PO, ...GATE },
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
    { path: '/contrats/tableau-de-bord', component: DashboardPage, ...GATE },
    { path: '/contrats', component: ContratsList, ...GATE },
    { path: '/contrats/location', component: LocationPage, ...GATE },
    { path: '/contrats/config-location', component: ConfigLocationPage, ...GATE },
    { path: '/contrats/modeles', component: ModelesPage, ...GATE },
    { path: '/contrats/echeances', component: EcheancesPage, ...GATE },
    { path: '/contrats/finances', component: FinancesPage, ...GATE },
    { path: '/contrats/abonnements', component: AbonnementsPage, ...GATE },
    { path: '/contrats/relances-impayes', component: DunningPage, ...GATE },
    { path: '/contrats/:id', component: ContratDetail, ...GATE },
  ],
}
