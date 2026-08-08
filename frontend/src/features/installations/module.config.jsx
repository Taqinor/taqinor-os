/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + pages lazy), pas un module de
   composants : le fast-refresh ne s'y applique pas (cf. router/moduleRoutes). */
import { lazy } from 'react'
import { CalendarClock, HardHat, ClipboardList, Wrench, Boxes, BarChart3, MapPin } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'

/* ============================================================================
   ARC54 — Migration des routes legacy Chantiers / Installations / Production
   vers le registre (phase 2, après les pilotes ARC48 stock/sav).
   ----------------------------------------------------------------------------
   Routes migrées ici (section `nav` ajoutée depuis par ODX7, voir plus bas).
   Les titres de page (`routes.meta.js` → `BASE_PAGE_TITLES`/`SECTION_LABELS`)
   restent déjà déclarés là-bas pour ces chemins et ne sont PAS dupliqués ici.
   Toutes ces routes utilisaient `authLoader` (aucun rôle/perm) dans
   `index.jsx` — préservé à l'identique : aucune entrée `roles` ci-dessous, donc
   `buildModuleRoutes` applique `authLoader` (cf. router/moduleRoutes.jsx).

   ODX7 — la section `nav` ci-dessous est le littéral CHANTIERS qui vivait dans
   `Sidebar.jsx` (`NAV_SECTIONS`), déplacé ici À L'IDENTIQUE (regroupement
   fonctionnel only, zéro changement visuel). Sidebar lit désormais cette
   section par clé (`navFor('installations')`), à la même place dans l'ordre
   d'affichage.
   ========================================================================== */

// eslint-disable-next-line no-unused-vars -- Comp est un composant polymorphe, rendu via <Comp> ci-dessous
const navIcon = (Comp) => <Comp size={17} strokeWidth={1.75} aria-hidden="true" />

// Pages chargées à la demande (code-splitting préservé — <Suspense> côté routeur).
const InstallationsPage = lazy(() => import('../../pages/installations/InstallationsPage'))
const DemandesAchatList = lazy(() => import('../../pages/installations/DemandesAchatList'))
// WIR110 — consultation approvisionnement avancé (6 familles FG310-318).
const ApprovisionnementPage = lazy(() => import('../../pages/installations/ApprovisionnementPage'))
// WIR114 — astreintes / indisponibilités / récurrences (FG302, ZFSM3).
const AstreintesPage = lazy(() => import('../../pages/installations/AstreintesPage'))
// WIR113 — suivi GPS terrain web-first (XFSM23) : consentements + carte live.
const SuiviGpsPage = lazy(() => import('../../pages/installations/SuiviGpsPage'))
const InterventionsPage = lazy(() => import('../../pages/interventions/InterventionsPage'))
const PlanificationPage = lazy(() => import('../../pages/installations/PlanificationPage'))
const MaJourneePage = lazy(() => import('../../pages/interventions/MaJourneePage'))
const ParcInstallePage = lazy(() => import('../../pages/installations/ParcInstallePage'))
const AteliersPage = lazy(() => import('../../pages/installations/AteliersPage'))
// PACT55 — sous-traitance chantier : ordres, factures, attestations,
// évaluations, retenues de garantie (FG304-309), aucun appelant jusqu'ici.
const SousTraitanceChantier = lazy(() => import('./SousTraitanceChantier'))
// PACT56 — import et douane : dossiers, frais, coût débarqué (FG315-316).
const SuiviImport = lazy(() => import('./SuiviImport'))
// PACT57 — prix négociés fournisseurs : écriture commandes-cadres/contrats
// de prix (FG314/FG318), lecture seule existante avant cette tâche.
const PrixNegocies = lazy(() => import('./PrixNegocies'))
// PACT58 — contrôle documentaire de projet : registre + révisions (FG297).
const DocumentsProjet = lazy(() => import('./DocumentsProjet'))
// PACT59 — suivi projet du chantier : jalons, modèles, réunions (FG293/296/298).
const SuiviProjetChantier = lazy(() => import('./SuiviProjetChantier'))
// PACT60 — consultation fournisseurs (RFQ) et comparatif d'offres (FG311).
const RFQ = lazy(() => import('./RFQ'))
const ProductionPage = lazy(() => import('../../pages/monitoring/ProductionPage'))
const FleetPage = lazy(() => import('../../pages/monitoring/FleetPage'))
const OmAnalyticsPage = lazy(() => import('../../pages/monitoring/OmAnalyticsPage'))
const WarrantiesPage = lazy(() => import('../../pages/monitoring/WarrantiesPage'))
const Co2Page = lazy(() => import('../../pages/monitoring/Co2Page'))
const CleaningsPage = lazy(() => import('../../pages/monitoring/CleaningsPage'))
const OmReportPage = lazy(() => import('../../pages/monitoring/OmReportPage'))
const ClientPortalPage = lazy(() => import('../../pages/monitoring/ClientPortalPage'))
// WIR123 — Abonnements de supervision (revenu récurrent, FG244).
const AbonnementsPage = lazy(() => import('../../pages/monitoring/AbonnementsPage'))
const OutillagePage = lazy(() => import('../../pages/outillage/OutillagePage'))

