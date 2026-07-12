/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration du routeur (lazy imports + loaders), pas un module
   de composants : le fast-refresh ne s'y applique pas. */
import { createBrowserRouter, redirect, useLocation } from 'react-router-dom'
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
// ODX6 — source unique des modules désactivés (état /auth/me/ → store).
import { isModuleDisabled } from './moduleGating'

// ── Pages lazy ────────────────────────────────────────────────────────────────
const Landing = lazy(() => import('../pages/Landing'))
const Login = lazy(() => import('../pages/Login'))
const Dashboard = lazy(() => import('../pages/Dashboard').then(m => ({ default: m.Component })))
const ToitureDesign = lazy(() => import('../pages/ventes/ToitureDesign'))
const RoofViewerPage = lazy(() => import('../pages/ventes/RoofViewerPage'))
const AgentChat = lazy(() => import('../pages/ia/AgentChat'))
const OcrUpload = lazy(() => import('../pages/ia/OcrUpload'))
// XPLT10 — kiosque TV public des dashboards partagés (sans layout ERP).
const DashboardsTvPage = lazy(() => import('../pages/reporting/DashboardsTvPage'))
const AgentActions = lazy(() => import('../pages/ia/AgentActions'))
// Vitrine interne du système UI (refonte, P68) — référence vivante des primitifs.
const UIShowcase = lazy(() => import('../pages/ui/UIShowcase'))
// XSAL17 — page publique de réservation de visite (placeholder {lien_rdv}).
const PublicBookingPage = lazy(() => import('../pages/crm/PublicBookingPage'))
// XCTR14 — portail client public « Mes contrats » (token, sans login).
const PortailContratsPage = lazy(() => import('../features/contrats/PortailContratsPage'))
// XGED1/XGED2 — cérémonie de signature électronique publique (sans login).
const PublicSignaturePage = lazy(() => import('../pages/ged/PublicSignaturePage'))
// XGED7 — dépôt public de fichier (upload-request, sans login).
const PublicDepotPage = lazy(() => import('../pages/ged/PublicDepotPage'))
// XRH10 — guichet kiosque de pointage (device-token, sans session ni layout ERP).
const KiosquePointage = lazy(() => import('../features/rh/Kiosque'))
// XSAV19 — page publique « Signaler un problème » via QR équipement.
const EquipementSignalerPage = lazy(() => import('../pages/sav/EquipementSignalerPage'))
// XSAV10/FG86 — page publique de suivi client d'un ticket SAV + CSAT.
const TicketSuiviPage = lazy(() => import('../pages/sav/TicketSuiviPage'))
// XKB19 — page publique de consultation d'un article KB partagé (lien tokenisé).
const PublicArticlePage = lazy(() => import('../pages/kb/PublicArticlePage'))
const ChatPage = lazy(() => import('../pages/messaging/ChatPage'))
const DocumentsPage = lazy(() => import('../pages/ged/DocumentsPage'))
// VX78 — Écran 404 déjà construit (ui/NotFound.jsx), jusqu'ici jamais importé
// par le routeur : le catch-all rebondissait en silence vers /dashboard.
const NotFound = lazy(() => import('../ui/NotFound'))
// VX131(c) — jumeau 403 de NotFound : un refus de rôle/permission rebondissait
// en silence vers /dashboard (aucun écran dédié, aucune explication).
const Forbidden = lazy(() => import('../ui/Forbidden'))

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

// VX65 — Lien profond survivant à une reconnexion : si la session a expiré,
// on capture l'URL d'origine (`?next=`) avant de rediriger vers /login, pour
// que Login.jsx puisse y revenir après une connexion réussie (au lieu de
// toujours retomber sur /dashboard). Le loader reçoit le `Request` de
// react-router — on lit son URL, pas `window.location` (SSR-safe/testable).
const buildLoginRedirect = (request) => {
  const url = new URL(request.url)
  const next = url.pathname + url.search + url.hash
  if (next && next !== '/') {
    return redirect(`/login?next=${encodeURIComponent(next)}`)
  }
  return redirect('/login')
}

const authLoader = async ({ request }) => {
  const ok = await ensureSession()
  return ok ? null : buildLoginRedirect(request)
}

