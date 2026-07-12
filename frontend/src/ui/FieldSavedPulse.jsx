import { useEffect, useState } from 'react'
import { cn } from '../lib/cn'

/* VX249(a) — micro-accusé au GRAIN DU CHAMP pour une sauvegarde SILENCIEUSE
   (édition inline DataTable, statut, note chatter…) : jusqu'ici, aucune
   confirmation locale — soit rien, soit un toast générique déconnecté de LA
   cellule modifiée. Pulse vert bref (300-400 ms, --motion-pulse dans
   design/tokens.css, cf. .field-saved-pulse) directement SUR le champ.

   Sous prefers-reduced-motion, --motion-pulse tombe à 0 ms (tokens.css) : le
   pulse dégrade en changement STATIQUE (la couleur est posée puis retirée
   sans transition perceptible), jamais un mouvement — même patron que
   --motion-slow/.stat-value-solidify.

   Usage : incrémenter `pulseKey` (n'importe quel entier changeant, ex. un
   compteur de sauvegardes réussies) déclenche UN pulse. `pulseKey` initial
   à 0/null/undefined ne pulse jamais (pas de faux-pulse au montage). */
export function FieldSavedPulse({ pulseKey, children, className, as: As = 'div' }) {
  const [pulsing, setPulsing] = useState(false)

  useEffect(() => {
    if (!pulseKey) return undefined
    setPulsing(true)
    // Marge au-delà de --motion-pulse (350 ms) pour ne jamais couper
    // l'animation en cours si le thread est légèrement chargé.
    const t = setTimeout(() => setPulsing(false), 500)
    return () => clearTimeout(t)
  }, [pulseKey])

  return (
    <As className={cn(pulsing && 'field-saved-pulse rounded', className)}>
      {children}
    </As>
  )
}

export default FieldSavedPulse
