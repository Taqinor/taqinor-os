import { NavLink, useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  LayoutDashboard, MessageSquare, Package, Boxes, Truck, ArrowLeftRight,
  ClipboardList, PackageCheck, FileText, Undo2, ScanLine, Users, Target, Map,
  UserPlus, ShoppingCart, Receipt, FileMinus, Wallet, CalendarClock,
  CalendarDays, HardHat, Wrench, Cpu, BarChart3, Search, Bot, UserCog, Shield,
  ScrollText, Settings, DownloadCloud, LogOut, ChevronLeft, ChevronRight, Key,
  Briefcase, User as UserIcon, FolderOpen,
} from 'lucide-react'
import { logoutUser } from '../../features/auth/store/authSlice'

// ── P168 — Système d'icônes unifié (lucide-react) ─────────────────────────────
// Toutes les icônes de la coquille viennent désormais d'une seule librairie, à
// une épaisseur (1.75) et des tailles standardisées issues de l'échelle 3.5/4/5
// (14 / 16 / 20 px). Plus aucun SVG dessiné à la main : géométrie, alignement et
// poids de trait sont cohérents partout. `aria-hidden` car le libellé textuel
// porte déjà l'accessibilité.
const ICON_MD = 17     // ~4 (16–18 px) — items de navigation
const ICON_SM = 13     // ~3.5 (14 px)  — badges de rôle (denses)
const STROKE = 1.75
const mk = (Comp, size = ICON_MD) => (
  <Comp size={size} strokeWidth={STROKE} aria-hidden="true" />
)

const I = {
  dashboard:    mk(LayoutDashboard),
  produits:     mk(Package),
  mouvements:   mk(ArrowLeftRight),
  ocr_import:   mk(ScanLine),
  clients:      mk(Users),
  leads:        mk(Target),
  devis:        mk(FileText),
  bons_cmd:     mk(ShoppingCart),
  factures:     mk(Receipt),
  wallet:       mk(Wallet),
  ocr:          mk(Search),
  agent_ia:     mk(Bot),
  reporting:    mk(BarChart3),
  utilisateurs: mk(UserCog),
  parametres:   mk(Settings),
  logout:       mk(LogOut),
  chevL:        mk(ChevronLeft),
  chevR:        mk(ChevronRight),
  key:          mk(Key, ICON_SM),
  roles_icon:   mk(Shield),
  briefcase:    mk(Briefcase, ICON_SM),
  user_single:  mk(UserIcon, ICON_SM),
  chantiers:    mk(HardHat),
  outillage:    mk(Wrench),
  equipements:  mk(Boxes),
  sav:          mk(Wrench),
  agenda:       mk(CalendarClock),
  calendrier:   mk(CalendarDays),
  carte:        mk(Map),
  journal:      mk(ScrollText),
  messages:     mk(MessageSquare),
  fournisseurs: mk(Truck),
  cmd_fourn:    mk(ClipboardList),
  reception:    mk(PackageCheck),
  retour:       mk(Undo2),
  parrainage:   mk(UserPlus),
  avoir:        mk(FileMinus),
  production:   mk(BarChart3),
  export:       mk(DownloadCloud),
  cpu:          mk(Cpu),
  documents:    mk(FolderOpen),
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
      { to: '/messages',             label: 'Messages',         icon: I.messages,     roles: ['normal','responsable','admin'] },
    ],
  },
  {
    label: 'STOCK',
    items: [
      { to: '/stock',                label: 'Produits',         icon: I.produits,     roles: ['normal','responsable','admin'] },
      { to: '/stock/categories',     label: 'Catégories & marques', icon: I.equipements, roles: ['responsable','admin'] },
      { to: '/stock/fournisseurs',   label: 'Fournisseurs',     icon: I.fournisseurs, roles: ['responsable','admin'] },
      { to: '/stock/mouvements',     label: 'Mouvements',       icon: I.mouvements,   roles: ['normal','responsable','admin'] },
      { to: '/stock/bons-commande-fournisseur', label: 'Commandes fournisseur', icon: I.cmd_fourn, roles: ['responsable','admin'] },
      { to: '/stock/receptions-fournisseur', label: 'Réceptions fournisseur', icon: I.reception, roles: ['responsable','admin'] },
      { to: '/stock/factures-fournisseur', label: 'Factures fournisseur', icon: I.factures, roles: ['responsable','admin'] },
      { to: '/stock/retours-fournisseur', label: 'Retours fournisseur', icon: I.retour, roles: ['responsable','admin'] },
      { to: '/stock/ocr-import',     label: 'Import OCR',       icon: I.ocr_import,   roles: ['responsable','admin'] },
    ],
  },
  {
    label: 'CRM',
    items: [
      { to: '/activites',            label: 'Mes activités',    icon: I.agenda,       roles: ['normal','responsable','admin'] },
      { to: '/calendrier',           label: 'Calendrier',       icon: I.calendrier,   roles: ['normal','responsable','admin'] },
      { to: '/crm',                  label: 'Clients',          icon: I.clients,      roles: ['normal','responsable','admin'] },
      { to: '/crm/leads',            label: 'Leads',            icon: I.leads,        roles: ['normal','responsable','admin'] },
      { to: '/carte',                label: 'Carte',            icon: I.carte,        roles: ['normal','responsable','admin'] },
      { to: '/crm/parrainage',       label: 'Parrainage',       icon: I.parrainage,   roles: ['normal','responsable','admin'] },
    ],
  },
  {
    label: 'VENTES',
    items: [
      { to: '/ventes/devis',         label: 'Devis',            icon: I.devis,        roles: ['normal','responsable','admin'] },
      { to: '/ventes/bons-commande', label: 'Bons de commande', icon: I.bons_cmd,     roles: ['normal','responsable','admin'] },
      { to: '/ventes/factures',      label: 'Factures',         icon: I.factures,     roles: ['normal','responsable','admin'] },
      { to: '/ventes/avoirs',        label: 'Avoirs',           icon: I.avoir,        roles: ['normal','responsable','admin'] },
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
      { to: '/production',           label: 'Production',       icon: I.production,   roles: ['normal','responsable','admin'] },
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
    label: 'DOCUMENTS',
    items: [
      { to: '/ged',                  label: 'Documents (GED)',  icon: I.documents,    roles: ['normal','responsable','admin'] },
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
      { to: '/parametres/export',    label: 'Export / Sauvegarde', icon: I.export, roles: ['admin'] },
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
                  // I135 — l'item actif porte aria-current="page" : NavLink le
                  // pose automatiquement sur le lien actif (valeur par défaut
                  // "page"), en plus de la classe `active` (pastille discrète).
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
