import { useState } from 'react'
import { Button, toast, confirmLeaveIfDirty } from '../../../ui'
import { isDirty } from '../../../ui/form-utils'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { TextField, TextAreaField } from './fields'

/* UX38 — Clôture d'un projet + retour d'expérience (REX). `date_cloture` est
   obligatoire ; le projet passe à « Terminé » côté serveur (un projet annulé
   est refusé en 400 par le backend). */

export default function ClotureDialog({ projetId, onClose, onSaved }) {
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    date_cloture: today,
    date_reception: '',
    points_positifs: '',
    points_amelioration: '',
    recommandations: '',
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  // VX168 — garde de fermeture (snapshot pris au montage).
  const [initialSnapshot] = useState(() => form)
  const dirty = isDirty(initialSnapshot, form)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!form.date_cloture) {
      toast.error('La date de clôture est obligatoire.')
      return
    }
    setSaving(true)
    try {
      await gestionProjetApi.cloturerProjet(projetId, {
        date_cloture: form.date_cloture,
        date_reception: form.date_reception || null,
        points_positifs: form.points_positifs,
        points_amelioration: form.points_amelioration,
        recommandations: form.recommandations,
      })
      onSaved?.()
    } catch (err) {
      toast.error(errMessage(err, 'Clôture impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) closeIfConfirmed() }}
      title="Clôturer le projet"
      description="Passe le projet à « Terminé » et enregistre le retour d'expérience."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="date_cloture" label="Date de clôture" type="date" required autoFocus value={form.date_cloture} onChange={set('date_cloture')} />
          <TextField id="date_reception" label="Date de réception" type="date" value={form.date_reception} onChange={set('date_reception')} />
        </div>
        <TextAreaField id="points_positifs" label="Points positifs" rows={2} value={form.points_positifs} onChange={set('points_positifs')} />
        <TextAreaField id="points_amelioration" label="Points d'amélioration" rows={2} value={form.points_amelioration} onChange={set('points_amelioration')} />
        <TextAreaField id="recommandations" label="Recommandations" rows={2} value={form.recommandations} onChange={set('recommandations')} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Clôture…' : 'Clôturer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
