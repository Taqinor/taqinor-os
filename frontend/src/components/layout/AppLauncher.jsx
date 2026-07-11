// VX9 — Lanceur d'applications (grille légère, PAS une page).
//   • Overlay Radix Dialog (~150 ms, cf. index.css) affichant les modules
//     « coquille » enregistrés par `router/moduleRoutes.jsx` (`moduleConfigs`,
//     UX1) en grille par catégorie : icône (VX8 accent) + label FR.
//   • Favoris en tête (localStorage, MÊME clé que VX10 `PinnedApps`), puis
//     3 récents (localStorage propre à ce composant), puis le reste par ordre
//     d'enregistrement.
//   • Clic / Entrée = navigation vers le cockpit du module (1er item `nav`).
//   • S'ouvre sur DEUX déclencheurs, comme la palette de commandes (I134) :
//     l'événement window `taqinor:app-launcher` (bouton grille du Header) et
//     le raccourci global « g a » (capté par ShortcutsProvider, cf. shortcuts.js
//     GOTO_SHORTCUTS ne convient pas ici car « g a » doit OUVRIR, pas naviguer —
//     câblé directement dans ce composant pour rester lane-disjoint).
//   • Coordination ODX6 : quand le catalogue ODX3/ODX6 livrera le filtrage de
//     modules actifs par société, cette grille consommera la MÊME source —
//     aujourd'hui elle affiche tous les `moduleConfigs` enregistrés (pas de
//     duplication de logique de filtrage).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Star } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../ui/Dialog'
import { moduleConfigs } from '../../router/moduleRoutes'
import { isTypingTarget } from '../../providers/shortcuts'

// Même clé que VX10 (PinnedApps) — état d'épinglage PARTAGÉ entre la Sidebar et
// le lanceur, posée ici en repli tolérant tant que VX10 n'est pas construit.
const PINNED_KEY = 'taqinor.sidebar.pinned'
// Récents PROPRES au lanceur (distinct de `taqinor.cmdk.recent`, I134 — la
// palette et le lanceur ont des usages différents : entités vs modules).
const RECENT_KEY = 'taqinor.launcher.recent'
const RECENT_MAX = 3

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

