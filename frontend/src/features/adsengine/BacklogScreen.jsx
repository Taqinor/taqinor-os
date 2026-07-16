import { useEffect, useState, useCallback } from 'react'
import { Layers, Check, Upload } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeBacklog, runwayTone, clampRatio, formatPercent, formatNumber,
} from './adsengine'

/* ============================================================================
   ENG41 — Gestionnaire de backlog créatif (CreativeGenerationBatch par campagne).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md, domaine 4 — production créative pilotée) :
   - une FILE par campagne, avec une barre de RUNWAY (jours de créatifs frais qui
     restent avant épuisement) et une jauge de DIVERSITÉ des hooks ;
   - les recombinaisons arrivent par LOTS (CreativeGenerationBatch) approuvés par
     LOT (jamais pièce par pièce) — l'humain garde la main sur ce qui part ;
   - dépôt d'assets bruts dans le backlog d'une campagne.
   Tous les nombres viennent de l'API ENG27 (mockée en test).
   ========================================================================== */

export default function BacklogScreen() {
  const [campagnes, setCampagnes] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyLot, setBusyLot] = useState(null)
  const [msg, setMsg] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.backlog.list()
      .then(r => setCampagnes(normalizeBacklog(r.data)))
      .catch(() => setCampagnes([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // Approbation par LOT (bout-en-bout) : le lot passe « approuvé » et quitte la
  // file d'attente (optimiste — l'API confirme).
  const approveLot = async (campId, lotId) => {
    setBusyLot(lotId); setMsg('')
    try {
      await adsengineApi.backlog.approveLot(lotId)
      setCampagnes(list => list.map(c => c.id !== campId ? c : {
        ...c,
        lots: c.lots.map(l => l.id === lotId
          ? { ...l, statut: 'approuve', statut_display: 'Approuvé' } : l),
      }))
      setMsg('Lot approuvé.')
    } catch {
      setMsg("Approbation du lot impossible.")
    } finally {
      setBusyLot(null)
    }
  }

  const dropAsset = async (campId, file) => {
    if (!file) return
    setMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      await adsengineApi.backlog.dropAsset(campId, fd)
      setMsg('Asset déposé dans le backlog.')
      load()
    } catch {
      setMsg("Dépôt de l'asset impossible.")
    }
  }

  return (
    <div className="page ae-backlog">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Layers size={20} aria-hidden="true" /> Backlog créatif
        </h2>
      </div>

      {msg && <p data-testid="ae-backlog-msg" style={{ color: '#475569' }}>{msg}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : campagnes.length === 0
          ? <p data-testid="ae-backlog-empty" style={{ color: '#64748b' }}>
              Aucune campagne dans le backlog.</p>
          : (
            <div style={{ display: 'grid', gap: '1.25rem' }}>
              {campagnes.map(c => {
                const rw = runwayTone(c.runway_jours, c.runway_cible)
                const divRatio = clampRatio(c.diversite_hooks)
                return (
                  <section key={c.id} className="card ae-backlog-campaign" data-testid="ae-backlog-campaign"
                    style={{ padding: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.75rem' }}>{c.campagne}</h3>

                    {/* Runway + diversité */}
                    <div style={{ display: 'grid', gap: '0.75rem',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginBottom: '0.9rem' }}>
                      <div data-testid="ae-backlog-runway">
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                          <span style={{ color: '#475569' }}>Runway créatif</span>
                          <strong data-testid={`ae-backlog-runway-val-${c.id}`}>
                            {c.runway_jours != null ? `${formatNumber(c.runway_jours)} j` : '—'}
                            {c.runway_cible != null ? ` sur ${formatNumber(c.runway_cible)} j` : ''}
                          </strong>
                        </div>
                        <div aria-hidden="true" style={{ height: 8, background: '#f1f5f9',
                          borderRadius: 999, marginTop: '0.3rem', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${rw.ratio * 100}%`, background: rw.color }} />
                        </div>
                      </div>
                      <div data-testid="ae-backlog-diversity">
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                          <span style={{ color: '#475569' }}>Diversité des hooks</span>
                          <strong data-testid={`ae-backlog-diversity-val-${c.id}`}>
                            {formatPercent(c.diversite_hooks)}
                          </strong>
                        </div>
                        <div aria-hidden="true" style={{ height: 8, background: '#f1f5f9',
                          borderRadius: 999, marginTop: '0.3rem', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${divRatio * 100}%`,
                            background: divRatio < 0.4 ? '#d97706' : '#16a34a' }} />
                        </div>
                      </div>
                    </div>

                    {/* Lots (recombinaisons) — approbation par LOT */}
                    {c.lots.length === 0
                      ? <p style={{ color: '#64748b', margin: 0 }}>Aucun lot en attente.</p>
                      : (
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
                          {c.lots.map(l => {
                            const approved = String(l.statut).startsWith('approuv')
                            return (
                              <li key={l.id} className="ae-backlog-lot" data-testid="ae-backlog-lot"
                                style={{ display: 'flex', alignItems: 'center', gap: '0.6rem',
                                  border: '1px solid #e2e8f0', borderRadius: 6, padding: '0.6rem 0.75rem' }}>
                                <div style={{ flex: 1 }}>
                                  <strong>{l.nom}</strong>
                                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                                    {formatNumber(l.assets.length)} asset(s)
                                    {l.nb_hooks != null ? ` · ${formatNumber(l.nb_hooks)} hook(s)` : ''}
                                  </div>
                                </div>
                                <span className="badge" data-testid={`ae-backlog-lot-status-${l.id}`}
                                  style={{ background: approved ? '#dcfce7' : '#fef9c3',
                                    color: approved ? '#166534' : '#854d0e' }}>
                                  {l.statut_display}
                                </span>
                                {!approved && (
                                  <button type="button" className="btn btn-success"
                                    data-testid={`ae-backlog-approve-lot-${l.id}`}
                                    disabled={busyLot === l.id}
                                    onClick={() => approveLot(c.id, l.id)}
                                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                    <Check size={14} aria-hidden="true" /> Approuver le lot
                                  </button>
                                )}
                              </li>
                            )
                          })}
                        </ul>
                      )}

                    {/* Dépôt d'asset */}
                    <label className="ae-backlog-drop" style={{ display: 'inline-flex', alignItems: 'center',
                      gap: '0.4rem', marginTop: '0.75rem', cursor: 'pointer', color: '#2563eb' }}>
                      <Upload size={15} aria-hidden="true" />
                      <span>Déposer un asset</span>
                      <input type="file" data-testid={`ae-backlog-drop-${c.id}`}
                        aria-label={`Déposer un asset dans ${c.campagne}`}
                        onChange={e => dropAsset(c.id, e.target.files?.[0] || null)}
                        style={{ display: 'none' }} />
                    </label>
                  </section>
                )
              })}
            </div>
          )}
    </div>
  )
}
