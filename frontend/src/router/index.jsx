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
// NTUX10 — hôte du quick-create universel (⌘K → « Créer… »), même chokepoint
// que CommandPalette ci-dessus (indépendant de son cycle de vie).
import QuickCreateModalHost from '../features/uxviews/quickcreate/QuickCreateModalHost'
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
// ODY3 — résolution de l'atterrissage (préférence VX46 → dernier module VX11 →
// mono-app → Menu d'accueil `/apps`), partagée avec Login.jsx.
import { resolveLandingFromAuth } from '../lib/apps/landing'
// NTPRT8/20/27 — portée d'un compte PORTAIL externe (source unique, pure).
import {
  PORTEE_CLIENT, PORTEE_FOURNISSEUR, PORTEE_PARTENAIRE,
  peutEntrerDansPortail, portalHomePath,
} from '../features/portail/portalScope'

// ── Pages lazy ────────────────────────────────────────────────────────────────
const Landing = lazy(() => import('../pages/Landing'))
const Login = lazy(() => import('../pages/Login'))
const Dashboard = lazy(() => import('../pages/Dashboard').then(m => ({ default: m.Component })))
// ODY2 — Menu d'accueil plein écran (`/apps`) : la porte d'entrée du paradigme
// « j'ouvre → MES apps ». Grille des apps installées ∩ autorisées (ODY1).
const HomeMenu = lazy(() => import('../pages/home/HomeMenu'))
// ODY8 — écran « App non activée » (module OFF pour la société), à la place du
// renvoi muet vers /dashboard.
const AppNotInstalled = lazy(() => import('../pages/home/AppNotInstalled'))
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
// VX247(d) — glossaire métier statique (les HelpTip VX47 y pointent).
const LexiquePage = lazy(() => import('../pages/aide/LexiquePage'))
// NTPRT8 — shell + écrans du PORTAIL CLIENT authentifié (hors shell ERP).
const PortalClientLayout = lazy(() => import('../features/portail/client/PortalClientLayout'))
const PortailClientAccueil = lazy(() => import('../features/portail/client/PortailClientAccueil'))
const PortailClientDevis = lazy(() => import('../features/portail/client/PortailClientDevis'))
const PortailClientFactures = lazy(() => import('../features/portail/client/PortailClientFactures'))
// NTPRT20 — shell + tableau de bord du PORTAIL FOURNISSEUR.
const PortalFournisseurLayout = lazy(() => import('../features/portail/fournisseur/PortalFournisseurLayout'))
const PortailFournisseurAccueil = lazy(() => import('../features/portail/fournisseur/PortailFournisseurAccueil'))
// NTPRT27 — shell + tableau de bord du PORTAIL PARTENAIRE.
const PortalPartenaireLayout = lazy(() => import('../features/portail/partenaire/PortalPartenaireLayout'))
const PortailPartenaireAccueil = lazy(() => import('../features/portail/partenaire/PortailPartenaireAccueil'))

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

// ── NTPRT8/20/27 — Frontière PORTAIL externe ⟷ ERP interne ────────────────────
//
// La garde qui FAIT AUTORITÉ est le backend (NTPRT5 : un compte `portee !=
// interne` reçoit 403 sur toute route interne). Ces loaders ne font qu'éviter à
// un client/fournisseur/partenaire d'atterrir sur une coquille ERP vide.
//
// `ensurePortalScope` garantit que la PORTÉE est connue avant de décider : au
// retour de `/token/`, le store ne porte que `{ username }` (le login ne
// rappelle pas /auth/me/), donc `user.portee` est encore `undefined` — décider
// sur cette valeur laisserait passer un compte portail vers /dashboard le temps
// d'un écran. On force alors UN `fetchMe()` (une seule fois : ensuite `portee`
// est défini, y compris à `interne`).
const ensurePortalScope = async () => {
  const ok = await ensureSession()
  if (!ok) return null
  let user = store.getState().auth.user
  if (!user || user.portee === undefined) {
    await store.dispatch(fetchMe())
    user = store.getState().auth.user
  }
  return user || null
}

// Renvoie une redirection vers le shell portail si `user` est un compte
// externe, sinon `null` (compte interne — parcours inchangé).
const redirectSiPortail = (user) => {
  const home = portalHomePath(user)
  return home ? redirect(home) : null
}

const authLoader = async ({ request }) => {
  const user = await ensurePortalScope()
  if (!user) return buildLoginRedirect(request)
  return redirectSiPortail(user)
}

