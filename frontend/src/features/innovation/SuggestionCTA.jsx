import { useState } from 'react'
import { Lightbulb } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../../ui'
import ProposerIdeeForm from './ProposerIdeeForm'

/* ============================================================================
   NTIDE9 — CTA « Suggérer une amélioration » (style Intercom), fixe en bas de
   chaque écran ERP principal. Modale légère avec le formulaire partagé
   (contexte autodétecté + idée liée, NTIDE10/NTIDE11). Dismiss-able (Échap /
   clic extérieur / croix — comportement Dialog standard).
   ========================================================================== */

export default function SuggestionCTA() {
  const [open, setOpen] = useState(false)

  return (
    <>
      {/* Masqué sous `md` : sur mobile l'écran est bord-à-bord (+ barre d'onglets
          basse), un bouton flottant bas-droite recouvrirait le contenu de la liste
          (garde e2e MB6). Accessible sur mobile via la nav Innovation. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Suggérer une amélioration"
        title="Suggérer une amélioration"
        className="hidden md:inline-flex fixed bottom-5 right-5 z-[var(--z-modal)] items-center gap-2
                   rounded-full border border-border bg-card px-4 py-2.5 text-sm font-medium
                   text-foreground shadow-ui-md transition-colors hover:bg-accent focus-ring"
      >
        <Lightbulb className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">Suggérer une amélioration</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Suggérer une amélioration</DialogTitle>
          </DialogHeader>
          <ProposerIdeeForm
            compact
            onCreated={() => setOpen(false)}
            onCancel={() => setOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
