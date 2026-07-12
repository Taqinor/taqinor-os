import { useMemo, useState } from 'react'
import { AlertTriangle, ShieldCheck } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Checkbox, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'
import { controlePermis } from './flotte'

/* ============================================================================
   UX17 — Formulaire d'affectation conducteur ↔ véhicule (FLOTTE8/FLOTTE9).
   ----------------------------------------------------------------------------
   Le contrôle de permis (`controlePermis`, miroir de `services.controle_permis`)
   s'exécute EN DIRECT dès qu'un couple conducteur/véhicule est choisi :
   - permis conforme → enregistrement autorisé ;
   - permis invalide → enregistrement BLOQUÉ avec un message FR clair, sauf si
     l'utilisateur coche « Forcer malgré l'alerte » (le backend enregistre alors
     l'affectation et conserve l'avertissement en lecture — `permis_avertissement`).
   ========================================================================== */

export default function AffectationDialog({ conducteurs = [], vehicules = [], onClose, onSaved }) {
  const [conducteurId, setConducteurId] = useState('')
  const [vehiculeId, setVehiculeId] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [notes, setNotes] = useState('')
  const [force, setForce] = useState(false)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const conducteur = useMemo(
    () => conducteurs.find((c) => String(c.id) === String(conducteurId)) || null,
    [conducteurs, conducteurId],
  )
  const vehicule = useMemo(
    () => vehicules.find((v) => String(v.id) === String(vehiculeId)) || null,
    [vehicules, vehiculeId],
  )

  // Contrôle de permis en direct : seulement quand les deux sont choisis.
  const controle = useMemo(() => {
    if (!conducteur || !vehicule) return { ok: true, code: '', message: '' }
    return controlePermis(conducteur, vehicule)
  }, [conducteur, vehicule])

  const permisBloque = !controle.ok && !force
  const peutEnregistrer = Boolean(conducteurId && vehiculeId && dateDebut) && !permisBloque
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(conducteurId || vehiculeId || dateDebut || dateFin || notes || force)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.affectations.create({
        conducteur: Number(conducteurId),
        vehicule: Number(vehiculeId),
        date_debut: dateDebut,
        date_fin: dateFin || null,
        notes: notes || '',
        // `force` (write-only) : n'est envoyé que si l'utilisateur a coché la case.
        ...(force ? { force: true } : {}),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      // Message serveur en clair (le backend renvoie {conducteur: <message>}).
      setServerError(
        data?.conducteur
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
          <DialogTitle>Nouvelle affectation</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aff-conducteur">Conducteur</Label>
            <select
              id="aff-conducteur"
              autoFocus
              value={conducteurId}
              onChange={(e) => setConducteurId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {conducteurs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nom}{c.categorie_permis ? ` (${c.categorie_permis})` : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aff-vehicule">Véhicule</Label>
            <select
              id="aff-vehicule"
              value={vehiculeId}
              onChange={(e) => setVehiculeId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {vehicules.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.immatriculation}{v.categorie_permis_requise ? ` — permis ${v.categorie_permis_requise}` : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="aff-debut">Date de début</Label>
              <Input id="aff-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="aff-fin">Date de fin (option.)</Label>
              <Input id="aff-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="aff-notes">Notes</Label>
            <Input id="aff-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optionnel" />
          </div>

          {/* Bandeau de contrôle de permis (FLOTTE9). */}
          {conducteur && vehicule && (
            controle.ok ? (
              <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
                <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
                Permis conforme pour ce véhicule.
              </div>
            ) : (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div>
                    <p className="font-medium">Affectation bloquée — permis non conforme</p>
                    <p className="mt-0.5">{controle.message}</p>
                  </div>
                </div>
                <label className="mt-2 flex items-center gap-2 text-xs text-foreground">
                  <Checkbox checked={force} onCheckedChange={(v) => setForce(Boolean(v))} />
                  Forcer malgré l’alerte (responsable) — l’avertissement sera conservé.
                </label>
              </div>
            )
          )}

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