// Garde des routes `/portail/<scope>` : session valide + portée EXACTE.
// Un interne y est renvoyé sur /dashboard ; un compte portail d'une AUTRE
// portée (fournisseur sur l'espace client) est renvoyé sur SON portail —
// jamais toléré « parce qu'il est portail ».
const portalLoader = (portee) => async ({ request }) => {
  const user = await ensurePortalScope()
  if (!user) return buildLoginRedirect(request)
  if (peutEntrerDansPortail(user, portee)) return null
  return redirectSiPortail(user) || redirect('/dashboard')
}

// Catch-all (VX78) : la route 404 n'a volontairement AUCUN loader (un visiteur
// anonyme doit voir le 404, pas /login). On y ajoute donc la SEULE bascule
// portail — sans exiger de session — pour qu'un lien périmé ne rende jamais la
// coquille ERP à un compte externe.
const notFoundLoader = async () => {
  const { isAuthenticated, user } = store.getState().auth
  if (!isAuthenticated) return null
  return redirectSiPortail(user)
}

// ERR27 — Garde de rôle/permission sur les routes d'administration. Reflète
// EXACTEMENT le gating du menu (Sidebar.jsx) : une route n'est accessible que si
// le rôle (menu_tier) figure dans `roles` ET — si une permission est exigée —
// qu'elle est présente dans les permissions de l'utilisateur.
// VX131(c) — un refus rebondissait en SILENCE vers `/dashboard` (aucun écran
// dédié, aucune explication) : redirige désormais vers `/403` (ui/Forbidden.jsx).
const roleLoader = (roles, perm) => async ({ request }) => {
  const user = await ensurePortalScope()
  if (!user) return buildLoginRedirect(request)
  // NTPRT8 — un compte portail externe ne franchit jamais une route interne,
  // même gardée par rôle : il rejoint son propre shell.
  const versPortail = redirectSiPortail(user)
  if (versPortail) return versPortail
  const { role, permissions } = store.getState().auth
  const tier = role || 'normal'
  const allowed = roles.includes(tier) && (!perm || (permissions || []).includes(perm))
  return allowed ? null : redirect('/403')
}

// ODY3 — Garde de l'ENTRÉE `/`. Jusqu'ici `/` rendait Login SANS aucun loader :
// un utilisateur DÉJÀ connecté qui ouvre la racine (favori, PWA, retour
// d'onglet) revoyait l'écran de connexion. Il atterrit désormais sur SES apps
// (ou l'app d'atterrissage préférée VX46 / l'unique app en mono-app, cf.
// `lib/apps/landing.js`). Un visiteur ANONYME voit toujours le Login, ici même,
// sans redirection vers /login — comportement inchangé, et c'est pourquoi cette
// garde ne réutilise pas `authLoader` (qui redirigerait).
const rootLoader = async () => {
  const user = await ensurePortalScope()
  if (!user) return null // anonyme : Login rendu sur `/`, comme avant
  // Un compte PORTAIL externe ne voit jamais la coquille interne.
  const versPortail = redirectSiPortail(user)
  if (versPortail) return versPortail
  return redirect(resolveLandingFromAuth(store.getState().auth))
}

// ODX6 — Garde de MODULE. Enveloppe un loader de base (auth ou rôle) : une fois
// la session/le rôle validés (le loader de base a renvoyé `null`), on décide du
// sort d'une route dont le module `key` est désactivé pour la société.
// Défaut (aucun toggle → liste vide) ⇒ le module n'est jamais désactivé, donc
// comportement byte-identique. La liste vient du store, alimentée par /auth/me/
// (déjà résolue par `ensureSession`).
//
// ODY8 — ce refus renvoyait EN SILENCE vers `/dashboard` : l'utilisateur
// changeait d'écran sans savoir pourquoi ni comment obtenir l'app. Il atterrit
// désormais sur l'écran dédié `/app-non-activee` (pages/home/AppNotInstalled),
// qui NOMME l'app et donne la marche à suivre selon le rôle. Cette fonction est
// l'UNIQUE implémentation du refus ; ses deux points d'appel (les routes du
// registre, injectées dans `buildModuleRoutes`, et les routes déclarées
// directement ici) en héritent automatiquement.
//
// L'ORDRE compte : `base(args)` s'exécute d'ABORD, donc un refus de RÔLE
// (roleLoader → `/403`, VX131) l'emporte et l'utilisateur n'apprend même pas si
// l'app est installée — aucune donnée révélée.
const moduleLoader = (key, base) => async (args) => {
  const result = await base(args)
  // Le loader de base a redirigé (login / rôle insuffisant) → on respecte.
  if (result) return result
  const disabled = store.getState().auth.modulesDesactives || []
  if (isModuleDisabled(disabled, key)) {
    return redirect(`/app-non-activee?app=${encodeURIComponent(key)}`)
  }
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
      <QuickCreateModalHost />
    </ShortcutsProvider>
  )
}

