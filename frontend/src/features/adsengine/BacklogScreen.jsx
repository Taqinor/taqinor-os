import { useEffect, useState, useCallback } from 'react'
import { Layers, Check, X, Upload, Sparkles } from 'lucide-react'
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

   PACT111 — trois trous de câblage réparés :
   1. « Générer des variantes » (CreativeLibraryScreen) appelle en réalité
      ``creatifs/<id>/variantes/`` — un endpoint simple SANS ancrage aux
      faits. Le VRAI pipeline (``generation/variantes-ancrees/``, PUB16)
      n'était appelé nulle part, alors que son propre commentaire backend le
      documente comme « câblé depuis BacklogScreen / CreativeLibrary ». Ce
      fichier lui ajoute son déclencheur réel (le lot produit apparaît
      ensuite ci-dessous, une fois la tâche async terminée).
   2. L'écran n'avait aucun bouton pour REJETER un lot (seule l'approbation
      existait) — ajouté, même effet que ``recombine.reject_lot`` (le lot
      passe REJETEE, ses membres restent PENDING, jamais dans le backlog).
   3. Un item déposé SANS lot (``batch`` nul) est silencieusement ignoré par
      la vue groupée (``BacklogListView`` saute les items ``batch is None``).
      Une section séparée interroge la collection BRUTE (``backlog-creatif/``)
      pour les montrer — SANS toucher la vue groupée existante.
   ========================================================================== */

