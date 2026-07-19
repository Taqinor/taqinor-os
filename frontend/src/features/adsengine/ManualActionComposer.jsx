import { useState, useMemo } from 'react'
import { Send } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB22 — Composeur d'action manuel GÉNÉRIQUE (piloté par manualActions.js).
   ----------------------------------------------------------------------------
   Rend le formulaire ciblé d'UN kind (champs déclarés + raison obligatoire +
   APERÇU du payload) et l'envoie en PROPOSITION : jamais un write Meta direct,
   toujours via propose_action (mode `raw` → actions.create ; mode `curated` →
   actions.proposeCurated vers le producteur backend). L'id cible n'est jamais
   re-saisi : il est injecté par `descriptor.buildPayload` depuis `target.metaId`.
   Même doctrine qu'EditCopyComposer (ADSDEEP35), généralisée à tous les kinds.
   ========================================================================== */

export default function ManualActionComposer({ descriptor, target, onProposed }) {
  const [values, setValues] = useState({})
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)

  const setField = (name, value) => setValues(v => ({ ...v, [name]: value }))

  // Parse les champs JSON ; collecte une éventuelle erreur de parsing.
  const parsed = useMemo(() => {
    const out = {}
    let jsonError = ''
    for (const f of descriptor.fields) {
      const raw = values[f.name]
      if (f.type === 'json') {
        if (raw == null || String(raw).trim() === '') { out[f.name] = undefined; continue }
        try { out[f.name] = JSON.parse(raw) } catch { jsonError = `Champ « ${f.label} » : JSON invalide.` }
      } else {
        out[f.name] = raw
      }
    }
    return { out, jsonError }
  }, [values, descriptor])

  const missingRequired = descriptor.fields.some(
    f => f.required && (values[f.name] == null || String(values[f.name]).trim() === ''))

  const payloadPreview = useMemo(() => {
    try { return descriptor.buildPayload(parsed.out, target || {}) } catch { return {} }
  }, [parsed, descriptor, target])

  const canSubmit = reason.trim() && !missingRequired && !parsed.jsonError && !busy

  const submit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true); setErr(''); setDone(false)
    try {
      const params = descriptor.buildPayload(parsed.out, target || {})
      if (descriptor.mode === 'curated') {
        await adsengineApi.actions.proposeCurated(
          descriptor.kind, { ...params, reason_fr: reason.trim() })
      } else {
        await adsengineApi.actions.create(
          { kind: descriptor.kind, reason_fr: reason.trim(), payload: params })
      }
      setDone(true)
      onProposed?.()
    } catch {
      setErr('Proposition refusée (permission ou champ invalide).')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="ae-maction-composer" data-testid="ae-maction-composer" onSubmit={submit}
      style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.85rem', margin: '0.6rem 0' }}>
      <h4 style={{ margin: '0 0 0.5rem' }} data-testid="ae-maction-title">{descriptor.label}</h4>

      {descriptor.fields.map(f => (
        <label key={f.name} style={{ display: 'block', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', color: '#475569' }}>{f.label}</span>
          {f.type === 'json'
            ? (
              <textarea className="form-input" data-testid={`ae-maction-field-${f.name}`}
                value={values[f.name] || ''} onChange={e => setField(f.name, e.target.value)}
                placeholder={f.placeholder} rows={3} required={f.required} />
            ) : (
              <input className="form-input" data-testid={`ae-maction-field-${f.name}`}
                type={f.type === 'number' ? 'number' : 'text'}
                step={f.type === 'number' ? 'any' : undefined}
                value={values[f.name] || ''} onChange={e => setField(f.name, e.target.value)}
                placeholder={f.placeholder} required={f.required} />
            )}
        </label>
      ))}

      <label style={{ display: 'block', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.85rem', color: '#475569' }}>Raison (une phrase)</span>
        <input className="form-input" data-testid="ae-maction-reason"
          value={reason} onChange={e => setReason(e.target.value)}
          placeholder={descriptor.reasonPlaceholder} required />
      </label>

      {/* Aperçu du payload proposé (traçabilité — jamais un chiffre boîte-noire). */}
      <div style={{ margin: '0.25rem 0 0.5rem' }}>
        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Aperçu du payload</span>
        <pre data-testid="ae-maction-preview"
          style={{ margin: '0.2rem 0 0', padding: '0.5rem', background: '#f8fafc',
            border: '1px solid #e2e8f0', borderRadius: 6, fontSize: '0.78rem', overflowX: 'auto' }}>
          {JSON.stringify(payloadPreview, null, 2)}
        </pre>
      </div>

      {parsed.jsonError && <p data-testid="ae-maction-json-err" style={{ color: '#dc2626' }}>{parsed.jsonError}</p>}
      {err && <p data-testid="ae-maction-err" style={{ color: '#dc2626' }}>{err}</p>}
      {done && <p data-testid="ae-maction-done" style={{ color: '#15803d' }}>Proposition envoyée.</p>}

      <button type="submit" className="btn btn-primary" data-testid="ae-maction-submit"
        disabled={!canSubmit}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Send size={14} aria-hidden="true" /> Proposer
      </button>
    </form>
  )
}
