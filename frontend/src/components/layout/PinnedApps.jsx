// VX10 — Apps épinglées personnelles dans la Sidebar.
//   • Bande fine sous `.sidebar-role` : 4-6 icônes de modules épinglés (clic =
//     cockpit du module), bouton « + » pour épingler/désépingler depuis
//     `moduleConfigs` (UX1).
//   • Persistance localStorage `taqinor.sidebar.pinned` — MÊME clé que VX9
//     (AppLauncher.jsx), patron `COLLAPSE_KEY` de Layout.jsx:16 (accès
//     défensif, jamais d'exception si le stockage est indisponible).
//   • Masquée quand aucune app n'est épinglée (pas de bande vide) et masquée
//     en tiroir replié (mêmes contraintes visuelles que `.sidebar-role`).
import { useEffect, useMemo, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Pin, Plus, X } from 'lucide-react'
import { moduleConfigs } from '../../router/moduleRoutes'

// Même clé que AppLauncher.jsx (VX9) — état d'épinglage PARTAGÉ.
const PINNED_KEY = 'taqinor.sidebar.pinned'
const PINNED_MAX = 6

function readPinned() {
  try {
    const raw = window.localStorage.getItem(PINNED_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function writePinned(list) {
  try {
    window.localStorage.setItem(PINNED_KEY, JSON.stringify(list))
  } catch { /* stockage indisponible : on ignore, état en mémoire seulement */ }
}

// buildEntries — mêmes règles que AppLauncher.jsx (VX9) : un module « coquille »
// avec section `nav` → une entrée { key, label, to, icon }.
function buildEntries(configs) {
  return configs
    .filter((c) => c.nav && c.nav.items && c.nav.items.length > 0)
    .map((c) => {
      const first = c.nav.items[0]
      return { key: c.key, label: c.nav.label, to: first.to, icon: first.icon }
    })
}

export default function PinnedApps({ collapsed }) {
  const [pinned, setPinned] = useState(readPinned)
  const [pickerOpen, setPickerOpen] = useState(false)

  const entries = useMemo(() => buildEntries(moduleConfigs), [])
  const entryByKey = useMemo(() => new Map(entries.map((e) => [e.key, e])), [entries])

  // Re-synchronise si une AUTRE surface (AppLauncher, VX9) modifie la même clé
  // pendant que la Sidebar est montée — écoute l'événement `storage` standard
  // (autres onglets) ET un événement interne pour le même onglet.
  useEffect(() => {
    const sync = () => setPinned(readPinned())
    window.addEventListener('storage', sync)
    window.addEventListener('taqinor:pinned-changed', sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener('taqinor:pinned-changed', sync)
    }
  }, [])

  const persist = (next) => {
    setPinned(next)
    writePinned(next)
    try {
      window.dispatchEvent(new CustomEvent('taqinor:pinned-changed'))
    } catch { /* environnement sans window : silencieux */ }
  }

  const togglePin = (key) => {
    const next = pinned.includes(key) ? pinned.filter((k) => k !== key) : [...pinned, key].slice(0, PINNED_MAX)
    persist(next)
  }

  const pinnedEntries = pinned.map((k) => entryByKey.get(k)).filter(Boolean)

  // Rien à afficher : pas de bande, pas de bouton « + » orphelin (repli, comme
  // ImpactPastille — aucun coût visuel pour un utilisateur sans épingle).
  if (collapsed) return null
  if (pinnedEntries.length === 0 && !pickerOpen) {
    return (
      <div className="sidebar-pinned sidebar-pinned--empty">
        <button
          type="button"
          className="sidebar-pinned-add"
          onClick={() => setPickerOpen(true)}
          aria-label="Épingler une application"
          title="Épingler une application"
        >
          <Plus size={13} strokeWidth={1.75} aria-hidden="true" />
          <span>Épingler une app</span>
        </button>
      </div>
    )
  }

  return (
    <div className="sidebar-pinned">
      <div className="sidebar-pinned-list">
        {pinnedEntries.map((entry) => (
          <NavLink
            key={entry.key}
            to={entry.to}
            className="sidebar-pinned-item"
            title={entry.label}
            aria-label={entry.label}
          >
            <span className="sidebar-pinned-icon">{entry.icon}</span>
          </NavLink>
        ))}
        <button
          type="button"
          className="sidebar-pinned-toggle"
          onClick={() => setPickerOpen((v) => !v)}
          aria-label={pickerOpen ? 'Fermer le sélecteur d’épingles' : 'Gérer les apps épinglées'}
          aria-expanded={pickerOpen}
          title="Gérer les apps épinglées"
        >
          {pickerOpen ? <X size={13} strokeWidth={1.75} aria-hidden="true" /> : <Plus size={13} strokeWidth={1.75} aria-hidden="true" />}
        </button>
      </div>
      {pickerOpen && (
        <div className="sidebar-pinned-picker" role="menu">
          {entries.map((entry) => {
            const isPinned = pinned.includes(entry.key)
            return (
              <button
                key={entry.key}
                type="button"
                role="menuitemcheckbox"
                aria-checked={isPinned}
                className="sidebar-pinned-picker-item"
                onClick={() => togglePin(entry.key)}
                disabled={!isPinned && pinned.length >= PINNED_MAX}
              >
                <span className="sidebar-pinned-picker-icon">{entry.icon}</span>
                <span className="sidebar-pinned-picker-label">{entry.label}</span>
                {isPinned && <Pin size={12} strokeWidth={1.75} aria-hidden="true" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
