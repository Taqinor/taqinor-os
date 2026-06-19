import { NavLink, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { logoutUser } from '../../features/auth/store/authSlice'

// ── SVG icon system ───────────────────────────────────────────────────────────
function Ic({ size = 17, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, display: 'block' }}>
      {children}
    </svg>
  )
}

const I = {
  dashboard:    <Ic><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></Ic>,
  produits:     <Ic><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></Ic>,
  mouvements:   <Ic><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></Ic>,
  ocr_import:   <Ic><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></Ic>,
  clients:      <Ic><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></Ic>,
  leads:        <Ic><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></Ic>,
  devis:        <Ic><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="8" y1="9" x2="10" y2="9"/></Ic>,
  bons_cmd:     <Ic><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></Ic>,
  factures:     <Ic><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="15" y2="11"/><line x1="9" y1="15" x2="12" y2="15"/></Ic>,
  wallet:       <Ic><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/></Ic>,
  ocr:          <Ic><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></Ic>,
  agent_ia:     <Ic><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/><line x1="12" y1="15" x2="12" y2="17"/></Ic>,
  reporting:    <Ic><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></Ic>,
  utilisateurs: <Ic><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></Ic>,
  parametres:   <Ic><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></Ic>,
  logout:       <Ic><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></Ic>,
  chevL:        <Ic><polyline points="15 18 9 12 15 6"/></Ic>,
  chevR:        <Ic><polyline points="9 18 15 12 9 6"/></Ic>,
  key:          <Ic size={13}><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></Ic>,
  roles_icon:   <Ic><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></Ic>,
  briefcase:    <Ic size={13}><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></Ic>,
  user_single:  <Ic size={13}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></Ic>,
  chantiers:    <Ic><path d="M2 20h20"/><path d="M4 20V8l8-5 8 5v12"/><path d="M9 20v-6h6v6"/></Ic>,
  outillage:    <Ic><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6a2 2 0 1 0 2.8 2.8l6-6a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.1-2.1 2.6-2.6z"/></Ic>,
  equipements:  <Ic><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/></Ic>,
  sav:          <Ic><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6a2 2 0 1 0 2.8 2.8l6-6a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.1-2.1 2.6-2.6z"/></Ic>,
  agenda:       <Ic><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></Ic>,
  carte:        <Ic><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></Ic>,
  journal:      <Ic><path d="M3 3v18h18"/><rect x="7" y="12" width="3" height="6"/><rect x="12" y="8" width="3" height="10"/><rect x="17" y="5" width="3" height="13"/></Ic>,
}

const ROLE_META = {
  admin:       { label: 'Administrateur', icon: I.key },
  responsable: { label: 'Responsable',    icon: I.briefcase },
  normal:      { label: 'Utilisateur',    icon: I.user_single },
}

const NAV_SECTIONS = [
  {
    label: null,
    items: [
      { to: '/dashboard',            label: 'Dashboard',        icon: I.dashboard,    roles: ['normal','responsable','admin'] },
    ],
  },
  {
    label: 'STOCK',
    items: [
      { to: '/stock',                label: 'Produits',         icon: I.produits,     roles: ['normal','responsable','admin'] },
      { to: '/stock/categories',     label: 'Catégories & marques', icon: I.equipements, roles: ['responsable','admin'] },
      { to: '/stock/fournisseurs',   label: 'Fournisseurs',     icon: I.clients,      roles: ['responsable','admin'] },
      { to: '/stock/mouvements',     label: 'Mouvements',       icon: I.mouvements,   roles: ['normal','responsable','admin'] },
      { to: '/stock/bons-commande-fournisseur', label: 'Commandes fournisseur', icon: I.bons_cmd, roles: ['responsable','admin'] },
      { to: '/stock/retours-fournisseur', label: 'Retours fournisseur', icon: I.mouvements, roles: ['responsable','admin'] },
      { to: '/stock/ocr-import',     label: 'Import OCR',       icon: I.ocr_import,   roles: ['responsable','admin'] },
    ],
  },
  {
    label: 'CRM',
    items: [
      { to: '/activites',            label: 'Mes activités',    icon: I.agenda,       roles: ['normal','responsable','admin'] },
      { to: '/calendrier',           label: 'Calendrier',       icon: I.agenda,       roles: ['normal','responsable','admin'] },
      { to: '/crm',                  label: 'Clients',          icon: I.clients,      roles: ['normal','responsable','admin'] },
      { to: '/crm/leads',            label: 'Leads',            icon: I.leads,        roles: ['normal','responsable','admin'] },
      { to: '/carte',                label: 'Carte',            icon: I.carte,        roles: ['normal','responsable','admin'] },
      { to: '/crm/parrainage',       label: 'Parrainage',       icon: I.clients,      roles: ['normal','responsable','admin'] },
    ],
  },
  {
    label: 'VENTES',
    items: [
      { to: '/ventes/devis',         label: 'Devis',            icon: I.devis,        roles: ['normal','responsable','admin'] },
      { to: '/ventes/bons-commande', label: 'Bons de commande', icon: I.bons_cmd,     roles: ['normal','responsable','admin'] },
      { to: '/ventes/factures',      label: 'Factures',         icon: I.factures,     roles: ['normal','responsable','admin'] },
      { to: '/ventes/avoirs',        label: 'Avoirs',           icon: I.factures,     roles: ['normal','responsable','admin'] },
      { to: '/ventes/paiements',     label: 'Encaissements',    icon: I.wallet,       roles: ['normal','responsable','admin'] },
      { to: '/ventes/relances',      label: 'Relances / Impayés', icon: I.agenda,     roles: ['responsable','admin'] },
    ],
  },
  {
    label: 'CHANTIERS',
    items: [
      { to: '/ma-journee',           label: 'Ma journée',       icon: I.agenda,       roles: ['normal','responsable','admin'] },
      { to: '/chantiers',            label: 'Chantiers',        icon: I.chantiers,    roles: ['normal','responsable','admin'] },
      { to: '/interventions',        label: 'Interventions',    icon: I.outillage,    roles: ['normal','responsable','admin'] },
      { to: '/parc',                 label: 'Parc installé',    icon: I.equipements,  roles: ['normal','responsable','admin'] },
      { to: '/production',           label: 'Production',       icon: I.reporting,    roles: ['normal','responsable','admin'] },
      { to: '/outillage',            label: 'Outillage',        icon: I.outillage,    roles: ['normal','responsable','admin'] },
    ],
  },
  {
    label: 'APRÈS-VENTE',
    items: [
      { to: '/equipements',          label: 'Équipements',      icon: I.equipements,  roles: ['normal','responsable','admin'] },
      { to: '/sav',                  label: 'Tickets SAV',      icon: I.sav,          roles: ['normal','responsable','admin'] },
      { to: '/sav/contrats',         label: 'Contrats maintenance', icon: I.sav,      roles: ['responsable','admin'] },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { to: '/ia/ocr',               label: 'OCR',              icon: I.ocr,          roles: ['responsable','admin'] },
      { to: '/ia/agent',             label: 'Agent IA',         icon: I.agent_ia,     roles: ['admin'] },
    ],
  },
  {
    label: 'ANALYSE',
    items: [
      { to: '/reporting',            label: 'Reporting',        icon: I.reporting,    roles: ['responsable','admin'] },
      { to: '/rapports',             label: 'Rapports',         icon: I.reporting,    roles: ['responsable','admin'] },
      { to: '/reporting/balance-agee', label: 'Balance âgée',   icon: I.reporting,    roles: ['responsable','admin'] },
    ],
  },
  {
    label: 'ADMINISTRATION',
    items: [
      { to: '/admin/users',          label: 'Utilisateurs',     icon: I.utilisateurs,  roles: ['responsable','admin'] },
      { to: '/admin/roles',          label: 'Rôles',            icon: I.roles_icon,    roles: ['responsable','admin'] },
      // Journal d'activité — visible UNIQUEMENT avec la permission dédiée
      // (Directeur par défaut), indépendamment du palier de menu.
      { to: '/journal',              label: "Journal d'activité", icon: I.journal,    roles: ['normal','responsable','admin'], perm: 'journal_activite_voir' },
      { to: '/parametres',           label: 'Paramètres',       icon: I.parametres,    roles: ['responsable','admin'] },
      // N97 — export configurable & sauvegarde : réservé à l'administrateur
      // (l'endpoint backend exige le rôle admin).
      { to: '/parametres/export',    label: 'Export / Sauvegarde', icon: I.parametres, roles: ['admin'] },
    ],
  },
]

