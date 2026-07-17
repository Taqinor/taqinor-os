import { useEffect, useState, useCallback } from 'react'
import { Check, X, ClipboardCheck, AlertTriangle, PlusCircle } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  actionTypeLabel, budgetDiff, actionCreative, formatMAD, REJECTION_REASONS,
  actionWarnings, editCopyDiff,
} from './adsengine'
import EditCopyComposer from './EditCopyComposer'

/* ============================================================================
   ENG25 — Boîte d'approbation (l'écran-vaisseau-amiral).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md — la boîte d'approbation EST le produit) : chaque
   carte `EngineAction` montre l'ARTEFACT RÉEL (préview du créatif, diff budget
   avant→après) + `reason_fr` (le « pourquoi »), et l'humain approuve/rejette via
   des CONTRÔLES STRUCTURÉS — JAMAIS un chat libre. Le rejet passe par un motif
   choisi dans une liste (REJECTION_REASONS), pas une zone de texte ouverte.
   Vue batch : toggle par item, approbation de la sélection (batch PARTIEL
   possible). Une action appliquée QUITTE la boîte immédiatement.
   Approuver reste une permission distincte de proposer (ENG19, gated backend) :
   si l'API refuse, l'action reste dans la boîte et une erreur s'affiche.
   ========================================================================== */

