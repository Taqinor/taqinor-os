/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC54 — Migration des routes legacy Ventes vers le registre (phase 2, après
   les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes-only (aucune section `nav` : Sidebar.jsx garde son menu Ventes
   hard-codé, non touché — `buildModuleRoutes` traite `nav` comme optionnel via
   `.filter(Boolean)`, donc « Sidebar sans doublon » tient trivialement ici).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).

   NON-MIGRABLES (laissées dans index.jsx, cf. rapport de lane) :
   `/ventes/devis/:id/3d` et `/devis-design/:id` portent un `errorElement`
   dédié (`<RouteErrorBoundary />`) que `buildModuleRoutes` ne sait pas
   exprimer (le registre ne construit que `{ path, loader, element }`).
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const DevisList = lazy(() => import('../../pages/ventes/DevisList'))
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
  routes: [
    { path: '/ventes/devis', component: DevisList },
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
