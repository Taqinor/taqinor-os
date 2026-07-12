import { useSelector, useDispatch } from 'react-redux'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import {
  Menu, Search, LogOut, User as UserIcon, Settings, Zap, Bot, LayoutGrid,
  SlidersHorizontal, Sun, Moon, Monitor,
} from 'lucide-react'
// VX185 — imports DIRECTS (jamais le barrel `../../ui`) : Header est statique
// (Layout.jsx → router/index.jsx → main.jsx), donc TOUT ce que le barrel
// touche (dont `datatable` → recharts/pdfjs-dist, dernière ligne du barrel)
// finissait en `<link rel="modulepreload">` sur CHAQUE page, `/login` inclus
// (~350 Ko gzip avant l'écran de connexion, sur le 4G marocain).
import { Avatar, AvatarFallback, initials } from '../../ui/Avatar'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuCheckboxItem, DropdownMenuLabel, DropdownMenuSeparator,
} from '../../ui/DropdownMenu'
import { logoutUser } from '../../features/auth/store/authSlice'
import { toggleCopilot } from '../../features/ia/store/iaSlice'
import GlobalSearch from './GlobalSearch'
import CompanySwitcher from './CompanySwitcher'
import NotificationBell from './NotificationBell'
import ChatBell from './ChatBell'
import Breadcrumbs from './Breadcrumbs'
import LanguageSwitcher from './LanguageSwitcher'
// VX9 — Lanceur d'applications (overlay grille), déclenché par le bouton
// grille ci-dessous ou le raccourci « g a » (câblé dans le composant lui-même).
import AppLauncher from './AppLauncher'
import { titleFor } from './routes.meta'
import { ThemeToggle } from '../../design/ThemeToggle'
import { useTheme } from '../../design/theme-context'
import { useT } from '../../i18n'
import { getCurrentTenantTheme, subscribeTenantTheme } from '../../design/tenantTheme'
// VX46 — « Mes préférences » : panneau ouvert depuis le menu utilisateur.
import PreferencesPanel from '../../pages/preferences/PreferencesPanel'
import { initPreferences } from '../../pages/preferences/prefs'

// SCA24 — marque produit neutre par défaut (build-time), écrasée par le
// `nom_affichage` du TenantTheme de la société quand il est renseigné.
const PRODUCT_NAME = import.meta.env.VITE_PRODUCT_NAME || 'ERP'

// I35 — Déclenche la palette de commandes (⌘K) construite par l'autre lane,
// qui écoute cet événement exact. On ne construit PAS la palette ici.
function fireCommandPalette() {
  try {
    window.dispatchEvent(new CustomEvent('taqinor:command-palette'))
  } catch { /* environnement sans window : silencieux */ }
}

// VX9 — même patron que fireCommandPalette, pour le lanceur d'applications
// (AppLauncher.jsx écoute exactement cet événement).
function fireAppLauncher() {
  try {
    window.dispatchEvent(new CustomEvent('taqinor:app-launcher'))
  } catch { /* environnement sans window : silencieux */ }
}

