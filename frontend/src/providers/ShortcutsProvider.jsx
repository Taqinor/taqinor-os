// I37 — Raccourcis clavier globaux + dialogue d'aide « ? ».
//   • « ? »          → ouvre l'aide listant les raccourcis (FR).
//   • « g » puis x   → navigation directe (g d = dashboard, g l = leads, …).
// La frappe est IGNORÉE quand le focus est dans un champ de saisie / textarea /
// contenteditable, et toute combinaison avec modificateur (⌘/Ctrl/Alt) est
// laissée au système (la palette gère ⌘K). Aucun vol de focus en saisie normale.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import { GOTO_SHORTCUTS, GLOBAL_SHORTCUTS, isTypingTarget } from './shortcuts'

// Fenêtre (ms) pour taper la 2e touche d'une séquence « g x ».
const SEQUENCE_MS = 1200

export function ShortcutsProvider({ children }) {
  const [helpOpen, setHelpOpen] = useState(false)
  const navigate = useNavigate()
  // Séquence en cours (ex. on a appuyé sur « g », on attend la lettre).
  const pendingRef = useRef(null)
  const timerRef = useRef(null)

  const clearPending = useCallback(() => {
    pendingRef.current = null
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      // Jamais en saisie, jamais avec modificateur (réservé au système / ⌘K).
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return

      // « ? » → aide. (Shift+/ sur la plupart des claviers ; on teste la touche.)
      if (e.key === '?') {
        e.preventDefault()
        clearPending()
        setHelpOpen(true)
        return
      }

      // Séquence « g » puis lettre de navigation.
      if (pendingRef.current === 'g') {
        const combo = `g ${e.key.toLowerCase()}`
        const match = GOTO_SHORTCUTS.find((s) => s.keys === combo)
        clearPending()
        if (match) {
          e.preventDefault()
          navigate(match.to)
        }
        return
      }
      if (e.key === 'g' || e.key === 'G') {
        pendingRef.current = 'g'
        timerRef.current = setTimeout(clearPending, SEQUENCE_MS)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      clearPending()
    }
  }, [navigate, clearPending])

  return (
    <>
      {children}
      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent aria-label="Aide des raccourcis clavier">
          <DialogHeader>
            <DialogTitle>Raccourcis clavier</DialogTitle>
            <DialogDescription>
              Gagnez du temps avec ces raccourcis. Ils sont inactifs pendant la saisie.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <ShortcutGroup title="Général" items={GLOBAL_SHORTCUTS} />
            <ShortcutGroup title="Navigation rapide" items={GOTO_SHORTCUTS} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function ShortcutGroup({ title, items }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <ul className="flex flex-col gap-1">
        {items.map((s) => (
          <li key={s.keys} className="flex items-center justify-between gap-4 text-sm">
            <span>{s.label}</span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
              {s.keys}
            </kbd>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default ShortcutsProvider