export default function BacklogScreen() {
  const [campagnes, setCampagnes] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyLot, setBusyLot] = useState(null)
  const [msg, setMsg] = useState('')

  // PACT111 — génération ancrée aux faits (le pipeline RÉEL, PUB16).
  const [seedBrief, setSeedBrief] = useState('')
  const [genBusy, setGenBusy] = useState(false)
  const [genMsg, setGenMsg] = useState('')

  // PACT111 — items de backlog SANS lot (collection brute, jamais la vue
  // groupée qui les ignore).
  const [itemsSansLot, setItemsSansLot] = useState([])
  const [itemsSansLotLoading, setItemsSansLotLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.backlog.list()
      .then(r => setCampagnes(normalizeBacklog(r.data)))
      .catch(() => setCampagnes([]))
      .finally(() => setLoading(false))
  }, [])

  const loadItemsSansLot = useCallback(() => {
    setItemsSansLotLoading(true)
    adsengineApi.backlog.rawItems()
      .then(r => {
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        setItemsSansLot(rows.filter(it => it && (it.batch === null || it.batch === undefined)))
      })
      .catch(() => setItemsSansLot([]))
      .finally(() => setItemsSansLotLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { loadItemsSansLot() }, [loadItemsSansLot])

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

  // PACT111 — rejet par LOT : le lot passe « rejeté », ses membres restent
  // PENDING et n'entrent jamais au backlog (même effet que l'approbation,
  // en miroir — optimiste, l'API confirme).
  const rejectLot = async (campId, lotId) => {
    setBusyLot(lotId); setMsg('')
    try {
      await adsengineApi.backlog.rejectLot(lotId)
      setCampagnes(list => list.map(c => c.id !== campId ? c : {
        ...c,
        lots: c.lots.map(l => l.id === lotId
          ? { ...l, statut: 'rejetee', statut_display: 'Rejeté' } : l),
      }))
      setMsg('Lot rejeté.')
    } catch {
      setMsg('Rejet du lot impossible.')
    } finally {
      setBusyLot(null)
    }
  }

  // PACT111 — déclenche le pipeline RÉEL de génération ancrée aux faits.
  // Key-gated côté serveur : ``enabled:false`` reste un message clair, jamais
  // une erreur brute ni un crash.
  const generateGrounded = async (e) => {
    e.preventDefault()
    if (!seedBrief.trim()) return
    setGenBusy(true); setGenMsg('')
    try {
      const r = await adsengineApi.backlog.generateGroundedVariants({ seed_brief: seedBrief })
      setGenMsg(r.data?.detail || (r.data?.enabled === false
        ? 'Génération désactivée.' : 'Génération lancée.'))
      if (r.data?.enabled !== false) setSeedBrief('')
    } catch {
      setGenMsg('Génération impossible.')
    } finally {
      setGenBusy(false)
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

      {/* PACT111 — déclencheur du VRAI pipeline de génération ancrée aux faits
          (generation/variantes-ancrees/, PUB16) — jamais l'endpoint simple
          sans ancrage. Le lot produit apparaîtra ci-dessous une fois prêt. */}
      <section className="card ae-backlog-generate" data-testid="ae-backlog-generate"
        style={{ padding: '1rem', marginBottom: '1.25rem' }}>
        <h3 style={{ margin: '0 0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Sparkles size={17} aria-hidden="true" /> Générer des variantes ancrées aux faits
        </h3>
        <form onSubmit={generateGrounded} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <textarea className="form-input ae-backlog-seed-brief" data-testid="ae-backlog-seed-brief"
            placeholder="Brief de génération (chaque chiffre produit citera une donnée publiée)"
            value={seedBrief} onChange={e => setSeedBrief(e.target.value)}
            style={{ flex: '1 1 320px', minHeight: 60 }} />
          <button type="submit" className="btn btn-primary" data-testid="ae-backlog-generate-submit"
            disabled={genBusy || !seedBrief.trim()}
            style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <Sparkles size={14} aria-hidden="true" /> Générer
          </button>
        </form>
        {genMsg && <p data-testid="ae-backlog-generate-msg" style={{ color: '#475569', margin: '0.5rem 0 0' }}>
          {genMsg}</p>}
      </section>

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
                            const rejected = String(l.statut).startsWith('rejet')
                            const decided = approved || rejected
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
                                  style={{ background: approved ? '#dcfce7' : rejected ? '#fee2e2' : '#fef9c3',
                                    color: approved ? '#166534' : rejected ? '#991b1b' : '#854d0e' }}>
                                  {l.statut_display}
                                </span>
                                {!decided && (
                                  <>
                                    <button type="button" className="btn btn-success"
                                      data-testid={`ae-backlog-approve-lot-${l.id}`}
                                      disabled={busyLot === l.id}
                                      onClick={() => approveLot(c.id, l.id)}
                                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                      <Check size={14} aria-hidden="true" /> Approuver le lot
                                    </button>
                                    {/* PACT111 — bouton rejet manquant (seule l'approbation existait). */}
                                    <button type="button" className="btn btn-danger-outline"
                                      data-testid={`ae-backlog-reject-lot-${l.id}`}
                                      disabled={busyLot === l.id}
                                      onClick={() => rejectLot(c.id, l.id)}
                                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                      <X size={14} aria-hidden="true" /> Rejeter le lot
                                    </button>
                                  </>
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

      {/* PACT111 — items SANS lot : la vue groupée ci-dessus les ignore
          silencieusement (BacklogListView saute tout item dont batch est nul).
          Section séparée, collection brute — la vue groupée n'est PAS touchée. */}
      <section className="card ae-backlog-sans-lot" data-testid="ae-backlog-sans-lot"
        style={{ padding: '1rem', marginTop: '1.25rem' }}>
        <h3 style={{ margin: '0 0 0.6rem' }}>Items sans lot</h3>
        {itemsSansLotLoading
          ? <p className="page-loading">Chargement…</p>
          : itemsSansLot.length === 0
            ? <p data-testid="ae-backlog-sans-lot-empty" style={{ color: '#64748b', margin: 0 }}>
                Aucun item sans lot.</p>
            : (
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.4rem' }}>
                {itemsSansLot.map(it => (
                  <li key={it.id} data-testid="ae-backlog-sans-lot-item"
                    style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center',
                      border: '1px solid #e2e8f0', borderRadius: 6, padding: '0.5rem 0.75rem',
                      fontSize: '0.85rem', color: '#334155' }}>
                    <strong>Asset #{it.asset}</strong>
                    <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>
                      {it.status}
                    </span>
                    <span style={{ color: '#64748b' }}>{it.source}</span>
                    {it.target_campaign != null && (
                      <span style={{ color: '#64748b' }}>Campagne #{it.target_campaign}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
      </section>
    </div>
  )
}
