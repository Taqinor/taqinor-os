import { useEffect, useState, useCallback } from 'react'
import { Route, Check, X, Plus, Trash2, PlayCircle } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizePreflight, normalizeValidation, normalizeFlightTemplate,
} from './adsengine'
// PUB5 — picker « Audiences d'engagement » (ADSDEEP59), orphelin : construit +
// testé mais jamais monté dans le composeur d'adset. Aucun composeur d'adset
// dédié n'existe encore côté front — le composeur du plan de vol EST le seul
// endroit où une audience se prépare aujourd'hui.
import EngagementAudiencePicker from './EngagementAudiencePicker'

/* ============================================================================
   ENG40 — Éditeur de plan de vol + panneau préflight (l'écran-amiral P7).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md) : composer les 6 mois d'une campagne AVANT tout
   dirham réel. On assemble :
   - un GABARIT de phases (ADSENG28) → phases 6 mois pré-composées, nommables ;
   - des VARIABLES du plan (ville, mode, objectif…) — paires clé/valeur ;
   - des BRAS depuis le backlog (recombinaisons prêtes).
   Le panneau PRÉFLIGHT (ADSENG38) affiche en checklist verte/rouge FR TOUTES les
   portes d'autonomie : tant qu'une porte est rouge, le mode autonome ne peut PAS
   s'activer (structurel) — la liste de ce qui manque est explicite.
   « Valider le plan » renvoie soit un feu vert, soit un REFUS avec ses raisons FR
   (jamais fabriquées : elles viennent de l'API). La simulation se lance d'ici.
   ========================================================================== */

const EMPTY_VAR = { cle: '', valeur: '' }

// PUB5 — ciblage de base pour l'estimation d'audience (dossier §5, doctrine
// « montrer l'estimation AVANT usage ») : le marché est le Maroc (aucun autre
// pays n'est jamais ciblé), jamais un ciblage inventé au-delà de ce socle.
const BASE_TARGETING_SPEC = { geo_locations: { countries: ['MA'] } }

