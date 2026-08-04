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

/* ORDRE FONDATEUR 2026-08-04 — « les deux parties en bas sont bien mais pas
   là tout le temps : garde-les dans profil ou paramètres ». Le bouton FLOTTANT
   est supprimé ; la modale devient PILOTABLE (props `open`/`onOpenChange`) et
   son unique point d'entrée est le menu profil du Header. */
export default function SuggestionCTA({ open, onOpenChange }) {

  return (
    <>

      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Suggérer une amélioration</DialogTitle>
          </DialogHeader>
          <ProposerIdeeForm
            compact
            onCreated={() => onOpenChange?.(false)}
            onCancel={() => onOpenChange?.(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  )
}
