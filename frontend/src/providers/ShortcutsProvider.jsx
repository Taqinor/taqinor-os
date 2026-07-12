// I37 — Raccourcis clavier globaux + dialogue d'aide « ? ».
//   • « ? »          → ouvre l'aide listant les raccourcis (FR).
//   • « g » puis x   → navigation directe (g d = dashboard, g l = leads, …).
//   • « c » puis x   → CRÉATION directe (VX220 : c l = lead, c d = devis,
//                       c c = client).
//   • VX248 — les raccourcis d'ACTION sur le record FOCALISÉ (a archiver, d
//     déléguer, 1..4 changer d'étape…) sont câblés par écran via
//     `focusedRecordShortcuts.js` (LeadForm.jsx, DevisList.jsx,
//     FactureList.jsx) ; ce provider expose seulement l'écran ACTIF à la
//     cheatsheet ci-dessous (`ActiveScreenProvider`), il ne les câble pas.
// La frappe est IGNORÉE quand le focus est dans un champ de saisie / textarea /
// contenteditable, et toute combinaison avec modificateur (⌘/Ctrl/Alt) est
// laissée au système (la palette gère ⌘K). Aucun vol de focus en saisie normale.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import {
  GOTO_SHORTCUTS, CREATE_SHORTCUTS, GLOBAL_SHORTCUTS, isTypingTarget,
} from './shortcuts'
import {
  FOCUSED_RECORD_SHORTCUTS, ActiveScreenProvider, useActiveScreen,
} from './focusedRecordShortcuts'

// VX220(b) — une séquence « <préfixe> puis lettre » par table : 'g' = aller à,
// 'c' = créer. Généralisé ici (au lieu de dupliquer le handler « g ») pour que
// l'ajout d'un futur préfixe reste une ligne, jamais un deuxième bloc copié.
const SEQUENCE_TABLES = { g: GOTO_SHORTCUTS, c: CREATE_SHORTCUTS }

// Fenêtre (ms) pour taper la 2e touche d'une séquence « g x ».
const SEQUENCE_MS = 1200

// VX248 — classification légère du rôle en un « profil » (commercial/sav/
// général), calquée sur Dashboard.jsx `cockpitProfile` (mêmes mots-clés FR)
// mais SANS en dépendre — évite une dépendance providers→pages pour 3 lignes.
// Sert UNIQUEMENT à trier l'affichage de la cheatsheet (« Pour votre rôle »
// d'abord) — jamais à activer/désactiver un raccourci.
// eslint-disable-next-line react-refresh/only-export-components -- helper pur co-localisé, testé isolément
export function roleProfile(roleNom) {
  const n = String(roleNom ?? '').toLowerCase()
  if (/sav|technicien|support|après-vente|apres-vente|maintenance|terrain/.test(n)) return 'sav'
  if (/commercial|vente|sales/.test(n)) return 'commercial'
  return 'general'
}

export function ShortcutsProvider({ children }) {
  const [helpOpen, setHelpOpen] = useState(false)
  const navigate = useNavigate()
  const roleNom = useSelector((s) => s.auth?.role_nom)
  const profile = roleProfile(roleNom)
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

      // Séquence « <préfixe> » puis lettre — navigation (g) ou création (c).
      if (pendingRef.current && SEQUENCE_TABLES[pendingRef.current]) {
        const combo = `${pendingRef.current} ${e.key.toLowerCase()}`
        const match = SEQUENCE_TABLES[pendingRef.current].find((s) => s.keys === combo)
        clearPending()
        if (match) {
          e.preventDefault()
          navigate(match.to)
        }
        return
      }
      const lower = e.key.toLowerCase()
      if (SEQUENCE_TABLES[lower]) {
        pendingRef.current = lower
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
    // VX248 — `ActiveScreenProvider` doit envelopper `children` (les écrans
    // routés, dont LeadForm/DevisList/FactureList) ET la cheatsheet, pour que
    // les deux consomment le MÊME contexte (`useFocusedRecordShortcuts` côté
    // écran, `ShortcutsCheatsheet` côté aide).
    <ActiveScreenProvider>
      {children}
      <ShortcutsCheatsheet open={helpOpen} onOpenChange={setHelpOpen} profile={profile} />
    </ActiveScreenProvider>
  )
}

// VX248 — extrait de ShortcutsProvider pour pouvoir appeler
// `useActiveScreen()` (le composant doit être un DESCENDANT du
// `ActiveScreenProvider` rendu ci-dessus, pas son propre parent).
function ShortcutsCheatsheet({ open, onOpenChange, profile }) {
  const { activeScreen } = useActiveScreen()
  const focusedEntry = activeScreen ? FOCUSED_RECORD_SHORTCUTS[activeScreen] : null
  // `ShortcutGroup` attend `{keys, label}` (comme GOTO_SHORTCUTS/CREATE_SHORTCUTS) ;
  // le registre focusedRecordShortcuts.js utilise `key` (singulier, une seule
  // touche — jamais une séquence).
  const focusedItems = focusedEntry
    ? focusedEntry.items.map((it) => ({ keys: it.key, label: it.label }))
    : []
  const roleMatches = focusedEntry ? (focusedEntry.roles ?? []).includes(profile) : false

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="Aide des raccourcis clavier">
        <DialogHeader>
          <DialogTitle>Raccourcis clavier</DialogTitle>
          <DialogDescription>
            Gagnez du temps avec ces raccourcis. Ils sont inactifs pendant la saisie.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {/* VX248 — « Pour votre rôle » EN TÊTE : filtre d'AFFICHAGE
              seulement (les touches marchent pour tout le monde, peu importe
              le rôle — seul l'ORDRE d'apprentissage passif change). */}
          {focusedEntry && roleMatches && (
            <ShortcutGroup
              title={`${focusedEntry.title} — pour votre rôle`}
              items={focusedItems}
            />
          )}
          <ShortcutGroup title="Général" items={GLOBAL_SHORTCUTS} />
          <ShortcutGroup title="Navigation rapide" items={GOTO_SHORTCUTS} />
          <ShortcutGroup title="Créer" items={CREATE_SHORTCUTS} />
          {focusedEntry && !roleMatches && (
            <ShortcutGroup
              title={`${focusedEntry.title} (autres rôles)`}
              items={focusedItems}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
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
