import { useState } from 'react'
import { Button, toast, confirmLeaveIfDirty } from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { SelectField, TextField } from './fields'

/* UX38 — Relie une pièce métier (devis / facture / ticket / achat) au projet
   via une référence lâche typée (type_cible + cible_id). */

export default function LienFormDialog({ projetId, typesCible = [], onClose, onSaved }) {
  const [form, setForm] = useState({ type_cible: '', cible_id: '', libelle: '' })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(form.type_cible || form.cible_id || form.libelle)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!form.type_cible || !form.cible_id) {
      toast.error('Type et référence de la pièce sont obligatoires.')
      return
    }
    setSaving(true)
    try {
      const res = await gestionProjetApi.createLien({
        projet: projetId,
        type_cible: form.type_cible,
        cible_id: Number(form.cible_id),
        libelle: form.libelle || '',
      })
      onSaved?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Lien impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }} title="Lier une pièce">
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <SelectField id="type_cible" label="Type de pièce" required autoFocus options={typesCible} value={form.type_cible} onChange={set('type_cible')} />
        <TextField id="cible_id" label="Identifiant de la pièce" required inputMode="numeric" value={form.cible_id} onChange={set('cible_id')} />
        <TextField id="libelle" label="Libellé (optionnel)" value={form.libelle} onChange={set('libelle')} />
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Lier'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
