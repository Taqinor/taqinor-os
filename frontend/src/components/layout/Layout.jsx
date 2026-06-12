import { useState, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigation } from 'react-router-dom'
import { fetchMe } from '../../features/auth/store/authSlice'
import { fetchProfile } from '../../features/parametres/store/parametresSlice'
import Sidebar from './Sidebar'
import Header from './Header'

export default function Layout({ children }) {
  const dispatch = useDispatch()
  const [collapsed, setCollapsed] = useState(false)
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

  return (
    <div className={`layout${drawerOpen ? ' drawer-open' : ''}`}>
      {/* Indicateur de navigation instantané — plus d'écran périmé muet */}
      {navigation.state !== 'idle' && <div className="route-progress" />}
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(v => !v)}
               onNavigate={() => setDrawerOpen(false)} />
      {drawerOpen && (
        <div className="drawer-overlay" onClick={() => setDrawerOpen(false)} />
      )}
      <div className="layout-main">
        <Header onMenu={() => setDrawerOpen(v => !v)} />
        <main className="layout-content">
          {children}
        </main>
      </div>
    </div>
  )
}
