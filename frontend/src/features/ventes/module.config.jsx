/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import {
  FileText, ShoppingCart, Receipt, FileMinus, Wallet, CalendarClock, AlertTriangle, Tags,
  LayoutDashboard,
  HandCoins,
  CreditCard, Banknote,
  Upload,
} from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

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

   WIR23 — `ListesPrixPage` (route déjà enregistrée ci-dessous, API XSAL1-2
   prête) et `DevisActionBoardPage` (route déjà enregistrée, miroir de
   `/sav/action-requise`/ZSAV6) étaient construites/testées mais orphelines
   de menu. Rôles alignés sur ce que la page permet réellement : lecture
   `ListesPrixPage` ouverte à tout rôle authentifié (écriture Responsable/
   Admin gardée serveur, cf. `apps/ventes/views/liste_prix.py`) ;
   `DevisActionBoardPage` réservé responsable/admin, comme son miroir SAV.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
// ODY16 — Cockpit Ventes : porte d'entrée de l'app (ModuleHero + actions + KPI).
const VentesCockpit = lazy(() => import('../../pages/ventes/VentesCockpit'))
const DevisList = lazy(() => import('../../pages/ventes/DevisList'))
// QX29 — « Relances du jour » : tableau d'action des devis (miroir ZSAV6).
const DevisActionBoardPage = lazy(() => import('../../pages/ventes/DevisActionBoardPage'))
const DevisGenerator = lazy(() => import('../../pages/ventes/DevisGenerator'))
// APX15 — le fichier portait un nom qui MENTAIT (« VentesKanban ») alors
// qu'il rend la LISTE des bons de commande : renomme honnetement, URL
// `/ventes/bons-commande` strictement inchangee.
const BonCommandeList = lazy(() => import('../../pages/ventes/BonCommandeList'))
const FactureList = lazy(() => import('../../pages/ventes/FactureList'))
const AvoirsPage = lazy(() => import('../../pages/ventes/AvoirsPage'))
const RelancesPage = lazy(() => import('../../pages/ventes/RelancesPage'))
const PaiementsPage = lazy(() => import('../../pages/ventes/PaiementsPage'))
// WIR265/FG42 — import d'un releve bancaire (dry-run puis commit).
const ImportReleveBancairePage = lazy(() => import('../../pages/ventes/ImportReleveBancairePage'))
// XSAL1-2 — administration des listes de prix clients (écriture Responsable/Admin, gardée serveur).
const ListesPrixPage = lazy(() => import('../../pages/ventes/ListesPrixPage'))
// WIR104 — écran unique du cluster réglementaire / mise en service
// (FG245, FG268-287), jusqu'ici complet côté serveur et sans consommateur.
const DossiersReglementairesPage = lazy(() => import('../../pages/ventes/DossiersReglementairesPage'))
// PACT43 — vue INTERNE des mandats de paiement récurrents (cartes tokenisées) :
// lister par statut + révoquer. Aucune donnée de carte n'entre dans l'ERP.
const MandatsPaiementPage = lazy(() => import('../../pages/ventes/MandatsPaiementPage'))
// PACT46 — remises d'encaissement terrain (espèces/chèques) : déclaration
// technicien, clôture responsable, écart JAMAIS masqué + bordereau PDF.
const RemisesEncaissementPage = lazy(() => import('../../pages/ventes/RemisesEncaissementPage'))

