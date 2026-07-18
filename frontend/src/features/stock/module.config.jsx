/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { Package, Boxes, Truck, ArrowLeftRight, ClipboardList, PackageCheck, Receipt, Undo2, ScanLine } from 'lucide-react'

/* ============================================================================
   ARC48 — Migration des routes legacy Stock vers le registre de modules.
   ----------------------------------------------------------------------------
   Pilote ARC48 (avec `sav`) : `index.jsx` gardait ~90 routes hard-codées pour
   les apps métier legacy (stock/crm/ventes/installations/sav/reporting/admin/
   parametres) après ODX7 (qui ne migre que la NAV de Sidebar.jsx). Ce fichier
   migre les ROUTES SEULES (section `nav` ajoutée depuis par ODX7, voir plus
   bas). Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`
   /`SECTION_LABELS`) restent déjà déclarés là-bas pour ces chemins et ne sont
   PAS dupliqués ici.
   Toutes les routes Stock legacy utilisaient `authLoader` (aucun rôle/perm) —
   préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).

   ODX7 — la section `nav` ci-dessous est le littéral STOCK qui vivait dans
   `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE (mêmes routes,
   libellés, i18n `k`, gardes de rôles, icônes taille 17/1.75 — même rendu que
   `mk()` dans Sidebar.jsx) : regroupement fonctionnel only, zéro changement
   visuel. Sidebar lit désormais cette section par clé (`navFor('stock')`),
   À LA MÊME PLACE dans l'ordre d'affichage qu'avant.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const StockList = lazy(() => import('../../pages/stock/StockList'))
const MouvementsPage = lazy(() => import('../../pages/stock/MouvementsPage'))
const CategoriesStock = lazy(() => import('../../pages/stock/CategoriesStock'))
const FournisseursStock = lazy(() => import('../../pages/stock/FournisseursStock'))
// XPUR25/WIR27 — fiche fournisseur 360 (BCF/factures/retours/conformité/
// accords de prix), jusqu'ici construite mais routée nulle part. Atteinte
// depuis un lien de `FournisseursStock.jsx` (pas d'entrée de menu dédiée).
const FournisseurFiche360 = lazy(() => import('../../pages/stock/FournisseurFiche360'))
const BonsCommandeFournisseur = lazy(() => import('../../pages/stock/BonsCommandeFournisseur'))
const ModelesBcf = lazy(() => import('../../pages/stock/ModelesBcf'))
const ReceptionsFournisseur = lazy(() => import('../../pages/stock/ReceptionsFournisseur'))
const FacturesFournisseur = lazy(() => import('../../pages/stock/FacturesFournisseur'))
const RetoursFournisseur = lazy(() => import('../../pages/stock/RetoursFournisseur'))
const OcrStockImport = lazy(() => import('../../pages/stock/OcrStockImport'))

const config = {
  key: 'stock',
  order: 20,
  nav: {
    label: 'STOCK', labelKey: 'nav.section.stock',
    accent: 'lune',
    items: [
      { to: '/stock',                label: 'Produits',         k: 'nav.produits',   icon: navIcon(Package),     roles: ['normal','responsable','admin'] },
      { to: '/stock/categories',     label: 'Catégories & marques', k: 'nav.categories', icon: navIcon(Boxes), roles: ['responsable','admin'] },
      { to: '/stock/fournisseurs',   label: 'Fournisseurs',     k: 'nav.fournisseurs', icon: navIcon(Truck), roles: ['responsable','admin'] },
      { to: '/stock/mouvements',     label: 'Mouvements',       k: 'nav.mouvements', icon: navIcon(ArrowLeftRight),   roles: ['normal','responsable','admin'] },
      { to: '/stock/bons-commande-fournisseur', label: 'Commandes fournisseur', k: 'nav.commandes_fournisseur', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/stock/modeles-bcf',    label: 'Modèles de commande', k: 'nav.modeles_bcf', icon: navIcon(ClipboardList),    roles: ['responsable','admin'] },
      { to: '/stock/receptions-fournisseur', label: 'Réceptions fournisseur', k: 'nav.receptions_fournisseur', icon: navIcon(PackageCheck), roles: ['responsable','admin'] },
      { to: '/stock/factures-fournisseur', label: 'Factures fournisseur', k: 'nav.factures_fournisseur', icon: navIcon(Receipt), roles: ['responsable','admin'] },
      { to: '/stock/retours-fournisseur', label: 'Retours fournisseur', k: 'nav.retours_fournisseur', icon: navIcon(Undo2), roles: ['responsable','admin'] },
      { to: '/stock/ocr-import',     label: 'Import OCR',       k: 'nav.import_ocr', icon: navIcon(ScanLine),   roles: ['responsable','admin'] },
    ],
  },
  routes: [
    { path: '/stock', component: StockList },
    { path: '/stock/mouvements', component: MouvementsPage },
    { path: '/stock/categories', component: CategoriesStock },
    { path: '/stock/fournisseurs', component: FournisseursStock },
    { path: '/stock/fournisseurs/:id/360', component: FournisseurFiche360 },
    { path: '/stock/bons-commande-fournisseur', component: BonsCommandeFournisseur },
    { path: '/stock/modeles-bcf', component: ModelesBcf },
    { path: '/stock/receptions-fournisseur', component: ReceptionsFournisseur },
    { path: '/stock/factures-fournisseur', component: FacturesFournisseur },
    { path: '/stock/retours-fournisseur', component: RetoursFournisseur },
    { path: '/stock/ocr-import', component: OcrStockImport },
  ],
}

export default config
