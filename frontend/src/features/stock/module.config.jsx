/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import {
  Package, Boxes, Truck, ArrowLeftRight, ClipboardList, PackageCheck, Receipt,
  Undo2, ScanLine, Layers, Lock, TrendingUp, PackagePlus, Banknote, Warehouse,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'
// APX22 - accent unique de la famille inventaire (Stock/Magasin/Logistique).
import { INVENTAIRE_ACCENT_KEY } from './inventaireAccent'

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
// PACT51 — registre consolidé des paiements fournisseur + relevé RAS-TVA
// (XPUR2/XPUR6). La ressource autonome `/stock/paiements-fournisseur/` existait
// sans aucun appelant : l'export Simpl-TVA, la vue trésorerie tous fournisseurs
// confondus et le flag d'escompte n'étaient atteignables nulle part.
const PaiementsFournisseurLedgerPage = lazy(() => import('../../pages/stock/PaiementsFournisseurLedgerPage'))
const OcrStockImport = lazy(() => import('../../pages/stock/OcrStockImport'))
// WIR109 — inventaire/stock avancé (XSTK6/13/14/15), jusqu'ici backend-only.
const LotsEntrepot = lazy(() => import('../../pages/stock/LotsEntrepot'))
const InventairesAnnuels = lazy(() => import('../../pages/stock/InventairesAnnuels'))
const RevalorisationsStock = lazy(() => import('../../pages/stock/RevalorisationsStock'))
const ConditionnementsProduit = lazy(() => import('../../pages/stock/ConditionnementsProduit'))
// NTWMS29 — cockpit entrepôt (remplissage par zone, vagues en retard,
// comptages dus, expéditions du jour, lots proches de péremption).
const CockpitEntrepot = lazy(() => import('../../pages/stock/CockpitEntrepot'))

const config = {
  key: 'stock',
  order: 20,
  // ODY17 — métadonnées d'app pour le futur registre unifié (ODY1
  // `useInstalledApps()` / ODY9 `AppIcon.jsx`, aucun des deux livré ici) :
  // MIROIR EXACT du manifest backend (`apps/stock/apps.py::module_manifest`
  // — icône 'package', description identique) pour que ce futur registre
  // n'ait rien à réconcilier entre backend et frontend.
  icon: Package,
  description: 'Gestion des stocks, mouvements et fournisseurs.',
  nav: {
    label: 'STOCK', labelKey: 'nav.section.stock',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(Boxes),
    // APX22 - accent de la FAMILLE INVENTAIRE : Stock, Magasin et
    // Logistique portent desormais la MEME cle (celle-ci, inchangee cote
    // Stock). Source unique : `features/stock/inventaireAccent.js`.
    accent: INVENTAIRE_ACCENT_KEY,
    items: [
      { to: '/stock',                label: 'Produits',         k: 'nav.produits',   icon: navIcon(Package),     roles: ['normal','responsable','admin'] },
      { to: '/stock/categories',     label: 'Catégories & marques', k: 'nav.categories', icon: navIcon(Boxes), roles: ['responsable','admin'] },
      { to: '/stock/fournisseurs',   label: 'Fournisseurs',     k: 'nav.fournisseurs', icon: navIcon(Truck), roles: ['responsable','admin'] },
      { to: '/stock/mouvements',     label: 'Mouvements',       k: 'nav.mouvements', icon: navIcon(ArrowLeftRight),   roles: ['normal','responsable','admin'] },
      // ── ACHATS — sous-groupe prêt à déplacer (ODX20 pas livré : `apps/achats`
      // existe déjà côté backend — manifest `key:'achats'`, `depends:['stock']`
      // — mais sa vue/frontend n'a pas atterri ; en attendant, ces 5 écrans
      // restent ici). `group: 'achats'` marque EXACTEMENT le lot que ODX20
      // devra extraire vers `features/achats/module.config.jsx` (nav ET
      // routes ci-dessous portent le même tag — grep `group: 'achats'`) : la
      // « Fournisseurs » (répertoire fournisseur lui-même, PrixFournisseur
      // exclu) et l'Import OCR restent des écrans Stock, hors de ce lot.
      { to: '/stock/bons-commande-fournisseur', label: 'Commandes fournisseur', k: 'nav.commandes_fournisseur', icon: navIcon(ClipboardList), roles: ['responsable','admin'], group: 'achats' },
      { to: '/stock/modeles-bcf',    label: 'Modèles de commande', k: 'nav.modeles_bcf', icon: navIcon(ClipboardList),    roles: ['responsable','admin'], group: 'achats' },
      { to: '/stock/receptions-fournisseur', label: 'Réceptions fournisseur', k: 'nav.receptions_fournisseur', icon: navIcon(PackageCheck), roles: ['responsable','admin'], group: 'achats' },
      { to: '/stock/factures-fournisseur', label: 'Factures fournisseur', k: 'nav.factures_fournisseur', icon: navIcon(Receipt), roles: ['responsable','admin'], group: 'achats' },
      { to: '/stock/retours-fournisseur', label: 'Retours fournisseur', k: 'nav.retours_fournisseur', icon: navIcon(Undo2), roles: ['responsable','admin'], group: 'achats' },
      // PACT51 — registre consolidé des paiements + relevé RAS-TVA (Simpl-TVA).
      // Pas de clé `k` : le catalogue i18n du chrome est un ensemble fermé
      // (fr/en/ar strictement identiques) — `tr()` retombe sur le libellé FR.
      { to: '/stock/paiements-fournisseur', label: 'Paiements fournisseur', icon: navIcon(Banknote), roles: ['responsable','admin'], group: 'achats' },
      // ── fin du sous-groupe ACHATS ──
      { to: '/stock/ocr-import',     label: 'Import OCR',       k: 'nav.import_ocr', icon: navIcon(ScanLine),   roles: ['responsable','admin'] },
      // WIR109 — lots FEFO, inventaire annuel, revalorisations, conditionnements.
      { to: '/stock/lots-entrepot',  label: 'Lots (FEFO)',      k: 'nav.lots_entrepot', icon: navIcon(Layers), roles: ['responsable','admin'] },
      { to: '/stock/inventaires-annuels', label: 'Inventaires annuels', k: 'nav.inventaires_annuels', icon: navIcon(Lock), roles: ['admin'] },
      { to: '/stock/revalorisations', label: 'Revalorisations', k: 'nav.revalorisations', icon: navIcon(TrendingUp), roles: ['admin'] },
      { to: '/stock/conditionnements', label: 'Conditionnements', k: 'nav.conditionnements', icon: navIcon(PackagePlus), roles: ['responsable','admin'] },
      // NTWMS29 — cockpit entrepôt. Pas de clé `k` : le catalogue i18n du
      // chrome est un ensemble fermé (fr/en/ar identiques) — `tr()` retombe
      // sur le libellé FR.
      { to: '/stock/entrepot', label: 'Tableau de bord entrepôt', icon: navIcon(Warehouse), roles: ['responsable','admin'] },
    ],
  },
  routes: [
    { path: '/stock', component: StockList },
    { path: '/stock/mouvements', component: MouvementsPage },
    { path: '/stock/categories', component: CategoriesStock },
    { path: '/stock/fournisseurs', component: FournisseursStock },
    { path: '/stock/fournisseurs/:id/360', component: FournisseurFiche360 },
    // ── ACHATS — même sous-groupe que la nav ci-dessus (miroir `group`). ──
    { path: '/stock/bons-commande-fournisseur', component: BonsCommandeFournisseur, group: 'achats' },
    { path: '/stock/modeles-bcf', component: ModelesBcf, group: 'achats' },
    { path: '/stock/receptions-fournisseur', component: ReceptionsFournisseur, group: 'achats' },
    { path: '/stock/factures-fournisseur', component: FacturesFournisseur, group: 'achats' },
    { path: '/stock/retours-fournisseur', component: RetoursFournisseur, group: 'achats' },
    { path: '/stock/paiements-fournisseur', component: PaiementsFournisseurLedgerPage, group: 'achats' },
    // ── fin du sous-groupe ACHATS ──
    { path: '/stock/ocr-import', component: OcrStockImport },
    // WIR109 — lots FEFO, inventaire annuel, revalorisations, conditionnements.
    { path: '/stock/lots-entrepot', component: LotsEntrepot },
    { path: '/stock/inventaires-annuels', component: InventairesAnnuels },
    { path: '/stock/revalorisations', component: RevalorisationsStock },
    { path: '/stock/conditionnements', component: ConditionnementsProduit },
    // NTWMS29 — route ET entrée de nav déclarées ENSEMBLE (motif PACT150 :
    // un écran livré sans l'une des deux est un écran mort).
    { path: '/stock/entrepot', component: CockpitEntrepot },
  ],
}

export default config
