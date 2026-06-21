// I36 — Barre d'onglets inférieure (mobile ≤ 768 px uniquement, via CSS).
// Navigation primaire au pouce, inset de zone sûre iOS respecté. Le 5e onglet
// « Plus » ouvre le tiroir latéral complet (toute la navigation).
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Target, FileText, CalendarClock, Menu } from 'lucide-react'

// Destinations primaires — un sous-ensemble du menu, pensé pour le pouce.
// Toutes existent pour tous les rôles (cf. router/index.jsx + Sidebar).
const TABS = [
  { to: '/dashboard',     label: 'Accueil',    Icon: LayoutDashboard },
  { to: '/crm/leads',     label: 'Leads',      Icon: Target },
  { to: '/ventes/devis',  label: 'Devis',      Icon: FileText },
  { to: '/activites',     label: 'Activités',  Icon: CalendarClock },
]

// M156 — Plafond DUR de 5 onglets atteignables au pouce : au plus 4 raccourcis
// directs + l'onglet « Plus » (qui ouvre tout le menu). Au-delà, le 5e raccourci
// serait hors zone de pouce confortable et écraserait « Plus ».
const MAX_DIRECT_TABS = 4
const PRIMARY_TABS = TABS.slice(0, MAX_DIRECT_TABS)

export default function BottomTabBar({ onMore }) {
  return (
    <nav className="bottom-tabbar" aria-label="Navigation principale">
      {PRIMARY_TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end
          className={({ isActive }) => `bottom-tab${isActive ? ' active' : ''}`}
        >
          <tab.Icon size={20} aria-hidden="true" />
          <span className="bottom-tab-label">{tab.label}</span>
        </NavLink>
      ))}
      <button type="button" className="bottom-tab bottom-tab-more"
              onClick={onMore} aria-label="Plus de menus">
        <Menu size={20} aria-hidden="true" />
        <span className="bottom-tab-label">Plus</span>
      </button>
    </nav>
  )
}
