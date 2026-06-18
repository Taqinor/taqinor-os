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

export default function BottomTabBar({ onMore }) {
  return (
    <nav className="bottom-tabbar" aria-label="Navigation principale">
      {TABS.map((tab) => (
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
