import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import assurancesApi from './assurancesApi'
import { Button, Label, Input, Textarea, Checkbox } from '../../ui'
import { RecordShell } from '../../ui/module'
import { POLICE_TYPES, POLICE_STATUS } from './status'

/* ============================================================================
   WIR56 — Écran de création de police d'assurance (`/assurances/nouvelle`).
   ----------------------------------------------------------------------------
   Route déclarée AVANT le catch-all `:id` (voir module.config.jsx) pour que
   « nouvelle » ne soit jamais capturé comme un id de police. Crée une police
   via `assurancesApi.createPolice` (la société est posée côté serveur). Le
   sélecteur d'assureur/courtier lit les référentiels NTASS1. Aucun prix
   d'achat / marge n'est manipulé ici.
   ========================================================================== */

const STATUT_OPTIONS = Object.entries(POLICE_STATUS).map(([value, v]) => ({ value, label: v.label }))

export default function PoliceForm() {
  const navigate = useNavigate()
  const [assureurs, setAssureurs] = useState([])
  const [courtiers, setCourtiers] = useState([])
  const [form, setForm] = useState({
    assureur: '',
    courtier: '',
    numero_police: '',
    type_police: 'rc_pro',
    libelle: '',
    date_effet: '',
    date_echeance: '',
    prime_annuelle_ht: '',
    tacite_reconduction: false,
    statut: 'active',
    notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  useEffect(() => {
    assurancesApi.getAssureurs()
      .then((res) => setAssureurs(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setAssureurs([]))
    assurancesApi.getCourtiers()
      .then((res) => setCourtiers(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setCourtiers([]))
  }, [])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const peutEnregistrer = Boolean(form.assureur && form.numero_police.trim())

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      const res = await assurancesApi.createPolice({
        assureur: Number(form.assureur),
        courtier: form.courtier ? Number(form.courtier) : null,
        numero_police: form.numero_police.trim(),
        type_police: form.type_police,
        libelle: form.libelle,
        date_effet: form.date_effet || null,
        date_echeance: form.date_echeance || null,
        prime_annuelle_ht: form.prime_annuelle_ht === '' ? 0 : Number(form.prime_annuelle_ht),
        tacite_reconduction: form.tacite_reconduction,
        statut: form.statut,
        notes: form.notes,
      })
      navigate(`/assurances/${res.data.id}`)
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.numero_police
        || data?.assureur
        || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <RecordShell
      title="Nouvelle police"
      subtitle="Enregistrer une police d'assurance d'entreprise"
      backTo="/assurances"
      backLabel="Retour aux polices"
      tabs={[{
        value: 'form',
        label: 'Police',
        content: (
          <form onSubmit={submit} className="flex max-w-2xl flex-col gap-4" noValidate>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-assureur">Assureur</Label>
                <select
                  id="pol-assureur"
                  value={form.assureur}
                  onChange={(e) => set('assureur', e.target.value)}
                  className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                >
                  <option value="">— Sélectionner —</option>
                  {assureurs.map((a) => (
                    <option key={a.id} value={a.id}>{a.raison_sociale}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-courtier">Courtier (optionnel)</Label>
                <select
                  id="pol-courtier"
                  value={form.courtier}
                  onChange={(e) => set('courtier', e.target.value)}
                  className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                >
                  <option value="">— Aucun —</option>
                  {courtiers.map((c) => (
                    <option key={c.id} value={c.id}>{c.raison_sociale}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-numero">N° police</Label>
                <Input id="pol-numero" value={form.numero_police} onChange={(e) => set('numero_police', e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-type">Type</Label>
                <select
                  id="pol-type"
                  value={form.type_police}
                  onChange={(e) => set('type_police', e.target.value)}
                  className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                >
                  {POLICE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pol-libelle">Libellé</Label>
              <Input id="pol-libelle" value={form.libelle} onChange={(e) => set('libelle', e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-effet">Date d'effet</Label>
                <Input id="pol-effet" type="date" value={form.date_effet} onChange={(e) => set('date_effet', e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-echeance">Date d'échéance</Label>
                <Input id="pol-echeance" type="date" value={form.date_echeance} onChange={(e) => set('date_echeance', e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-prime">Prime annuelle HT (MAD)</Label>
                <Input id="pol-prime" type="number" step="any" value={form.prime_annuelle_ht} onChange={(e) => set('prime_annuelle_ht', e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="pol-statut">Statut</Label>
                <select
                  id="pol-statut"
                  value={form.statut}
                  onChange={(e) => set('statut', e.target.value)}
                  className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                >
                  {STATUT_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.tacite_reconduction}
                onCheckedChange={(v) => set('tacite_reconduction', Boolean(v))}
              />
              Tacite reconduction
            </label>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pol-notes">Notes</Label>
              <Textarea id="pol-notes" value={form.notes} onChange={(e) => set('notes', e.target.value)} />
            </div>

            {serverError && (
              <p className="text-sm text-destructive" role="alert">{serverError}</p>
            )}

            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={() => navigate('/assurances')}>Annuler</Button>
              <Button type="submit" disabled={!peutEnregistrer || saving}>
                {saving ? 'Enregistrement…' : 'Créer la police'}
              </Button>
            </div>
          </form>
        ),
      }]}
    />
  )
}
