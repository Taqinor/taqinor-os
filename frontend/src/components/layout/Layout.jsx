import { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigation } from 'react-router-dom'
import { fetchMe } from '../../features/auth/store/authSlice'
import { fetchProfile } from '../../features/parametres/store/parametresSlice'
import Sidebar from './Sidebar'
import Header from './Header'
import BottomTabBar from './BottomTabBar'
import CopilotPanel from '../../features/ia/CopilotPanel'
import OnboardingCoachmarks from '../../features/onboarding/OnboardingCoachmarks'
import { OfflineBanner } from '../../ui/OfflineState'

// I34 — État réduit de la sidebar persisté en localStorage. Défaut = false
// (comportement actuel : sidebar dépliée). Lecture défensive : tout accès au
// stockage est protégé pour ne jamais casser le rendu (mode privé, SSR…).
const COLLAPSE_KEY = 'taqinor.sidebar.collapsed'

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

  // Layout est remonté à CHAQUE navigation de module : ne refetcher la
  // session et le profil entreprise que s'ils manquent — chaque clic de
  // menu coûtait deux allers-retours API inutiles.
  useEffect(() => {
    if (!isAuthenticated) dispatch(fetchMe())
    if (!profile) dispatch(fetchProfile())
  }, [dispatch]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggleCollapsed = () => setCollapsed(v => {
    const next = !v
    writeCollapsed(next)
    return next
  })

  return (
    <div className={`layout${drawerOpen ? ' drawer-open' : ''}`}>
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
        <main className="layout-content">
          {/* I36 — Barre de progression de navigation : feedback instantané,
              plus d'écran périmé muet. Ancrée en haut de la zone de contenu. */}
          {navigation.state !== 'idle' && (
            <div className="route-progress" role="progressbar"
                 aria-label="Chargement de la page" aria-busy="true">
              <span className="route-progress-bar" />
            </div>
          )}
          {children}
        </main>
        {/* I36 — Barre d'onglets inférieure (mobile uniquement, via CSS). */}
        <BottomTabBar onMore={() => setDrawerOpen(true)} />
      </div>
      {/* FG350 — Copilote in-app : tiroir conversationnel global (agent FastAPI),
          monté une fois pour toute l'app, piloté par la slice `ia`. */}
      <CopilotPanel />
      {/* FG16 — Guide d'accueil (coachmarks) : monté une fois, ne s'affiche
          qu'à la première visite (drapeau localStorage) et rejouable depuis
          les Paramètres. Rend null le reste du temps. */}
      <OnboardingCoachmarks />
    </div>
  )
}
