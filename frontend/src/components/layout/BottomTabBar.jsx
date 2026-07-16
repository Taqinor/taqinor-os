// I36 — Barre d'onglets inférieure (mobile ≤ 768 px uniquement, via CSS).
// Navigation primaire au pouce, inset de zone sûre iOS respecté.
//
// VX12 — Le 5e onglet « Plus » n'ouvre PLUS le tiroir latéral complet (celui-ci
// reste réservé au hamburger du Header, façon Odoo mobile) : il ouvre un
// tiroir COMPACT auto-porté qui affiche d'abord la GRILLE de modules (3-4
// colonnes, façon apps Odoo mobile), puis déroule les items du module choisi
// en second niveau (bouton retour vers la grille). Réutilise `NAV_SECTIONS`
// (Sidebar.jsx, exportée pour cette tâche) + `moduleNavSections`
// (router/moduleRoutes.jsx, UX1) — seule la PRÉSENTATION change, aucune
// donnée de nav dupliquée.
import { useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Target, FileText, CalendarClock, Menu, ChevronLeft, X } from 'lucide-react'
// ODX7 — LEGACY_NAV_KEYS exclut du merge générique les 6 sections legacy
// (stock/crm/ventes/installations/sav/reporting) que NAV_SECTIONS place déjà
// explicitement à leur position historique (via `navFor()` dans Sidebar.jsx) :
// sans ce filtre, leur `.nav` (désormais aussi présent dans le registre
// générique) ferait doublon dans ce tiroir mobile.
import { NAV_SECTIONS, LEGACY_NAV_KEYS } from './Sidebar'
import { moduleNavSections } from '../../router/moduleRoutes'
// ODX6 — même gating par module actif/désactivé que la Sidebar desktop.
import { filterNavSections, selectModulesDesactives } from '../../router/moduleGating'

const coquilleNavSections = moduleNavSections.filter((s) => !LEGACY_NAV_KEYS.has(s.key))

// Destinations primaires — un sous-ensemble du menu, pensé pour le pouce.
// Toutes existent pour tous les rôles (cf. router/index.jsx + Sidebar).
const TABS = [
  { to: '/dashboard',     label: 'Accueil',    Icon: LayoutDashboard },
  { to: '/crm/leads',     label: 'Leads',      Icon: Target },
  { to: '/ventes/devis',  label: 'Devis',      Icon: FileText },
  { to: '/activites',     label: 'Activités',  Icon: CalendarClock },
]

// M156 — Plafond DUR de 5 onglets atteignables au pouce : au plus 4 raccourcis
// directs + l'onglet « Plus » (qui ouvre le sélecteur d'apps). Au-delà, le 5e
// raccourci serait hors zone de pouce confortable et écraserait « Plus ».
const MAX_DIRECT_TABS = 4
const PRIMARY_TABS = TABS.slice(0, MAX_DIRECT_TABS)

export default function BottomTabBar() {
  const [gridOpen, setGridOpen] = useState(false)

  return (
    <>
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
                onClick={() => setGridOpen(true)} aria-label="Plus de menus">
          <Menu size={20} aria-hidden="true" />
          <span className="bottom-tab-label">Plus</span>
        </button>
      </nav>
      {gridOpen && <AppGridDrawer onClose={() => setGridOpen(false)} />}
    </>
  )
}

// AppGridDrawer — tiroir compact « Plus » : grille de catégories, puis items
// de la catégorie choisie (2e niveau), retour possible à la grille.
const EMPTY_PERMISSIONS = []

function AppGridDrawer({ onClose }) {
  const role = useSelector((s) => s.auth.role) || 'normal'
  // Repli sur une référence STABLE (pas un `[]` littéral recréé à chaque rendu)
  // pour ne pas invalider le useMemo `sections` ci-dessous à chaque render.
  const permissions = useSelector((s) => s.auth.permissions) || EMPTY_PERMISSIONS
  // ODX6 — clés de modules désactivés pour la société ([] par défaut).
  const modulesOff = useSelector(selectModulesDesactives)
  const [activeSection, setActiveSection] = useState(null)

  // Mêmes règles de gating que la Sidebar (role + perm + module actif), mêmes
  // sections dans le MÊME ordre (coquille insérée avant Administration comme sur
  // bureau).
  const sections = useMemo(() => {
    const all = (() => {
      const adminIdx = NAV_SECTIONS.findIndex((s) => s.label === 'ADMINISTRATION')
      if (adminIdx < 0) return [...NAV_SECTIONS, ...coquilleNavSections]
      return [
        ...NAV_SECTIONS.slice(0, adminIdx),
        ...coquilleNavSections,
        ...NAV_SECTIONS.slice(adminIdx),
      ]
    })()
    // ODX6 — retire les sections des modules désactivés (liste vide ⇒ no-op).
    return filterNavSections(all, modulesOff)
      .map((section) => ({
        ...section,
        items: section.items.filter(
          (it) => it.roles.includes(role) && (!it.perm || permissions.includes(it.perm)),
        ),
      }))
      .filter((section) => section.items.length > 0 && section.label)
  }, [role, permissions, modulesOff])

  const current = sections.find((s) => s.label === activeSection) || null

  return (
    <div className="app-grid-drawer" role="dialog" aria-modal="true" aria-label="Toutes les applications">
      <div className="app-grid-overlay" onClick={onClose} />
      <div className="app-grid-panel">
        <div className="app-grid-header">
          {current ? (
            <button type="button" className="app-grid-back" onClick={() => setActiveSection(null)}
                    aria-label="Retour à la grille des applications">
              <ChevronLeft size={18} aria-hidden="true" />
              <span>{current.label}</span>
            </button>
          ) : (
            <span className="app-grid-title">Toutes les applications</span>
          )}
          <button type="button" className="app-grid-close" onClick={onClose} aria-label="Fermer">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {!current && (
          <div className="app-grid" role="list">
            {sections.map((section) => (
              <button
                key={section.label}
                type="button"
                role="listitem"
                className="app-grid-tile"
                onClick={() => setActiveSection(section.label)}
              >
                <span className="app-grid-tile-icon">{section.items[0]?.icon}</span>
                <span className="app-grid-tile-label">{section.label}</span>
              </button>
            ))}
          </div>
        )}

        {current && (
          <div className="app-grid-items" role="list">
            {current.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className="app-grid-item"
                onClick={onClose}
              >
                <span className="app-grid-item-icon">{item.icon}</span>
                <span className="app-grid-item-label">{item.label}</span>
              </NavLink>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
