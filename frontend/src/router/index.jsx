/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration du routeur (lazy imports + loaders), pas un module
   de composants : le fast-refresh ne s'y applique pas. */
import { createBrowserRouter, Navigate, redirect } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { store } from '../store'
import { fetchMe } from '../features/auth/store/authSlice'
import Layout from '../components/layout/Layout'

// ── Pages lazy ────────────────────────────────────────────────────────────────
const Landing = lazy(() => import('../pages/Landing'))
const Login = lazy(() => import('../pages/Login'))
const Dashboard = lazy(() => import('../pages/Dashboard').then(m => ({ default: m.Component })))
const Reporting = lazy(() => import('../pages/Reporting').then(m => ({ default: m.Component })))
const StockList = lazy(() => import('../pages/stock/StockList'))
const MouvementsPage = lazy(() => import('../pages/stock/MouvementsPage'))
const ClientList = lazy(() => import('../pages/crm/ClientList'))
const LeadsPage = lazy(() => import('../pages/crm/leads/LeadsPage'))
const DevisList = lazy(() => import('../pages/ventes/DevisList'))
const DevisGenerator = lazy(() => import('../pages/ventes/DevisGenerator'))
const FactureList = lazy(() => import('../pages/ventes/FactureList'))
const VentesKanban = lazy(() => import('../pages/ventes/VentesKanban'))
const InstallationsPage = lazy(() => import('../pages/installations/InstallationsPage'))
const EquipementsPage = lazy(() => import('../pages/sav/EquipementsPage'))
const TicketsPage = lazy(() => import('../pages/sav/TicketsPage'))
const AgentChat = lazy(() => import('../pages/ia/AgentChat'))
const OcrUpload = lazy(() => import('../pages/ia/OcrUpload'))
const OcrStockImport = lazy(() => import('../pages/stock/OcrStockImport'))
const UsersManagement = lazy(() => import('../pages/admin/UsersManagement'))
const RolesManagement = lazy(() => import('../pages/admin/RolesManagement'))
const ParametresEntreprise = lazy(() => import('../pages/parametres/ParametresEntreprise'))
const MesActivitesPage = lazy(() => import('../pages/activities/MesActivitesPage'))
const AvoirsPage = lazy(() => import('../pages/ventes/AvoirsPage'))
const RelancesPage = lazy(() => import('../pages/ventes/RelancesPage'))
const BalanceAgeePage = lazy(() => import('../pages/reporting/BalanceAgeePage'))
const PipelineValuePage = lazy(() => import('../pages/reporting/PipelineValuePage'))
const RapportsHub = lazy(() => import('../pages/reporting/RapportsHub'))
const SalesReportPage = lazy(() => import('../pages/reporting/SalesReportPage'))
const StockReportPage = lazy(() => import('../pages/reporting/StockReportPage'))
const ServiceReportPage = lazy(() => import('../pages/reporting/ServiceReportPage'))
const ContratsMaintenancePage = lazy(() => import('../pages/sav/ContratsMaintenancePage'))
const ContratsAVenirPage = lazy(() => import('../pages/sav/ContratsAVenirPage'))

// ── Auth loader ────────────────────────────────────────────────────────────────
// Verifie la session via le cookie httpOnly — aucun token cote client
const authLoader = async () => {
  const state = store.getState().auth
  if (state.isAuthenticated) return null
  // Session inconnue : tente de la restaurer depuis le cookie
  const result = await store.dispatch(fetchMe())
  if (fetchMe.fulfilled.match(result)) return null
  return redirect('/login')
}

const Fallback = () => <div style={{ padding: '2rem', textAlign: 'center' }}>Chargement...</div>

function WithLayout({ children }) {
  return (
    <Layout>
      <Suspense fallback={<Fallback />}>{children}</Suspense>
    </Layout>
  )
}

