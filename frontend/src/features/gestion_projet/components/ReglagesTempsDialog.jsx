import { useEffect, useRef, useState } from 'react'
import { Button, Label, toast, confirmLeaveIfDirty } from '../../../ui'
import { isDirty } from '../../../ui/form-utils'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { TextField } from './fields'

/* ZPRJ1 — Réglages société d'encodage des temps (singleton, get_or_create côté
   serveur) : pas d'arrondi, mode d'arrondi, unité de saisie, heures/jour
   (consommées par le chrono XPRJ5 et les sélecteurs de charge). */

export default function ReglagesTempsDialog({ onClose, onSaved }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(null)
  // VX168 — garde de fermeture : snapshot pris au premier chargement réussi.
  const initialSnapshotRef = useRef(null)

  useEffect(() => {
    let alive = true
    gestionProjetApi.getReglageTemps()
      .then((res) => {
        if (!alive) return
        initialSnapshotRef.current = res.data
        setForm(res.data)
      })
      .catch((err) => { if (alive) toast.error(errMessage(err, 'Chargement des réglages impossible.')) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const dirty = Boolean(form) && isDirty(initialSnapshotRef.current || {}, form)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await gestionProjetApi.updateReglageTemps({
        arrondi_minutes: form.arrondi_minutes,
        mode_arrondi: form.mode_arrondi,
        unite_saisie: form.unite_saisie,
        heures_par_jour: form.heures_par_jour,
      })
      onSaved?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) closeIfConfirmed() }}
      title="Réglages temps de la société"
    >
      {loading || !form ? (
        <p className="text-sm text-muted-foreground">Chargement…</p>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <TextField id="rt-arrondi" label="Pas d'arrondi (minutes)" type="number" min="1" autoFocus value={form.arrondi_minutes ?? ''} onChange={set('arrondi_minutes')} />
          <div className="flex flex-col gap-1">
            <Label htmlFor="rt-mode">Mode d'arrondi</Label>
            <select id="rt-mode" className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm" value={form.mode_arrondi ?? 'superieur'} onChange={set('mode_arrondi')}>
              <option value="inferieur">Arrondi au pas inférieur</option>
              <option value="superieur">Arrondi au pas supérieur</option>
              <option value="proche">Arrondi au pas le plus proche</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="rt-unite">Unité de saisie</Label>
            <select id="rt-unite" className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm" value={form.unite_saisie ?? 'heures'} onChange={set('unite_saisie')}>
              <option value="heures">Heures</option>
              <option value="jours">Jours</option>
            </select>
          </div>
          <TextField id="rt-heures-jour" label="Heures par jour" type="number" min="0" step="any" value={form.heures_par_jour ?? ''} onChange={set('heures_par_jour')} />
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </div>
        </form>
      )}
    </ResponsiveDialog>
  )
}