const config = {
  key: 'installations',
  order: 60,
  // ODY18 — métadonnées d'app pour le futur registre unifié (ODY1
  // `useInstalledApps()` / ODY9 `AppIcon.jsx`, aucun des deux livré ici) :
  // MIROIR EXACT du manifest backend (`apps/installations/apps.py::module_manifest`
  // — icône 'hard-hat', description identique) pour que ce futur registre
  // n'ait rien à réconcilier entre backend et frontend.
  icon: HardHat,
  description: 'Installations et interventions terrain.',
  // ODY18 — cockpit (`/chantiers`, InstallationsPage.jsx) : ModuleHero VX15
  // DÉLIBÉRÉMENT NON posé ici, contrairement à Stock (ODY17)/Magasin. Le
  // <h2> existant PORTE le compteur + les raccourcis « pose(s) à venir »/
  // « nouveau(x) chantier(s) » (VX218/N14) et son texte « Chantiers » est la
  // cible EXACTE d'un test e2e LIVE (pas fixme) : `frontend/e2e/mobile.spec.js`
  // MB6, `getByRole('heading', { name: 'Chantiers' })` — Playwright fait un
  // match sous-chaîne/casse-insensible, donc SUPERPOSER un second heading
  // contenant « Chantiers » (ModuleHero) casserait ce test en mode strict
  // (2 correspondances). `mobile.spec.js` n'est pas dans les fichiers
  // possédés par cette tâche (STAY IN YOUR FILES) : convertir proprement cet
  // en-tête (déplacer les badges hors du <h2>, ajuster le test dans LE MÊME
  // commit) est un lot pour une tâche future coordonnée avec ce fichier
  // e2e — pas ODY18. La richesse existante (funnel N14, badges VX218, export,
  // copier-lien, bascule de vue) reste « actions rapides + KPI » de fait.
  nav: {
    label: 'CHANTIERS', labelKey: 'nav.section.chantiers',
    // ODY34 — glyphe d’APP (contrat APX1 `nav.icon`, prioritaire sur
    // `items[0].icon`) : le portail montre le métier du module, jamais
    // l’icône de son premier écran. Unique sur tout le portail — garanti
    // par `lib/apps/appGlyph.test.jsx`.
    icon: appGlyph(HardHat),
    accent: 'success',
    items: [
      { to: '/ma-journee',           label: 'Ma journée',       k: 'nav.ma_journee', icon: navIcon(CalendarClock),       roles: ['normal','responsable','admin'] },
      { to: '/chantiers',            label: 'Chantiers',        k: 'nav.chantiers',  icon: navIcon(HardHat),    roles: ['normal','responsable','admin'] },
      { to: '/chantiers/demandes-achat', label: "Demandes d'achat", k: 'nav.demandes_achat', icon: navIcon(ClipboardList), roles: ['normal','responsable','admin'] },
      { to: '/chantiers/approvisionnement', label: 'Approvisionnement', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/chantiers/sous-traitance', label: 'Sous-traitance', icon: navIcon(HardHat), roles: ['responsable','admin'] },
      { to: '/chantiers/import', label: 'Import & douane', icon: navIcon(Boxes), roles: ['responsable','admin'] },
      { to: '/chantiers/prix-negocies', label: 'Prix négociés', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/chantiers/documents-projet', label: 'Documents projet', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/chantiers/suivi-projet', label: 'Suivi projet', icon: navIcon(CalendarClock), roles: ['responsable','admin'] },
      { to: '/chantiers/consultations', label: 'Consultations fournisseurs', icon: navIcon(ClipboardList), roles: ['responsable','admin'] },
      { to: '/interventions',        label: 'Interventions',    k: 'nav.interventions', icon: navIcon(Wrench), roles: ['normal','responsable','admin'] },
      { to: '/planification',        label: 'Planification',    k: 'nav.planification', icon: navIcon(CalendarClock),    roles: ['normal','responsable','admin'] },
      { to: '/planification/astreintes', label: 'Astreintes',   icon: navIcon(CalendarClock), roles: ['responsable','admin'] },
      { to: '/planification/suivi-gps', label: 'Suivi GPS',     icon: navIcon(MapPin), roles: ['responsable','admin'] },
      { to: '/parc',                 label: 'Parc installé',    k: 'nav.parc',       icon: navIcon(Boxes),  roles: ['normal','responsable','admin'] },
      { to: '/atelier',              label: 'Atelier',          k: 'nav.atelier',    icon: navIcon(Wrench),    roles: ['normal','responsable','admin'] },
      { to: '/production',           label: 'Production',       k: 'nav.production', icon: navIcon(BarChart3),   roles: ['normal','responsable','admin'] },
      { to: '/production/abonnements', label: 'Abonnements',    icon: navIcon(BarChart3), roles: ['responsable','admin'] },
      { to: '/outillage',            label: 'Outillage',        k: 'nav.outillage',  icon: navIcon(Wrench),  roles: ['normal','responsable','admin'] },
    ],
  },
  routes: [
    { path: '/chantiers', component: InstallationsPage },
    { path: '/chantiers/demandes-achat', component: DemandesAchatList },
    { path: '/chantiers/approvisionnement', component: ApprovisionnementPage, roles: ['responsable', 'admin'] },
    { path: '/chantiers/sous-traitance', component: SousTraitanceChantier, roles: ['responsable', 'admin'] },
    { path: '/chantiers/import', component: SuiviImport, roles: ['responsable', 'admin'] },
    { path: '/chantiers/prix-negocies', component: PrixNegocies, roles: ['responsable', 'admin'] },
    { path: '/chantiers/documents-projet', component: DocumentsProjet, roles: ['responsable', 'admin'] },
    { path: '/chantiers/suivi-projet', component: SuiviProjetChantier, roles: ['responsable', 'admin'] },
    { path: '/chantiers/consultations', component: RFQ, roles: ['responsable', 'admin'] },
    { path: '/interventions', component: InterventionsPage },
    { path: '/planification', component: PlanificationPage },
    { path: '/planification/astreintes', component: AstreintesPage, roles: ['responsable', 'admin'] },
    { path: '/planification/suivi-gps', component: SuiviGpsPage, roles: ['responsable', 'admin'] },
    { path: '/ma-journee', component: MaJourneePage },
    { path: '/parc', component: ParcInstallePage },
    { path: '/atelier', component: AteliersPage },
    { path: '/production', component: ProductionPage },
    { path: '/production/parc', component: FleetPage },
    { path: '/production/analytique', component: OmAnalyticsPage },
    { path: '/production/garanties', component: WarrantiesPage },
    { path: '/production/co2', component: Co2Page },
    { path: '/production/nettoyages', component: CleaningsPage },
    { path: '/production/rapports', component: OmReportPage },
    { path: '/production/portail-client', component: ClientPortalPage },
    { path: '/production/abonnements', component: AbonnementsPage, roles: ['responsable', 'admin'] },
    { path: '/outillage', component: OutillagePage },
  ],
}

export default config
