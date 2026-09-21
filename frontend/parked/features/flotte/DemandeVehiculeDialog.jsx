import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   WIR41(b) — Formulaire de demande d'un véhicule du pool (FLOTTE32).
   ----------------------------------------------------------------------------
   `DemandeVehiculeViewSet` n'avait AUCUN consommateur frontend. Tout rôle peut
   soumettre une demande — `company` ET `demandeur` sont posés côté serveur
   (jamais du body) ; la décision (approuver/refuser) reste un flux séparé
   réservé au responsable/admin.
   ========================================================================== */

export default function DemandeVehiculeDialog({ onClose, onSaved }) {
  const [besoin, setBesoin] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(besoin.trim() && dateDebut && dateFin)
  const dirty = Boolean(besoin || dateDebut || dateFin || notes)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.demandesVehicule.create({
        besoin: besoin.trim(),
        date_debut_souhaitee: dateDebut,
        date_fin_souhaitee: dateFin,
        notes,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.non_field_errors?.[0]
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Demander un véhicule</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dvh-besoin">Besoin / objet de la demande</Label>
            <Input id="dvh-besoin" autoFocus value={besoin} onChange={(e) => setBesoin(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dvh-debut">Début souhaité</Label>
              <Input id="dvh-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dvh-fin">Fin souhaitée</Label>
              <Input id="dvh-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dvh-notes">Notes (option.)</Label>
            <Textarea id="dvh-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Demander'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
