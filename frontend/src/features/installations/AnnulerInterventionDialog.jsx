import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'
import { errorMessageFrom } from '../../lib/toast'
import { toast } from '../../ui/confirm'
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Input, Label,
} from '../../ui'

// ACSV4 — « Annuler l'intervention » : motif obligatoire, refus serveur
// (terminée, validée, déjà annulée) affiché tel quel. Même patron que
// « Annuler ce chantier » de la fiche chantier.
export default function AnnulerInterventionDialog({ intervention, onClose, onDone }) {
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { setMotif('') }, [intervention?.id])

  const confirmer = async (e) => {
    e.preventDefault()
    if (!motif.trim()) return
    setBusy(true)
    try {
      await installationsApi.annulerIntervention(intervention.id, motif.trim())
      toast.success('Intervention annulée.')
      await onDone?.()
    } catch (err) {
      toast.error(errorMessageFrom(err, "Annulation de l'intervention impossible."))
    } finally { setBusy(false) }
  }

  return (
    <AlertDialog open={!!intervention} onOpenChange={(o) => { if (!o) onClose?.() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Annuler l&apos;intervention ?</AlertDialogTitle>
          <AlertDialogDescription>
            {intervention?.type_intervention_display ?? intervention?.type_intervention} — elle
            quittera le planning. Le motif est obligatoire.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="grid gap-1.5">
          <Label htmlFor="annuler-intervention-motif">Motif d&apos;annulation</Label>
          <Input id="annuler-intervention-motif" value={motif}
                 onChange={(e) => setMotif(e.target.value)}
                 placeholder="Ex. client absent" />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Retour</AlertDialogCancel>
          <AlertDialogAction disabled={!motif.trim() || busy} onClick={confirmer}>
            Annuler l&apos;intervention
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
