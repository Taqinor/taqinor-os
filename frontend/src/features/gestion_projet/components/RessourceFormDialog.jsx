import { useState } from 'react'
import { Button, Switch, Label, toast, confirmLeaveIfDirty } from '../../../ui'
import { isDirty } from '../../../ui/form-utils'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { TextField, TextAreaField } from './fields'

/* UX40 — Création / édition d'un profil de ressource interne. `cout_horaire`
   est un indicateur INTERNE (jamais un prix d'achat, jamais rendu client). */

export default function RessourceFormDialog({ ressource, onClose, onSaved }) {
  const isEdit = !!ressource?.id
  const [form, setForm] = useState({
    nom: ressource?.nom ?? '',
    role: ressource?.role ?? '',
    competences: ressource?.competences ?? '',
    cout_horaire: ressource?.cout_horaire ?? '',
    actif: ressource?.actif ?? true,
  })
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  // VX168 — garde de fermeture (snapshot pris au montage ; couvre édition ET
  // création puisque `form` part déjà des valeurs de `ressource` en édition).
  const [initialSnapshot] = useState(() => form)
  const dirty = isDirty(initialSnapshot, form)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!form.nom.trim()) { toast.error('Le nom est obligatoire.'); return }
    setSaving(true)
    const payload = {
      nom: form.nom,
      role: form.role || '',
      competences: form.competences || '',
      cout_horaire: form.cout_horaire === '' ? null : form.cout_horaire,
      actif: form.actif,
    }
    try {
      const res = isEdit
        ? await gestionProjetApi.updateRessource(ressource.id, payload)
        : await gestionProjetApi.createRessource(payload)
      onSaved?.(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }} title={isEdit ? 'Modifier la ressource' : 'Nouvelle ressource'}>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="nom" label="Nom" required autoFocus value={form.nom} onChange={set('nom')} />
          <TextField id="role" label="Rôle" value={form.role} onChange={set('role')} />
        </div>
        <TextAreaField id="competences" label="Compétences" rows={2} value={form.competences} onChange={set('competences')} />
        <TextField id="cout_horaire" label="Coût horaire interne (MAD)" inputMode="decimal" value={form.cout_horaire} onChange={set('cout_horaire')} hint="Interne — jamais affiché au client." />
        <div className="flex items-center gap-2">
          <Switch id="actif" checked={form.actif} onCheckedChange={(v) => setForm((f) => ({ ...f, actif: v }))} />
          <Label htmlFor="actif">Ressource active</Label>
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
