/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration du routeur (lazy imports + loaders), pas un module
   de composants : le fast-refresh ne s'y applique pas. */
import { createBrowserRouter, Navigate, redirect, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { store } from '../store'
import { fetchMe } from '../features/auth/store/authSlice'
import Layout from '../components/layout/Layout'
// Providers UX dépendant du contexte routeur (useNavigate) → montés DANS le
// router, au chokepoint commun des écrans authentifiés (WithLayout).
import { CommandPalette } from '../providers/CommandPalette'
import { ShortcutsProvider } from '../providers/ShortcutsProvider'
// O65 — Repli « skeleton-first » pendant le chargement lazy d'un bundle de page.
import RouteFallback from '../components/RouteFallback'
// L880 — Error-boundary de route globale : écran FR de récupération au lieu
// d'une application blanche sur une erreur de rendu non capturée.
import RouteErrorBoundary from '../components/RouteErrorBoundary'
// UX1 — Registre de modules : chaque module « coquille » (Compta, Paie, RH,
// Flotte, QHSE, Contrats, Projet, GED, KB, Litiges…) enregistre ses routes via
// un fichier `features/<module>/module.config.jsx`, sans toucher ce fichier.
import { buildModuleRoutes } from './moduleRoutes'

// ── Pages lazy ────────────────────────────────────────────────────────────────
const Landing = lazy(() => import('../pages/Landing'))
const Login = lazy(() => import('../pages/Login'))
const Dashboard = lazy(() => import('../pages/Dashboard').then(m => ({ default: m.Component })))
const Reporting = lazy(() => import('../pages/Reporting').then(m => ({ default: m.Component })))
const Rapports = lazy(() => import('../pages/Rapports').then(m => ({ default: m.Component })))
const ContratsMaintenance = lazy(() => import('../pages/sav/ContratsMaintenance').then(m => ({ default: m.Component })))
const StockList = lazy(() => import('../pages/stock/StockList'))
const MouvementsPage = lazy(() => import('../pages/stock/MouvementsPage'))
const BonsCommandeFournisseur = lazy(() => import('../pages/stock/BonsCommandeFournisseur'))
const CategoriesStock = lazy(() => import('../pages/stock/CategoriesStock'))
const FournisseursStock = lazy(() => import('../pages/stock/FournisseursStock'))
const RetoursFournisseur = lazy(() => import('../pages/stock/RetoursFournisseur'))
const ReceptionsFournisseur = lazy(() => import('../pages/stock/ReceptionsFournisseur'))
const FacturesFournisseur = lazy(() => import('../pages/stock/FacturesFournisseur'))
const ClientList = lazy(() => import('../pages/crm/ClientList'))
const LeadsPage = lazy(() => import('../pages/crm/leads/LeadsPage'))
const DevisList = lazy(() => import('../pages/ventes/DevisList'))
const DevisGenerator = lazy(() => import('../pages/ventes/DevisGenerator'))
const ToitureDesign = lazy(() => import('../pages/ventes/ToitureDesign'))
const FactureList = lazy(() => import('../pages/ventes/FactureList'))
const VentesKanban = lazy(() => import('../pages/ventes/VentesKanban'))
const InstallationsPage = lazy(() => import('../pages/installations/InstallationsPage'))
const InterventionsPage = lazy(() => import('../pages/interventions/InterventionsPage'))
const MaJourneePage = lazy(() => import('../pages/interventions/MaJourneePage'))
const ParcInstallePage = lazy(() => import('../pages/installations/ParcInstallePage'))
const OutillagePage = lazy(() => import('../pages/outillage/OutillagePage'))
const ProductionPage = lazy(() => import('../pages/monitoring/ProductionPage'))
const FleetPage = lazy(() => import('../pages/monitoring/FleetPage'))
const OmAnalyticsPage = lazy(() => import('../pages/monitoring/OmAnalyticsPage'))
const WarrantiesPage = lazy(() => import('../pages/monitoring/WarrantiesPage'))
const Co2Page = lazy(() => import('../pages/monitoring/Co2Page'))
const CleaningsPage = lazy(() => import('../pages/monitoring/CleaningsPage'))
const OmReportPage = lazy(() => import('../pages/monitoring/OmReportPage'))
const ClientPortalPage = lazy(() => import('../pages/monitoring/ClientPortalPage'))
const EquipementsPage = lazy(() => import('../pages/sav/EquipementsPage'))
const TicketsPage = lazy(() => import('../pages/sav/TicketsPage'))
const AgentChat = lazy(() => import('../pages/ia/AgentChat'))
const OcrUpload = lazy(() => import('../pages/ia/OcrUpload'))
const OcrStockImport = lazy(() => import('../pages/stock/OcrStockImport'))
const UsersManagement = lazy(() => import('../pages/admin/UsersManagement'))
const RolesManagement = lazy(() => import('../pages/admin/RolesManagement'))
const ParametresEntreprise = lazy(() => import('../pages/parametres/ParametresEntreprise'))
const ExportSauvegarde = lazy(() => import('../pages/parametres/ExportSauvegarde'))
const NotificationsPreferences = lazy(() => import('../pages/parametres/NotificationsPreferences'))
const Journal = lazy(() => import('../pages/Journal'))
const MesActivitesPage = lazy(() => import('../pages/activities/MesActivitesPage'))
const CalendarPage = lazy(() => import('../pages/CalendarPage'))
const CartePage = lazy(() => import('../pages/CartePage'))
const ParrainagePage = lazy(() => import('../pages/crm/ParrainagePage'))
const AvoirsPage = lazy(() => import('../pages/ventes/AvoirsPage'))
const RelancesPage = lazy(() => import('../pages/ventes/RelancesPage'))
const PaiementsPage = lazy(() => import('../pages/ventes/PaiementsPage'))
const BalanceAgeePage = lazy(() => import('../pages/reporting/BalanceAgeePage'))
const ArchiveClientPage = lazy(() => import('../pages/reporting/ArchiveClientPage'))
const ArchiveChantierPage = lazy(() => import('../pages/reporting/ArchiveChantierPage'))
const CommercialDashboard = lazy(() => import('../pages/reporting/CommercialDashboard'))
const CohortsPage = lazy(() => import('../pages/reporting/CohortsPage'))
const DashboardConfigPage = lazy(() => import('../pages/reporting/DashboardConfigPage'))
const AgentActions = lazy(() => import('../pages/ia/AgentActions'))
// Vitrine interne du système UI (refonte, P68) — référence vivante des primitifs.
const UIShowcase = lazy(() => import('../pages/ui/UIShowcase'))
const ChatPage = lazy(() => import('../pages/messaging/ChatPage'))
const DocumentsPage = lazy(() => import('../pages/ged/DocumentsPage'))

// ── Auth loader ────────────────────────────────────────────────────────────────
// Verifie la session via le cookie httpOnly — aucun token cote client.
//
// I37 (bug « C7 ») — Robustesse du tout premier chargement à froid sur desktop :
// au démarrage l'app pouvait nécessiter un 2e chargement. La cause : plusieurs
// loaders de routes (et le double-montage StrictMode en dev) déclenchaient
// CHACUN un `fetchMe()` concurrent au lieu de PARTAGER l'amorçage de session.
// On dédoublonne désormais via une UNIQUE promesse d'amorçage : le premier
// loader lance `fetchMe`, les suivants attendent le MÊME résultat. La première
// vue authentifiée n'est rendue qu'une fois la session résolue — un seul
// chargement suffit.
let bootstrapPromise = null

const ensureSession = async () => {
  const state = store.getState().auth
  if (state.isAuthenticated) return true
  // Une amorce est déjà en cours (autre loader / double-montage) → on attend la
  // même, sans relancer un second appel réseau.
  if (!bootstrapPromise) {
    bootstrapPromise = store
      .dispatch(fetchMe())
      .then((result) => fetchMe.fulfilled.match(result))
      .finally(() => { bootstrapPromise = null })
  }
  return bootstrapPromise
}

const authLoader = async () => {
  const ok = await ensureSession()
  return ok ? null : redirect('/login')
}

// ERR27 — Garde de rôle/permission sur les routes d'administration. Reflète
// EXACTEMENT le gating du menu (Sidebar.jsx) : une route n'est accessible que si
// le rôle (menu_tier) figure dans `roles` ET — si une permission est exigée —
// qu'elle est présente dans les permissions de l'utilisateur. Sinon, l'utilisateur
// authentifié mais non autorisé est renvoyé vers `/dashboard` (accessible à tous),
// au lieu de monter la page d'admin via un lien direct.
const roleLoader = (roles, perm) => async () => {
  const ok = await ensureSession()
  if (!ok) return redirect('/login')
  const { role, permissions } = store.getState().auth
  const tier = role || 'normal'
  const allowed = roles.includes(tier) && (!perm || (permissions || []).includes(perm))
  return allowed ? null : redirect('/dashboard')
}

// O65 — squelette de page (en-tête + contenu) au lieu d'un texte brut, pour un
// chargement « skeleton-first » sur toutes les routes (publiques et authentifiées).
const Fallback = () => <RouteFallback />

function WithLayout({ children }) {
  // ShortcutsProvider + CommandPalette vivent ici : ils ont besoin du contexte
  // routeur (navigation clavier / ouverture d'un enregistrement) et ne
  // concernent que les écrans authentifiés. La palette s'ouvre sur ⌘K et sur
  // l'événement window émis par le bouton ⌘K du Header (autre lane).
  //
  // L880 — La page est enveloppée d'une error-boundary keyée par chemin : une
  // erreur de rendu non capturée affiche un écran FR de récupération (« Une
  // erreur est survenue — recharger ») au lieu d'une app blanche, et naviguer
  // ailleurs réinitialise la barrière (nouvelle key).
  const { pathname } = useLocation()
  return (
    <ShortcutsProvider>
      <Layout>
        <RouteErrorBoundary key={pathname}>
          <Suspense fallback={<Fallback />}>{children}</Suspense>
        </RouteErrorBoundary>
      </Layout>
      <CommandPalette />
    </ShortcutsProvider>
  )
}

const router = createBrowserRouter([
  // Entrée de l'OS : un visiteur non connecté arrive DIRECTEMENT sur le login.
  // La landing reste dans le code (route /landing) mais n'est plus l'entrée.
  { path: '/',      element: <Suspense fallback={<Fallback />}><Login /></Suspense> },
  { path: '/landing', element: <Suspense fallback={<Fallback />}><Landing /></Suspense> },
  { path: '/login',  element: <Suspense fallback={<Fallback />}><Login /></Suspense> },
  // Référence interne du design system (sans auth ni layout : page autonome).
  { path: '/ui', element: <Suspense fallback={<Fallback />}><UIShowcase /></Suspense> },

  { path: '/dashboard', loader: authLoader, element: <WithLayout><Dashboard /></WithLayout> },
  { path: '/messages', loader: authLoader, element: <WithLayout><ChatPage /></WithLayout> },

  // Stock
  { path: '/stock', loader: authLoader, element: <WithLayout><StockList /></WithLayout> },
  { path: '/stock/mouvements', loader: authLoader, element: <WithLayout><MouvementsPage /></WithLayout> },
  { path: '/stock/categories', loader: authLoader, element: <WithLayout><CategoriesStock /></WithLayout> },
  { path: '/stock/fournisseurs', loader: authLoader, element: <WithLayout><FournisseursStock /></WithLayout> },
  { path: '/stock/bons-commande-fournisseur', loader: authLoader, element: <WithLayout><BonsCommandeFournisseur /></WithLayout> },
  { path: '/stock/receptions-fournisseur', loader: authLoader, element: <WithLayout><ReceptionsFournisseur /></WithLayout> },
  { path: '/stock/factures-fournisseur', loader: authLoader, element: <WithLayout><FacturesFournisseur /></WithLayout> },
  { path: '/stock/retours-fournisseur', loader: authLoader, element: <WithLayout><RetoursFournisseur /></WithLayout> },
  { path: '/stock/ocr-import', loader: authLoader, element: <WithLayout><OcrStockImport /></WithLayout> },

  // CRM
  { path: '/crm', loader: authLoader, element: <WithLayout><ClientList /></WithLayout> },
  { path: '/crm/leads', loader: authLoader, element: <WithLayout><LeadsPage /></WithLayout> },
  { path: '/activites', loader: authLoader, element: <WithLayout><MesActivitesPage /></WithLayout> },
  { path: '/calendrier', loader: authLoader, element: <WithLayout><CalendarPage /></WithLayout> },
  { path: '/carte', loader: authLoader, element: <WithLayout><CartePage /></WithLayout> },
  { path: '/crm/parrainage', loader: authLoader, element: <WithLayout><ParrainagePage /></WithLayout> },

  // Ventes
  { path: '/ventes/devis', loader: authLoader, element: <WithLayout><DevisList /></WithLayout> },
  { path: '/ventes/devis/nouveau', loader: authLoader, element: <WithLayout><DevisGenerator /></WithLayout> },
  // Conception 3D de la toiture (héberge le builder roofPro11 du site, en ERP).
  { path: '/devis-design/:id', loader: authLoader, errorElement: <RouteErrorBoundary />, element: <WithLayout><ToitureDesign /></WithLayout> },
  { path: '/ventes/bons-commande', loader: authLoader, element: <WithLayout><VentesKanban /></WithLayout> },
  { path: '/ventes/factures', loader: authLoader, element: <WithLayout><FactureList /></WithLayout> },
  { path: '/ventes/avoirs', loader: authLoader, element: <WithLayout><AvoirsPage /></WithLayout> },
  { path: '/ventes/relances', loader: authLoader, element: <WithLayout><RelancesPage /></WithLayout> },
  { path: '/ventes/paiements', loader: authLoader, element: <WithLayout><PaiementsPage /></WithLayout> },

  // Chantiers / Installations
  { path: '/chantiers', loader: authLoader, element: <WithLayout><InstallationsPage /></WithLayout> },
  { path: '/interventions', loader: authLoader, element: <WithLayout><InterventionsPage /></WithLayout> },
  { path: '/ma-journee', loader: authLoader, element: <WithLayout><MaJourneePage /></WithLayout> },
  { path: '/parc', loader: authLoader, element: <WithLayout><ParcInstallePage /></WithLayout> },
  { path: '/production', loader: authLoader, element: <WithLayout><ProductionPage /></WithLayout> },
  { path: '/production/parc', loader: authLoader, element: <WithLayout><FleetPage /></WithLayout> },
  { path: '/production/analytique', loader: authLoader, element: <WithLayout><OmAnalyticsPage /></WithLayout> },
  { path: '/production/garanties', loader: authLoader, element: <WithLayout><WarrantiesPage /></WithLayout> },
  { path: '/production/co2', loader: authLoader, element: <WithLayout><Co2Page /></WithLayout> },
  { path: '/production/nettoyages', loader: authLoader, element: <WithLayout><CleaningsPage /></WithLayout> },
  { path: '/production/rapports', loader: authLoader, element: <WithLayout><OmReportPage /></WithLayout> },
  { path: '/production/portail-client', loader: authLoader, element: <WithLayout><ClientPortalPage /></WithLayout> },
  { path: '/outillage', loader: authLoader, element: <WithLayout><OutillagePage /></WithLayout> },

  // GED — gestion documentaire (navigateur arborescent)
  { path: '/ged', loader: authLoader, element: <WithLayout><DocumentsPage /></WithLayout> },

  // Après-vente : parc d'équipements & tickets SAV
  { path: '/equipements', loader: authLoader, element: <WithLayout><EquipementsPage /></WithLayout> },
  { path: '/sav', loader: authLoader, element: <WithLayout><TicketsPage /></WithLayout> },
  { path: '/sav/contrats', loader: authLoader, element: <WithLayout><ContratsMaintenance /></WithLayout> },

  // IA
  { path: '/ia/agent', loader: authLoader, element: <WithLayout><AgentChat /></WithLayout> },
  { path: '/ia/actions', loader: authLoader, element: <WithLayout><AgentActions /></WithLayout> },
  { path: '/ia/ocr', loader: authLoader, element: <WithLayout><OcrUpload /></WithLayout> },

  // Reporting
  { path: '/reporting', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><Reporting /></WithLayout> },
  { path: '/rapports', loader: authLoader, element: <WithLayout><Rapports /></WithLayout> },
  { path: '/reporting/balance-agee', loader: authLoader, element: <WithLayout><BalanceAgeePage /></WithLayout> },
  { path: '/reporting/commercial', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><CommercialDashboard /></WithLayout> },
  { path: '/reporting/cohortes', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><CohortsPage /></WithLayout> },
  { path: '/reporting/dashboards', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><DashboardConfigPage /></WithLayout> },
  { path: '/reporting/archive/client/:id', loader: authLoader, element: <WithLayout><ArchiveClientPage /></WithLayout> },
  { path: '/reporting/archive/chantier/:id', loader: authLoader, element: <WithLayout><ArchiveChantierPage /></WithLayout> },

  // Administration
  { path: '/admin/users', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><UsersManagement /></WithLayout> },
  { path: '/admin/roles', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><RolesManagement /></WithLayout> },
  { path: '/parametres', loader: roleLoader(['responsable', 'admin']), element: <WithLayout><ParametresEntreprise /></WithLayout> },
  { path: '/parametres/export', loader: authLoader, element: <WithLayout><ExportSauvegarde /></WithLayout> },
  { path: '/parametres/notifications', loader: authLoader, element: <WithLayout><NotificationsPreferences /></WithLayout> },
  { path: '/journal', loader: roleLoader(['normal', 'responsable', 'admin'], 'journal_activite_voir'), element: <WithLayout><Journal /></WithLayout> },

  // UX1 — Routes des modules « coquille » enregistrées via le registre. Chaque
  // route est gatée par le même authLoader/roleLoader que le reste de l'app.
  ...buildModuleRoutes({ WithLayout, authLoader, roleLoader }),

  // Catch-all
  { path: '*', element: <Navigate to="/dashboard" replace /> },
])

export default router

