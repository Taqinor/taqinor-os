// NTCRM11 — Écran Plan de compte (/crm/comptes/:id/plan).
//
// Formulaire structuré SWOT + objectifs + potentiel, timeline des revues, et
// des liens vers l'org chart (NTCRM9) et les devis/factures du client.
import { useCallback, useEffect, useState } from 'react'
import api from '../../../api/axios'
import { Spinner, Button, Textarea, Input, Card } from '../../../ui'
import { toast } from '../../../ui/confirm'

const SWOT_FIELDS = [
  { key: 'swot_forces', label: 'Forces' },
  { key: 'swot_faiblesses', label: 'Faiblesses' },
  { key: 'swot_opportunites', label: 'Opportunités' },
  { key: 'swot_menaces', label: 'Menaces' },
]

export default function PlanComptePage({ clientId, planId }) {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    objectifs_strategiques: '', potentiel_estime: '', concurrents_presents: '',
    swot_forces: '', swot_faiblesses: '', swot_opportunites: '', swot_menaces: '',
    prochaine_revue: '', statut: 'brouillon',
  })

  const load = useCallback(() => {
    setLoading(true)
    const req = planId
      ? api.get(`/crm/plans-compte/${planId}/`)
      : api.get('/crm/plans-compte/', { params: { client: clientId } })
    req
      .then((res) => {
        const data = planId ? res.data : (res.data?.results ?? res.data ?? [])[0]
        if (data) {
          setPlan(data)
          setForm({
            objectifs_strategiques: data.objectifs_strategiques || '',
            potentiel_estime: data.potentiel_estime || '',
            concurrents_presents: data.concurrents_presents || '',
            swot_forces: (data.swot_forces || []).join('\n'),
            swot_faiblesses: (data.swot_faiblesses || []).join('\n'),
            swot_opportunites: (data.swot_opportunites || []).join('\n'),
            swot_menaces: (data.swot_menaces || []).join('\n'),
            prochaine_revue: data.prochaine_revue || '',
            statut: data.statut || 'brouillon',
          })
        }
      })
      .catch(() => toast.error('Impossible de charger le plan de compte.'))
      .finally(() => setLoading(false))
  }, [planId, clientId])

  useEffect(() => { load() }, [load])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    const payload = {
      ...form,
      swot_forces: form.swot_forces.split('\n').filter(Boolean),
      swot_faiblesses: form.swot_faiblesses.split('\n').filter(Boolean),
      swot_opportunites: form.swot_opportunites.split('\n').filter(Boolean),
      swot_menaces: form.swot_menaces.split('\n').filter(Boolean),
    }
    try {
      if (plan) {
        await api.patch(`/crm/plans-compte/${plan.id}/`, payload)
      } else {
        await api.post('/crm/plans-compte/', { ...payload, client: clientId })
      }
      toast.success('Plan de compte enregistré.')
      load()
    } catch {
      toast.error("Échec de l'enregistrement du plan de compte.")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="space-y-6" data-testid="plan-compte-screen">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Plan de compte</h2>
        <div className="flex gap-3 text-sm">
          <a href={`/crm/clients/${clientId}?tab=organigramme`} className="underline">
            Organigramme
          </a>
          <a href={`/ventes/devis?client=${clientId}`} className="underline">Devis</a>
          <a href={`/compta/factures?client=${clientId}`} className="underline">Factures</a>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-4">
        <Card className="p-4 space-y-3">
          <Textarea
            placeholder="Objectifs stratégiques"
            value={form.objectifs_strategiques}
            onChange={(e) => setForm((f) => ({ ...f, objectifs_strategiques: e.target.value }))}
          />
          <Input
            type="number"
            placeholder="Potentiel estimé (MAD)"
            value={form.potentiel_estime}
            onChange={(e) => setForm((f) => ({ ...f, potentiel_estime: e.target.value }))}
          />
          <Textarea
            placeholder="Concurrents présents"
            value={form.concurrents_presents}
            onChange={(e) => setForm((f) => ({ ...f, concurrents_presents: e.target.value }))}
          />
          <Input
            type="date"
            value={form.prochaine_revue}
            onChange={(e) => setForm((f) => ({ ...f, prochaine_revue: e.target.value }))}
          />
          <select
            className="form-select"
            value={form.statut}
            onChange={(e) => setForm((f) => ({ ...f, statut: e.target.value }))}
          >
            <option value="brouillon">Brouillon</option>
            <option value="actif">Actif</option>
            <option value="archive">Archivé</option>
          </select>
        </Card>

        <Card className="p-4 grid grid-cols-2 gap-3">
          {SWOT_FIELDS.map((f) => (
            <div key={f.key}>
              <label className="text-xs font-medium">{f.label}</label>
              <Textarea
                value={form[f.key]}
                onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
                placeholder={`${f.label} (une par ligne)`}
              />
            </div>
          ))}
        </Card>

        <Button type="submit" disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer le plan de compte'}
        </Button>
      </form>

      {plan?.revues?.length > 0 && (
        <Card className="p-4">
          <h3 className="font-medium mb-2">Timeline des revues</h3>
          <ul className="space-y-2 text-sm">
            {plan.revues.map((r) => (
              <li key={r.id} className="border-b pb-2">
                <div className="font-medium">{r.date_revue}</div>
                <div className="text-muted-foreground">{r.decisions}</div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
