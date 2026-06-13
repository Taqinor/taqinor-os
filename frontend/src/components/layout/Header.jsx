import { useSelector } from 'react-redux'
import { useLocation } from 'react-router-dom'

const PAGE_TITLES = {
  '/dashboard': 'Dashboard',
  '/stock': 'Gestion du Stock',
  '/crm/leads': 'CRM — Pipeline',
  '/crm': 'CRM — Clients',
  '/ventes/devis/nouveau': 'Nouveau Devis Solaire',
  '/ventes/devis': 'Devis',
  '/ventes/bons-commande': 'Bons de Commande',
  '/ventes/factures': 'Factures',
  '/ia/agent': 'Agent IA Conversationnel',
  '/ia/ocr': 'Traitement OCR',
  '/reporting': 'Reporting & Analytics',
}

export default function Header({ onMenu }) {
  const location = useLocation()
  const user = useSelector((state) => state.auth.user)

  const title = Object.entries(PAGE_TITLES).find(([path]) =>
    location.pathname.startsWith(path)
  )?.[1] ?? 'ERP Agentique'

  return (
    <header className="header">
      {/* Hamburger : visible uniquement ≤ 768 px (CSS) */}
      <button type="button" className="header-menu-btn" onClick={onMenu}
              aria-label="Ouvrir le menu">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none"
             stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="4" y1="6" x2="20" y2="6" />
          <line x1="4" y1="12" x2="20" y2="12" />
          <line x1="4" y1="18" x2="20" y2="18" />
        </svg>
      </button>
      <h1 className="header-title">{title}</h1>
      <div className="header-user">
        <span className="header-user-avatar">
          {user?.username?.[0]?.toUpperCase() ?? 'U'}
        </span>
        <span className="header-user-name">{user?.username ?? 'Utilisateur'}</span>
      </div>
    </header>
  )
}
