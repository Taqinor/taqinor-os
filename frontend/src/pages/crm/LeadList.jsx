import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchLeads } from '../../features/crm/store/crmSlice'

// French labels for the canonical pipeline stages (keys come from the backend).
const STAGE_LABELS = {
  NEW: 'Nouveau',
  CONTACTED: 'Contacté',
  QUOTE_SENT: 'Devis envoyé',
  FOLLOW_UP: 'Relance',
  SIGNED: 'Signé',
  COLD: 'Froid',
}

export default function LeadList() {
  const dispatch = useDispatch()
  const { leads, leadsLoading, error } = useSelector(s => s.crm)

  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => { dispatch(fetchLeads()) }, [dispatch])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return leads.filter(l => {
      if (stage && l.stage !== stage) return false
      if (source && l.source !== source) return false
      if (!q) return true
      return (
        (l.nom ?? '').toLowerCase().includes(q) ||
        (l.prenom ?? '').toLowerCase().includes(q) ||
        (l.societe ?? '').toLowerCase().includes(q) ||
        (l.email ?? '').toLowerCase().includes(q) ||
        (l.telephone ?? '').includes(q) ||
        (l.ville ?? '').toLowerCase().includes(q)
      )
    })
  }, [leads, search, stage, source])

  if (leadsLoading) return <p className="page-loading">Chargement des leads...</p>
  if (error) return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Leads
          {leads.length > 0 && <span className="count-badge">{leads.length}</span>}
        </h2>
        <div className="page-header-actions">
          <input
            className="search-input"
            type="search"
            placeholder="Rechercher nom, société, ville…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select className="search-input" value={stage} onChange={e => setStage(e.target.value)}>
            <option value="">Tous les stades</option>
            {Object.entries(STAGE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select className="search-input" value={source} onChange={e => setSource(e.target.value)}>
            <option value="">Toutes origines</option>
            <option value="os_native">Créé dans TAQINOR</option>
            <option value="odoo_import_test">Import test Odoo</option>
          </select>
        </div>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Lead</th>
            <th>Société</th>
            <th>Email</th>
            <th>Téléphone</th>
            <th>Ville</th>
            <th>Stade</th>
            <th>Origine</th>
            <th>Depuis</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(l => (
            <tr key={l.id}>
              <td><div className="client-name">{l.nom}{l.prenom ? ` ${l.prenom}` : ''}</div></td>
              <td>{l.societe || '—'}</td>
              <td>{l.email ? <a className="link-blue" href={`mailto:${l.email}`}>{l.email}</a> : '—'}</td>
              <td>{l.telephone || '—'}</td>
              <td>{l.ville || '—'}</td>
              <td><span className="count-pill">{l.stage_label || STAGE_LABELS[l.stage] || l.stage}</span></td>
              <td>{l.source === 'odoo_import_test' ? 'Import test Odoo' : 'TAQINOR'}</td>
              <td>{new Date(l.date_creation).toLocaleDateString('fr-FR')}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {filtered.length === 0 && !leadsLoading && (
        <p className="empty-state">
          {search || stage || source
            ? 'Aucun lead ne correspond aux filtres.'
            : 'Aucun lead pour le moment.'}
        </p>
      )}
    </div>
  )
}
