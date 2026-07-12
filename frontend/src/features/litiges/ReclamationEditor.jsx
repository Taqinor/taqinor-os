import { useRef, useState } from 'react'
import { ArrowLeft, Save } from 'lucide-react'
import { Button, Input, Textarea, Label, Switch, toast } from '../../ui'
import { isDirty } from '../../ui/form-utils'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'
import litigesApi from '../../api/litigesApi'
import { GRAVITE_MAP, TYPE_MAP } from './litigesStatus'
import FilterSelect from './FilterSelect'

/* ============================================================================
   UX44 — Éditeur de réclamation (création + édition).
   ----------------------------------------------------------------------------
   ``statut`` n'est PAS éditable ici (lecture seule côté API) : il évolue via les
   transitions de l'écran de détail. Le formulaire est ``noValidate`` et les
   montants acceptent toute saisie (``step="any"``) — jamais de rejet de valeur.
   Aucune donnée sensible : montant CONTESTÉ (client-facing), pas de coût/marge.
   ========================================================================== */

const TYPE_OPTIONS = Object.entries(TYPE_MAP).map(([value, label]) => ({ value, label }))
const GRAVITE_OPTIONS = Object.entries(GRAVITE_MAP).map(([value, v]) => ({
  value, label: v.label,
}))

export default function ReclamationEditor({ reclamation, onCancel, onSaved }) {
  const isEdit = !!reclamation?.id
  const [form, setForm] = useState({
    reference: reclamation?.reference ?? '',
    objet: reclamation?.objet ?? '',
    description: reclamation?.description ?? '',
    type_reclamation: reclamation?.type_reclamation ?? 'autre',
    gravite: reclamation?.gravite ?? 'moyenne',
    montant_conteste: reclamation?.montant_conteste ?? '',
    bloque_relances: reclamation?.bloque_relances ?? true,
    concurrent_nom: reclamation?.concurrent_nom ?? '',
    concurrent_prix: reclamation?.concurrent_prix ?? '',
    motif_perte: reclamation?.motif_perte ?? '',
    ncr_id: reclamation?.ncr_id ?? '',
    audit_id: reclamation?.audit_id ?? '',
  })
  const [saving, setSaving] = useState(false)
  // VX169 — garde de navigation IN-APP (snapshot pris au montage).
  const initialSnapshotRef = useRef(form)
  const dirty = isDirty(initialSnapshotRef.current, form)
  useNavigationGuard(dirty)

  const set = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e?.target ? e.target.value : e }))

  const save = async () => {
    if (!form.objet.trim()) {
      toast.error("L'objet est requis.")
      return
    }
    setSaving(true)
    try {
      const payload = {
        ...form,
        montant_conteste: form.montant_conteste === '' ? 0 : form.montant_conteste,
        concurrent_prix: form.concurrent_prix === '' ? null : form.concurrent_prix,
        ncr_id: form.ncr_id === '' ? null : form.ncr_id,
        audit_id: form.audit_id === '' ? null : form.audit_id,
      }
      const saved = isEdit
        ? (await litigesApi.update(reclamation.id, payload)).data
        : (await litigesApi.create(payload)).data
      toast.success('Réclamation enregistrée.')
      onSaved?.(saved)
    } catch {
      toast.error('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page flex flex-col gap-4">
      <button
        type="button"
        onClick={onCancel}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Retour au registre
      </button>

      <h1 className="font-display text-xl font-semibold tracking-tight">
        {isEdit ? 'Éditer la réclamation' : 'Nouvelle réclamation'}
      </h1>

      <form
        noValidate
        onSubmit={(e) => { e.preventDefault(); save() }}
        className="flex max-w-3xl flex-col gap-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-ref">Référence</Label>
            <Input id="lit-ref" value={form.reference} onChange={set('reference')} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-objet">Objet</Label>
            <Input id="lit-objet" value={form.objet} onChange={set('objet')} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-type">Type</Label>
            <FilterSelect
              id="lit-type"
              value={form.type_reclamation}
              onChange={set('type_reclamation')}
              options={TYPE_OPTIONS}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-gravite">Gravité</Label>
            <FilterSelect
              id="lit-gravite"
              value={form.gravite}
              onChange={set('gravite')}
              options={GRAVITE_OPTIONS}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-montant">Montant contesté (MAD)</Label>
            <Input
              id="lit-montant"
              type="number"
              step="any"
              value={form.montant_conteste}
              onChange={set('montant_conteste')}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="lit-desc">Description</Label>
          <Textarea id="lit-desc" rows={6} value={form.description} onChange={set('description')} />
        </div>

        <label className="flex items-center gap-2 text-sm">
          <Switch
            checked={form.bloque_relances}
            onCheckedChange={(v) => setForm((f) => ({ ...f, bloque_relances: v }))}
          />
          Bloquer les relances automatiques sur la facture liée
        </label>

        <fieldset className="grid gap-4 rounded-lg border border-border p-4 sm:grid-cols-3">
          <legend className="px-1 text-sm font-medium text-muted-foreground">
            Deal perdu (optionnel)
          </legend>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-concurrent">Concurrent gagnant</Label>
            <Input id="lit-concurrent" value={form.concurrent_nom} onChange={set('concurrent_nom')} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-cprix">Prix du concurrent</Label>
            <Input
              id="lit-cprix"
              type="number"
              step="any"
              value={form.concurrent_prix}
              onChange={set('concurrent_prix')}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-motif">Motif de la perte</Label>
            <Input id="lit-motif" value={form.motif_perte} onChange={set('motif_perte')} />
          </div>
        </fieldset>

        <fieldset className="grid gap-4 rounded-lg border border-border p-4 sm:grid-cols-2">
          <legend className="px-1 text-sm font-medium text-muted-foreground">
            Rattachement QHSE (optionnel)
          </legend>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-ncr">ID de la NCR liée</Label>
            <Input
              id="lit-ncr"
              type="number"
              step="1"
              value={form.ncr_id}
              onChange={set('ncr_id')}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lit-audit">ID de l'audit fin de chantier lié</Label>
            <Input
              id="lit-audit"
              type="number"
              step="1"
              value={form.audit_id}
              onChange={set('audit_id')}
            />
          </div>
        </fieldset>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={saving}>
            <Save /> {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={saving}>
            Annuler
          </Button>
        </div>
      </form>
    </div>
  )
}