const router = createBrowserRouter([
  // Entrée de l'OS : un visiteur non connecté arrive DIRECTEMENT sur le login.
  // La landing reste dans le code (route /landing) mais n'est plus l'entrée.
  { path: '/',      element: <Suspense fallback={<Fallback />}><Login /></Suspense> },
  { path: '/landing', element: <Suspense fallback={<Fallback />}><Landing /></Suspense> },
  { path: '/login',  element: <Suspense fallback={<Fallback />}><Login /></Suspense> },

  { path: '/dashboard', loader: authLoader, element: <WithLayout><Dashboard /></WithLayout> },

  // Stock
  { path: '/stock', loader: authLoader, element: <WithLayout><StockList /></WithLayout> },
  { path: '/stock/mouvements', loader: authLoader, element: <WithLayout><MouvementsPage /></WithLayout> },
  { path: '/stock/ocr-import', loader: authLoader, element: <WithLayout><OcrStockImport /></WithLayout> },

  // CRM
  { path: '/crm', loader: authLoader, element: <WithLayout><ClientList /></WithLayout> },
  { path: '/crm/leads', loader: authLoader, element: <WithLayout><LeadsPage /></WithLayout> },
  { path: '/activites', loader: authLoader, element: <WithLayout><MesActivitesPage /></WithLayout> },

  // Ventes
  { path: '/ventes/devis', loader: authLoader, element: <WithLayout><DevisList /></WithLayout> },
  { path: '/ventes/devis/nouveau', loader: authLoader, element: <WithLayout><DevisGenerator /></WithLayout> },
  { path: '/ventes/bons-commande', loader: authLoader, element: <WithLayout><VentesKanban /></WithLayout> },
  { path: '/ventes/factures', loader: authLoader, element: <WithLayout><FactureList /></WithLayout> },
  { path: '/ventes/avoirs', loader: authLoader, element: <WithLayout><AvoirsPage /></WithLayout> },
  { path: '/ventes/relances', loader: authLoader, element: <WithLayout><RelancesPage /></WithLayout> },

  // Chantiers / Installations
  { path: '/chantiers', loader: authLoader, element: <WithLayout><InstallationsPage /></WithLayout> },

  // Après-vente : parc d'équipements & tickets SAV
  { path: '/equipements', loader: authLoader, element: <WithLayout><EquipementsPage /></WithLayout> },
  { path: '/sav', loader: authLoader, element: <WithLayout><TicketsPage /></WithLayout> },
  { path: '/sav/contrats', loader: authLoader, element: <WithLayout><ContratsMaintenancePage /></WithLayout> },
  { path: '/sav/maintenance-a-venir', loader: authLoader, element: <WithLayout><ContratsAVenirPage /></WithLayout> },

  // IA
  { path: '/ia/agent', loader: authLoader, element: <WithLayout><AgentChat /></WithLayout> },
  { path: '/ia/ocr', loader: authLoader, element: <WithLayout><OcrUpload /></WithLayout> },

  // Reporting
  { path: '/reporting', loader: authLoader, element: <WithLayout><Reporting /></WithLayout> },
  { path: '/reporting/balance-agee', loader: authLoader, element: <WithLayout><BalanceAgeePage /></WithLayout> },
  { path: '/reporting/pipeline', loader: authLoader, element: <WithLayout><PipelineValuePage /></WithLayout> },
  { path: '/reporting/rapports', loader: authLoader, element: <WithLayout><RapportsHub /></WithLayout> },
  { path: '/reporting/rapports/ventes', loader: authLoader, element: <WithLayout><SalesReportPage /></WithLayout> },
  { path: '/reporting/rapports/stock', loader: authLoader, element: <WithLayout><StockReportPage /></WithLayout> },
  { path: '/reporting/rapports/service', loader: authLoader, element: <WithLayout><ServiceReportPage /></WithLayout> },

  // Administration
  { path: '/admin/users', loader: authLoader, element: <WithLayout><UsersManagement /></WithLayout> },
  { path: '/admin/roles', loader: authLoader, element: <WithLayout><RolesManagement /></WithLayout> },
  { path: '/parametres', loader: authLoader, element: <WithLayout><ParametresEntreprise /></WithLayout> },

  // Catch-all
  { path: '*', element: <Navigate to="/dashboard" replace /> },
])

export default router

