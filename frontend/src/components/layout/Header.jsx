import { useSelector, useDispatch } from 'react-redux'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { Menu, Search, LogOut, User as UserIcon, Settings, Zap, Bot } from 'lucide-react'
import {
  Avatar, AvatarFallback, initials,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
} from '../../ui'
import { logoutUser } from '../../features/auth/store/authSlice'
import { toggleCopilot } from '../../features/ia/store/iaSlice'
import GlobalSearch from './GlobalSearch'
import CompanySwitcher from './CompanySwitcher'
import NotificationBell from './NotificationBell'
import ChatBell from './ChatBell'
import Breadcrumbs from './Breadcrumbs'
import LanguageSwitcher from './LanguageSwitcher'
import { titleFor } from './routes.meta'
import { ThemeToggle } from '../../design/ThemeToggle'
import { useT } from '../../i18n'
import { getCurrentTenantTheme, subscribeTenantTheme } from '../../design/tenantTheme'

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

export default function Header({ onMenu }) {
  const location = useLocation()
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const user = useSelector((state) => state.auth.user)
  const t = useT()
  // SCA24 — thème de société (logo/nom) posé par Layout ; Header s'abonne
  // sans refetch (pub/sub en mémoire, cf. design/tenantTheme.js). Repli neutre
  // (PRODUCT_NAME, pas de logo) tant qu'aucun thème n'est chargé/renseigné.
  const [tenantTheme, setTenantThemeState] = useState(getCurrentTenantTheme)
  useEffect(() => subscribeTenantTheme(setTenantThemeState), [])
  const brandName = tenantTheme.nomAffichage || PRODUCT_NAME
  const brandLogoUrl = tenantTheme.logoUrl

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
        <GlobalSearch />
        {/* Déclencheur ⌘K — visible quand la barre de recherche est masquée
            (mobile) et toujours utilisable comme raccourci palette. */}
        <button type="button" className="header-cmdk" onClick={fireCommandPalette}
                aria-label="Recherche et commandes (⌘K)" title="Recherche et commandes (⌘K)">
          <Search size={16} aria-hidden="true" />
          <kbd className="header-cmdk-kbd">⌘K</kbd>
        </button>

        <div className="header-user">
          {/* XPLT19 — sélecteur de société active (multi-sociétés uniquement). */}
          <CompanySwitcher />
          {/* N93 — sélecteur de langue d'interface (FR / EN / العربية). */}
          <LanguageSwitcher />
          <ThemeToggle />
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
        </div>
      </div>
    </header>
  )
}