function readList(key) {
  const s = storage()
  if (!s) return []
  try {
    const raw = s.getItem(key)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function writeList(key, list) {
  const s = storage()
  if (!s) return
  try {
    s.setItem(key, JSON.stringify(list))
  } catch { /* stockage indisponible : on ignore, état en mémoire seulement */ }
}

// pushRecentModule — place la clé de module en tête (dédoublonnée), tronque à
// RECENT_MAX, persiste.
function pushRecentModule(key) {
  if (!key) return readList(RECENT_KEY)
  const next = [key, ...readList(RECENT_KEY).filter((k) => k !== key)].slice(0, RECENT_MAX)
  writeList(RECENT_KEY, next)
  return next
}

function readRecentModules() {
  return readList(RECENT_KEY)
}

function readPinnedModules() {
  return readList(PINNED_KEY)
}

// buildEntries — dérive de `moduleConfigs` la liste affichable : une entrée
// par module ayant une section `nav` (les modules routes-only comme `admin`/
// `crm` n'en ont pas et n'apparaissent pas — ils vivent déjà dans la Sidebar
// « coquille » historique, hors périmètre `moduleConfigs`).
function buildEntries(configs) {
  return configs
    .filter((c) => c.nav && c.nav.items && c.nav.items.length > 0)
    .map((c) => {
      const first = c.nav.items[0]
      return {
        key: c.key,
        label: c.nav.label,
        to: first.to,
        icon: first.icon,
      }
    })
}

export default function AppLauncher() {
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState([])
  const [recent, setRecent] = useState([])
  const navigate = useNavigate()
  const gPendingRef = useRef(false)
  const gTimerRef = useRef(null)

  const entries = useMemo(() => buildEntries(moduleConfigs), [])
  const entryByKey = useMemo(() => new Map(entries.map((e) => [e.key, e])), [entries])

  // Relit favoris/récents à CHAQUE ouverture (repli défensif — VX10 peut
  // modifier la clé pinned pendant que le lanceur est fermé). Fait en phase de
  // rendu au front montant de `open` (patron React « ajuster l'état quand une
  // valeur change »), pas dans un effet-setState ; lecture localStorage pure.
  const [wasOpen, setWasOpen] = useState(false)
  if (open && !wasOpen) {
    setWasOpen(true)
    setPinned(readPinnedModules())
    setRecent(readRecentModules())
  } else if (!open && wasOpen) {
    setWasOpen(false)
  }

  // Déclencheur (a) — événement window (bouton grille du Header), même patron
  // que `taqinor:command-palette` (I134).
  useEffect(() => {
    const onOpen = () => setOpen(true)
    window.addEventListener('taqinor:app-launcher', onOpen)
    return () => window.removeEventListener('taqinor:app-launcher', onOpen)
  }, [])

  // Déclencheur (b) — raccourci « g a ». Séquence indépendante de celle de
  // ShortcutsProvider (fichiers disjoints, lane-safe) : ignore la saisie et les
  // combinaisons avec modificateur, comme I37.
  useEffect(() => {
    const clearPending = () => {
      gPendingRef.current = false
      if (gTimerRef.current) { clearTimeout(gTimerRef.current); gTimerRef.current = null }
    }
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return
      if (gPendingRef.current) {
        const key = e.key.toLowerCase()
        clearPending()
        if (key === 'a') {
          e.preventDefault()
          setOpen(true)
        }
        return
      }
      if (e.key === 'g' || e.key === 'G') {
        gPendingRef.current = true
        gTimerRef.current = setTimeout(clearPending, 1200)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      clearPending()
    }
  }, [])

  const goTo = useCallback((entry) => {
    pushRecentModule(entry.key)
    setOpen(false)
    navigate(entry.to)
  }, [navigate])

  const togglePin = useCallback((e, key) => {
    e.stopPropagation()
    const isPinned = pinned.includes(key)
    const next = isPinned ? pinned.filter((k) => k !== key) : [...pinned, key]
    setPinned(next)
    writeList(PINNED_KEY, next)
  }, [pinned])

  const pinnedEntries = pinned.map((k) => entryByKey.get(k)).filter(Boolean)
  const recentEntries = recent
    .map((k) => entryByKey.get(k))
    .filter((e) => e && !pinned.includes(e.key))
  const restEntries = entries.filter(
    (e) => !pinned.includes(e.key) && !recentEntries.some((r) => r.key === e.key),
  )

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="app-launcher-content"
        aria-label="Lanceur d'applications"
      >
        <DialogTitle className="app-launcher-title">Mes applications</DialogTitle>
        <DialogDescription>
          Toutes vos applications. Cliquez ou naviguez au clavier pour ouvrir un module.
        </DialogDescription>

        {pinnedEntries.length > 0 && (
          <AppLauncherSection
            title="Favoris"
            entries={pinnedEntries}
            pinned={pinned}
            onOpen={goTo}
            onTogglePin={togglePin}
          />
        )}
        {recentEntries.length > 0 && (
          <AppLauncherSection
            title="Récents"
            entries={recentEntries}
            pinned={pinned}
            onOpen={goTo}
            onTogglePin={togglePin}
          />
        )}
        <AppLauncherSection
          title="Toutes les applications"
          entries={restEntries}
          pinned={pinned}
          onOpen={goTo}
          onTogglePin={togglePin}
        />
      </DialogContent>
    </Dialog>
  )
}

function AppLauncherSection({ title, entries, pinned, onOpen, onTogglePin }) {
  if (entries.length === 0) return null
  return (
    <div className="app-launcher-section">
      <div className="app-launcher-section-label">{title}</div>
      <div className="app-launcher-grid" role="list">
        {entries.map((entry) => (
          <button
            key={entry.key}
            type="button"
            role="listitem"
            className="app-launcher-tile"
            onClick={() => onOpen(entry)}
          >
            <span className="app-launcher-tile-icon">{entry.icon}</span>
            <span className="app-launcher-tile-label">{entry.label}</span>
            <span
              className="app-launcher-tile-pin"
              role="button"
              tabIndex={0}
              aria-label={pinned.includes(entry.key) ? `Désépingler ${entry.label}` : `Épingler ${entry.label}`}
              onClick={(e) => onTogglePin(e, entry.key)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onTogglePin(e, entry.key)
                }
              }}
            >
              <Star
                size={13}
                strokeWidth={1.75}
                aria-hidden="true"
                fill={pinned.includes(entry.key) ? 'currentColor' : 'none'}
              />
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
