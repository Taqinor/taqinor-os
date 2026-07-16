/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { FileText, ShoppingCart, Receipt, FileMinus, Wallet, CalendarClock } from 'lucide-react'

/* ============================================================================
   ARC54 — Migration des routes legacy Ventes vers le registre (phase 2, après
   les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes migrées ici (section `nav` ajoutée depuis par ODX7, voir plus bas).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).

   NON-MIGRABLES (laissées dans index.jsx, cf. rapport de lane) :
   `/ventes/devis/:id/3d` et `/devis-design/:id` portent un `errorElement`
   dédié (`<RouteErrorBoundary />`) que `buildModuleRoutes` ne sait pas
   exprimer (le registre ne construit que `{ path, loader, element }`).

   ODX7 — la section `nav` ci-dessous est le littéral VENTES qui vivait dans
   `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE (regroupement
   fonctionnel only, zéro changement visuel). Sidebar lit désormais cette
   section par clé (`navFor('ventes')`), à la même place dans l'ordre
   d'affichage.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const DevisList = lazy(() => import('../../pages/ventes/DevisList'))
// QX29 — « Relances du jour » : tableau d'action des devis (miroir ZSAV6).
const DevisActionBoardPage = lazy(() => import('../../pages/ventes/DevisActionBoardPage'))
const DevisGenerator = lazy(() => import('../../pages/ventes/DevisGenerator'))
const VentesKanban = lazy(() => import('../../pages/ventes/VentesKanban'))
const FactureList = lazy(() => import('../../pages/ventes/FactureList'))
const AvoirsPage = lazy(() => import('../../pages/ventes/AvoirsPage'))
const RelancesPage = lazy(() => import('../../pages/ventes/RelancesPage'))
const PaiementsPage = lazy(() => import('../../pages/ventes/PaiementsPage'))
// XSAL1-2 — administration des listes de prix clients (écriture Responsable/Admin, gardée serveur).
const ListesPrixPage = lazy(() => import('../../pages/ventes/ListesPrixPage'))

const config = {
  key: 'ventes',
  order: 50,
  nav: {
    label: 'VENTES', labelKey: 'nav.section.ventes',
    accent: 'brass',
    items: [
      { to: '/ventes/devis',         label: 'Devis',            k: 'nav.devis',      icon: navIcon(FileText),        roles: ['normal','responsable','admin'] },
      { to: '/ventes/bons-commande', label: 'Bons de commande', k: 'nav.bons_commande', icon: navIcon(ShoppingCart),  roles: ['normal','responsable','admin'] },
      { to: '/ventes/factures',      label: 'Factures',         k: 'nav.factures',   icon: navIcon(Receipt),     roles: ['normal','responsable','admin'] },
      { to: '/ventes/avoirs',        label: 'Avoirs',           k: 'nav.avoirs',     icon: navIcon(FileMinus),        roles: ['normal','responsable','admin'] },
      { to: '/ventes/paiements',     label: 'Encaissements',    k: 'nav.encaissements', icon: navIcon(Wallet),    roles: ['normal','responsable','admin'] },
      { to: '/ventes/relances',      label: 'Relances / Impayés', k: 'nav.relances', icon: navIcon(CalendarClock),      roles: ['responsable','admin'] },
    ],
  },
  routes: [
    { path: '/ventes/devis', component: DevisList },
    // QX29 — « Relances du jour » : tableau d'action des devis (miroir ZSAV6).
    { path: '/ventes/devis/action-requise', component: DevisActionBoardPage },
    { path: '/ventes/devis/nouveau', component: DevisGenerator },
    { path: '/ventes/bons-commande', component: VentesKanban },
    { path: '/ventes/factures', component: FactureList },
    { path: '/ventes/avoirs', component: AvoirsPage },
    { path: '/ventes/relances', component: RelancesPage },
    { path: '/ventes/paiements', component: PaiementsPage },
    { path: '/ventes/listes-prix', component: ListesPrixPage },
  ],
}

export default config
