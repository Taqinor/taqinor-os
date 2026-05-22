import { useSelector } from 'react-redux'
import { useLocation } from 'react-router-dom'

const PAGE_TITLES = {
  '/dashboard': 'Dashboard',
  '/stock': 'Gestion du Stock',
  '/crm': 'CRM — Clients',
  '/ventes/devis': 'Devis',
  '/ventes/bons-commande': 'Bons de Commande',
  '/ventes/factures': 'Factures',
  '/ia/agent': 'Agent IA Conversationnel',
  '/ia/ocr': 'Traitement OCR',
  '/reporting': 'Reporting & Analytics',
}

export default function Header() {
  const location = useLocation()
  const user = useSelector((state) => state.auth.user)

  const title = Object.entries(PAGE_TITLES).find(([path]) =>
    location.pathname.startsWith(path)
  )?.[1] ?? 'ERP Agentique'

  return (
    <header className="header">
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
