import { ChevronDown, ChevronRight } from 'lucide-react'

/* En-tête cliquable d'un bloc repliable des relances (script d'appel, texte de
   la touche) : chevron ouvert/fermé puis le libellé en enfants. */
export default function BasculeReplie({ ouvert, onBasculer, children }) {
  return (
    <button
      type="button"
      className="flex w-full items-center gap-1.5 text-left text-xs font-medium text-foreground"
      aria-expanded={ouvert}
      onClick={onBasculer}
    >
      {ouvert ? <ChevronDown className="size-3.5 shrink-0" aria-hidden="true" />
        : <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" />}
      {children}
    </button>
  )
}
