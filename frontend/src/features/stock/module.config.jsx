/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'

/* ============================================================================
   ARC48 — Migration des routes legacy Stock vers le registre de modules.
   ----------------------------------------------------------------------------
   Pilote ARC48 (avec `sav`) : `index.jsx` gardait ~90 routes hard-codées pour
   les apps métier legacy (stock/crm/ventes/installations/sav/reporting/admin/
   parametres) après ODX7 (qui ne migre que la NAV de Sidebar.jsx). Ce fichier
   migre les ROUTES SEULES (aucune section `nav` : Sidebar.jsx garde son menu
   Stock hard-codé, non touché — `buildModuleRoutes` traite `nav` comme
   optionnel via `.filter(Boolean)`, donc « Sidebar sans doublon » tient
   trivialement ici). Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`
   /`SECTION_LABELS`) restent déjà déclarés là-bas pour ces chemins et ne sont
   PAS dupliqués ici.
   Toutes les routes Stock legacy utilisaient `authLoader` (aucun rôle/perm) —
   préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).
   ========================================================================== */

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const StockList = lazy(() => import('../../pages/stock/StockList'))
const MouvementsPage = lazy(() => import('../../pages/stock/MouvementsPage'))
const CategoriesStock = lazy(() => import('../../pages/stock/CategoriesStock'))
const FournisseursStock = lazy(() => import('../../pages/stock/FournisseursStock'))
const BonsCommandeFournisseur = lazy(() => import('../../pages/stock/BonsCommandeFournisseur'))
const ModelesBcf = lazy(() => import('../../pages/stock/ModelesBcf'))
const ReceptionsFournisseur = lazy(() => import('../../pages/stock/ReceptionsFournisseur'))
const FacturesFournisseur = lazy(() => import('../../pages/stock/FacturesFournisseur'))
const RetoursFournisseur = lazy(() => import('../../pages/stock/RetoursFournisseur'))
const OcrStockImport = lazy(() => import('../../pages/stock/OcrStockImport'))

const config = {
  key: 'stock',
  order: 20,
  routes: [
    { path: '/stock', component: StockList },
    { path: '/stock/mouvements', component: MouvementsPage },
    { path: '/stock/categories', component: CategoriesStock },
    { path: '/stock/fournisseurs', component: FournisseursStock },
    { path: '/stock/bons-commande-fournisseur', component: BonsCommandeFournisseur },
    { path: '/stock/modeles-bcf', component: ModelesBcf },
    { path: '/stock/receptions-fournisseur', component: ReceptionsFournisseur },
    { path: '/stock/factures-fournisseur', component: FacturesFournisseur },
    { path: '/stock/retours-fournisseur', component: RetoursFournisseur },
    { path: '/stock/ocr-import', component: OcrStockImport },
  ],
}

export default config
