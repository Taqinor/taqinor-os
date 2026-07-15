/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { ClipboardList, PackageCheck, Receipt, Undo2, ScanLine } from 'lucide-react'

/* ============================================================================
   ODX20 — App Achats (équivalent Odoo Purchase, séparé de Inventory).
   ----------------------------------------------------------------------------
   Regroupement FONCTIONNEL only : la section « Achats » (Commandes fournisseur,
   Modèles de commande, Réceptions, Factures fournisseur, Retours, Import OCR)
   est EXTRAITE de la section STOCK vers son propre module « coquille ». Mêmes
   routes (/stock/…), mêmes pages, mêmes gardes de rôles, mêmes hooks DOM e2e —
   zéro page reconstruite. Les routes API correspondantes sont servies sous DEUX
   préfixes (/api/django/achats/… et /api/django/stock/… historique). Les
   mouvements de stock à la réception/au retour passent par apps.stock.services
   (Produit/Fournisseur/MouvementStock restent des master data dans stock).
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const BonsCommandeFournisseur = lazy(() => import('../../pages/stock/BonsCommandeFournisseur'))
const ModelesBcf = lazy(() => import('../../pages/stock/ModelesBcf'))
const ReceptionsFournisseur = lazy(() => import('../../pages/stock/ReceptionsFournisseur'))
const FacturesFournisseur = lazy(() => import('../../pages/stock/FacturesFournisseur'))
const RetoursFournisseur = lazy(() => import('../../pages/stock/RetoursFournisseur'))
const OcrStockImport = lazy(() => import('../../pages/stock/OcrStockImport'))

const config = {
  key: 'achats',
  order: 21,
  nav: {
    label: 'ACHATS', labelKey: 'nav.section.achats',
    accent: 'lune',
    items: [
      { to: '/stock/bons-commande-fournisseur', label: 'Commandes fournisseur', k: 'nav.commandes_fournisseur', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/stock/modeles-bcf',    label: 'Modèles de commande', k: 'nav.modeles_bcf', icon: navIcon(ClipboardList),    roles: ['responsable','admin'] },
      { to: '/stock/receptions-fournisseur', label: 'Réceptions fournisseur', k: 'nav.receptions_fournisseur', icon: navIcon(PackageCheck), roles: ['responsable','admin'] },
      { to: '/stock/factures-fournisseur', label: 'Factures fournisseur', k: 'nav.factures_fournisseur', icon: navIcon(Receipt), roles: ['responsable','admin'] },
      { to: '/stock/retours-fournisseur', label: 'Retours fournisseur', k: 'nav.retours_fournisseur', icon: navIcon(Undo2), roles: ['responsable','admin'] },
      { to: '/stock/ocr-import',     label: 'Import OCR',       k: 'nav.import_ocr', icon: navIcon(ScanLine),   roles: ['responsable','admin'] },
    ],
  },
  routes: [
    { path: '/stock/bons-commande-fournisseur', component: BonsCommandeFournisseur },
    { path: '/stock/modeles-bcf', component: ModelesBcf },
    { path: '/stock/receptions-fournisseur', component: ReceptionsFournisseur },
    { path: '/stock/factures-fournisseur', component: FacturesFournisseur },
    { path: '/stock/retours-fournisseur', component: RetoursFournisseur },
    { path: '/stock/ocr-import', component: OcrStockImport },
  ],
}

export default config
