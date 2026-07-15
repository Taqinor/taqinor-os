/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { Package, Boxes, Truck, ArrowLeftRight } from 'lucide-react'

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
// ODX20 — Commandes/Réceptions/Factures/Retours fournisseur + Import OCR
// déplacés dans le module « Achats » (features/achats/module.config.jsx).
// Mêmes routes (/stock/…), mêmes pages. Fournisseurs reste master data ici.

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
    ],
  },
  routes: [
    { path: '/stock', component: StockList },
    { path: '/stock/mouvements', component: MouvementsPage },
    { path: '/stock/categories', component: CategoriesStock },
    { path: '/stock/fournisseurs', component: FournisseursStock },
  ],
}

export default config
