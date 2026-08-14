// NTRET22 — Écran caisse : mode « scan douchette en flux continu » + raccourcis
// clavier. Basculable depuis CaisseScreen (bouton « Mode scan ») : focus
// permanent sur un champ dédié, ajout auto au panier à CHAQUE scan (Entrée —
// la douchette termine sa trame par Entrée), sans clic, avec un anti-doublon
// pour une rafale de scans rapides (douchette qui répète le même code sous le
// délai de rebond mécanique).
import { useEffect, useRef, useState } from 'react'

// Délai (ms) sous lequel DEUX scans successifs du MÊME code sont fusionnés en
// un seul ajout — absorbe le rebond mécanique d'une douchette ou une double
// lecture accidentelle, sans jamais bloquer un VRAI second scan du même
// article (au-delà du délai, il compte normalement).
export const SCAN_DEBOUNCE_MS = 400

// Traite un code scanné : PURE, sans I/O — le composant n'appelle que ceci.
// `dernier` = { code, ts } | null (dernier scan accepté). Renvoie
// { accepte, dernier } : `accepte` faux pour un code vide OU un doublon du
// même code arrivé sous SCAN_DEBOUNCE_MS ; `dernier` à reporter à l'appel
// suivant dans tous les cas où un code non vide a été soumis.
export function traiterScan(code, dernier, maintenant = Date.now()) {
  const c = (code ?? '').trim()
  if (!c) return { accepte: false, dernier }
  if (dernier && dernier.code === c && (maintenant - dernier.ts) < SCAN_DEBOUNCE_MS) {
    return { accepte: false, dernier }
  }
  return { accepte: true, dernier: { code: c, ts: maintenant } }
}

// Raccourcis clavier caisse : F2 nouveau ticket, F4 encaisser, Échap annuler
// la ligne en cours. `handlers` = { onNouveauTicket, onEncaisser,
// onAnnulerLigne } — chaque callback est optionnel (raccourci sans handler =
// no-op silencieux, jamais une erreur). Renvoie la fonction de nettoyage
// (retirer l'écouteur) — à appeler au démontage/à chaque changement de deps.
export function attacherRaccourcisClavier(handlers, target = typeof window !== 'undefined' ? window : null) {
  if (!target) return () => {}
  const onKeyDown = (e) => {
    if (e.key === 'F2') { e.preventDefault?.(); handlers.onNouveauTicket?.() }
    else if (e.key === 'F4') { e.preventDefault?.(); handlers.onEncaisser?.() }
    else if (e.key === 'Escape') { handlers.onAnnulerLigne?.() }
  }
  target.addEventListener('keydown', onKeyDown)
  return () => target.removeEventListener('keydown', onKeyDown)
}

// Bip de confirmation (best-effort — Web Audio absente en test/jsdom ou
// navigateur restreint = no-op silencieux, jamais une exception qui casse le
// scan suivant).
export function biperConfirmation() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 880
    gain.gain.value = 0.05
    osc.start()
    osc.stop(ctx.currentTime + 0.08)
  } catch {
    // best-effort — jamais bloquant.
  }
}

/* Composant : barre de scan continu, basculable. `onScan(code)` est appelé
   pour chaque scan ACCEPTÉ (dédupliqué) — c'est à l'appelant (CaisseScreen)
   de résoudre le produit et de l'ajouter au panier. `actif` = false ne rend
   rien (jamais monté quand le mode est désactivé, même patron que PinLock/
   NTRET3 : pas de coût quand la fonctionnalité n'est pas utilisée). */
export default function ScanMode({ onScan, actif = true }) {
  const [valeur, setValeur] = useState('')
  const [aideOuverte, setAideOuverte] = useState(false)
  const dernierRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (actif) inputRef.current?.focus()
  }, [actif])

  if (!actif) return null

  const handleKeyDown = (e) => {
    if (e.key !== 'Enter') return
    e.preventDefault()
    const { accepte, dernier } = traiterScan(valeur, dernierRef.current)
    dernierRef.current = dernier
    if (accepte) {
      onScan?.(dernier.code)
      biperConfirmation()
    }
    setValeur('')
  }

  return (
    <div
      className="flex flex-col gap-1.5 rounded-md border border-dashed border-border bg-muted/30 p-2"
      data-testid="scan-mode"
    >
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          autoFocus
          value={valeur}
          onChange={(e) => setValeur(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            // Focus permanent (douchette = clavier virtuel) — sauf si le mode
            // vient d'être désactivé pendant l'événement de blur.
            if (actif) setTimeout(() => inputRef.current?.focus(), 0)
          }}
          placeholder="Scanner un code-barres…"
          aria-label="Scan douchette continu"
          className="h-9 flex-1 rounded-md border border-input bg-card px-2 text-sm"
        />
        <button
          type="button"
          className="text-xs text-muted-foreground underline"
          onClick={() => setAideOuverte((v) => !v)}
        >
          Raccourcis
        </button>
      </div>
      {aideOuverte && (
        <ul className="text-xs text-muted-foreground" data-testid="scan-mode-aide">
          <li>F2 — Nouveau ticket</li>
          <li>F4 — Encaisser</li>
          <li>Échap — Annuler la dernière ligne</li>
        </ul>
      )}
    </div>
  )
}
