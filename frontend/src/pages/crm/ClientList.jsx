import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchClients, deleteClient } from '../../features/crm/store/crmSlice'
import ClientForm from './ClientForm'

export default function ClientList() {
  const dispatch = useDispatch()
  const { clients, loading, error } = useSelector(s => s.crm)
  const role = useSelector(s => s.auth.role)

  const [showForm, setShowForm]       = useState(false)
  const [editClient, setEditClient]   = useState(null)
  const [search, setSearch]           = useState('')
  const [deletingId, setDeletingId]   = useState(null)

  useEffect(() => { dispatch(fetchClients()) }, [dispatch])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return clients
    return clients.filter(c =>
      c.nom.toLowerCase().includes(q) ||
      (c.prenom ?? '').toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      (c.telephone ?? '').includes(q)
    )
  }, [clients, search])

  const openNew   = () => { setEditClient(null); setShowForm(true) }
  const openEdit  = c  => { setEditClient(c);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);  setEditClient(null) }

  const handleDelete = async (c) => {
    const fullName = [c.nom, c.prenom].filter(Boolean).join(' ')
    if (!window.confirm(`Supprimer le client « ${fullName} » ?\nSes devis seront conservés mais sans client lié.`)) return
    setDeletingId(c.id)
    try {
      await dispatch(deleteClient(c.id)).unwrap()
    } catch (err) {
      alert(err?.detail ?? JSON.stringify(err))
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) return <p className="page-loading">Chargement des clients...</p>
  if (error)   return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Clients
          {clients.length > 0 && (
            <span className="count-badge">{clients.length}</span>
          )}
        </h2>
        <div className="page-header-actions">
          <input
            className="search-input"
            type="search"
            placeholder="Rechercher nom, email, tél…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button className="btn btn-primary" onClick={openNew}>
            + Nouveau client
          </button>
        </div>
      </div>

      {showForm && (
        <ClientForm client={editClient} onClose={closeForm} />
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Client</th>
            <th>Email</th>
            <th>Téléphone</th>
            <th>Adresse</th>
            <th className="ta-right">Devis</th>
            <th>Depuis</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(c => (
            <tr key={c.id}>
              <td>
                <div className="client-name">
                  {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                </div>
              </td>
              <td>
                <a className="link-blue" href={`mailto:${c.email}`}>{c.email}</a>
              </td>
              <td>{c.telephone ?? '—'}</td>
              <td className="text-truncate" title={c.adresse ?? ''}>
                {c.adresse ? c.adresse.split('\n')[0] : '—'}
              </td>
              <td className="ta-right">
                <span className="count-pill">{c.devis_count ?? 0}</span>
              </td>
              <td>{new Date(c.date_creation).toLocaleDateString('fr-FR')}</td>
              <td>
                <div className="actions-cell">
                  <button className="btn btn-sm btn-outline" onClick={() => openEdit(c)}>
                    Éditer
                  </button>
                  {role === 'admin' && (
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => handleDelete(c)}
                      disabled={deletingId === c.id}
                    >
                      {deletingId === c.id ? '...' : 'Supprimer'}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {filtered.length === 0 && !loading && (
        <p className="empty-state">
          {search
            ? `Aucun résultat pour « ${search} »`
            : 'Aucun client. Créez votre premier client.'}
        </p>
      )}
    </div>
  )
}
