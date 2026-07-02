import { useState } from 'react'
import { Button, toast } from '../../../ui'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { TextField, TextAreaField } from './fields'

/* UX38 — Création / édition d'un projet. Le `statut` n'est JAMAIS envoyé ici
   (piloté uniquement par la machine à états serveur) ; il est absent du corps. */

export default function ProjetFormDialog({ projet, onClose, onSaved }) {
  const isEdit = !!projet?.id
  const [form, setForm] = useState({
    code: projet?.code ?? '',
    nom: projet?.nom ?? '',
    description: projet?.description ?? '',
    client_id: projet?.client_id ?? '',
    date_debut: projet?.date_debut ?? '',
    date_fin_prevue: projet?.date_fin_prevue ?? '',
    budget_total: projet?.budget_total ?? '',
  })
  const [saving, setSaving] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.nom.trim()) {
      toast.error('Le nom du projet est obligatoire.')
      return
    }
    setSaving(true)
    const payload = {
      code: form.code || undefined,
      nom: form.nom,
      description: form.description || '',
      client_id: form.client_id ? Number(form.client_id) : null,
      date_debut: form.date_debut || null,
      date_fin_prevue: form.date_fin_prevue || null,
      budget_total: form.budget_total === '' ? null : form.budget_total,
    }
    try {
      const res = isEdit
        ? await gestionProjetApi.updateProjet(projet.id, payload)
        : await gestionProjetApi.createProjet(payload)
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
      onOpenChange={(o) => { if (!o) onClose?.() }}
      title={isEdit ? 'Modifier le projet' : 'Nouveau projet'}
      description="Le statut se pilote par les actions de transition (planifier, démarrer…)."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="code" label="Code" value={form.code} onChange={set('code')} placeholder="Auto si vide" />
          <TextField id="nom" label="Nom" required value={form.nom} onChange={set('nom')} />
        </div>
        <TextAreaField id="description" label="Description" rows={2} value={form.description} onChange={set('description')} />
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="client_id" label="Client (id CRM)" inputMode="numeric" value={form.client_id} onChange={set('client_id')} hint="Référence lâche vers un client CRM." />
          <TextField id="budget_total" label="Budget total (MAD)" inputMode="decimal" value={form.budget_total} onChange={set('budget_total')} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="date_debut" label="Date de début" type="date" value={form.date_debut} onChange={set('date_debut')} />
          <TextField id="date_fin_prevue" label="Fin prévue" type="date" value={form.date_fin_prevue} onChange={set('date_fin_prevue')} />
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
