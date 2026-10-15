import { AlertTriangle } from 'lucide-react'

/** Le motif d'un bloc OMIS (`motif_absence` non vide) — SEUL rendu, aucun
    chiffre à côté : jamais un panneau muet, jamais un chiffre inventé. */
export function MotifAbsence({ motif, testId }) {
  return (
    <p
      className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground"
      data-testid={testId}
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{motif}</span>
    </p>
  )
}
