import { useEffect, useRef } from 'react'

/* ============================================================================
   XSTK5 — Scan « clavier-wedge » (douchette qui frappe les caractères du code
   puis Entrée, comme un clavier). Aucune lib externe : on écoute les
   `keydown` du document et on détecte une frappe RAPIDE (bien plus vite
   qu'un humain ne tape) terminée par Entrée. Complète `useBarcodeScanner`
   (caméra) — les deux appellent le même `onDetected(value)` côté panneau,
   qui ne sait pas d'où vient le code.

   N'exige AUCUN input focalisé dédié : la plupart des douchettes USB/BT se
   comportent comme un clavier standard et émettent leurs frappes vers
   l'élément actif ; si aucun champ texte n'a le focus, on capture quand même
   au niveau document (sans intercepter les frappes DANS un champ texte —
   voir `ignoreWhenTypingIn`).
   ========================================================================== */

// Au-delà de ce délai (ms) entre deux touches, on considère qu'il s'agit
// d'une frappe humaine normale et on réinitialise le buffer (une douchette
// tape un code en quelques dizaines de ms, un humain > 150ms/touche).
const MAX_INTERVAL_MS = 60
// Longueur minimale pour éviter de traiter un simple retour humain (Entrée
// seule, ou 1-2 caractères) comme un scan.
const MIN_LENGTH = 3

export function useKeyboardWedge({ onScan, enabled = true } = {}) {
  const bufferRef = useRef('')
  const lastTimeRef = useRef(0)
  const onScanRef = useRef(onScan)
  useEffect(() => { onScanRef.current = onScan }, [onScan])

  useEffect(() => {
    if (!enabled) return undefined

    const handleKeyDown = (event) => {
      // Ne capte jamais les frappes destinées à un champ de saisie humain
      // (quantité tapée à la main, recherche…) : la douchette, elle, cible
      // en général un champ dédié ou rien — mais si l'utilisateur tape
      // réellement dans un input, on laisse passer sans construire de buffer.
      const target = event.target
      const tag = target?.tagName
      const isEditable = tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable
      const now = performance.now()
      const elapsed = now - lastTimeRef.current
      lastTimeRef.current = now

      if (event.key === 'Enter') {
        const code = bufferRef.current
        bufferRef.current = ''
        if (!isEditable && code.length >= MIN_LENGTH) {
          onScanRef.current?.(code)
        }
        return
      }

      if (event.key.length !== 1) return // ignore Shift, Tab, flèches…

      if (elapsed > MAX_INTERVAL_MS) {
        // Trop lent pour une douchette : on redémarre le buffer sur cette
        // touche (permet de rattraper le début d'un scan après une frappe
        // humaine isolée précédente).
        bufferRef.current = event.key
      } else {
        bufferRef.current += event.key
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [enabled])
}

export default useKeyboardWedge
