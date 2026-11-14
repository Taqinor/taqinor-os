// ACEL46 — « Interventions récurrentes » de la fiche chantier : créer une
// prestation périodique sans contrat (nettoyage, contrôle…), la voir avec sa
// prochaine échéance, l'arrêter. La tâche de 05:35 génère les interventions.
// Contrat : apps/installations/contract_samples/recurrences_intervention.json.
import { useCallback, useEffect, useState } from 'react'
import api from '../../api/axios'
import { lireToutesLesPages } from '../../utils/fetchAllPages'
import { frenchError } from '../../lib/frenchError'
import { formatDate } from '../../lib/format'
import { INTERVENTION_TYPES } from '../../features/installations/statuses'
import { Button, Input, FormField } from '../../ui'

const URL = '/installations/recurrences-intervention/'
const REGLES = [
  { value: 'mensuelle', label: 'Mensuelle' },
  { value: 'trimestrielle', label: 'Trimestrielle' },
  { value: 'semestrielle', label: 'Semestrielle' },
  { value: 'annuelle', label: 'Annuelle' },
]
const TYPES = [{ value: 'nettoyage', label: 'Nettoyage' }, ...INTERVENTION_TYPES]
const VIDE = { type_intervention: 'nettoyage', regle: 'mensuelle', intervalle: 1, prochaine_echeance: '' }
const libelle = (liste, v) => liste.find((o) => o.value === v)?.label ?? v

export default function RecurrencesInterventionSection({ installationId, peutGerer }) {
  const [recs, setRecs] = useState([])
  const [form, setForm] = useState(VIDE)
  const [erreur, setErreur] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    lireToutesLesPages((p) => api.get(URL, { params: { installation: installationId, ...p } }))
      .then(setRecs).catch((e) => setErreur(frenchError(e)))
  }, [installationId])
  useEffect(() => { load() }, [load])

  const creer = () => {
    setBusy(true)
    setErreur('')
    api.post(URL, { ...form, installation: installationId })
      .then(() => { setForm(VIDE); load() })
      .catch((e) => setErreur(frenchError(e)))
      .finally(() => setBusy(false))
  }
  const arreter = (rec) => api.post(`${URL}${rec.id}/desactiver/`)
    .then(load).catch((e) => setErreur(frenchError(e)))
  const champ = (cle) => (e) => setForm((f) => ({ ...f, [cle]: e.target.value }))

  return (
    <div className="flex flex-col gap-3">
      {recs.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune intervention récurrente sur ce chantier.</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {recs.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-2">
              <span>{libelle(TYPES, r.type_intervention)} — {libelle(REGLES, r.regle)}</span>
              <span className="text-muted-foreground">
                {r.actif ? `prochaine échéance ${formatDate(r.prochaine_echeance)}` : 'arrêtée'}
              </span>
              {peutGerer && r.actif && (
                <Button size="sm" variant="ghost" onClick={() => arreter(r)}>Arrêter</Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {peutGerer && (
        <div className="flex flex-wrap items-end gap-2">
          <FormField label="Type" htmlFor="rec-type">
            <select id="rec-type" className="h-9 rounded-md border px-2 text-sm"
                    value={form.type_intervention} onChange={champ('type_intervention')}>
              {TYPES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </FormField>
          <FormField label="Fréquence" htmlFor="rec-regle">
            <select id="rec-regle" className="h-9 rounded-md border px-2 text-sm"
                    value={form.regle} onChange={champ('regle')}>
              {REGLES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </FormField>
          <FormField label="Première échéance" htmlFor="rec-date">
            <Input id="rec-date" type="date" value={form.prochaine_echeance}
                   onChange={champ('prochaine_echeance')} />
          </FormField>
          <Button variant="outline" loading={busy} disabled={!form.prochaine_echeance} onClick={creer}>
            Ajouter
          </Button>
        </div>
      )}
      {erreur && <p className="text-sm text-destructive">{erreur}</p>}
    </div>
  )
}
