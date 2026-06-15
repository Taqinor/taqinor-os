/* Atelier Doublons (FEATURE 1) — scanne TOUS les leads de la société, les
   regroupe en clusters (téléphone / email / nom normalisé), et permet de
   choisir le survivant puis « Fusionner le groupe » SANS perte (le moteur
   serveur réutilise merge_leads : devis/activités/chantiers déplacés, absorbés
   archivés et réversibles). Modal autonome ouvert depuis le pipeline. */
import { useEffect, useState } from 'react'
import crmApi from '../../../api/crmApi'
import { STAGE_LABELS } from '../../../features/crm/stages'
import './doublonspanel.css'

function ClusterCard({ cluster, onMerged }) {
  const [survivor, setSurvivor] = useState(cluster.suggested_survivor_id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const others = cluster.members
    .filter(m => m.id !== survivor)
    .map(m => m.id)

  const doMerge = async () => {
    if (!others.length) return
    const survName = cluster.members.find(m => m.id === survivor)
    if (!window.confirm(
      `Fusionner ${others.length} doublon(s) dans « ${survName?.nom} `
      + `${survName?.prenom || ''} » ? Les autres fiches seront ARCHIVÉES `
      + `(jamais supprimées) et tout (devis, activités, historique) sera `
      + `rattaché au survivant.`)) return
    setBusy(true)
    setError(null)
    try {
      await crmApi.mergeLeads(survivor, others)
      setDone(true)
      onMerged?.()
    } catch {
      setError('La fusion a échoué — réessayez.')
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="dbl-cluster dbl-cluster-done">
        ✅ Groupe fusionné — {others.length} fiche(s) archivée(s).
      </div>
    )
  }

  return (
    <div className="dbl-cluster">
      <div className="dbl-cluster-grid">
        {cluster.members.map(m => (
          <label
            key={m.id}
            className={`dbl-member${m.id === survivor ? ' dbl-member-keep' : ''}`}
          >
            <div className="dbl-member-head">
              <input
                type="radio"
                name={`surv-${cluster.members[0].id}`}
                checked={m.id === survivor}
                onChange={() => setSurvivor(m.id)}
              />
              <strong>{m.nom} {m.prenom || ''}</strong>
              {m.id === survivor && <span className="dbl-keep-tag">à garder</span>}
              {m.is_archived && <span className="dbl-arch-tag">archivé</span>}
            </div>
            <div className="dbl-member-fields">
              {m.societe && <div>🏢 {m.societe}</div>}
              <div>📞 {m.telephone || '—'}</div>
              <div>✉️ {m.email || '—'}</div>
              <div>📍 {m.ville || '—'}</div>
              <div>📊 {STAGE_LABELS[m.stage] ?? m.stage}</div>
              <div>📄 {m.nb_devis} devis · {m.completeness} champs</div>
            </div>
          </label>
        ))}
      </div>
      {error && <div className="form-error-box">{error}</div>}
      <div className="dbl-cluster-actions">
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={doMerge}
          disabled={busy || !others.length}
        >
          {busy ? 'Fusion…' : `🔀 Fusionner le groupe (${cluster.members.length} → 1)`}
        </button>
      </div>
    </div>
  )
}

export default function DoublonsPanel({ onClose, onAnyMerge }) {
  const [clusters, setClusters] = useState(null)
  const [error, setError] = useState(null)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const reload = () => setReloadKey(k => k + 1)

  useEffect(() => {
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setClusters(null)
    setError(null)
    crmApi.getDoublons(includeArchived ? { archived: 1 } : {})
      .then(r => { if (!cancelled) setClusters(r.data) })
      .catch(() => { if (!cancelled) setError('Impossible de charger les doublons.') })
    return () => { cancelled = true }
  }, [includeArchived, reloadKey])

  return (
    <div className="dbl-overlay" onClick={onClose}>
      <div className="dbl-panel" onClick={e => e.stopPropagation()}>
        <div className="dbl-header">
          <h3>🔀 Doublons{clusters ? ` (${clusters.length} groupe${clusters.length > 1 ? 's' : ''})` : ''}</h3>
          <label className="dbl-arch-toggle">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={e => setIncludeArchived(e.target.checked)}
            />
            Inclure les archivés
          </label>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="dbl-body">
          {error && <div className="form-error-box">{error}</div>}
          {!clusters && !error && <p className="gen-hint">Analyse des leads…</p>}
          {clusters && clusters.length === 0 && (
            <p className="gen-hint">Aucun doublon détecté 🎉</p>
          )}
          {clusters && clusters.map((c, i) => (
            <ClusterCard
              key={c.members.map(m => m.id).join('-') + i}
              cluster={c}
              onMerged={() => { onAnyMerge?.(); reload() }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
