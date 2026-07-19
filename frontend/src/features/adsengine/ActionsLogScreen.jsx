import { useEffect, useState, useMemo, useCallback } from 'react'
import adsengineApi from './adsengineApi'
import {
  actionTypeLabel, actionResultLabel, actionResultKey, actionMode, filterActionLog,
} from './adsengine'

/* ============================================================================
   ENG28 — Journal d'actions (timeline EngineAction) — le backstop de confiance.
   ----------------------------------------------------------------------------
   Chaque entrée montre : le type d'action, la raison (reason_fr), le RÉSULTAT
   (approuvée / rejetée / appliquée / en attente / échec), QUI a approuvé, et le
   mode AUTO vs MANUEL. Timeline filtrable par statut et par mode (filtre pur
   `filterActionLog`, appliqué localement). Les dates sont affichées telles que
   fournies par l'API (aucune logique « aujourd'hui » → pas de flakiness).
   ========================================================================== */

const STATUT_FILTERS = [
  { value: '', label: 'Tous les statuts' },
  { value: 'en_attente', label: 'En attente' },
  { value: 'approuve', label: 'Approuvées' },
  { value: 'rejete', label: 'Rejetées' },
  { value: 'applique', label: 'Appliquées' },
  { value: 'echec', label: 'Échecs' },
]
const MODE_FILTERS = [
  { value: '', label: 'Auto + Manuel' },
  { value: 'auto', label: 'Auto' },
  { value: 'manuel', label: 'Manuel' },
]

export default function ActionsLogScreen() {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [statut, setStatut] = useState('')
  const [mode, setMode] = useState('')
  // PUB45 — état d'annulation PAR action ({ id: { ok, message } }) + id en cours.
  const [cancelState, setCancelState] = useState({})
  const [cancelBusy, setCancelBusy] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.actions.log()
      .then(r => setActions(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setActions([]))
      .finally(() => setLoading(false))
  }, [])

  // PUB45 — « Annuler » : PROPOSE l'inverse (jamais un write direct). Succès →
  // message renvoyant vers Approbations ; 422 → explication (kind non inversible).
  const handleCancel = useCallback((id) => {
    setCancelBusy(id)
    setCancelState(s => ({ ...s, [id]: null }))
    adsengineApi.actions.cancel(id)
      .then(() => setCancelState(s => ({
        ...s,
        [id]: { ok: true, message: 'Proposition inverse créée — à approuver dans « Approbations ».' },
      })))
      .catch(err => setCancelState(s => ({
        ...s,
        [id]: { ok: false, message: err?.response?.data?.detail || 'Annulation impossible.' },
      })))
      .finally(() => setCancelBusy(null))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const visible = useMemo(
    () => filterActionLog(actions, { statut, mode }), [actions, statut, mode])

  return (
    <div className="page ae-actions-log">
      <div className="page-header">
        <h2>Journal d&apos;actions</h2>
      </div>

      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <select className="form-input" data-testid="ae-log-filter-statut"
          value={statut} onChange={e => setStatut(e.target.value)} style={{ flex: '0 1 200px' }}>
          {STATUT_FILTERS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>
        <select className="form-input" data-testid="ae-log-filter-mode"
          value={mode} onChange={e => setMode(e.target.value)} style={{ flex: '0 1 180px' }}>
          {MODE_FILTERS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>
      </div>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : visible.length === 0
          ? <p data-testid="ae-log-empty" style={{ color: '#64748b' }}>Aucune action à afficher.</p>
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
              {visible.map(a => {
                const isAuto = actionMode(a) === 'auto'
                const resKey = actionResultKey(a)
                const resTone = resKey === 'rejete' || resKey === 'echec' ? '#991b1b'
                  : resKey === 'applique' || resKey === 'approuve' ? '#166534' : '#854d0e'
                return (
                  <li key={a.id} className="card ae-log-row" data-testid="ae-log-row"
                    style={{ padding: '0.75rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <strong>{actionTypeLabel(a.type)}</strong>
                      <span className="badge" data-testid="ae-log-result"
                        style={{ background: '#f1f5f9', color: resTone }}>
                        {actionResultLabel(a)}
                      </span>
                      <span className="badge" data-testid="ae-log-mode"
                        style={{ background: isAuto ? '#e0f2fe' : '#ede9fe',
                          color: isAuto ? '#075985' : '#5b21b6' }}>
                        {isAuto ? 'Auto' : 'Manuel'}
                      </span>
                      <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>
                        {a.created_at_display || a.created_at || ''}
                      </span>
                    </div>
                    {a.reason_fr && (
                      <p style={{ margin: '0.35rem 0 0', color: '#334155' }}>{a.reason_fr}</p>
                    )}
                    <p style={{ margin: '0.25rem 0 0', color: '#64748b', fontSize: '0.85rem' }}>
                      {a.approuve_par
                        ? `Approuvée par ${a.approuve_par}`
                        : isAuto ? 'Appliquée automatiquement (dans le band)' : 'En attente d’approbation'}
                      {/* PUB7 — le serializer expose `error` (texte de l'échec OU
                          du motif de rejet) et `result` (JSON, appliquée avec
                          succès) — PAS `result_detail` (n'existe pas côté API,
                          donc jamais rempli : les raisons d'échec ne
                          s'affichaient JAMAIS). */}
                      {a.error ? ` — ${a.error}` : ''}
                    </p>
                    {/* PUB45 — annuler une action APPLIQUÉE = proposer l'inverse. */}
                    {resKey === 'applique' && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <button type="button" className="btn btn-light" data-testid="ae-log-cancel"
                          onClick={() => handleCancel(a.id)} disabled={cancelBusy === a.id}>
                          Annuler (proposer l&apos;inverse)
                        </button>
                        {cancelState[a.id] && (
                          <p data-testid="ae-log-cancel-msg"
                            style={{ margin: '0.35rem 0 0', fontSize: '0.85rem',
                              color: cancelState[a.id].ok ? '#15803d' : '#b45309' }}>
                            {cancelState[a.id].message}
                          </p>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
    </div>
  )
}
