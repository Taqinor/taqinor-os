import { cn } from '../lib/cn'

/** Indicateur de chargement (SVG, courant). `size` via className (size-4 défaut). */
export function Spinner({ className, label = 'Chargement…', ...props }) {
  return (
    <svg
      role="status"
      aria-label={label}
      viewBox="0 0 24 24"
      fill="none"
      // VX135 — `motion-safe:` explicite (au lieu de compter seulement sur le
      // garde global `*` d'index.css) : sous reduced-motion, la classe
      // n'est même pas émise — repli STATIQUE lisible (le quart d'anneau
      // plein reste visible, immobile, sans figer à un angle arbitraire).
      className={cn('size-4 motion-safe:animate-spin text-current', className)}
      {...props}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export default Spinner
