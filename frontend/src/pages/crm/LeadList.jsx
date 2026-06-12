import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { fetchLeads } from '../../features/crm/store/crmSlice'
import LeadForm from './LeadForm'

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
  const navigate = useNavigate()
  const { leads, leadsLoading, error } = useSelector(s => s.crm)

  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('')
  const [source, setSource] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editLead, setEditLead] = useState(null)
  const [autoLead, setAutoLead] = useState(null)   // lead ciblé par « Devis auto »
  const [autoDiscount, setAutoDiscount] = useState('0')

  useEffect(() => { dispatch(fetchLeads()) }, [dispatch])

  const openNew = () => { setEditLead(null); setShowForm(true) }
  const openEdit = (l) => { setEditLead(l); setShowForm(true) }
  const closeForm = () => { setShowForm(false); setEditLead(null) }
  const onSaved = () => dispatch(fetchLeads())

  const launchAutoQuote = () => {
    const id = autoLead.id
    const d = autoDiscount !== '' ? autoDiscount : '0'
    setAutoLead(null)
    navigate(`/ventes/devis/nouveau?lead=${id}&discount=${encodeURIComponent(d)}&auto=1`)
  }

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
          <button className="btn btn-primary" onClick={openNew}>+ Nouveau lead</button>
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
            <th>Facture</th>
            <th>Devis</th>
            <th>Actions</th>
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
              <td>
                {l.facture_hiver
                  ? `${Math.round(parseFloat(l.facture_hiver))}${l.ete_differente && l.facture_ete ? ` / ${Math.round(parseFloat(l.facture_ete))}` : ''} MAD`
                  : '—'}
              </td>
              <td>{(l.devis ?? []).length || '—'}</td>
              <td>
                <div className="actions-cell">
                  <button className="btn btn-sm btn-outline" onClick={() => openEdit(l)}>
                    Éditer
                  </button>
                  <button className="btn btn-sm gen-btn-orange"
                          title="Créer un devis automatique depuis ce lead"
                          onClick={() => { setAutoLead(l); setAutoDiscount('0') }}>
                    ⚡ Devis auto
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showForm && (
        <LeadForm lead={editLead} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Devis automatique : remise puis lancement ── */}
      {autoLead && (
        <div className="modal-overlay" onClick={() => setAutoLead(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                ⚡ Devis automatique — {autoLead.nom} {autoLead.prenom || ''}
              </h3>
              <button type="button" className="modal-close" onClick={() => setAutoLead(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p className="gen-hint">
                Le devis sera dimensionné automatiquement depuis la facture du lead
                ({autoLead.facture_hiver
                  ? `${autoLead.facture_hiver} MAD${autoLead.ete_differente && autoLead.facture_ete ? ` hiver / ${autoLead.facture_ete} MAD été` : '/mois'}`
                  : 'aucune facture enregistrée — saisissez-la d\'abord via Éditer'}),
                avec l'équipement auto-rempli depuis le stock, puis créé en brouillon
                lié à ce lead.
              </p>
              <div className="form-group">
                <label className="form-label">Réduction (%) — optionnelle</label>
                <input type="number" min="0" max="100" step="any" className="form-control"
                       value={autoDiscount}
                       onChange={e => setAutoDiscount(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-outline" onClick={() => setAutoLead(null)}>
                Annuler
              </button>
              <button type="button" className="btn btn-primary"
                      disabled={!autoLead.facture_hiver}
                      onClick={launchAutoQuote}>
                ⚡ Créer le devis automatique
              </button>
            </div>
          </div>
        </div>
      )}

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
