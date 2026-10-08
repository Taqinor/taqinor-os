import { createPortal } from 'react-dom'
import DealSignedCelebration from './DealSignedCelebration'
import { useAffaireSignee, effacerAffaireSignee } from './dealSignedBus'

/* Hôte GLOBAL de la fête « affaire signée » : monté une seule fois (ShellGlobal,
   dans le Provider redux, hors du routeur) et rendu dans document.body, au-dessus
   des modales (--z-toast), cliquable même si une modale Radix a posé
   pointer-events:none sur le body. */
export default function DealSignedCelebrationHost() {
  const victoire = useAffaireSignee()
  if (!victoire || typeof document === 'undefined') return null
  return createPortal(
    <div className="pointer-events-auto fixed inset-0 z-[var(--z-toast)]"
         data-testid="deal-signed-host">
      <DealSignedCelebration
        open
        reference={victoire.reference}
        montantTtc={victoire.montantTtc}
        kwc={victoire.kwc}
        onClose={effacerAffaireSignee}
      />
    </div>,
    document.body,
  )
}
