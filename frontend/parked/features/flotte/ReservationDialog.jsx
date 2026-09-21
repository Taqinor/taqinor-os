import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   WIR41(a) — Formulaire de réservation d'un véhicule du pool (FLOTTE10).
   ----------------------------------------------------------------------------
   `ReservationsTab` était lecture seule malgré un backend full CRUD. La
   détection de conflit (chevauchement de plage sur le même véhicule) reste
   entièrement côté serveur — le message backend est réaffiché tel quel.
   ========================================================================== */

export default function ReservationDialog({ vehicules = [], conducteurs = [], onClose, onSaved }) {
  const [vehiculeId, setVehiculeId] = useState('')
  const [conducteurId, setConducteurId] = useState('')
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(vehiculeId && debut && fin)
  const dirty = Boolean(vehiculeId || conducteurId || debut || fin || motif)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.reservations.create({
        vehicule: Number(vehiculeId),
        conducteur: conducteurId ? Number(conducteurId) : null,
        debut,
        fin,
        motif,
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
          <DialogTitle>Nouvelle réservation</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="resa-vehicule">Véhicule</Label>
            <select
              id="resa-vehicule"
              autoFocus
              value={vehiculeId}
              onChange={(e) => setVehiculeId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {vehicules.map((v) => (
                <option key={v.id} value={v.id}>{v.immatriculation}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="resa-conducteur">Conducteur prévu (option.)</Label>
            <select
              id="resa-conducteur"
              value={conducteurId}
              onChange={(e) => setConducteurId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Non assigné —</option>
              {conducteurs.map((c) => (
                <option key={c.id} value={c.id}>{c.nom}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="resa-debut">Début</Label>
              <Input id="resa-debut" type="datetime-local" value={debut} onChange={(e) => setDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="resa-fin">Fin</Label>
              <Input id="resa-fin" type="datetime-local" value={fin} onChange={(e) => setFin(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="resa-motif">Motif</Label>
            <Input id="resa-motif" value={motif} onChange={(e) => setMotif(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Réserver'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
