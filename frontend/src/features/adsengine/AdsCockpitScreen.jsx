import { useEffect, useState, useCallback, useMemo } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown, Video, ImageOff } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMAD, formatNumber, formatRatio, sortCockpitRows } from './adsengine'
import DataWindowNotice from './DataWindowNotice'
import AdCreativePanel from './AdCreativePanel'
// PUB3 — panneau démographie/placement/région/heure, construit+testé mais
// jamais monté nulle part avant cette tâche (breakdowns/ est synchronisé
// chaque semaine côté back mais restait invisible).
import BreakdownsPanel from './BreakdownsPanel'

/* ============================================================================
   ADSDEEP22 — Cockpit par ad (écran-console QUOTIDIEN du fondateur).
   ----------------------------------------------------------------------------
   Une ligne PAR AD : miniature créatif, dépense, conversations, leads réels,
   CPL, signatures, coût/signature, fréquence, badge de fatigue (ADSDEEP45) et
   statut + apprentissage (badge hérité de l'ad set parent, ADSDEEP32). Table
   TRIABLE sur chaque colonne chiffrée (`sortCockpitRows`, adsengine.js — pur,
   valeurs manquantes toujours reléguées en fin de tri). Un clic sur une ligne
   DESCEND jusqu'au détail créatif de l'ad (réutilise `AdCreativePanel`,
   ADSDEEP14 — aucune réécriture).
   Toutes les valeurs viennent de ``metrics.adsCockpit`` — rien n'est inventé.
   ========================================================================== */

const COLUMNS = [
  { key: 'nom', label: 'Ad', sortable: true },
  { key: 'statut_display', label: 'Statut / apprentissage', sortable: true },
  { key: 'depense_mad', label: 'Dépense', sortable: true },
  { key: 'conversations', label: 'Conversations', sortable: true },
  { key: 'nb_leads', label: 'Leads', sortable: true },
  { key: 'cpl_mad', label: 'CPL', sortable: true },
  { key: 'signatures', label: 'Signatures', sortable: true },
  { key: 'cost_per_signature_mad', label: 'Coût / signature', sortable: true },
  { key: 'frequency', label: 'Fréquence', sortable: true },
]

// Miniature créatif RÉSOLUE à l'affichage (URL fraîche, jamais persistée —
// ADSDEEP12). Une ad vidéo montre une icône (pas de lecture inline dans une
// table) ; une ad image résout sa vraie miniature.
function AdThumbnail({ mediaRef, kind }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise avant résolution (changement de mediaRef/kind)
    setUrl('')
    if (mediaRef && kind === 'image') {
      adsengineApi.media.resolve(mediaRef, 'image')
        .then(r => { if (alive) setUrl(r.data?.url || '') })
        .catch(() => { if (alive) setUrl('') })
    }
    return () => { alive = false }
  }, [mediaRef, kind])

  if (!mediaRef) {
    return (
      <span data-testid="ae-cockpit-thumb-empty" aria-label="Aucun créatif miroité"
        style={{ display: 'inline-flex', width: 36, height: 36, alignItems: 'center',
          justifyContent: 'center', background: '#f1f5f9', borderRadius: 6, color: '#94a3b8' }}>
        <ImageOff size={16} aria-hidden="true" />
      </span>
    )
  }
  if (kind === 'video') {
    return (
      <span data-testid="ae-cockpit-thumb-video" aria-label="Créatif vidéo"
        style={{ display: 'inline-flex', width: 36, height: 36, alignItems: 'center',
          justifyContent: 'center', background: '#e0e7ff', borderRadius: 6, color: '#4338ca' }}>
        <Video size={16} aria-hidden="true" />
      </span>
    )
  }
  return url
    ? <img data-testid="ae-cockpit-thumb-image" src={url} alt=""
        style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 6 }} />
    : <span data-testid="ae-cockpit-thumb-loading" style={{ display: 'inline-block', width: 36, height: 36,
        background: '#f1f5f9', borderRadius: 6 }} />
}

function fatigueTone(fatigue) {
  if (!fatigue) return { bg: '#f1f5f9', color: '#64748b', label: 'Inconnu' }
  if (fatigue.insufficient_data) return { bg: '#f1f5f9', color: '#64748b', label: 'Historique insuffisant' }
  if (!fatigue.fired) return { bg: '#dcfce7', color: '#166534', label: 'Pas de fatigue' }
  return fatigue.severity === 'critique'
    ? { bg: '#fee2e2', color: '#991b1b', label: 'Fatigue confirmée' }
    : { bg: '#ffedd5', color: '#9a3412', label: 'Fatigue possible' }
}

