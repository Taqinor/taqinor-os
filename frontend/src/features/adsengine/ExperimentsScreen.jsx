import { useEffect, useState, useMemo, useCallback } from 'react'
import { FlaskConical, Trophy, ChevronDown, ChevronUp } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeExperiment, normalizeArms, normalizeDecisionLog, bestArm,
  formatPercent, formatMAD, formatNumber,
} from './adsengine'

/* ============================================================================
   ENG39 — Écran « Expérimentations » (moteur bandit).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md, domaine 3 — A/B testing traçable) : rendre les
   POSTERIORS lisibles par un NON-statisticien. TOUS les nombres viennent de
   l'API — rien n'est calculé ni inventé ici.

   PACT110 — câblage réparé : la section « Bras » lisait ``current.bras``
   depuis la réponse de ``GET /adsengine/experiences/<id>/`` — un champ que
   ``ExperimentSerializer`` ne renvoie JAMAIS. Les bras RÉELS (``ExperimentArm``)
   vivent sur leur propre collection ``bras/`` (aucun filtre serveur par
   expérience) ; leurs seules stats réellement exposées par l'API sont celles
   du DecisionLog le plus récent (``allocations.prob_best``/``budget_mad``,
   indexées par ``label``) — jamais une moyenne/bande de crédibilité
   fabriquée. La section « Journal des décisions » lisait ``decision_fr``/
   ``chiffres``/``phase`` — trois champs absents de ``DecisionLogSerializer`` ;
   la phrase FR réelle est ``summary_fr``. Deux vues jamais construites
   s'ajoutent : la série quotidienne d'un bras (``stats-bras/``) et le journal
   des décisions toutes expériences confondues (``decisions/``).
   ========================================================================== */

// Tons de statut de phase (déterministes, FR).
function phaseTone(statut) {
  const s = String(statut || '').toLowerCase()
  if (s.startsWith('termin')) return { bg: '#dcfce7', color: '#166534' }
  if (s.startsWith('en_cours') || s.startsWith('en cours')) return { bg: '#e0f2fe', color: '#075985' }
  return { bg: '#f1f5f9', color: '#64748b' }
}

/* PUB87 — Calculateur MDE/puissance (vue mince sur mde.py) : avant de lancer une
   expérience, l'opérateur voit « avec votre volume, ~X jours pour détecter
   +20 % ». Tous les chiffres viennent de l'API mde (backend) — rien n'est calculé
   ici. L'appel est GARDÉ : si l'API mde n'est pas câblée, le panneau reste inerte
   (jamais un crash). */
