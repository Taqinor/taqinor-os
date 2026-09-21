import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import {
  TYPES_ENQUETE, emptyWizardState, choisirType, majQuestion, peutPublier,
  buildPayload,
} from './enqueteWizard'

/* ============================================================================
   NTMKT32 — Wizard guidé « Créer une enquête NPS/personnalisée ».
   ----------------------------------------------------------------------------
   Choisir un type prédéfini (NPS pur, satisfaction post-installation,
   satisfaction SAV) ou personnalisé, questions pré-remplies ÉDITABLES,
   aperçu mobile avant publication, cible d'envoi (segment/liste/déclencheur
   post-événement métier — via `core/events.py`, ex. `installation_terminee`,
   consommé côté backend par un futur abonnement séquence ; ce wizard se
   contente d'enregistrer le choix de cible, jamais de le câbler lui-même).
   ========================================================================== */

const CIBLES = [
  { key: 'segment', label: 'Segment' },
  { key: 'liste', label: 'Liste de diffusion' },
  { key: 'evenement_installation_terminee', label: "Déclencheur : installation terminée" },
]

export default function EnqueteWizard({ onCreated, onCancel }) {
  const navigate = useNavigate()
  const [state, setState] = useState(emptyWizardState())
  const [segmentsDispo, setSegmentsDispo] = useState([])
  const [listesDispo, setListesDispo] = useState([])
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    marketingApi.segments.list().then(r => setSegmentsDispo(marketingApi.unwrapList(r))).catch(() => {})
    marketingApi.listes.list().then(r => setListesDispo(marketingApi.unwrapList(r))).catch(() => {})
  }, [])

  const publier = async () => {
    if (!peutPublier(state)) return
    setSaving(true)
    setErr('')
    try {
      const res = await marketingApi.enquetes.create(buildPayload(state))
      if (onCreated) onCreated(res.data)
      else navigate(`/marketing/enquetes/${res.data.id}`)
    } catch {
      setErr("Création de l'enquête impossible.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page" data-testid="enquete-wizard">
      <h3>Créer une enquête</h3>
      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      <section>
        <p>Type d&apos;enquête</p>
        {TYPES_ENQUETE.map(t => (
          <button key={t.key} type="button"
            className={t.key === state.type ? 'btn btn-primary' : 'btn btn-light'}
            data-testid={`wizard-type-${t.key}`}
            onClick={() => setState(s => choisirType(s, t.key))}
            style={{ marginRight: '0.5rem', marginBottom: '0.5rem' }}>
            {t.label}
          </button>
        ))}
      </section>

      {state.type && (
        <>
          <input className="form-input" data-testid="wizard-enquete-titre"
            placeholder="Titre de l'enquête" value={state.titre}
            onChange={e => setState(s => ({ ...s, titre: e.target.value }))} />

          <section style={{ marginTop: '1rem' }}>
            <h4>Questions ({state.questions.length})</h4>
            {state.questions.map((qq, i) => (
              <div key={qq.id} data-testid={`wizard-question-${i}`}
                style={{ marginBottom: '0.5rem' }}>
                <input className="form-input"
                  data-testid={`wizard-question-${i}-libelle`}
                  value={qq.libelle}
                  onChange={e => setState(s => majQuestion(s, i, { libelle: e.target.value }))} />
              </div>
            ))}
          </section>

          <section data-testid="wizard-apercu-mobile"
            style={{ marginTop: '1rem', maxWidth: 320, border: '1px solid #e2e8f0',
              borderRadius: 12, padding: '0.75rem' }}>
            <h4>Aperçu mobile</h4>
            <strong>{state.titre || '(titre)'}</strong>
            <ol>
              {state.questions.map(qq => <li key={qq.id}>{qq.libelle}</li>)}
            </ol>
          </section>

          <section style={{ marginTop: '1rem' }}>
            <h4>Cible d&apos;envoi</h4>
            <select className="form-input" data-testid="wizard-cible-mode"
              value={state.cible.mode}
              onChange={e => setState(s => ({ ...s, cible: { mode: e.target.value, ref: '' } }))}>
              <option value="">— choisir —</option>
              {CIBLES.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            {state.cible.mode === 'segment' && (
              <select className="form-input" data-testid="wizard-cible-ref"
                value={state.cible.ref}
                onChange={e => setState(s => ({ ...s, cible: { ...s.cible, ref: e.target.value } }))}>
                <option value="">— aucun —</option>
                {segmentsDispo.map(s => <option key={s.id} value={s.id}>{s.nom}</option>)}
              </select>
            )}
            {state.cible.mode === 'liste' && (
              <select className="form-input" data-testid="wizard-cible-ref"
                value={state.cible.ref}
                onChange={e => setState(s => ({ ...s, cible: { ...s.cible, ref: e.target.value } }))}>
                <option value="">— aucune —</option>
                {listesDispo.map(l => <option key={l.id} value={l.id}>{l.nom}</option>)}
              </select>
            )}
          </section>
        </>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <button className="btn btn-light" data-testid="wizard-annuler" onClick={onCancel}>
          Annuler
        </button>
        <button className="btn btn-primary" data-testid="wizard-publier"
          disabled={saving || !peutPublier(state)} onClick={publier}>
          {saving ? 'Publication…' : "Publier l'enquête"}
        </button>
      </div>
    </div>
  )
}
