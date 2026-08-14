import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import {
  OBJECTIFS, emptyWizardState, choisirObjectif, etapeValide, buildPayload,
  labelObjectif,
} from './campagneWizard'

/* ============================================================================
   NTMKT29 — Wizard guidé « Créer une campagne » (4 étapes).
   ----------------------------------------------------------------------------
   Étape 1 objectif (pré-remplit le canal) → étape 2 audience (liste/segment
   existant, NTMKT4/5) → étape 3 contenu (canal + objet/corps) → étape 4
   résumé + confirmation. Produit EXACTEMENT le même payload `Campagne` que
   `CampagneForm.jsx` (voir `campagneWizard.js` `buildPayload`) — remplace
   l'entrée directe pour les nouveaux utilisateurs ; le formulaire direct
   reste accessible en mode « expert » (`CampagnesList.jsx`, inchangé).
   Abandon à mi-parcours : AUCUN appel API tant que « Confirmer » (étape 4)
   n'a pas été cliqué — aucun brouillon orphelin.
   ========================================================================== */

export default function CampagneWizard({ onCreated, onCancel }) {
  const navigate = useNavigate()
  const [state, setState] = useState(emptyWizardState())
  const [listesDispo, setListesDispo] = useState([])
  const [segmentsDispo, setSegmentsDispo] = useState([])
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    marketingApi.listes.list().then(r => setListesDispo(marketingApi.unwrapList(r))).catch(() => {})
    marketingApi.segments.list().then(r => setSegmentsDispo(marketingApi.unwrapList(r))).catch(() => {})
  }, [])

  const suivant = () => setState(s => ({ ...s, etape: Math.min(4, s.etape + 1) }))
  const precedent = () => setState(s => ({ ...s, etape: Math.max(1, s.etape - 1) }))

  const confirmer = async () => {
    setSaving(true)
    setErr('')
    try {
      const payload = buildPayload(state)
      const res = await marketingApi.campagnes.create(payload)
      if (onCreated) onCreated(res.data)
      else navigate(`/marketing/campagnes/${res.data.id}`)
    } catch {
      setErr('Création de la campagne impossible.')
    } finally {
      setSaving(false)
    }
  }

  const abandonner = () => { setState(emptyWizardState()); if (onCancel) onCancel() }

  return (
    <div className="page" data-testid="campagne-wizard">
      <h3>Créer une campagne — étape {state.etape}/4</h3>
      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {state.etape === 1 && (
        <section data-testid="wizard-etape-objectif">
          <p>Quel est l&apos;objectif de la campagne ?</p>
          {OBJECTIFS.map(o => (
            <button key={o.key} type="button"
              className={o.key === state.objectif ? 'btn btn-primary' : 'btn btn-light'}
              data-testid={`wizard-objectif-${o.key}`}
              onClick={() => setState(s => choisirObjectif(s, o.key))}
              style={{ marginRight: '0.5rem', marginBottom: '0.5rem' }}>
              {o.label}
            </button>
          ))}
        </section>
      )}

      {state.etape === 2 && (
        <section data-testid="wizard-etape-audience">
          <p>Audience — choisissez une liste ou un segment existant.</p>
          <select className="form-input" data-testid="wizard-audience-liste"
            multiple value={state.listes}
            onChange={e => setState(s => ({
              ...s,
              listes: Array.from(e.target.selectedOptions, opt => Number(opt.value)),
            }))}>
            {listesDispo.map(l => <option key={l.id} value={l.id}>{l.nom}</option>)}
          </select>
          <select className="form-input" data-testid="wizard-audience-segment"
            value={state.segmentId}
            onChange={e => setState(s => ({ ...s, segmentId: e.target.value }))}>
            <option value="">— aucun segment —</option>
            {segmentsDispo.map(s => <option key={s.id} value={s.id}>{s.nom}</option>)}
          </select>
          <p data-testid="wizard-audience-compte">
            {state.listes.length} liste(s) sélectionnée(s)
            {state.segmentId ? ' + 1 segment' : ''}
          </p>
        </section>
      )}

      {state.etape === 3 && (
        <section data-testid="wizard-etape-contenu">
          <p>Contenu — canal {state.canal}.</p>
          {state.canal === 'email' && (
            <input className="form-input" data-testid="wizard-objet"
              placeholder="Objet" value={state.objet}
              onChange={e => setState(s => ({ ...s, objet: e.target.value }))} />
          )}
          <textarea className="form-input" data-testid="wizard-corps"
            placeholder="Message" value={state.corps}
            onChange={e => setState(s => ({ ...s, corps: e.target.value }))} />
        </section>
      )}

      {state.etape === 4 && (
        <section data-testid="wizard-etape-resume">
          <p>Résumé avant confirmation</p>
          <ul>
            <li>Objectif : {labelObjectif(state.objectif)}</li>
            <li>Canal : {state.canal}</li>
            <li>Audience : {state.listes.length} liste(s){state.segmentId ? ' + segment' : ''}</li>
          </ul>
        </section>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <button className="btn btn-light" data-testid="wizard-annuler" onClick={abandonner}>
          Annuler
        </button>
        {state.etape > 1 && (
          <button className="btn btn-light" data-testid="wizard-precedent" onClick={precedent}>
            ← Précédent
          </button>
        )}
        {state.etape < 4 && (
          <button className="btn btn-primary" data-testid="wizard-suivant"
            disabled={!etapeValide(state)} onClick={suivant}>
            Suivant →
          </button>
        )}
        {state.etape === 4 && (
          <button className="btn btn-primary" data-testid="wizard-confirmer"
            disabled={saving} onClick={confirmer}>
            {saving ? 'Création…' : 'Confirmer'}
          </button>
        )}
      </div>
    </div>
  )
}