const config = {
  key: 'ventes',
  order: 50,
  nav: {
    label: 'VENTES', labelKey: 'nav.section.ventes',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(HandCoins),
    accent: 'brass',
    items: [
      // ODY16 — porte d'entrée de l'app : PREMIER item (convention
      // `nav.items[0].to` déjà lue comme « cockpit du module » par
      // AppLauncher/PinnedApps/la préférence d'atterrissage VX46).
      { to: '/ventes/cockpit',       label: 'Cockpit',          k: 'nav.ventes_cockpit', icon: navIcon(LayoutDashboard), roles: ['normal','responsable','admin'] },
      { to: '/ventes/devis',         label: 'Devis',            k: 'nav.devis',      icon: navIcon(FileText),        roles: ['normal','responsable','admin'] },
      { to: '/ventes/bons-commande', label: 'Bons de commande', k: 'nav.bons_commande', icon: navIcon(ShoppingCart),  roles: ['normal','responsable','admin'] },
      // ODY16 — sous-groupe « Facturation » (Factures/Avoirs/Encaissements/
      // Relances) : reste DANS Ventes tant qu'ODX18 n'a pas livré
      // `features/facturation/module.config.jsx` — `navGroup` marque
      // exactement le lot qu'ODX18 devra déplacer tel quel (Sidebar ignore ce
      // champ aujourd'hui, purement préparatoire, aucun rendu ≠ actuel).
      { to: '/ventes/factures',      label: 'Factures',         k: 'nav.factures',   icon: navIcon(Receipt),     roles: ['normal','responsable','admin'], navGroup: 'facturation' },
      { to: '/ventes/avoirs',        label: 'Avoirs',           k: 'nav.avoirs',     icon: navIcon(FileMinus),        roles: ['normal','responsable','admin'], navGroup: 'facturation' },
      { to: '/ventes/paiements',     label: 'Encaissements',    k: 'nav.encaissements', icon: navIcon(Wallet),    roles: ['normal','responsable','admin'], navGroup: 'facturation' },
      // WIR265 — import de releve bancaire : ecriture reservee cote serveur
      // (IsResponsableOrAdmin sur les deux endpoints), nav gatee a l'identique.
      { to: '/ventes/paiements/import-releve', label: 'Import de relevé', k: 'nav.import_releve', icon: navIcon(Upload), roles: ['responsable','admin'], navGroup: 'facturation' },
      { to: '/ventes/relances',      label: 'Relances / Impayés', k: 'nav.relances', icon: navIcon(CalendarClock),      roles: ['responsable','admin'], navGroup: 'facturation' },
      // WIR23 — miroir de `/sav/action-requise` (ZSAV6) : « quels devis
      // traiter aujourd'hui » (QX29/QX30), réservé responsable/admin.
      { to: '/ventes/devis/action-requise', label: 'Action requise', k: 'nav.devis_action_requise', icon: navIcon(AlertTriangle), roles: ['responsable','admin'] },
      // WIR23 — lecture ouverte à tout rôle (écriture Responsable/Admin
      // gardée serveur, cf. apps/ventes/views/liste_prix.py).
      { to: '/ventes/listes-prix',   label: 'Listes de prix',   k: 'nav.listes_prix', icon: navIcon(Tags),  roles: ['normal','responsable','admin'] },
      // WIR104 — dossiers réglementaires & mise en service (lecture).
      { to: '/ventes/dossiers-reglementaires', label: 'Dossiers réglementaires', k: 'nav.dossiers_reglementaires', icon: navIcon(FileText), roles: ['normal','responsable','admin'] },
      // PACT43 — mandats de paiement récurrents (cartes tokenisées) : réservé
      // responsable/admin, comme le viewset serveur (IsResponsableOrAdmin).
      { to: '/ventes/mandats-paiement', label: 'Mandats de paiement', k: 'nav.mandats_paiement', icon: navIcon(CreditCard), roles: ['responsable','admin'], navGroup: 'facturation' },
      // PACT46 — remises d'encaissement terrain : la déclaration est ouverte à
      // tout rôle (le technicien déclare SA collecte), la clôture reste gardée
      // serveur (IsResponsableOrAdmin).
      { to: '/ventes/remises-encaissement', label: 'Remises d\'encaissement', k: 'nav.remises_encaissement', icon: navIcon(Banknote), roles: ['normal','responsable','admin'], navGroup: 'facturation' },
    ],
  },
  // ODY16 — `/ventes/cockpit` n'a pas de générique `/ventes` dans
  // `routes.meta.js` (BASE_PAGE_TITLES) pour le masquer : ce `titles` est
  // effectivement lu par `titleFor()` (contrairement à un sous-chemin de
  // `/crm`, déjà shadowé par l'entrée générique `/crm`).
  titles: [
    ['/ventes/cockpit', 'Cockpit Ventes'],
  ],
  routes: [
    // ODY16 — cockpit Ventes (porte d'entrée de l'app).
    { path: '/ventes/cockpit', component: VentesCockpit },
    { path: '/ventes/devis', component: DevisList },
    // QX29 — « Relances du jour » : tableau d'action des devis (miroir ZSAV6).
    { path: '/ventes/devis/action-requise', component: DevisActionBoardPage },
    { path: '/ventes/devis/nouveau', component: DevisGenerator },
    { path: '/ventes/bons-commande', component: BonCommandeList },
    { path: '/ventes/factures', component: FactureList },
    { path: '/ventes/avoirs', component: AvoirsPage },
    { path: '/ventes/relances', component: RelancesPage },
    { path: '/ventes/paiements', component: PaiementsPage },
    // WIR265 — ecran consommateur du couple dry-run/commit FG42.
    { path: '/ventes/paiements/import-releve', component: ImportReleveBancairePage },
    { path: '/ventes/listes-prix', component: ListesPrixPage },
    // WIR104 — écran consommateur du cluster réglementaire (FG245, FG268-287).
    { path: '/ventes/dossiers-reglementaires', component: DossiersReglementairesPage },
    // PACT43 — mandats de paiement récurrents (tokenisation carte).
    { path: '/ventes/mandats-paiement', component: MandatsPaiementPage },
    // PACT46 — remises d'encaissement terrain (écart + bordereau PDF).
    { path: '/ventes/remises-encaissement', component: RemisesEncaissementPage },
  ],
}

export default config
