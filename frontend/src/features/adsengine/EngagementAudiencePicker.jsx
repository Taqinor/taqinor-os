import { useEffect, useState, useCallback } from 'react'
import { Users, Sparkles } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   ADSDEEP59 — Picker « Audiences d'engagement » (composeur d'adset).
   ----------------------------------------------------------------------------
   Objets purement Meta-side : formulaire ouvert/abandonné/soumis, Page engagée,
   IG engagé (rétentions dossier §3). AUCUNE donnée CRM n'est envoyée → ce picker
   n'est PAS soumis au consentement Custom Audience (contrairement aux audiences
   CRM 57/58).

   L'estimation d'audience (delivery_estimate, dossier §5) est montrée AVANT de
   créer/utiliser l'audience. Le catalogue + l'estimation viennent de l'API
   (mockée en test) — jamais inventés. Le composeur d'adset passe son
   `targetingSpec` de base ; la création remonte via `onCreated`.
   ========================================================================== */

export default function EngagementAudiencePicker({
  targetingSpec = null,
  onCreated = () => {},
}) {
  const [presets, setPresets] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState('')
  const [estimate, setEstimate] = useState(null)
  const [estimating, setEstimating] = useState(false)
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.audiences
      .engagementPresets()
      .then((r) => setPresets(Array.isArray(r.data?.presets) ? r.data.presets : []))
      .catch(() => setPresets([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const runEstimate = useCallback(() => {
    if (!targetingSpec) {
      setMessage('Aucun ciblage de base fourni par le composeur.')
      return
    }
    setEstimating(true)
    setMessage('')
    adsengineApi.audiences
      .deliveryEstimate({ targeting_spec: targetingSpec })
      .then((r) => setEstimate(r.data?.estimate || null))
      .catch(() => setEstimate(null))
      .finally(() => setEstimating(false))
  }, [targetingSpec])

  const create = useCallback(() => {
    if (!selected) return
    setCreating(true)
    setMessage('')
    adsengineApi.audiences
      .createEngagement({ preset_key: selected })
      .then((r) => {
        if (r.data?.audience_id) {
          setMessage('Audience d\'engagement créée.')
          onCreated(r.data)
        } else {
          setMessage('Création impossible : ' + (r.data?.error || 'inconnu'))
        }
      })
      .catch(() => setMessage('Création impossible.'))
      .finally(() => setCreating(false))
  }, [selected, onCreated])

  if (loading) {
    return <div data-testid="ae-engagement-loading">Chargement…</div>
  }

  return (
    <div data-testid="ae-engagement-picker">
      <h4><Users size={16} aria-hidden /> Audiences d&apos;engagement</h4>
      <p data-testid="ae-engagement-note">
        Sans donnée client : dérivées des interactions Meta (formulaire, Page,
        Instagram).
      </p>

      <ul data-testid="ae-engagement-list">
        {presets.map((preset) => (
          <li key={preset.key}>
            <label>
              <input
                type="radio"
                name="engagement-preset"
                value={preset.key}
                checked={selected === preset.key}
                onChange={() => setSelected(preset.key)}
                data-testid={`ae-engagement-option-${preset.key}`}
              />
              <span data-testid="ae-engagement-label">{preset.label}</span>
              <span data-testid="ae-engagement-retention">
                Rétention {preset.retention_days} j
              </span>
            </label>
          </li>
        ))}
      </ul>

      <div>
        <button
          type="button"
          onClick={runEstimate}
          disabled={estimating}
          data-testid="ae-engagement-estimate-btn"
        >
          <Sparkles size={14} aria-hidden /> Estimer l&apos;audience
        </button>
        {estimate && (
          <span data-testid="ae-engagement-estimate">
            {estimate.estimate_ready
              ? `Portée quotidienne estimée : ${estimate.estimate_dau ?? '—'}`
              : 'Estimation en cours de préparation…'}
          </span>
        )}
      </div>

      <button
        type="button"
        onClick={create}
        disabled={!selected || creating}
        data-testid="ae-engagement-create-btn"
      >
        Créer l&apos;audience
      </button>

      {message && (
        <p data-testid="ae-engagement-message">{message}</p>
      )}
    </div>
  )
}