// ERR27 — Garde de rôle/permission sur les routes d'administration. Reflète
// EXACTEMENT le gating du menu (Sidebar.jsx) : une route n'est accessible que si
// le rôle (menu_tier) figure dans `roles` ET — si une permission est exigée —
// qu'elle est présente dans les permissions de l'utilisateur.
// VX131(c) — un refus rebondissait en SILENCE vers `/dashboard` (aucun écran
// dédié, aucune explication) : redirige désormais vers `/403` (ui/Forbidden.jsx).
const roleLoader = (roles, perm) => async ({ request }) => {
  const ok = await ensureSession()
  if (!ok) return buildLoginRedirect(request)
  const { role, permissions } = store.getState().auth
  const tier = role || 'normal'
  const allowed = roles.includes(tier) && (!perm || (permissions || []).includes(perm))
  return allowed ? null : redirect('/403')
}

// ODX6 — Garde de MODULE. Enveloppe un loader de base (auth ou rôle) : une fois
// la session/le rôle validés (le loader de base a renvoyé `null`), on redirige
// vers /dashboard si le module `key` de la route est désactivé pour la société.
// Défaut (aucun toggle → liste vide) ⇒ le module n'est jamais désactivé, donc
// comportement byte-identique à aujourd'hui. La liste vient du store, alimentée
// par /auth/me/ (déjà résolue par `ensureSession`).
const moduleLoader = (key, base) => async (args) => {
  const result = await base(args)
  // Le loader de base a redirigé (login / rôle insuffisant) → on respecte.
  if (result) return result
  const disabled = store.getState().auth.modulesDesactives || []
  if (isModuleDisabled(disabled, key)) return redirect('/dashboard')
  return null
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
          <Suspense fallback={<Fallback />}>
            {/* VX134(c) — le contenu de route post-Suspense apparaissait en cut
                dur ; même pattern de remontage par `key={pathname}` que
                RouteErrorBoundary ci-dessus, ici pour rejouer un fondu court
                à chaque navigation (View Transition API notée en option
                future — pas nécessaire pour ce simple fondu). */}
            <div key={pathname} className="route-fade">{children}</div>
          </Suspense>
        </RouteErrorBoundary>
      </Layout>
      <CommandPalette />
    </ShortcutsProvider>
  )
}