export default function AdsCockpitScreen() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [sort, setSort] = useState({ key: 'depense_mad', dir: 'desc' })
  const [openAdId, setOpenAdId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.metrics.adsCockpit()
      .then(r => setRows(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const sortedRows = useMemo(
    () => sortCockpitRows(rows, sort.key, sort.dir), [rows, sort])

  const toggleSort = (key) => {
    setSort(prev => prev.key === key
      ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: 'asc' })
  }

  const sortIcon = (key) => {
    if (sort.key !== key) return <ArrowUpDown size={13} aria-hidden="true" />
    return sort.dir === 'asc'
      ? <ArrowUp size={13} aria-hidden="true" />
      : <ArrowDown size={13} aria-hidden="true" />
  }

  const openRow = openAdId != null ? sortedRows.find(r => r.id === openAdId) : null

  return (
    <div className="page ae-ads-cockpit">
      <div className="page-header">
        <h2>Cockpit par ad</h2>
      </div>

      {/* ADSDEEP66 — fenêtres de données visibles à l'écran : leads (90 j,
          MetaLeadMirror ADSDEEP19) + insights (37 mois, dépense/fréquence). */}
      <DataWindowNotice kind="leads" />
      <DataWindowNotice kind="insights" />

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="ae-cockpit-table">
            <thead>
              <tr>
                <th aria-label="Miniature créatif" />
                {COLUMNS.map(col => (
                  <th key={col.key} aria-sort={sort.key === col.key
                    ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    <button type="button" className="btn-link" data-testid={`ae-cockpit-sort-${col.key}`}
                      onClick={() => toggleSort(col.key)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                        background: 'none', border: 0, padding: 0, font: 'inherit', cursor: 'pointer' }}>
                      {col.label} {sortIcon(col.key)}
                    </button>
                  </th>
                ))}
                <th>Fatigue</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sortedRows.map(row => {
                const tone = fatigueTone(row.fatigue)
                return (
                  <tr key={row.id} data-testid="ae-cockpit-row">
                    <td><AdThumbnail mediaRef={row.thumbnail_ref} kind={row.thumbnail_kind} /></td>
                    <td>{row.nom || '—'}</td>
                    <td>
                      {row.statut_display || '—'}{' '}
                      <span className="badge" data-testid="ae-cockpit-learning-badge">
                        {row.learning_badge?.label || 'Inconnu'}
                      </span>
                    </td>
                    <td>{formatMAD(row.depense_mad)}</td>
                    <td>{formatNumber(row.conversations)}</td>
                    <td>{formatNumber(row.nb_leads)}</td>
                    <td>{row.cpl_mad == null ? '—' : formatMAD(row.cpl_mad)}</td>
                    <td>{formatNumber(row.signatures)}</td>
                    <td>{row.cost_per_signature_mad == null ? '—' : formatMAD(row.cost_per_signature_mad)}</td>
                    <td>{row.frequency == null ? '—' : formatRatio(row.frequency)}</td>
                    <td>
                      <span className="badge" data-testid="ae-cockpit-fatigue-badge"
                        style={{ background: tone.bg, color: tone.color }}>
                        {tone.label}
                      </span>
                    </td>
                    <td>
                      <button type="button" className="btn btn-light" data-testid="ae-cockpit-open"
                        onClick={() => setOpenAdId(id => id === row.id ? null : row.id)}>
                        {openAdId === row.id ? 'Fermer' : 'Détail'}
                      </button>
                    </td>
                  </tr>
                )
              })}
              {sortedRows.length === 0 && (
                <tr><td colSpan={COLUMNS.length + 3} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune ad synchronisée</td></tr>
              )}
            </tbody>
          </table>
        )}

      {openRow && (
        <section className="card ae-cockpit-detail" data-testid="ae-cockpit-detail"
          style={{ padding: '1rem', marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>{openRow.nom || openRow.meta_id}</h3>
            <button type="button" className="btn btn-light" data-testid="ae-cockpit-detail-close"
              onClick={() => setOpenAdId(null)}>Fermer</button>
          </div>
          <AdCreativePanel
            adMetaId={openRow.meta_id}
            creative={{
              video_id: openRow.thumbnail_kind === 'video' ? openRow.thumbnail_ref : '',
              image_hash: openRow.thumbnail_kind === 'image' ? openRow.thumbnail_ref : '',
            }}
          />

          {/* PUB3 — drill démographie/placement/région/heure de CETTE ad
              (id du miroir, pas le meta_id — même clé que breakdowns/). */}
          <div style={{ marginTop: '1rem' }}>
            <BreakdownsPanel objectType="ad" objectId={openRow.id} />
          </div>
        </section>
      )}
    </div>
  )
}
