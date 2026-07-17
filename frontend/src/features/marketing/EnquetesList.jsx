import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import EnqueteBuilder, { emptyForm, formFromEnquete } from './EnqueteBuilder'

/* ============================================================================
   NTMKT8 — Liste des enquêtes (XMKT27) + constructeur inline.
   ========================================================================== */

export default function EnquetesList() {
  const navigate = useNavigate()
  const [enquetes, setEnquetes] = useState([])
  const [loading, setLoading] = useState(true)
  const [showBuilder, setShowBuilder] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.enquetes.list()
      .then(r => setEnquetes(marketingApi.unwrapList(r)))
      .catch(() => setEnquetes([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const startCreate = () => { setEditing(null); setShowBuilder(true) }
  const startEdit = (e, ev) => { ev.stopPropagation(); setEditing(e); setShowBuilder(true) }
  const closeBuilder = () => { setShowBuilder(false); setEditing(null); load() }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Enquêtes</h2>
        {!showBuilder && (
          <button className="btn btn-primary" data-testid="enquetes-nouvelle"
            onClick={startCreate}>Nouvelle enquête</button>
        )}
      </div>

      {showBuilder && (
        <div style={{ marginBottom: '1.25rem' }}>
          <EnqueteBuilder
            initial={editing ? formFromEnquete(editing) : emptyForm()}
            onSaved={closeBuilder} onCancel={closeBuilder} />
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="enquetes-table">
            <thead><tr><th>Titre</th><th>Questions</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {enquetes.map(e => (
                <tr key={e.id} data-testid="enquete-row" style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/marketing/enquetes/${e.id}`)}>
                  <td>{e.titre}</td>
                  <td>{(e.questions || []).length}</td>
                  <td>{e.actif ? 'Active' : 'Inactive'}</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="enquete-editer" onClick={(ev) => startEdit(e, ev)}>
                      Éditer
                    </button>
                  </td>
                </tr>
              ))}
              {enquetes.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune enquête
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
