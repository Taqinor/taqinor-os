/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composants lazy), collecté par
   `router/moduleRoutes.jsx` via glob : ce n'est pas un module de composants, le
   fast-refresh ne s'y applique pas (même dérogation que `moduleRoutes.jsx`). */
import { lazy } from 'react'
import { Link } from 'react-router-dom'
import {
  LayoutDashboard, PlugZap, Megaphone, ClipboardCheck,
  FileText, Images, History, FlaskConical, Route, Layers,
  SlidersHorizontal, MonitorPlay, BarChart3, MessagesSquare, Camera,
  Gauge, GitBranch, Table2, Scale, ShieldCheck, Palette, Binoculars,
} from 'lucide-react'
// PUB47 — enveloppe d'impression (bouton « Imprimer / PDF » + print.css
// globale) posée UNIQUEMENT au point d'enregistrement de route, sans toucher
// au corps d'AdsCockpitScreen (lane distincte).
import PrintPageWrapper from './PrintPageWrapper'
// PUB42 — icône de nav auto-chargée (porte SON PROPRE badge de comptage,
// jamais un composant lazy — elle doit être visible dès le premier rendu de
// la Sidebar, comme les autres icônes de ce fichier).
import TodayNavIcon from './TodayNavIcon'

/* ============================================================================
   ENG21 — configuration du module « Publicité » (moteur Meta-ads autonome,
   auto-enregistré).
   ----------------------------------------------------------------------------
   Déposée dans `src/features/adsengine/` ; le registre `router/moduleRoutes.jsx`
   la collecte via `import.meta.glob` — SANS toucher au routeur, à la Sidebar ni
   à routes.meta (template = `features/marketing/module.config.jsx`, pattern UX1).
   Gatée « responsable / admin ». Écrans chargés en lazy (code-splitting).
   Doctrine (docs/engine/research/scope-features.md) : la boîte d'approbation
   est l'écran-vaisseau-amiral ; le dashboard est « un chiffre » (coût par
   signature) ; approuver reste une permission DISTINCTE de proposer (ENG19,
   appliquée côté backend).
   ========================================================================== */

// PUB42 — file « Aujourd'hui » unifiée (écran d'accueil /publicite).
const TodayScreen = lazy(() => import('./TodayScreen'))
// PUB44 — fiche « histoire complète » d'une ad (deep-link, pas de nav item).
const AdDetailScreen = lazy(() => import('./AdDetailScreen'))
const DashboardScreen = lazy(() => import('./DashboardScreen'))
const ConnectionScreen = lazy(() => import('./ConnectionScreen'))
const CampaignsScreen = lazy(() => import('./CampaignsScreen'))
const ApprovalsScreen = lazy(() => import('./ApprovalsScreen'))
const BriefScreen = lazy(() => import('./BriefScreen'))
const CreativeLibraryScreen = lazy(() => import('./CreativeLibraryScreen'))
const ActionsLogScreen = lazy(() => import('./ActionsLogScreen'))
const ExperimentsScreen = lazy(() => import('./ExperimentsScreen'))
const FlightPlanScreen = lazy(() => import('./FlightPlanScreen'))
const BacklogScreen = lazy(() => import('./BacklogScreen'))
const RulesScreen = lazy(() => import('./RulesScreen'))
const SimulationScreen = lazy(() => import('./SimulationScreen'))
const ReportsScreen = lazy(() => import('./ReportsScreen'))
const CommentsInboxScreen = lazy(() => import('./CommentsInboxScreen'))
const InstagramScreen = lazy(() => import('./InstagramScreen'))
const AdsCockpitScreen = lazy(() => import('./AdsCockpitScreen'))
// ASG6 — L'Arbre (l'Assumption Engine : plan vivant, dd-assumption-engine.md §3).
const TreeScreen = lazy(() => import('./TreeScreen'))
// PUB6/AGEN1 — Table des faits versionnée (génération créative ancrée).
const FactTableScreen = lazy(() => import('./FactTableScreen'))
// PUB52 — comparateur côte-à-côte (ads/campagnes), nouvel écran additif.
const ComparatorScreen = lazy(() => import('./ComparatorScreen'))
// PUB75 — registre de consentement image/témoignage (CNDP loi 09-08).
const ConsentScreen = lazy(() => import('./ConsentScreen'))
// PUB83 — kit de marque persistant (logo/couleurs/zones/polices).
const BrandKitScreen = lazy(() => import('./BrandKitScreen'))
// PUB70 — veille concurrentielle (manuelle outillée, zéro scraping).
const VeilleScreen = lazy(() => import('./VeilleScreen'))
// PUB73 — import photo de chantier vers la créathèque.
const ChantierImportScreen = lazy(() => import('./ChantierImportScreen'))