const router = createBrowserRouter([
  // Entrée de l'OS : un visiteur non connecté arrive DIRECTEMENT sur le login.
  // La landing reste dans le code (route /landing) mais n'est plus l'entrée.
  //
  // VX64 — Ces routes NUES (sans WithLayout) n'ont AUCUNE boundary : un throw de
  // rendu montrait une page blanche, y compris sur des flux publics tokenisés
  // vus par des clients externes (signature légale, portail, kiosque…). Chaque
  // élément est désormais enveloppé du même `RouteErrorBoundary` que WithLayout,
  // sans layout ERP autour.
  { path: '/',      element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><Login /></Suspense></RouteErrorBoundary> },
  { path: '/landing', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><Landing /></Suspense></RouteErrorBoundary> },
  { path: '/login',  element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><Login /></Suspense></RouteErrorBoundary> },
  // Référence interne du design system (sans auth ni layout : page autonome).
  { path: '/ui', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><UIShowcase /></Suspense></RouteErrorBoundary> },
  // XSAL17 — réservation de visite publique (sans login, sans layout ERP).
  { path: '/rdv/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><PublicBookingPage /></Suspense></RouteErrorBoundary> },
  // XCTR14 — portail client public « Mes contrats » (sans login, sans layout ERP).
  { path: '/portail-contrats/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><PortailContratsPage /></Suspense></RouteErrorBoundary> },
  // XGED1 — cérémonie de signature publique (mono-signataire), sans login.
  { path: '/ged/signature/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><PublicSignaturePage mode="signature" /></Suspense></RouteErrorBoundary> },
  // XGED2 — cérémonie de signature publique d'un destinataire (multi-signataires).
  { path: '/ged/signataire/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><PublicSignaturePage mode="signataire" /></Suspense></RouteErrorBoundary> },
  // XGED7 — dépôt public de fichier (upload-request), sans login.
  { path: '/ged/depot/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><PublicDepotPage /></Suspense></RouteErrorBoundary> },
  // XRH10 — kiosque de pointage (jeton de device en localStorage, sans session).
  { path: '/kiosque', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><KiosquePointage /></Suspense></RouteErrorBoundary> },
  // XSAV19 — « Signaler un problème » via QR équipement (sans login, sans layout ERP).
  { path: '/e/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><EquipementSignalerPage /></Suspense></RouteErrorBoundary> },
  // XSAV10/FG86 — suivi client d'un ticket SAV + CSAT (sans login, sans layout ERP).
  { path: '/suivi/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><TicketSuiviPage /></Suspense></RouteErrorBoundary> },
  // XPLT10 — kiosque TV plein écran des dashboards partagés (authentifié,
  // sans layout ERP — rotation/rafraîchissement pilotés côté écran).
  { path: '/dashboards-tv', loader: authLoader, element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><DashboardsTvPage /></Suspense></RouteErrorBoundary> },
  // XKB19 — consultation publique d'un article KB partagé (sans login, sans layout ERP).
  { path: '/kb/public/:token', element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><PublicArticlePage /></Suspense></RouteErrorBoundary> },

  { path: '/dashboard', loader: authLoader, element: <WithLayout><Dashboard /></WithLayout> },
  { path: '/messages', loader: authLoader, element: <WithLayout><ChatPage /></WithLayout> },

  // Stock — migré vers frontend/src/features/stock/module.config.jsx (ARC48).

  // CRM — migré vers frontend/src/features/crm/module.config.jsx (ARC54).

  // Ventes — migré vers frontend/src/features/ventes/module.config.jsx (ARC54).
  // Non-migrables (errorElement dédié, non exprimable par buildModuleRoutes) :
  // QG12 — Design 3D d'un devis en LECTURE SEULE, plein écran, ouvrable dans une fenêtre.
  { path: '/ventes/devis/:id/3d', loader: authLoader, errorElement: <RouteErrorBoundary />, element: <WithLayout><RoofViewerPage /></WithLayout> },
  // Conception 3D de la toiture (héberge le builder roofPro11 du site, en ERP).
  { path: '/devis-design/:id', loader: authLoader, errorElement: <RouteErrorBoundary />, element: <WithLayout><ToitureDesign /></WithLayout> },

  // Chantiers / Installations — migré vers
  // frontend/src/features/installations/module.config.jsx (ARC54).

  // GED — gestion documentaire (navigateur arborescent)
  { path: '/ged', loader: authLoader, element: <WithLayout><DocumentsPage /></WithLayout> },

  // Après-vente : migré vers frontend/src/features/sav/module.config.jsx (ARC48).

  // IA
  { path: '/ia/agent', loader: authLoader, element: <WithLayout><AgentChat /></WithLayout> },
  { path: '/ia/actions', loader: authLoader, element: <WithLayout><AgentActions /></WithLayout> },
  { path: '/ia/ocr', loader: authLoader, element: <WithLayout><OcrUpload /></WithLayout> },

  // Reporting — migré vers frontend/src/features/reporting/module.config.jsx (ARC54).

  // Administration — migré vers frontend/src/features/admin/module.config.jsx (ARC54).
  // Paramètres — migré vers frontend/src/features/parametres/module.config.jsx (ARC54).

  // UX1 — Routes des modules « coquille » enregistrées via le registre. Chaque
  // route est gatée par le même authLoader/roleLoader que le reste de l'app.
  ...buildModuleRoutes({ WithLayout, authLoader, roleLoader, moduleLoader }),

  // VX131(c) — écran 403 dédié (roleLoader y redirige désormais un refus de
  // rôle/permission), rendu via authLoader seul (un utilisateur non connecté
  // qui atterrit ici passe d'abord par /login, comme toute route protégée).
  { path: '/403', loader: authLoader, element: <WithLayout><Forbidden /></WithLayout> },

  // Catch-all — VX78 : un favori/lien périmé affiche désormais l'écran 404
  // (ui/NotFound.jsx) au lieu de rebondir en silence vers /dashboard.
  { path: '*', element: <WithLayout><NotFound /></WithLayout> },
])

export default router

