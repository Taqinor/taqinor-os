import { useState } from 'react'
import { AlertTriangle, Send } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { EDIT_COPY_STATIC_WARNINGS } from './adsengine'

/* ============================================================================
   ADSDEEP35 — Composeur EDIT_COPY (édition du texte / créatif d'une ad EXISTANTE).
   ----------------------------------------------------------------------------
   Avant/après CÔTE À CÔTE : le texte ACTUEL (miroir AdCreativeMirror — saisi ici
   par l'approbateur ou pré-rempli via `currentCreative`, ADSDEEP11) vs le texte
   PROPOSÉ. Avertissements STATIQUES annoncés AVANT soumission (le backend les
   recalcule et les porte dans `payload.warnings` — ADSDEEP31/35, rendus par
   ApprovalsScreen sur la carte une fois proposée). Envoi = une PROPOSITION
   EngineAction (kind edit_copy) via la boîte d'approbation — jamais un write
   Meta direct depuis le front.
   ========================================================================== */

export default function EditCopyComposer({ adMetaId: initialAdMetaId = '', currentCreative, onProposed }) {
  const [adMetaId, setAdMetaId] = useState(initialAdMetaId)
  const [currentBody, setCurrentBody] = useState(currentCreative?.body || '')
  const [proposedTitle, setProposedTitle] = useState('')
  const [proposedBody, setProposedBody] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)

  const canSubmit = adMetaId.trim() && proposedBody.trim() && reason.trim() && !busy

  const submit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true); setErr(''); setDone(false)
    try {
      await adsengineApi.actions.create({
        kind: 'edit_copy',
        reason_fr: reason.trim(),
        payload: {
          ad_id: adMetaId.trim(),
          current_creative: { body: currentBody },
          creative_spec: { title: proposedTitle, body: proposedBody },
        },
      })
      setDone(true)
      onProposed?.()
    } catch {
      setErr('Proposition refusée (permission ou champ manquant).')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="ae-edit-copy-composer" data-testid="ae-composer"
      onSubmit={submit}
      style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '1rem', margin: '0.75rem 0' }}>
      <h3 style={{ marginTop: 0 }}>Éditer le texte d&apos;une ad existante</h3>

      {/* Avertissement STATIQUE — annoncé AVANT soumission (dossier §4/ADSDEEP31). */}
      <div data-testid="ae-composer-warnings"
        style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', marginBottom: '0.75rem' }}>
        {EDIT_COPY_STATIC_WARNINGS.map((w, i) => (
          <span key={i} data-testid="ae-composer-warning" style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            background: '#fff7ed', color: '#9a3412', border: '1px solid #fed7aa',
            borderRadius: 6, padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}>
            <AlertTriangle size={14} aria-hidden="true" /> {w}
          </span>
        ))}
      </div>

      <label style={{ display: 'block', marginBottom: '0.5rem' }}>
        <span>ID de l&apos;ad (Meta)</span>
        <input className="form-input" data-testid="ae-composer-ad-id"
          value={adMetaId} onChange={e => setAdMetaId(e.target.value)}
          placeholder="ex. 12345678901" required />
      </label>

      {/* Avant/après CÔTE À CÔTE */}
      <div data-testid="ae-composer-diff" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        <div>
          <h4 style={{ margin: '0 0 0.3rem' }}>Actuel</h4>
          <textarea className="form-input" data-testid="ae-composer-current-body"
            value={currentBody} onChange={e => setCurrentBody(e.target.value)}
            placeholder="Texte actuellement diffusé (miroir AdCreativeMirror)" rows={4} />
        </div>
        <div>
          <h4 style={{ margin: '0 0 0.3rem' }}>Proposé</h4>
          <input className="form-input" data-testid="ae-composer-proposed-title"
            value={proposedTitle} onChange={e => setProposedTitle(e.target.value)}
            placeholder="Nouveau titre (optionnel)" style={{ marginBottom: '0.4rem' }} />
          <textarea className="form-input" data-testid="ae-composer-proposed-body"
            value={proposedBody} onChange={e => setProposedBody(e.target.value)}
            placeholder="Nouveau texte proposé" rows={4} required />
        </div>
      </div>

      <label style={{ display: 'block', margin: '0.75rem 0' }}>
        <span>Raison (une phrase)</span>
        <input className="form-input" data-testid="ae-composer-reason"
          value={reason} onChange={e => setReason(e.target.value)}
          placeholder="ex. Accroche fatiguée — rafraîchir le texte." required />
      </label>

      {err && <p data-testid="ae-composer-err" style={{ color: '#dc2626' }}>{err}</p>}
      {done && <p data-testid="ae-composer-done" style={{ color: '#15803d' }}>Proposition envoyée.</p>}

      <button type="submit" className="btn btn-primary ae-composer-submit"
        data-testid="ae-composer-submit" disabled={!canSubmit}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Send size={14} aria-hidden="true" /> Proposer l&apos;édition
      </button>
    </form>
  )
}
