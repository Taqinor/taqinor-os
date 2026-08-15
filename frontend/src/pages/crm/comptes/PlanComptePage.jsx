// NTCRM11 — Écran Plan de compte (/crm/comptes/:id/plan).
//
// Formulaire structuré SWOT + objectifs + potentiel, timeline des revues, et
// des liens vers l'org chart (NTCRM9) et les devis/factures du client.
import { useCallback, useEffect, useState } from 'react'
import api from '../../../api/axios'
import { Spinner, Button, Textarea, Input, Card } from '../../../ui'
import { toast } from '../../../ui/confirm'
import ChatterTimeline from '../../../components/ChatterTimeline'

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

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  // WIR218 — section « Activité » : chatter générique du plan de compte
  // (`ChatterViewSetMixin`, endpoint réel `chatter/historique/`, jamais un
  // modèle *Activity local). Chargée dès que le plan existe, rafraîchie à
  // chaque `load()` réussi (même id ⇒ nouveau fetch inoffensif).
  const [historique, setHistorique] = useState([])
  useEffect(() => {
    if (!plan?.id) return
    api.get(`/crm/plans-compte/${plan.id}/chatter/historique/`)
      .then((res) => setHistorique(res.data?.results ?? res.data ?? []))
      .catch(() => {})
  }, [plan?.id, plan?.statut])

  // PACT105 — la timeline des revues s'affichait déjà EN LECTURE (`plan.
  // revues`, nested read-only sur PlanCompteSerializer) mais aucun formulaire
  // n'écrivait jamais sur `/crm/revues-compte/` : l'historique restait vide
  // tant que rien n'était créé. Une revue créée apparaît dans la MÊME liste
  // déjà affichée (rechargement du plan via `load()`), jamais un état local
  // dupliqué.
  const [revueForm, setRevueForm] = useState({
    date_revue: '', participants: '', decisions: '',
    prochaine_action: '', prochaine_action_date: '',
  })
  const [savingRevue, setSavingRevue] = useState(false)

  const creerRevue = async (e) => {
    e.preventDefault()
    if (!plan || !revueForm.date_revue) return
    setSavingRevue(true)
    try {
      await api.post('/crm/revues-compte/', {
        ...revueForm,
        // WIR218 — champ nullable : chaîne vide envoyée au serveur ⇒ 400
        // systématique (convention ClientPrixContractuelsTab).
        prochaine_action_date: revueForm.prochaine_action_date || undefined,
        plan: plan.id,
      })
      toast.success('Revue de compte enregistrée.')
      setRevueForm({
        date_revue: '', participants: '', decisions: '',
        prochaine_action: '', prochaine_action_date: '',
      })
      load()
    } catch {
      toast.error("Impossible d'enregistrer la revue de compte.")
    } finally {
      setSavingRevue(false)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    const payload = {
      ...form,
      // WIR218 — champs nullables : chaîne vide envoyée au serveur ⇒ 400
      // systématique (convention ClientPrixContractuelsTab).
      potentiel_estime: form.potentiel_estime || undefined,
      prochaine_revue: form.prochaine_revue || undefined,
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
          {/* APX1 — `/crm/clients/:id` était un 404 (aucune route de ce nom) ;
              le lien profond réel est `?id=` (VX220, lu par ClientList). Le
              paramètre `tab=organigramme` n'a jamais été lu par aucun écran :
              il est retiré plutôt que porté sur une URL qui l'ignore. */}
          <a href={`/crm?id=${clientId}`} className="underline">
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

      {plan && (
        <Card className="p-4 space-y-3">
          <h3 className="font-medium">Timeline des revues</h3>

          <form onSubmit={creerRevue} className="flex flex-wrap items-end gap-2">
            <Input
              type="date"
              aria-label="Date de la revue"
              value={revueForm.date_revue}
              onChange={(e) => setRevueForm((f) => ({ ...f, date_revue: e.target.value }))}
              required
            />
            <Input
              placeholder="Participants"
              aria-label="Participants de la revue"
              value={revueForm.participants}
              onChange={(e) => setRevueForm((f) => ({ ...f, participants: e.target.value }))}
            />
            <Input
              placeholder="Décisions"
              aria-label="Décisions de la revue"
              value={revueForm.decisions}
              onChange={(e) => setRevueForm((f) => ({ ...f, decisions: e.target.value }))}
            />
            <Input
              placeholder="Prochaine action"
              aria-label="Prochaine action"
              value={revueForm.prochaine_action}
              onChange={(e) => setRevueForm((f) => ({ ...f, prochaine_action: e.target.value }))}
            />
            <Input
              type="date"
              aria-label="Date de la prochaine action"
              value={revueForm.prochaine_action_date}
              onChange={(e) => setRevueForm((f) => ({ ...f, prochaine_action_date: e.target.value }))}
            />
            <Button type="submit" disabled={savingRevue}>
              {savingRevue ? 'Enregistrement…' : 'Ajouter une revue'}
            </Button>
          </form>

          {plan.revues?.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {plan.revues.map((r) => (
                <li key={r.id} className="border-b pb-2">
                  <div className="font-medium">{r.date_revue}</div>
                  <div className="text-muted-foreground">{r.decisions}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground">Aucune revue enregistrée.</p>
          )}
        </Card>
      )}

      {plan && (
        <Card className="p-4 space-y-3">
          <h3 className="font-medium">Activité</h3>
          <ChatterTimeline entries={historique} emptyLabel="Aucune activité pour le moment." />
        </Card>
      )}
    </div>
  )
}