export default function FlightPlanScreen() {
  const [templates, setTemplates] = useState([])
  const [arms, setArms] = useState([])
  const [preflight, setPreflight] = useState({ pret: false, portes: [], manquantes: [] })
  const [loading, setLoading] = useState(true)

  // Plan composé (état local).
  const [nom, setNom] = useState('')
  const [templateKey, setTemplateKey] = useState('')
  const [phases, setPhases] = useState([])
  const [variables, setVariables] = useState([{ ...EMPTY_VAR }])
  const [selectedArms, setSelectedArms] = useState(() => new Set())

  const [validation, setValidation] = useState(null) // { ok, raisons }
  const [simMsg, setSimMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.flightplan.templates()
      .then(r => setTemplates((Array.isArray(r.data) ? r.data : (r.data?.results || []))
        .map(normalizeFlightTemplate)))
      .catch(() => setTemplates([]))
    adsengineApi.flightplan.backlogArms()
      .then(r => setArms(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setArms([]))
    adsengineApi.flightplan.preflight()
      .then(r => setPreflight(normalizePreflight(r.data)))
      .catch(() => setPreflight({ pret: false, portes: [], manquantes: [] }))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // Composer : choisir un gabarit charge ses phases 6 mois.
  const pickTemplate = (key) => {
    setTemplateKey(key)
    setValidation(null)
    const t = templates.find(x => x.key === key)
    setPhases(t ? t.phases.map(p => ({ ...p })) : [])
  }

  const setVar = (i, field, value) =>
    setVariables(vs => vs.map((v, idx) => idx === i ? { ...v, [field]: value } : v))
  const addVar = () => setVariables(vs => [...vs, { ...EMPTY_VAR }])
  const removeVar = (i) => setVariables(vs => vs.filter((_, idx) => idx !== i))

  const toggleArm = (id) => setSelectedArms(s => {
    const next = new Set(s)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  // PUB5 — une audience d'engagement créée s'ajoute comme variable du plan
  // (traçable dans le payload composé) plutôt que de disparaître.
  const onAudienceCreated = (data) => {
    if (!data?.audience_id) return
    setVariables(vs => [...vs, { cle: 'audience_engagement', valeur: String(data.audience_id) }])
  }

  const composePayload = () => ({
    nom,
    template: templateKey,
    phases: phases.map(p => ({ key: p.key, duree_mois: p.duree_mois })),
    variables: variables.filter(v => v.cle),
    bras: [...selectedArms],
  })

  const validate = async () => {
    setBusy(true); setValidation(null); setSimMsg('')
    try {
      const r = await adsengineApi.flightplan.validate(composePayload())
      setValidation(normalizeValidation(r.data))
    } catch {
      setValidation({ ok: false, raisons: ['Validation impossible (erreur réseau).'] })
    } finally {
      setBusy(false)
    }
  }

  const simulate = async () => {
    setBusy(true); setSimMsg('')
    try {
      await adsengineApi.flightplan.simulate(composePayload())
      setSimMsg('Simulation lancée — consultez la visionneuse de simulation.')
    } catch {
      setSimMsg('Lancement de la simulation impossible.')
    } finally {
      setBusy(false)
    }
  }

  const composed = phases.length > 0

  return (
    <div className="page ae-flightplan" data-testid="ae-flightplan">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Route size={20} aria-hidden="true" /> Plan de vol
        </h2>
      </div>

      {loading ? <p className="page-loading">Chargement…</p> : (
        <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)' }}>
          {/* ── Colonne composition ── */}
          <div style={{ display: 'grid', gap: '1rem' }}>
            {/* Nom + gabarit */}
            <section className="card ae-fp-compose" data-testid="ae-fp-compose"
              style={{ padding: '1rem' }}>
              <h3 style={{ margin: '0 0 0.6rem' }}>Composer le plan (6 mois)</h3>
              <label style={{ display: 'grid', gap: '0.2rem', marginBottom: '0.6rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#475569' }}>Nom du plan</span>
                <input className="form-input" data-testid="ae-fp-nom"
                  value={nom} onChange={e => setNom(e.target.value)} />
              </label>
              <label style={{ display: 'grid', gap: '0.2rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#475569' }}>Gabarit de phases</span>
                <select className="form-input" data-testid="ae-fp-template"
                  value={templateKey} onChange={e => pickTemplate(e.target.value)}>
                  <option value="">Choisir un gabarit…</option>
                  {templates.map(t => (
                    <option key={t.key} value={t.key}>{t.nom}</option>
                  ))}
                </select>
              </label>

              {/* Phases composées */}
              {composed && (
                <ol data-testid="ae-fp-phases"
                  style={{ listStyle: 'none', margin: '0.75rem 0 0', padding: 0, display: 'grid', gap: '0.4rem' }}>
                  {phases.map((p, i) => (
                    <li key={p.key} data-testid="ae-fp-phase"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                        background: '#f8fafc', padding: '0.4rem 0.7rem', borderRadius: 6 }}>
                      <span className="badge" style={{ background: '#e0e7ff', color: '#3730a3' }}>{i + 1}</span>
                      <strong>{p.label}</strong>
                      <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: '0.85rem' }}>
                        {p.duree_mois != null ? `${p.duree_mois} mois` : '—'}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            {/* Variables */}
            <section className="card ae-fp-variables" data-testid="ae-fp-variables"
              style={{ padding: '1rem' }}>
              <h3 style={{ margin: '0 0 0.6rem' }}>Variables du plan</h3>
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                {variables.map((v, i) => (
                  <div key={i} data-testid="ae-fp-variable"
                    style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <input className="form-input" data-testid={`ae-fp-var-cle-${i}`}
                      placeholder="Clé (ex. ville)" aria-label={`Clé de la variable ${i + 1}`}
                      value={v.cle} onChange={e => setVar(i, 'cle', e.target.value)}
                      style={{ flex: '1 1 140px' }} />
                    <input className="form-input" data-testid={`ae-fp-var-val-${i}`}
                      placeholder="Valeur (ex. Casablanca)" aria-label={`Valeur de la variable ${i + 1}`}
                      value={v.valeur} onChange={e => setVar(i, 'valeur', e.target.value)}
                      style={{ flex: '1 1 140px' }} />
                    <button type="button" className="btn btn-light" data-testid={`ae-fp-var-remove-${i}`}
                      aria-label={`Retirer la variable ${i + 1}`} onClick={() => removeVar(i)}>
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
              <button type="button" className="btn btn-light" data-testid="ae-fp-var-add"
                onClick={addVar}
                style={{ marginTop: '0.5rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                <Plus size={14} aria-hidden="true" /> Ajouter une variable
              </button>
            </section>

            {/* Bras depuis le backlog */}
            <section className="card ae-fp-arms" data-testid="ae-fp-arms"
              style={{ padding: '1rem' }}>
              <h3 style={{ margin: '0 0 0.6rem' }}>Bras (depuis le backlog)</h3>
              {arms.length === 0
                ? <p style={{ color: '#64748b', margin: 0 }}>Aucun bras disponible dans le backlog.</p>
                : (
                  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.35rem' }}>
                    {arms.map(a => (
                      <li key={a.id}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <input type="checkbox" data-testid={`ae-fp-arm-${a.id}`}
                            checked={selectedArms.has(a.id)} onChange={() => toggleArm(a.id)} />
                          <span>{a.nom || a.name || `Bras ${a.id}`}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
            </section>

            {/* PUB5 — Audiences d'engagement (ADSDEEP59), orphelines avant cette
                tâche : preset + estimation AVANT usage + création, disponible
                depuis le composeur du plan de vol. */}
            <section className="card ae-fp-audiences" data-testid="ae-fp-audiences"
              style={{ padding: '1rem' }}>
              <EngagementAudiencePicker
                targetingSpec={BASE_TARGETING_SPEC}
                onCreated={onAudienceCreated}
              />
            </section>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-primary" data-testid="ae-fp-validate"
                disabled={busy || !composed} onClick={validate}>
                Valider le plan
              </button>
              <button type="button" className="btn btn-success" data-testid="ae-fp-simulate"
                disabled={busy || !composed}
                onClick={simulate}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <PlayCircle size={15} aria-hidden="true" /> Lancer la simulation
              </button>
            </div>

            {/* Résultat de validation */}
            {validation && (validation.ok
              ? <p className="ae-fp-valid" data-testid="ae-fp-valid"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem',
                    background: '#dcfce7', color: '#166534', padding: '0.6rem 0.8rem', borderRadius: 8 }}>
                  <Check size={16} aria-hidden="true" /> Plan valide — prêt à simuler.
                </p>
              : (
                <div className="ae-fp-refusal" data-testid="ae-fp-refusal"
                  style={{ background: '#fee2e2', color: '#991b1b', padding: '0.6rem 0.8rem', borderRadius: 8 }}>
                  <strong style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <X size={16} aria-hidden="true" /> Plan refusé
                  </strong>
                  <ul style={{ margin: '0.4rem 0 0', paddingLeft: '1.2rem' }}>
                    {validation.raisons.length === 0
                      ? <li data-testid="ae-fp-refusal-reason">Raison non précisée.</li>
                      : validation.raisons.map((r, i) => (
                        <li key={i} data-testid="ae-fp-refusal-reason">{r}</li>
                      ))}
                  </ul>
                </div>
              ))}

            {simMsg && <p data-testid="ae-fp-sim-msg" style={{ color: '#475569' }}>{simMsg}</p>}
          </div>

          {/* ── Colonne préflight (ADSENG38) ── */}
          <aside>
            <section className="card ae-fp-preflight" data-testid="ae-fp-preflight"
              style={{ padding: '1rem', position: 'sticky', top: '1rem' }}>
              <h3 style={{ margin: '0 0 0.6rem' }}>Préflight d&apos;autonomie</h3>
              <p data-testid="ae-fp-preflight-verdict"
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem',
                  background: preflight.pret ? '#dcfce7' : '#fef9c3',
                  color: preflight.pret ? '#166534' : '#854d0e',
                  padding: '0.5rem 0.7rem', borderRadius: 8, margin: '0 0 0.75rem' }}>
                {preflight.pret
                  ? <><Check size={16} aria-hidden="true" /> Prêt — autonomie activable (OFF par défaut).</>
                  : <><X size={16} aria-hidden="true" /> Autonomie bloquée — {preflight.manquantes.length} porte(s) à ouvrir.</>}
              </p>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.4rem' }}>
                {preflight.portes.length === 0
                  ? <li style={{ color: '#64748b' }}>Portes indisponibles.</li>
                  : preflight.portes.map(g => (
                    <li key={g.key} data-testid="ae-fp-gate"
                      style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                      <span aria-hidden="true" style={{
                        color: g.ok ? '#16a34a' : '#dc2626', flex: '0 0 auto', marginTop: '0.1rem' }}>
                        {g.ok ? <Check size={16} /> : <X size={16} />}
                      </span>
                      <span>
                        <span style={{ fontWeight: 600 }}>{g.label}</span>
                        {' '}
                        <span className="badge" data-testid={g.ok ? 'ae-fp-gate-ok' : 'ae-fp-gate-ko'}
                          style={{ background: g.ok ? '#dcfce7' : '#fee2e2',
                            color: g.ok ? '#166534' : '#991b1b' }}>
                          {g.ok ? 'Vert' : 'Rouge'}
                        </span>
                        {!g.ok && g.detail && (
                          <span style={{ display: 'block', color: '#64748b', fontSize: '0.85rem' }}>{g.detail}</span>
                        )}
                      </span>
                    </li>
                  ))}
              </ul>
            </section>
          </aside>
        </div>
      )}
    </div>
  )
}