export default function Header({ onMenu }) {
  const location = useLocation()
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const user = useSelector((state) => state.auth.user)
  const t = useT()
  // VX181 — le ThemeToggle segmenté disparaît sous md (voir plus bas) ; ces 3
  // options du menu utilisateur restent le SEUL accès au thème sur mobile.
  const { theme, setTheme } = useTheme()
  // SCA24 — thème de société (logo/nom) posé par Layout ; Header s'abonne
  // sans refetch (pub/sub en mémoire, cf. design/tenantTheme.js). Repli neutre
  // (PRODUCT_NAME, pas de logo) tant qu'aucun thème n'est chargé/renseigné.
  const [tenantTheme, setTenantThemeState] = useState(getCurrentTenantTheme)
  useEffect(() => subscribeTenantTheme(setTenantThemeState), [])
  const brandName = tenantTheme.nomAffichage || PRODUCT_NAME
  const brandLogoUrl = tenantTheme.logoUrl

  // VX46 — applique la préférence de réduction de mouvement déjà stockée, une
  // fois par montage de la coquille (Header est présent sur tout écran
  // authentifié — thème/densité ont leur propre init via <ThemeProvider>).
  useEffect(() => { initPreferences() }, [])
  const [prefsOpen, setPrefsOpen] = useState(false)

  // N93 — titre de page traduit via t() ; FR reste le repli (titleFor accepte
  // le traducteur et retombe sur le libellé FR pour tout titre non couvert).
  const title = titleFor(location.pathname, t)
  const username = user?.username ?? 'Utilisateur'

  // Le raccourci clavier global ⌘K / Ctrl+K est capté dans GlobalSearch (monté
  // juste à côté) ; ici on fournit le déclencheur VISIBLE de la palette.

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigate('/login')
  }

  return (
    <header className="header">
      <div className="header-left">
        {/* Hamburger : visible uniquement ≤ 768 px (CSS) */}
        <button type="button" className="header-menu-btn" onClick={onMenu}
                aria-label="Ouvrir le menu">
          <Menu size={22} aria-hidden="true" />
        </button>
        {/* I136 — repère de marque cliquable : pastille « éclair » qui ramène au
            tableau de bord (affordance d'accueil cohérente avec la sidebar).
            SCA24 — si la société a un logo white-label (TenantTheme), il
            remplace la pastille ; sinon repli neutre (icône éclair). */}
        <button type="button" className="header-brand" onClick={() => navigate('/dashboard')}
                aria-label={`Accueil — ${brandName}`} title="Accueil">
          {brandLogoUrl ? (
            <img src={brandLogoUrl} alt={brandName} className="header-brand-logo" />
          ) : (
            <span className="header-brand-bolt" aria-hidden="true">
              <Zap size={14} strokeWidth={2.4} />
            </span>
          )}
        </button>
        <div className="header-heading">
          <Breadcrumbs pathname={location.pathname} />
          {/* Titre de page en élément non-heading : évite la collision de rôle
              `heading` avec le <h2> de chaque page (les tests e2e ciblent le
              titre de page par getByRole('heading')). La classe .header-title
              reste le point d'ancrage des assertions e2e/mobile. */}
          <div className="header-title">{title}</div>
        </div>
      </div>

      <div className="header-right">
        {/* VX2 — les 8 contrôles de l'en-tête regroupés en 3 grappes visuelles
            (wrappers CSS uniquement, aucun changement de comportement) :
            Recherche · Communication · Préférences + compte. */}
        <div className="header-cluster header-cluster-search">
          <GlobalSearch />
          {/* Déclencheur ⌘K — visible quand la barre de recherche est masquée
              (mobile) et toujours utilisable comme raccourci palette. */}
          <button type="button" className="header-cmdk" onClick={fireCommandPalette}
                  aria-label="Recherche et commandes (⌘K)" title="Recherche et commandes (⌘K)">
            <Search size={16} aria-hidden="true" />
            <kbd className="header-cmdk-kbd">⌘K</kbd>
          </button>
          {/* VX9 — bouton grille : ouvre le lanceur d'applications (overlay léger,
              toutes les apps par catégorie). Raccourci clavier « g a ». */}
          <button type="button" className="nb-btn" onClick={fireAppLauncher}
                  aria-label="Toutes les applications (g a)" title="Toutes les applications (g a)">
            <LayoutGrid size={18} aria-hidden="true" />
          </button>
          <AppLauncher />
        </div>

        <div className="header-cluster header-cluster-comm">
          {/* FG350 — bascule du tiroir Copilote (agent FastAPI) accessible
              partout dans l'app shell. */}
          <button
            type="button"
            className="nb-btn"
            aria-label="Ouvrir le Copilote"
            title="Copilote"
            data-testid="copilot-toggle"
            onClick={() => dispatch(toggleCopilot())}
          >
            <Bot size={19} aria-hidden="true" />
          </button>
          <ChatBell />
          <NotificationBell />
        </div>

        <div className="header-user header-cluster header-cluster-account">
          {/* XPLT19 — sélecteur de société active (multi-sociétés uniquement). */}
          <CompanySwitcher />
          {/* N93 — sélecteur de langue d'interface (FR / EN / العربية). */}
          <LanguageSwitcher />
          {/* VX181 — `.header-right` débordait à 320-375px (9 cibles
              interactives, dont ce sélecteur segmenté jamais masqué) : masqué
              sous md, ses 3 options rejoignent le menu utilisateur ci-dessous
              (checkbox items) pour rester accessibles sur mobile. */}
          <ThemeToggle className="hidden md:flex" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="header-usermenu-trigger" aria-label="Menu utilisateur">
                <Avatar className="header-user-avatar-rt">
                  <AvatarFallback className="text-white">{initials(username) || 'U'}</AvatarFallback>
                </Avatar>
                <span className="header-user-name">{username}</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="header-usermenu">
              <DropdownMenuLabel>{username}</DropdownMenuLabel>
              {user?.email && <div className="header-usermenu-email">{user.email}</div>}
              <DropdownMenuSeparator />
              {/* VX181 — thème accessible même sous md, où le ThemeToggle du
                  header est masqué (débordement 320-375px, `.header-right`
                  n'a aucune garde de largeur). */}
              <DropdownMenuLabel className="md:hidden">Thème</DropdownMenuLabel>
              <DropdownMenuCheckboxItem className="md:hidden" checked={theme === 'light'}
                                         onSelect={() => setTheme('light')}>
                <Sun aria-hidden="true" /> Clair
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem className="md:hidden" checked={theme === 'system'}
                                         onSelect={() => setTheme('system')}>
                <Monitor aria-hidden="true" /> Système
              </DropdownMenuCheckboxItem>
              <DropdownMenuCheckboxItem className="md:hidden" checked={theme === 'dark'}
                                         onSelect={() => setTheme('dark')}>
                <Moon aria-hidden="true" /> Sombre
              </DropdownMenuCheckboxItem>
              <DropdownMenuSeparator className="md:hidden" />
              {/* VX46 — « Mes préférences » : thème/densité/atterrissage/mouvement. */}
              <DropdownMenuItem onSelect={() => setPrefsOpen(true)}>
                <SlidersHorizontal aria-hidden="true" /> Mes préférences
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => navigate('/parametres')}>
                <Settings aria-hidden="true" /> Paramètres
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => navigate('/admin/users')}>
                <UserIcon aria-hidden="true" /> Utilisateurs
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={handleLogout}>
                <LogOut aria-hidden="true" /> Déconnexion
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <PreferencesPanel open={prefsOpen} onOpenChange={setPrefsOpen} />
        </div>
      </div>
    </header>
  )
}
