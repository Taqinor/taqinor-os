// VX9 — Lanceur d'applications (grille légère, PAS une page).
//   • Overlay Radix Dialog (~150 ms, cf. index.css) affichant les modules
//     « coquille » enregistrés par `router/moduleRoutes.jsx` (`moduleConfigs`,
//     UX1) en grille par catégorie : icône (VX8 accent) + label FR.
//   • Favoris en tête (localStorage, MÊME clé que VX10 `PinnedApps`), puis
//     3 récents (localStorage propre à ce composant), puis le reste par ordre
//     d'enregistrement.
//   • Clic / Entrée = navigation vers le cockpit du module (1er item `nav`).
//   • S'ouvre sur UN SEUL déclencheur : l'événement window
//     `taqinor:app-launcher`. ODY28 — le raccourci est « g o », câblé dans
//     l'UNIQUE gestionnaire de séquences (`providers/ShortcutsProvider.jsx`,
//     entrée `event` de GOTO_SHORTCUTS) : ce composant n'installe plus de
//     listener `keydown` privé, qui entrait en collision avec « g a » →
//     /approbations. ODY5 — le bouton grille du Header n'émet plus cet
//     événement : il est devenu LA sortie canonique vers le Menu d'accueil.
//   • ODY1 — la grille consomme désormais `useInstalledApps()` (source UNIQUE
//     « mes apps » : registre ∩ modules actifs société ∩ rôle/permission) au
//     lieu de lire `moduleConfigs` directement — une app désactivée en
//     Paramètres ou hors rôle courant disparaît du lanceur.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Star } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../ui/Dialog'
import useInstalledApps from '../../lib/apps/useInstalledApps'
// ODY13 — l'ordre personnel de la grille (clé partagée `lib/apps/appPrefs.js`)
// s'applique aussi ici : lanceur et Menu d'accueil affichent le MÊME ordre.
import { readOrder, applyOrder } from '../../lib/apps/appPrefs'
import AppIcon from '../../ui/AppIcon'
import { prefetchRoute } from '../../router/prefetchMap'
// ODY28 — plus d'import `isTypingTarget` ici : le listener clavier privé de ce
// composant a été supprimé, `ShortcutsProvider` est le gestionnaire unique.

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

export default function AppLauncher() {
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState([])
  const [recent, setRecent] = useState([])
  // ODY13 — ordre personnel de la grille (relu à chaque ouverture, comme les
  // favoris/récents : l'utilisateur a pu réordonner depuis le Menu d'accueil).
  const [order, setOrder] = useState(readOrder)
  const navigate = useNavigate()

  // ODY1 — source unique « mes apps » (registre ∩ modules actifs ∩ rôle).
  // ODY13 — appliquée dans l'ORDRE PERSONNEL de la grille (même clé
  // localStorage) : le lanceur et le Menu d'accueil ne divergent jamais.
  const installees = useInstalledApps()
  const entries = useMemo(() => applyOrder(installees, order), [installees, order])
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
    setOrder(readOrder())
  } else if (!open && wasOpen) {
    setWasOpen(false)
  }

  // Déclencheur — événement window (émis par le raccourci « g o », ODY28),
  // même patron que `taqinor:command-palette` (I134).
  useEffect(() => {
    const onOpen = () => setOpen(true)
    window.addEventListener('taqinor:app-launcher', onOpen)
    return () => window.removeEventListener('taqinor:app-launcher', onOpen)
  }, [])

  // ODY28 — le déclencheur (b) « g a » vivait ici, dans un SECOND listener
  // `keydown` privé, pendant que `providers/shortcuts.js` faisait déjà naviguer
  // « g a » vers /approbations : les DEUX tiraient sur la même frappe (collision
  // réelle). Ce listener est supprimé ; le lanceur a désormais son binding
  // propre (« g o ») dans l'UNIQUE gestionnaire de séquences
  // (`ShortcutsProvider.jsx`), qui émet l'événement window ci-dessus.

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
            /* ODY12 — même préchargement que la grille du Menu d'accueil :
               survol/focus charge le chunk du cockpit avant le clic. */
            onMouseEnter={() => prefetchRoute(entry.to)}
            onFocus={() => prefetchRoute(entry.to)}
          >
            {/* ODY9 — LE composant d'icône d'app (même pastille que le Menu
                d'accueil, les épinglés et l'écran Applications). */}
            <AppIcon icon={entry.icon} accent={entry.accent} appKey={entry.key} size="sm" />
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