export default function Sidebar({ collapsed, onToggle, onNavigate }) {
  const dispatch    = useDispatch()
  const navigate    = useNavigate()
  const role        = useSelector((s) => s.auth.role) || 'normal'
  const permissions = useSelector((s) => s.auth.permissions) || []
  const companyName = useSelector((s) => s.parametres.profile?.nom) || 'TAQINOR ERP'
  const roleMeta    = ROLE_META[role] ?? ROLE_META.normal

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigate('/login')
  }

  return (
    <aside className={`sidebar${collapsed ? ' sidebar--collapsed' : ''}`}>

      {/* ── Brand header (marque) ──────────────── */}
      <div className="sidebar-header">
        <div className="sidebar-brand" title={collapsed ? companyName : undefined}>
          <div className="sidebar-bolt">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="#0d1b3e">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          </div>
          {!collapsed && (
            <span className="sidebar-brand-text">
              <span className="sidebar-company-name">{companyName}</span>
              <span className="sidebar-brand-sub">ERP Solaire</span>
            </span>
          )}
        </div>
        <button
          type="button"
          className="sidebar-toggle"
          onClick={onToggle}
          aria-label={collapsed ? 'Développer le menu' : 'Réduire le menu'}
          title={collapsed ? 'Développer' : 'Réduire'}
        >
          {collapsed ? I.chevR : I.chevL}
        </button>
      </div>

      {/* ── Role badge ─────────────────────────── */}
      {!collapsed && (
        <div className="sidebar-role">
          <span className="sidebar-role-icon">{roleMeta.icon}</span>
          <span className="sidebar-role-label">{roleMeta.label}</span>
        </div>
      )}

      {/* ── Navigation ─────────────────────────── */}
      <nav className="sidebar-nav">
        {NAV_SECTIONS.map((section, si) => {
          const items = section.items.filter(it =>
            it.roles.includes(role) && (!it.perm || permissions.includes(it.perm)))
          if (items.length === 0) return null
          return (
            <div key={si} className="sidebar-section">
              {section.label && !collapsed && (
                <div className="sidebar-section-label">{section.label}</div>
              )}
              {items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  title={collapsed ? item.label : undefined}
                  onClick={onNavigate}
                  className={({ isActive }) => `sidebar-nav-item${isActive ? ' active' : ''}`}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  {!collapsed && <span className="sidebar-nav-label">{item.label}</span>}
                </NavLink>
              ))}
            </div>
          )
        })}
      </nav>

      {/* ── Logout ─────────────────────────────── */}
      <button
        className="sidebar-logout"
        onClick={handleLogout}
        title={collapsed ? 'Déconnexion' : undefined}
      >
        {I.logout}
        {!collapsed && <span className="sidebar-logout-label">Déconnexion</span>}
      </button>
    </aside>
  )
}
