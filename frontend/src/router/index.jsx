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
const DevisList = lazy(() => import('../pages/ventes/DevisList'))
const FactureList = lazy(() => import('../pages/ventes/FactureList'))
const VentesKanban = lazy(() => import('../pages/ventes/VentesKanban'))
const AgentChat = lazy(() => import('../pages/ia/AgentChat'))
const OcrUpload = lazy(() => import('../pages/ia/OcrUpload'))
const OcrStockImport = lazy(() => import('../pages/stock/OcrStockImport'))
const UsersManagement = lazy(() => import('../pages/admin/UsersManagement'))
const RolesManagement = lazy(() => import('../pages/admin/RolesManagement'))
const ParametresEntreprise = lazy(() => import('../pages/parametres/ParametresEntreprise'))

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
  { path: '/',      element: <Suspense fallback={<Fallback />}><Landing /></Suspense> },
  { path: '/login',  element: <Suspense fallback={<Fallback />}><Login /></Suspense> },

  { path: '/dashboard', loader: authLoader, element: <WithLayout><Dashboard /></WithLayout> },

  // Stock
  { path: '/stock', loader: authLoader, element: <WithLayout><StockList /></WithLayout> },
  { path: '/stock/mouvements', loader: authLoader, element: <WithLayout><MouvementsPage /></WithLayout> },
  { path: '/stock/ocr-import', loader: authLoader, element: <WithLayout><OcrStockImport /></WithLayout> },

  // CRM
  { path: '/crm', loader: authLoader, element: <WithLayout><ClientList /></WithLayout> },

  // Ventes
  { path: '/ventes/devis', loader: authLoader, element: <WithLayout><DevisList /></WithLayout> },
  { path: '/ventes/bons-commande', loader: authLoader, element: <WithLayout><VentesKanban /></WithLayout> },
  { path: '/ventes/factures', loader: authLoader, element: <WithLayout><FactureList /></WithLayout> },

  // IA
  { path: '/ia/agent', loader: authLoader, element: <WithLayout><AgentChat /></WithLayout> },
  { path: '/ia/ocr', loader: authLoader, element: <WithLayout><OcrUpload /></WithLayout> },

  // Reporting
  { path: '/reporting', loader: authLoader, element: <WithLayout><Reporting /></WithLayout> },

  // Administration
  { path: '/admin/users', loader: authLoader, element: <WithLayout><UsersManagement /></WithLayout> },
  { path: '/admin/roles', loader: authLoader, element: <WithLayout><RolesManagement /></WithLayout> },
  { path: '/parametres', loader: authLoader, element: <WithLayout><ParametresEntreprise /></WithLayout> },

  // Catch-all
  { path: '*', element: <Navigate to="/dashboard" replace /> },
])

export default router

