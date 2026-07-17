import { useState, useEffect, lazy, Suspense } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigation } from 'react-router-dom'
import { fetchMe } from '../../features/auth/store/authSlice'
import { fetchProfile } from '../../features/parametres/store/parametresSlice'
import Sidebar from './Sidebar'
import Header from './Header'
import BottomTabBar from './BottomTabBar'
import RouteFocus from './RouteFocus'
import OnboardingCoachmarks from '../../features/onboarding/OnboardingCoachmarks'
import { OfflineBanner } from '../../ui/OfflineState'
import coreApi from '../../api/coreApi'
import { setTenantTheme, resetTenantTheme } from '../../design/tenantTheme'

// I34 — État réduit de la sidebar persisté en localStorage. Défaut = false
// (comportement actuel : sidebar dépliée). Lecture défensive : tout accès au
// stockage est protégé pour ne jamais casser le rendu (mode privé, SSR…).
const COLLAPSE_KEY = 'taqinor.sidebar.collapsed'

// VX57 — CopilotPanel était monté en dur sur CHAQUE écran authentifié : son
// chunk (icônes, textarea, slice ia…) pesait sur le chemin froid même pour
// les utilisateurs qui n'ouvrent jamais le copilote. Chargé paresseusement
// (React.lazy) et rendu seulement une fois `copilotOpen` devenu vrai une
// première fois (patron AgentChat) — après quoi il reste monté (pas de
// démontage sur fermeture, pour ne pas perdre l'état de la conversation).
const CopilotPanel = lazy(() => import('../../features/ia/CopilotPanel'))

// NTIDE9 — CTA « Suggérer une amélioration » (Intercom-style), chargé
// paresseusement comme le copilote : n'ajoute rien au chemin froid pour un
// utilisateur qui ne l'ouvre jamais.
const SuggestionCTA = lazy(() => import('../../features/innovation/SuggestionCTA'))

// NTIDE37 — bouton discret « Envoyer un retour » (canal feedback produit,
// FeedbackProduit — distinct de la boîte à idées ci-dessus), même patron de
// chargement paresseux.
const FeedbackButton = lazy(() => import('../../features/innovation/FeedbackButton'))