export default function ApprovalsScreen() {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(() => new Set()) // ids du batch
  const [rejectingId, setRejectingId] = useState(null)
  const [rejectReason, setRejectReason] = useState(REJECTION_REASONS[0].value)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  // ADSDEEP35 — composeur EDIT_COPY (avant/après + envoi comme proposition).
  const [showComposer, setShowComposer] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.actions.pending()
      .then(r => setActions(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setActions([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // Retire une (ou plusieurs) action(s) appliquée(s) de la boîte + du batch.
  const removeApplied = (ids) => {
    const set = new Set(ids)
    setActions(list => list.filter(a => !set.has(a.id)))
    setSelected(sel => {
      const next = new Set(sel)
      ids.forEach(id => next.delete(id))
      return next
    })
  }

  const approve = async (id) => {
    setBusy(true); setErr('')
    try {
      await adsengineApi.actions.approve(id)
      removeApplied([id])
    } catch {
      setErr("Approbation refusée (permission ?). L'action reste dans la boîte.")
    } finally {
      setBusy(false)
    }
  }

  const openReject = (id) => {
    setRejectingId(id)
    setRejectReason(REJECTION_REASONS[0].value)
  }

  const confirmReject = async (id) => {
    setBusy(true); setErr('')
    try {
      await adsengineApi.actions.reject(id, { reason: rejectReason })
      setRejectingId(null)
      removeApplied([id])
    } catch {
      setErr("Rejet impossible. L'action reste dans la boîte.")
    } finally {
      setBusy(false)
    }
  }

  const toggleSelect = (id) => setSelected(sel => {
    const next = new Set(sel)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  // Batch PARTIEL : n'approuve QUE les cases cochées.
  const approveSelected = async () => {
    const ids = actions.map(a => a.id).filter(id => selected.has(id))
    if (ids.length === 0) return
    setBusy(true); setErr('')
    try {
      await Promise.all(ids.map(id => adsengineApi.actions.approve(id)))
      removeApplied(ids)
    } catch {
      setErr("Une partie de la sélection n'a pu être approuvée.")
      load()
    } finally {
      setBusy(false)
    }
  }

  const selectedCount = actions.filter(a => selected.has(a.id)).length

  return (
    <div className="page ae-approvals">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <ClipboardCheck size={20} aria-hidden="true" /> Boîte d&apos;approbation
        </h2>
        <button type="button" className="btn btn-light ae-toggle-composer"
          data-testid="ae-toggle-composer"
          onClick={() => setShowComposer(v => !v)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <PlusCircle size={15} aria-hidden="true" />
          {showComposer ? 'Fermer le composeur' : "Éditer le texte d'une ad"}
        </button>
      </div>

      {showComposer && (
        <EditCopyComposer onProposed={() => { setShowComposer(false); load() }} />
      )}

      {err && <p data-testid="ae-approvals-err" style={{ color: '#dc2626' }}>{err}</p>}

      {/* Barre de batch (toggle par item ci-dessous) */}
      {selectedCount > 0 && (
        <div className="ae-batch-bar" data-testid="ae-batch-bar"
          style={{ display: 'flex', alignItems: 'center', gap: '0.75rem',
            background: '#eef2ff', padding: '0.6rem 0.9rem', borderRadius: 8, marginBottom: '1rem' }}>
          <span data-testid="ae-batch-count">{selectedCount} sélectionnée(s)</span>
          <button type="button" className="btn btn-primary" data-testid="ae-batch-approve"
            disabled={busy} onClick={approveSelected}>
            Approuver la sélection
          </button>
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : actions.length === 0
          ? <p data-testid="ae-approvals-empty" style={{ color: '#64748b' }}>
              Aucune action en attente d&apos;approbation.</p>
          : (
            <div style={{ display: 'grid', gap: '1rem' }}>
              {actions.map(a => {
                const diff = budgetDiff(a)
                const creative = actionCreative(a)
                const warnings = actionWarnings(a)
                const copyDiff = editCopyDiff(a)
                return (
                  <article key={a.id} className="card ae-action-card" data-testid="ae-action-card"
                    style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem' }}>
                      <input type="checkbox" className="ae-batch-toggle"
                        data-testid={`ae-batch-toggle-${a.id}`}
                        checked={selected.has(a.id)} onChange={() => toggleSelect(a.id)}
                        aria-label={`Sélectionner l'action ${actionTypeLabel(a.type)}`}
                        style={{ marginTop: '0.3rem' }} />
                      <div style={{ flex: 1 }}>
                        <h3 style={{ margin: 0 }}>{actionTypeLabel(a.type)}</h3>

                        {/* Le « pourquoi » — reason_fr */}
                        <p data-testid="ae-action-reason" style={{ margin: '0.35rem 0', color: '#334155' }}>
                          {a.reason_fr || 'Aucune raison fournie.'}
                        </p>

                        {/* Artefact réel — diff budget avant→après */}
                        {diff && (
                          <div className="ae-artifact-budget" data-testid="ae-artifact-budget"
                            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                              background: '#f8fafc', padding: '0.5rem 0.75rem', borderRadius: 6 }}>
                            <span>{formatMAD(diff.avant)}</span>
                            <span aria-hidden="true">→</span>
                            <strong style={{
                              color: diff.direction === 'up' ? '#b91c1c'
                                : diff.direction === 'down' ? '#15803d' : '#334155' }}>
                              {formatMAD(diff.apres)}
                            </strong>
                            <span style={{ color: '#64748b', fontSize: '0.85rem' }}>
                              ({diff.delta > 0 ? '+' : ''}{formatMAD(diff.delta)})
                            </span>
                          </div>
                        )}

                        {/* ADSDEEP31/32/34 — avertissements (reset d'apprentissage,
                            perte de preuve sociale, immutabilité d'étude…) : PORTÉS
                            par le backend, jamais recalculés ici. */}
                        {warnings.length > 0 && (
                          <div className="ae-warnings" data-testid="ae-warnings"
                            style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', margin: '0.4rem 0' }}>
                            {warnings.map((w, i) => (
                              <span key={i} className="ae-warning-chip" data-testid="ae-warning-chip"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                                  background: '#fff7ed', color: '#9a3412', border: '1px solid #fed7aa',
                                  borderRadius: 999, padding: '0.2rem 0.6rem', fontSize: '0.8rem' }}>
                                <AlertTriangle size={12} aria-hidden="true" /> {w}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* ADSDEEP35 — avant/après côte à côte (EDIT_COPY) */}
                        {copyDiff && (
                          <div className="ae-edit-copy-diff" data-testid="ae-edit-copy-diff"
                            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem',
                              background: '#f8fafc', padding: '0.6rem', borderRadius: 6, margin: '0.5rem 0' }}>
                            <div data-testid="ae-edit-copy-before">
                              <strong style={{ fontSize: '0.8rem', color: '#64748b' }}>Actuel</strong>
                              <p style={{ margin: '0.2rem 0' }}>{copyDiff.before.body || '—'}</p>
                            </div>
                            <div data-testid="ae-edit-copy-after">
                              <strong style={{ fontSize: '0.8rem', color: '#64748b' }}>Proposé</strong>
                              <p style={{ margin: '0.2rem 0' }}>{copyDiff.after.body || '—'}</p>
                            </div>
                          </div>
                        )}

                        {/* Artefact réel — préview du créatif */}
                        {creative && (
                          <div className="ae-artifact-creative" data-testid="ae-artifact-creative"
                            style={{ marginTop: '0.5rem' }}>
                            {creative.url
                              ? <img src={creative.url} alt={creative.designation}
                                  style={{ maxWidth: 240, maxHeight: 160, borderRadius: 6, display: 'block' }} />
                              : <div style={{ padding: '0.75rem', background: '#f1f5f9',
                                  borderRadius: 6, color: '#475569' }}>
                                  {creative.designation}{creative.type ? ` (${creative.type})` : ''}
                                </div>}
                          </div>
                        )}

                        {/* Contrôles STRUCTURÉS — jamais du chat */}
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                          <button type="button" className="btn btn-success ae-approve"
                            data-testid={`ae-approve-${a.id}`} disabled={busy}
                            onClick={() => approve(a.id)}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                            <Check size={15} aria-hidden="true" /> Approuver
                          </button>
                          <button type="button" className="btn btn-danger-outline ae-reject"
                            data-testid={`ae-reject-${a.id}`} disabled={busy}
                            onClick={() => openReject(a.id)}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                            <X size={15} aria-hidden="true" /> Rejeter
                          </button>
                        </div>

                        {/* Motif de rejet STRUCTURÉ (select — jamais du texte libre) */}
                        {rejectingId === a.id && (
                          <div className="ae-reject-panel" data-testid={`ae-reject-panel-${a.id}`}
                            style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <span style={{ fontSize: '0.85rem', color: '#475569' }}>Motif</span>
                              <select className="form-input ae-reject-reason"
                                data-testid={`ae-reject-reason-${a.id}`}
                                value={rejectReason}
                                onChange={e => setRejectReason(e.target.value)}>
                                {REJECTION_REASONS.map(r => (
                                  <option key={r.value} value={r.value}>{r.label}</option>
                                ))}
                              </select>
                            </label>
                            <button type="button" className="btn btn-danger ae-reject-confirm"
                              data-testid={`ae-reject-confirm-${a.id}`} disabled={busy}
                              onClick={() => confirmReject(a.id)}>
                              Confirmer le rejet
                            </button>
                            <button type="button" className="btn btn-light"
                              onClick={() => setRejectingId(null)}>Annuler</button>
                          </div>
                        )}
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
    </div>
  )
}