// NTPRT8/20/27 — équivalent de `WithLayout` pour les PORTAILS EXTERNES : même
// error-boundary + Suspense keyées par chemin, mais AUCUNE surface interne
// (pas de Layout ERP, pas de palette de commandes, pas de quick-create).
function WithPortal(props) {
  const { shell: Shell, children } = props
  const { pathname } = useLocation()
  return (
    <RouteErrorBoundary key={pathname}>
      <Suspense fallback={<Fallback />}>
        <Shell>
          <div key={pathname} className="route-fade">{children}</div>
        </Shell>
      </Suspense>
    </RouteErrorBoundary>
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
  // ODY3 — `/` authentifié → SES apps (`rootLoader`) ; `/` anonyme → Login.
  { path: '/',      loader: rootLoader, element: <RouteErrorBoundary><Suspense fallback={<Fallback />}><Login /></Suspense></RouteErrorBoundary> },
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

  // NTPRT8 — PORTAIL CLIENT authentifié. Shell dédié (jamais le shell ERP) ;
  // `portalLoader` exige la portée EXACTE `portail_client` et renvoie tout
  // autre compte vers SON espace (ou /dashboard pour un interne).
  {
    path: '/portail/client',
    loader: portalLoader(PORTEE_CLIENT),
    element: <WithPortal shell={PortalClientLayout}><PortailClientAccueil /></WithPortal>,
  },
  // NTPRT10 — « Mes devis » : liste + PDF `/proposal` (règle #4) + acceptation.
  {
    path: '/portail/client/devis',
    loader: portalLoader(PORTEE_CLIENT),
    element: <WithPortal shell={PortalClientLayout}><PortailClientDevis /></WithPortal>,
  },
  // NTPRT11 — « Mes commandes & factures » + paiement en ligne GATÉ (CMI).
  {
    path: '/portail/client/factures',
    loader: portalLoader(PORTEE_CLIENT),
    element: <WithPortal shell={PortalClientLayout}><PortailClientFactures /></WithPortal>,
  },
  // NTPRT20 — PORTAIL FOURNISSEUR : garde SYMÉTRIQUE (portée exacte
  // `portail_fournisseur`), shell dédié, jamais la coquille ERP.
  {
    path: '/portail/fournisseur',
    loader: portalLoader(PORTEE_FOURNISSEUR),
    element: <WithPortal shell={PortalFournisseurLayout}><PortailFournisseurAccueil /></WithPortal>,
  },
  // NTPRT27 — PORTAIL PARTENAIRE : garde symétrique (portée exacte
  // `portail_partenaire`), structure identique aux deux shells ci-dessus.
  {
    path: '/portail/partenaire',
    loader: portalLoader(PORTEE_PARTENAIRE),
    element: <WithPortal shell={PortalPartenaireLayout}><PortailPartenaireAccueil /></WithPortal>,
  },

  // ODY2 — Menu d'accueil : la grille de MES apps. `/dashboard` reste une route
  // valide (l'app « Tableau de bord »), ce n'est plus la porte d'entrée.
  { path: '/apps', loader: authLoader, element: <WithLayout><HomeMenu /></WithLayout> },
  // ODY8 — porte dédiée d'une app non activée pour la société (`?app=<clé>`),
  // à la place du renvoi silencieux vers /dashboard.
  { path: '/app-non-activee', loader: authLoader, element: <WithLayout><AppNotInstalled /></WithLayout> },
  { path: '/dashboard', loader: authLoader, element: <WithLayout><Dashboard /></WithLayout> },
  { path: '/messages', loader: authLoader, element: <WithLayout><ChatPage /></WithLayout> },
  // VX247(d) — glossaire métier (les HelpTip VX47 y pointent au lieu de dupliquer).
  { path: '/aide/lexique', loader: authLoader, element: <WithLayout><LexiquePage /></WithLayout> },

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
  // NTPRT8 — `notFoundLoader` n'exige AUCUNE session (le 404 anonyme est
  // préservé) mais renvoie un compte PORTAIL connecté vers son shell : un lien
  // périmé ne doit jamais rendre la coquille ERP à un client externe.
  { path: '*', loader: notFoundLoader, element: <WithLayout><NotFound /></WithLayout> },
])

export default router

