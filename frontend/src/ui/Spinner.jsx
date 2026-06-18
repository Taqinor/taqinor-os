import { cn } from '../lib/cn'

/** Indicateur de chargement (SVG, courant). `size` via className (size-4 défaut). */
export function Spinner({ className, label = 'Chargement…', ...props }) {
  return (
    <svg
      role="status"
      aria-label={label}
      viewBox="0 0 24 24"
      fill="none"
      className={cn('size-4 animate-spin text-current', className)}
      {...props}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export default Spinner