function MdeCalculator() {
  const [p, setP] = useState('0.02')
  const [volume, setVolume] = useState('300')
  const [cible, setCible] = useState('0.20')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const compute = useCallback(() => {
    const req = adsengineApi.experiments.mde?.({ p, volume, cible })
    if (!req || typeof req.then !== 'function') return
    req
      .then(r => { setResult(r.data); setError('') })
      .catch(() => { setResult(null); setError('Calcul indisponible.') })
  }, [p, volume, cible])

  useEffect(() => { compute() }, [compute])

  return (
    <section className="card ae-exp-mde" data-testid="ae-exp-mde"
      style={{ padding: '1rem', marginBottom: '1rem' }}>
      <h3 style={{ margin: '0 0 0.6rem' }}>Avant de lancer — combien de temps ?</h3>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'grid', gap: '0.2rem' }}>
          <span style={{ fontSize: '0.8rem', color: '#475569' }}>Taux de base (p)</span>
          <input className="form-input" data-testid="ae-mde-p" type="number" step="any"
            value={p} onChange={e => setP(e.target.value)} style={{ width: 110 }} />
        </label>
        <label style={{ display: 'grid', gap: '0.2rem' }}>
          <span style={{ fontSize: '0.8rem', color: '#475569' }}>Volume (essais/bras/jour)</span>
          <input className="form-input" data-testid="ae-mde-volume" type="number" step="any"
            value={volume} onChange={e => setVolume(e.target.value)} style={{ width: 130 }} />
        </label>
        <label style={{ display: 'grid', gap: '0.2rem' }}>
          <span style={{ fontSize: '0.8rem', color: '#475569' }}>Effet cible (fraction)</span>
          <input className="form-input" data-testid="ae-mde-cible" type="number" step="any"
            value={cible} onChange={e => setCible(e.target.value)} style={{ width: 110 }} />
        </label>
        <button type="button" className="btn btn-primary" data-testid="ae-mde-compute"
          onClick={compute}>Calculer</button>
      </div>
      {error && <p data-testid="ae-mde-error" style={{ color: '#b91c1c', marginTop: '0.6rem' }}>{error}</p>}
      {result && (
        <>
          <p data-testid="ae-mde-phrase" style={{ margin: '0.7rem 0 0.4rem', fontWeight: 600 }}>
            {result.phrase_fr}
          </p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {(result.mde_par_horizon || []).map(h => (
              <li key={h.jours} data-testid="ae-mde-horizon" className="badge"
                style={{ background: '#f1f5f9', color: '#475569' }}>
                {h.jours} j : {h.mde_relatif_pct == null ? '—' : `${h.mde_relatif_pct} %`} détectable
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

// PACT110 — Série quotidienne d'un bras (``ArmDailyStat``), chargée à la
// demande (un panneau par bras, évite N appels au chargement de l'écran).
function ArmDailySeries({ armId }) {
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect -- indicateur de chargement au montage
    setLoading(true)
    adsengineApi.experiments.armStats()
      .then(r => {
        if (cancelled) return
        const all = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        const mine = all.filter(s => s && s.arm === armId)
          .sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')))
        setRows(mine)
      })
      .catch(() => { if (!cancelled) setRows([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [armId])

  if (loading) return <p style={{ color: '#64748b', margin: '0.5rem 0 0' }}>Chargement…</p>
  if (!rows || rows.length === 0) {
    return <p data-testid="ae-exp-arm-series-empty" style={{ color: '#64748b', margin: '0.5rem 0 0' }}>
      Aucune statistique quotidienne pour ce bras.</p>
  }
  return (
    <table data-testid="ae-exp-arm-series" style={{ width: '100%', marginTop: '0.5rem', fontSize: '0.85rem',
      borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ textAlign: 'left', color: '#64748b' }}>
          <th style={{ padding: '0.2rem 0.4rem' }}>Date</th>
          <th style={{ padding: '0.2rem 0.4rem' }}>Impressions</th>
          <th style={{ padding: '0.2rem 0.4rem' }}>Clics</th>
          <th style={{ padding: '0.2rem 0.4rem' }}>Conversations</th>
          <th style={{ padding: '0.2rem 0.4rem' }}>Dépense</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(s => (
          <tr key={s.id} data-testid="ae-exp-arm-series-row" style={{ borderTop: '1px solid #e2e8f0' }}>
            <td style={{ padding: '0.2rem 0.4rem' }}>{s.date || '—'}</td>
            <td style={{ padding: '0.2rem 0.4rem' }}>{formatNumber(s.impressions)}</td>
            <td style={{ padding: '0.2rem 0.4rem' }}>{formatNumber(s.clicks)}</td>
            <td style={{ padding: '0.2rem 0.4rem' }}>{formatNumber(s.conversations)}</td>
            <td style={{ padding: '0.2rem 0.4rem' }}>{formatMAD(s.spend)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function ExperimentsScreen() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [current, setCurrent] = useState(null) // expérimentation normalisée
  const [arms, setArms] = useState([])
  const [log, setLog] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [openArmId, setOpenArmId] = useState(null)

  // PACT110 — Journal des décisions TOUTES expériences (vue globale, chargée
  // une fois au montage — indépendante de l'expérimentation sélectionnée).
  const [allDecisions, setAllDecisions] = useState([])
  const [allDecisionsLoading, setAllDecisionsLoading] = useState(true)

  // Charge le détail (expérience + ses bras réels + son DecisionLog).
  const loadDetail = useCallback((id) => {
    setSelectedId(id)
    setOpenArmId(null)
    adsengineApi.experiments.get(id)
      .then(r => setCurrent(normalizeExperiment(r.data)))
      .catch(() => setCurrent(null))
    Promise.all([
      adsengineApi.experiments.decisionLog(id),
      adsengineApi.experiments.arms(),
    ])
      .then(([decisionsRes, armsRes]) => {
        const rawDecisions = Array.isArray(decisionsRes.data)
          ? decisionsRes.data : (decisionsRes.data?.results || [])
        const latestDecision = rawDecisions[0] || null
        setLog(normalizeDecisionLog(rawDecisions))
        setArms(normalizeArms(armsRes.data, id, latestDecision))
      })
      .catch(() => { setLog([]); setArms([]) })
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.experiments.list()
      .then(r => {
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        setList(rows)
        if (rows.length) loadDetail(rows[0].id)
      })
      .catch(() => setList([]))
      .finally(() => setLoading(false))
  }, [loadDetail])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    setAllDecisionsLoading(true)
    adsengineApi.experiments.allDecisions()
      .then(r => setAllDecisions(normalizeDecisionLog(r.data)))
      .catch(() => setAllDecisions([]))
      .finally(() => setAllDecisionsLoading(false))
  }, [])

  const expNameById = useMemo(() => {
    const map = new Map()
    list.forEach(e => map.set(e.id, e.nom || e.name || `Expérimentation ${e.id}`))
    return map
  }, [list])

  const best = current ? bestArm(arms) : null

  return (
    <div className="page ae-experiments" data-testid="ae-experiments">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <FlaskConical size={20} aria-hidden="true" /> Expérimentations
        </h2>
      </div>

      {/* PUB87 — calculateur MDE/puissance avant lancement (interactif). */}
      <MdeCalculator />

      {loading
        ? <p className="page-loading">Chargement…</p>
        : list.length === 0
          ? <p data-testid="ae-exp-empty" style={{ color: '#64748b' }}>
              Aucune expérimentation en cours.</p>
          : (
            <>
              {/* Sélecteur d'expérimentation */}
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}
                data-testid="ae-exp-list" role="group" aria-label="Choisir une expérimentation">
                {list.map(e => (
                  <button key={e.id} type="button"
                    className={`btn ${selectedId === e.id ? 'btn-primary' : 'btn-light'}`}
                    data-testid={`ae-exp-select-${e.id}`}
                    aria-pressed={selectedId === e.id}
                    onClick={() => loadDetail(e.id)}>
                    {e.nom || e.name || `Expérimentation ${e.id}`}
                  </button>
                ))}
              </div>

              {current && (
                <>
                  {/* Timeline des phases */}
                  <section className="card ae-exp-phases" data-testid="ae-exp-phases"
                    style={{ padding: '1rem', marginBottom: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.6rem' }}>Phases</h3>
                    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex',
                      gap: '0.5rem', flexWrap: 'wrap' }}>
                      {current.phases.length === 0
                        ? <li style={{ color: '#64748b' }}>Aucune phase définie.</li>
                        : current.phases.map(p => {
                          const tone = phaseTone(p.statut)
                          return (
                            <li key={p.key} data-testid="ae-exp-phase"
                              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem',
                                background: tone.bg, color: tone.color,
                                padding: '0.4rem 0.7rem', borderRadius: 999 }}>
                              <strong>{p.label}</strong>
                              <span style={{ fontSize: '0.8rem' }}>· {p.statut_display || '—'}</span>
                            </li>
                          )
                        })}
                    </ol>
                  </section>

                  {/* Bras — PACT110 : liste RÉELLE (ExperimentArm), enrichie des
                      seules stats que le DecisionLog le plus récent renvoie. */}
                  <section className="card ae-exp-arms" data-testid="ae-exp-arms"
                    style={{ padding: '1rem', marginBottom: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.75rem' }}>Bras</h3>
                    {arms.length === 0
                      ? <p data-testid="ae-exp-arms-empty" style={{ color: '#64748b' }}>
                          Aucun bras créé pour cette expérimentation.</p>
                      : (
                        <div style={{ display: 'grid', gap: '0.6rem' }}>
                          {arms.map(b => {
                            const isBest = best && b.id === best.id
                            const isOpen = openArmId === b.id
                            return (
                              <article key={b.id} data-testid="ae-exp-arm"
                                style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.75rem',
                                  background: isBest ? '#f0fdf4' : '#fff' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                                  flexWrap: 'wrap' }}>
                                  <strong data-testid={`ae-exp-arm-nom-${b.id}`}>{b.nom}</strong>
                                  <span className="badge" style={{
                                    background: b.actif ? '#dcfce7' : '#f1f5f9',
                                    color: b.actif ? '#166534' : '#64748b' }}>
                                    {b.actif ? 'Actif' : 'Inactif'}
                                  </span>
                                  {isBest && (
                                    <span className="badge" data-testid="ae-exp-arm-best"
                                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                                        background: '#dcfce7', color: '#166534' }}>
                                      <Trophy size={13} aria-hidden="true" /> Favori du moteur
                                    </span>
                                  )}
                                  <button type="button" className="btn btn-light"
                                    data-testid={`ae-exp-arm-series-toggle-${b.id}`}
                                    style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}
                                    onClick={() => setOpenArmId(isOpen ? null : b.id)}>
                                    Série quotidienne
                                    {isOpen ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
                                  </button>
                                </div>

                                {(b.p_best != null || b.budget_mad != null) && (
                                  <p style={{ margin: '0.4rem 0 0', color: '#334155', fontSize: '0.9rem' }}>
                                    {b.p_best != null && (
                                      <>Probabilité d&apos;être le meilleur :{' '}
                                        <strong data-testid={`ae-exp-pbest-${b.id}`}>{formatPercent(b.p_best)}</strong>
                                      </>
                                    )}
                                    {b.p_best != null && b.budget_mad != null && '  ·  '}
                                    {b.budget_mad != null && (
                                      <>Budget alloué :{' '}
                                        <strong data-testid={`ae-exp-budget-${b.id}`}>{formatMAD(b.budget_mad)}/jour</strong>
                                      </>
                                    )}
                                  </p>
                                )}

                                {isOpen && <ArmDailySeries armId={b.id} />}
                              </article>
                            )
                          })}
                        </div>
                      )}
                  </section>

                  {/* DecisionLog de l'expérimentation sélectionnée — PACT110 :
                      ``decision_fr`` = ``summary_fr`` réel, ``chiffres`` = les
                      montants/probas RÉELS de ``allocations``. */}
                  <section className="card ae-exp-decisions" data-testid="ae-exp-decisions"
                    style={{ padding: '1rem', marginBottom: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.6rem' }}>Journal des décisions</h3>
                    {log.length === 0
                      ? <p data-testid="ae-exp-decisions-empty" style={{ color: '#64748b' }}>
                          Aucune décision pour cette expérimentation.</p>
                      : (
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
                          {log.map(d => (
                            <li key={d.id} className="ae-exp-decision" data-testid="ae-exp-decision"
                              style={{ borderLeft: '3px solid #cbd5e1', paddingLeft: '0.75rem' }}>
                              <p style={{ margin: 0, color: '#1e293b' }}>{d.decision_fr}</p>
                              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap',
                                marginTop: '0.3rem' }}>
                                {Object.entries(d.chiffres).map(([k, v]) => (
                                  <span key={k} className="badge" data-testid="ae-exp-decision-figure"
                                    style={{ background: '#f1f5f9', color: '#475569' }}>
                                    {k} : {typeof v === 'number' ? formatNumber(v, Number.isInteger(v) ? 0 : 2) : String(v)}
                                  </span>
                                ))}
                                {d.quand && (
                                  <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>
                                    {d.quand}
                                  </span>
                                )}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                  </section>
                </>
              )}

              {/* PACT110 — vue jamais construite : le journal des décisions
                  TOUTES expériences confondues (pas seulement la sélectionnée). */}
              <section className="card ae-exp-decisions-all" data-testid="ae-exp-decisions-all"
                style={{ padding: '1rem' }}>
                <h3 style={{ margin: '0 0 0.6rem' }}>Toutes les décisions (toutes expérimentations)</h3>
                {allDecisionsLoading
                  ? <p style={{ color: '#64748b' }}>Chargement…</p>
                  : allDecisions.length === 0
                    ? <p data-testid="ae-exp-decisions-all-empty" style={{ color: '#64748b' }}>
                        Aucune décision enregistrée.</p>
                    : (
                      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
                        {allDecisions.map(d => (
                          <li key={d.id} data-testid="ae-exp-decision-all"
                            style={{ borderLeft: '3px solid #cbd5e1', paddingLeft: '0.75rem' }}>
                            <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'baseline', flexWrap: 'wrap' }}>
                              <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>
                                {expNameById.get(d.experiment) || `Expérimentation ${d.experiment}`}
                              </span>
                              {d.quand && <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{d.quand}</span>}
                            </div>
                            <p style={{ margin: '0.3rem 0 0', color: '#1e293b' }}>{d.decision_fr}</p>
                          </li>
                        ))}
                      </ul>
                    )}
              </section>
            </>
          )}
    </div>
  )
}
