import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import SegmentBuilder from './SegmentBuilder'

/* ============================================================================
   NTMKT4 — Liste des segments marketing (XMKT6) + constructeur inline.
   ----------------------------------------------------------------------------
   Un segment sauvegardé (nom + `regles`) est immédiatement RÉUTILISABLE
   côté serveur — les endpoints `marketing/campagnes/`/`marketing/enquetes/`
   consomment un segment par son `id` (ex. NTMKT8 `inviter` avec
   `segment_id`) sans duplication d'écran ici.
   ========================================================================== */

export default function SegmentsList() {
  const [segments, setSegments] = useState([])
  const [loading, setLoading] = useState(true)
  const [showBuilder, setShowBuilder] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.segments.list()
      .then(r => setSegments(marketingApi.unwrapList(r)))
      .catch(() => setSegments([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const startCreate = () => { setEditing(null); setShowBuilder(true) }
  const startEdit = (s) => { setEditing(s); setShowBuilder(true) }
  const closeBuilder = () => { setShowBuilder(false); setEditing(null); load() }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Segments marketing</h2>
        {!showBuilder && (
          <button className="btn btn-primary" data-testid="segments-nouveau"
            onClick={startCreate}>Nouveau segment</button>
        )}
      </div>

      {showBuilder && (
        <div style={{ marginBottom: '1.25rem' }}>
          <SegmentBuilder initial={editing} onSaved={closeBuilder} onCancel={closeBuilder} />
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="segments-table">
            <thead>
              <tr><th>Nom</th><th>Règles</th><th /></tr>
            </thead>
            <tbody>
              {segments.map(s => (
                <tr key={s.id} data-testid="segment-row">
                  <td>{s.nom}</td>
                  <td>{Object.keys(s.regles || {}).length} critère(s)</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="segment-editer" onClick={() => startEdit(s)}>
                      Éditer
                    </button>
                  </td>
                </tr>
              ))}
              {segments.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun segment
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
