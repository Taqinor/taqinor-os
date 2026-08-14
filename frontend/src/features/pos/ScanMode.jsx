// NTRET22 — Écran caisse : mode « scan douchette en flux continu » + raccourcis
// clavier. Basculable depuis CaisseScreen (bouton « Mode scan ») : focus
// permanent sur un champ dédié, ajout auto au panier à CHAQUE scan (Entrée —
// la douchette termine sa trame par Entrée), sans clic, avec un anti-doublon
// pour une rafale de scans rapides (douchette qui répète le même code sous le
// délai de rebond mécanique).
import { useEffect, useRef, useState } from 'react'
// NTRET22 — traiterScan/attacherRaccourcisClavier/biperConfirmation/
// SCAN_DEBOUNCE_MS vivent dans scanApi.js (react-refresh/only-export-
// components : ce fichier n'exporte QUE le composant).
import { traiterScan, biperConfirmation } from './scanApi'

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
