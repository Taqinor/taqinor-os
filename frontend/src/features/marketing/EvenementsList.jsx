import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import EvenementForm, { emptyForm, formFromEvenement } from './EvenementForm'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   NTMKT7 — Liste des événements marketing (XMKT28) + éditeur inline.
   ========================================================================== */

export default function EvenementsList() {
  const navigate = useNavigate()
  const [evenements, setEvenements] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.evenements.list()
      .then(r => setEvenements(marketingApi.unwrapList(r)))
      .catch(() => setEvenements([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const startCreate = () => { setEditing(null); setShowForm(true) }
  const startEdit = (ev, e) => { e.stopPropagation(); setEditing(ev); setShowForm(true) }
  const closeForm = () => { setShowForm(false); setEditing(null); setErr('') }

  const save = async (payload) => {
    if (editing) await marketingApi.evenements.update(editing.id, payload)
    else await marketingApi.evenements.create(payload)
    closeForm()
    load()
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Événements marketing</h2>
        {!showForm && (
          <button className="btn btn-primary" data-testid="evenements-nouveau"
            onClick={startCreate}>Nouvel événement</button>
        )}
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {showForm && (
        <div style={{ marginBottom: '1.25rem' }}>
          <EvenementForm
            initial={editing ? formFromEvenement(editing) : emptyForm()}
            editing={!!editing} onSave={save} onCancel={closeForm} />
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="evenements-table">
            <thead>
              <tr><th>Nom</th><th>Type</th><th>Début</th><th>Inscrits</th><th /></tr>
            </thead>
            <tbody>
              {evenements.map(ev => (
                <tr key={ev.id} data-testid="evenement-row" style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/marketing/evenements/${ev.id}`)}>
                  <td>{ev.nom}</td>
                  <td>{ev.type_display || ev.type_evenement}</td>
                  <td>{ev.date_debut ? formatDateTime(ev.date_debut) : '—'}</td>
                  <td>{ev.nb_inscrits ?? 0}</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="evenement-editer" onClick={(e) => startEdit(ev, e)}>
                      Éditer
                    </button>
                  </td>
                </tr>
              ))}
              {evenements.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun événement
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