function readCollapsed() {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

function writeCollapsed(v) {
  try {
    window.localStorage.setItem(COLLAPSE_KEY, v ? '1' : '0')
  } catch { /* stockage indisponible : on ignore, l'état reste en mémoire */ }
}

export default function Layout({ children }) {
  const dispatch = useDispatch()
  const [collapsed, setCollapsed] = useState(readCollapsed)
  // Tiroir mobile (≤ 768 px) — sans effet sur le bureau (classe ignorée
  // hors media query). Fermé à chaque navigation.
  const [drawerOpen, setDrawerOpen] = useState(false)
  const isAuthenticated = useSelector(s => s.auth.isAuthenticated)
  const profile = useSelector(s => s.parametres.profile)
  const navigation = useNavigation()
  // VX57 — une fois `copilotOpen` vu vrai, on garde le panneau monté (le
  // fermer ne doit pas jeter son état/historique de conversation) ; tant
  // qu'il n'a jamais été ouvert, son chunk lazy n'est jamais demandé.
  const copilotOpen = useSelector(s => s.ia.copilotOpen)
  // Latch monotone en phase de rendu (patron React « ajuster l'état quand une
  // prop change ») : une fois ouvert, le panneau reste monté ; pas d'effet.
  const [copilotEverOpened, setCopilotEverOpened] = useState(false)
  if (copilotOpen && !copilotEverOpened) setCopilotEverOpened(true)

  // Layout est remonté à CHAQUE navigation de module : ne refetcher la
  // session et le profil entreprise que s'ils manquent — chaque clic de
  // menu coûtait deux allers-retours API inutiles.
  useEffect(() => {
    if (!isAuthenticated) dispatch(fetchMe())
    if (!profile) dispatch(fetchProfile())
  }, [dispatch]) // eslint-disable-line react-hooks/exhaustive-deps

  // SCA24 — thème white-label (TenantTheme) : posé une fois au montage du shell.
  // Résilient par construction : un échec réseau/permission ne doit JAMAIS
  // casser l'app, on retombe silencieusement sur le thème neutre par défaut.
  useEffect(() => {
    let cancelled = false
    coreApi.theme.getCourant()
      .then((res) => { if (!cancelled) setTenantTheme(res.data) })
      .catch(() => { if (!cancelled) resetTenantTheme() })
    return () => { cancelled = true }
  }, [])

  const toggleCollapsed = () => setCollapsed(v => {
    const next = !v
    writeCollapsed(next)
    return next
  })

  return (
    <div className={`layout${drawerOpen ? ' drawer-open' : ''}`}>
      {/* VX197 — skip-link + annonce de route : DOIT être le tout premier
          contenu du DOM pour que le skip-link soit le premier élément
          focalisable au Tab (WCAG 2.4.1). */}
      <RouteFocus />
      <Sidebar collapsed={collapsed} onToggle={toggleCollapsed}
               onNavigate={() => setDrawerOpen(false)} />
      {drawerOpen && (
        <div className="drawer-overlay" onClick={() => setDrawerOpen(false)} />
      )}
      <div className="layout-main">
        <Header onMenu={() => setDrawerOpen(v => !v)} />
        {/* M61 — Bannière hors-ligne visible sur tous les écrans authentifiés.
            Inerte tant que la connexion est présente (rend null en ligne). */}
        <OfflineBanner />
        {/* VX197 — `id="contenu"` = cible du skip-link ET du focus déplacé
            après chaque navigation SPA (RouteFocus.jsx) ; `tabIndex={-1}`
            rend le conteneur focalisable par script sans l'ajouter à l'ordre
            de tabulation normal. */}
        <main id="contenu" tabIndex={-1} className="layout-content">
          {/* I36 — Barre de progression de navigation : feedback instantané,
              plus d'écran périmé muet. Ancrée en haut de la zone de contenu.
              VX197 — aria-live="polite" : un lecteur d'écran n'avait aucun
              moyen de savoir qu'une page était en cours de chargement. */}
          {navigation.state !== 'idle' && (
            <div className="route-progress" role="progressbar"
                 aria-label="Chargement de la page" aria-busy="true" aria-live="polite">
              <span className="route-progress-bar" />
            </div>
          )}
          {children}
        </main>
        {/* I36 — Barre d'onglets inférieure (mobile uniquement, via CSS).
            VX12 — « Plus » ouvre désormais son PROPRE tiroir compact (grille de
            modules), auto-porté par BottomTabBar : ne pilote plus `drawerOpen`
            (réservé au hamburger du Header → tiroir latéral complet). */}
        <BottomTabBar />
      </div>
      {/* FG350 — Copilote in-app : tiroir conversationnel global (agent FastAPI),
          piloté par la slice `ia`. VX57 — chargé et monté paresseusement, à
          partir de la première ouverture seulement (voir copilotEverOpened
          ci-dessus) ; fallback null pour ne jamais afficher de spinner sur un
          panneau encore fermé le temps du chunk. */}
      {copilotEverOpened && (
        <Suspense fallback={null}>
          <CopilotPanel />
        </Suspense>
      )}
      {/* FG16 — Guide d'accueil (coachmarks) : monté une fois, ne s'affiche
          qu'à la première visite (drapeau localStorage) et rejouable depuis
          les Paramètres. Rend null le reste du temps. */}
      <OnboardingCoachmarks />
      {/* NTIDE9 — CTA « Suggérer une amélioration », visible sur chaque écran
          authentifié. Chargé paresseusement (fallback null le temps du
          chunk) ; toujours monté (contrairement au copilote) car LE bouton
          lui-même est le déclencheur, pas un panneau ouvert d'ailleurs. */}
      <Suspense fallback={null}>
        <SuggestionCTA />
      </Suspense>
      {/* NTIDE37 — bouton « Envoyer un retour », même patron de montage que
          SuggestionCTA ci-dessus (canal distinct : feedback produit 1→N
          founder, pas la boîte à idées). */}
      <Suspense fallback={null}>
        <FeedbackButton />
      </Suspense>
    </div>
  )
}