// PUB47 — cockpit imprimable A4 (bouton + print.css) sans éditer l'écran.
// PUB52 — + lien « Comparer » vers le Comparateur, même patron non-intrusif.
function AdsCockpitScreenPrintable() {
  return (
    <PrintPageWrapper extraActions={
      <Link to="/publicite/comparateur" className="btn btn-light" data-testid="ae-cockpit-compare-link">
        <Scale size={15} aria-hidden="true" /> Comparer
      </Link>
    }>
      <AdsCockpitScreen />
    </PrintPageWrapper>
  )
}

const ROLES = ['responsable', 'admin']

const config = {
  key: 'adsengine',
  order: 56, // juste après Marketing (55) — même famille croissance/commercial.
  nav: {
    label: 'PUBLICITÉ',
    accent: 'brass', // VX8 — croissance/commercial = accent brass (dérivé).
    items: [
      // PUB42 — point d'entrée du matin, en tête de nav (badge de comptage
      // porté par TodayNavIcon, auto-chargé — jamais un « 0 » avant l'arrivée
      // du compte réel).
      { to: '/publicite', label: "Aujourd'hui", icon: <TodayNavIcon />, roles: ROLES },
      { to: '/publicite/tableau-de-bord', label: 'Tableau de bord', icon: <LayoutDashboard size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/cockpit', label: 'Cockpit par ad', icon: <Gauge size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/approbations', label: 'Approbations', icon: <ClipboardCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/campagnes', label: 'Campagnes', icon: <Megaphone size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/creatifs', label: 'Bibliothèque créative', icon: <Images size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/commentaires', label: 'Commentaires', icon: <MessagesSquare size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/instagram', label: 'Instagram', icon: <Camera size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/experimentations', label: 'Expérimentations', icon: <FlaskConical size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/plan-de-vol', label: 'Plan de vol', icon: <Route size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/backlog', label: 'Backlog créatif', icon: <Layers size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/regles', label: 'Règles & anomalies', icon: <SlidersHorizontal size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/simulation', label: 'Simulation', icon: <MonitorPlay size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/reporting', label: 'Reporting', icon: <BarChart3 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/brief', label: 'Brief hebdomadaire', icon: <FileText size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/journal', label: "Journal d'actions", icon: <History size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/connexion', label: 'Connexion & garde-fous', icon: <PlugZap size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/arbre', label: "L'Arbre", icon: <GitBranch size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/table-des-faits', label: 'Table des faits', icon: <Table2 size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/comparateur', label: 'Comparateur', icon: <Scale size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/consentements', label: 'Consentements', icon: <ShieldCheck size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/kit-marque', label: 'Kit de marque', icon: <Palette size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/veille', label: 'Veille concurrentielle', icon: <Binoculars size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
      { to: '/publicite/import-chantier', label: 'Import photo chantier', icon: <Camera size={17} strokeWidth={1.75} aria-hidden="true" />, roles: ROLES },
    ],
  },
  // routes.meta — du plus spécifique au plus général.
  titles: [
    ['/publicite/tableau-de-bord', 'Publicité — Tableau de bord'],
    ['/publicite/cockpit', 'Publicité — Cockpit par ad'],
    ['/publicite/approbations', "Publicité — Boîte d'approbation"],
    ['/publicite/campagnes', 'Publicité — Campagnes'],
    ['/publicite/creatifs', 'Publicité — Bibliothèque créative'],
    ['/publicite/commentaires', 'Publicité — Commentaires'],
    ['/publicite/instagram', 'Publicité — Instagram'],
    ['/publicite/experimentations', 'Publicité — Expérimentations'],
    ['/publicite/plan-de-vol', 'Publicité — Plan de vol'],
    ['/publicite/backlog', 'Publicité — Backlog créatif'],
    ['/publicite/regles', 'Publicité — Règles & anomalies'],
    ['/publicite/simulation', 'Publicité — Simulation'],
    ['/publicite/reporting', 'Publicité — Reporting'],
    ['/publicite/brief', 'Publicité — Brief hebdomadaire'],
    ['/publicite/journal', "Publicité — Journal d'actions"],
    ['/publicite/connexion', 'Publicité — Connexion & garde-fous'],
    ['/publicite/arbre', "Publicité — L'Arbre"],
    ['/publicite/table-des-faits', 'Publicité — Table des faits'],
    ['/publicite/comparateur', 'Publicité — Comparateur'],
    ['/publicite/consentements', 'Publicité — Consentements'],
    ['/publicite/kit-marque', 'Publicité — Kit de marque'],
    ['/publicite/veille', 'Publicité — Veille concurrentielle'],
    ['/publicite/import-chantier', 'Publicité — Import photo chantier'],
    // PUB44 — fiche ad (préfixe fixe avant l'id dynamique).
    ['/publicite/ad/', 'Publicité — Fiche ad'],
    // PUB42 — le PLUS général (préfixe de tous les autres) : DERNIER, sinon
    // il matcherait `/publicite/tableau-de-bord` etc. avant leur propre entrée
    // (routes.meta.js fait un `find` sur `startsWith`, premier match gagne).
    ['/publicite', "Publicité — Aujourd'hui"],
  ],
  sectionLabels: { publicite: 'Publicité' },
  routes: [
    // PUB42 — écran d'accueil (chemin exact, aucune ambiguïté de préfixe côté
    // react-router : chaque `path` reste un match littéral indépendant).
    { path: '/publicite', component: TodayScreen, roles: ROLES },
    // PUB44 — fiche « histoire complète » d'une ad (deep-link, sans item nav).
    { path: '/publicite/ad/:id', component: AdDetailScreen, roles: ROLES },
    { path: '/publicite/tableau-de-bord', component: DashboardScreen, roles: ROLES },
    { path: '/publicite/cockpit', component: AdsCockpitScreenPrintable, roles: ROLES },
    { path: '/publicite/approbations', component: ApprovalsScreen, roles: ROLES },
    { path: '/publicite/campagnes', component: CampaignsScreen, roles: ROLES },
    { path: '/publicite/creatifs', component: CreativeLibraryScreen, roles: ROLES },
    { path: '/publicite/commentaires', component: CommentsInboxScreen, roles: ROLES },
    { path: '/publicite/instagram', component: InstagramScreen, roles: ROLES },
    { path: '/publicite/experimentations', component: ExperimentsScreen, roles: ROLES },
    { path: '/publicite/plan-de-vol', component: FlightPlanScreen, roles: ROLES },
    { path: '/publicite/backlog', component: BacklogScreen, roles: ROLES },
    { path: '/publicite/regles', component: RulesScreen, roles: ROLES },
    { path: '/publicite/simulation', component: SimulationScreen, roles: ROLES },
    { path: '/publicite/reporting', component: ReportsScreen, roles: ROLES },
    { path: '/publicite/brief', component: BriefScreen, roles: ROLES },
    { path: '/publicite/journal', component: ActionsLogScreen, roles: ROLES },
    { path: '/publicite/connexion', component: ConnectionScreen, roles: ROLES },
    { path: '/publicite/arbre', component: TreeScreen, roles: ROLES },
    { path: '/publicite/table-des-faits', component: FactTableScreen, roles: ROLES },
    { path: '/publicite/comparateur', component: ComparatorScreen, roles: ROLES },
    { path: '/publicite/consentements', component: ConsentScreen, roles: ROLES },
    { path: '/publicite/kit-marque', component: BrandKitScreen, roles: ROLES },
    { path: '/publicite/veille', component: VeilleScreen, roles: ROLES },
    { path: '/publicite/import-chantier', component: ChantierImportScreen, roles: ROLES },
  ],
}

export default config
