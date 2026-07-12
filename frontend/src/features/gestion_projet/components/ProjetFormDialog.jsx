import { useRef, useState } from 'react'
import { Button, toast, confirmLeaveIfDirty } from '../../../ui'
import { isDirty } from '../../../ui/form-utils'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import { TextField, TextAreaField } from './fields'

/* XPRJ27 — Volet marchés publics FACULTATIF (aucun champ obligatoire, tous
   vides/0/None par défaut, sans impact sur les projets privés) : n° de
   marché, maître d'ouvrage, délai d'exécution, taux/plafond de pénalité de
   retard et montant du marché (assiette du calcul de pénalités, distincte du
   `budget_total` interne de pilotage). */

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
    numero_marche: projet?.numero_marche ?? '',
    maitre_ouvrage: projet?.maitre_ouvrage ?? '',
    delai_execution_jours: projet?.delai_execution_jours ?? '',
    taux_penalite_retard: projet?.taux_penalite_retard ?? '',
    plafond_penalite_pct: projet?.plafond_penalite_pct ?? '',
    montant_marche: projet?.montant_marche ?? '',
  })
  const [showMarchePublic, setShowMarchePublic] = useState(
    !!(projet?.numero_marche || projet?.maitre_ouvrage || projet?.montant_marche))
  const [saving, setSaving] = useState(false)
  // VX168 — garde de fermeture (snapshot pris au montage ; couvre édition ET
  // création puisque `form` part déjà des valeurs de `projet` en édition).
  const initialSnapshotRef = useRef(form)
  const dirty = isDirty(initialSnapshotRef.current, form)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

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
      // XPRJ27 — volet marchés publics, facultatif (vide/0/None par défaut).
      numero_marche: form.numero_marche || '',
      maitre_ouvrage: form.maitre_ouvrage || '',
      delai_execution_jours: form.delai_execution_jours === '' ? null : form.delai_execution_jours,
      taux_penalite_retard: form.taux_penalite_retard === '' ? null : form.taux_penalite_retard,
      plafond_penalite_pct: form.plafond_penalite_pct === '' ? null : form.plafond_penalite_pct,
      montant_marche: form.montant_marche === '' ? null : form.montant_marche,
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
      onOpenChange={(o) => { if (!o) closeIfConfirmed() }}
      title={isEdit ? 'Modifier le projet' : 'Nouveau projet'}
      description="Le statut se pilote par les actions de transition (planifier, démarrer…)."
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField id="code" label="Code" autoFocus value={form.code} onChange={set('code')} placeholder="Auto si vide" />
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

        {/* XPRJ27 — volet marchés publics, facultatif (replié par défaut). */}
        <button
          type="button"
          className="self-start text-xs font-medium text-primary hover:underline"
          onClick={() => setShowMarchePublic((v) => !v)}
        >
          {showMarchePublic ? 'Masquer le volet marché public' : "Marché public ? (facultatif)"}
        </button>
        {showMarchePublic && (
          <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField id="numero_marche" label="N° de marché" value={form.numero_marche} onChange={set('numero_marche')} />
              <TextField id="maitre_ouvrage" label="Maître d'ouvrage" value={form.maitre_ouvrage} onChange={set('maitre_ouvrage')} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField id="delai_execution_jours" label="Délai d'exécution (jours)" inputMode="numeric" value={form.delai_execution_jours} onChange={set('delai_execution_jours')} />
              <TextField id="montant_marche" label="Montant du marché (MAD)" inputMode="decimal" value={form.montant_marche} onChange={set('montant_marche')} hint="Assiette du calcul de pénalités, distincte du budget interne." />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField id="taux_penalite_retard" label="Taux de pénalité de retard (‰/jour)" inputMode="decimal" value={form.taux_penalite_retard} onChange={set('taux_penalite_retard')} />
              <TextField id="plafond_penalite_pct" label="Plafond de pénalité (%)" inputMode="decimal" value={form.plafond_penalite_pct} onChange={set('plafond_penalite_pct')} />
            </div>
          </div>
        )}
        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
          <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </div>
      </form>
    </ResponsiveDialog>
  )
}
