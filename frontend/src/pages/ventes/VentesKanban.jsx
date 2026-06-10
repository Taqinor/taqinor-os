import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchBonsCommande,
  createBonCommande,
  updateBonCommande,
  confirmerBC,
  marquerLivreBC,
  annulerBC,
  creerFactureFromBC,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'

const STATUT_META = {
  en_attente: { label: 'En attente', bg: '#fef9c3', color: '#a16207' },
  confirme:   { label: 'Confirmé',   bg: '#dbeafe', color: '#1d4ed8' },
  livre:      { label: 'Livré',      bg: '#dcfce7', color: '#15803d' },
  annule:     { label: 'Annulé',     bg: '#f1f5f9', color: '#94a3b8' },
}

const TABS = [
  { key: 'tous',       label: 'Tous' },
  { key: 'en_attente', label: 'En attente' },
  { key: 'confirme',   label: 'Confirmés' },
  { key: 'livre',      label: 'Livrés' },
  { key: 'annule',     label: 'Annulés' },
]

export default function BonCommandeList() {
  const dispatch = useDispatch()
  const { bonsCommande, loading, error } = useSelector(s => s.ventes)

  const [activeTab, setActiveTab] = useState('tous')
  const [search, setSearch]       = useState('')
  const [actionId, setActionId]   = useState(null)
  const [showForm, setShowForm]   = useState(false)
  const [editBC, setEditBC]       = useState(null)

  useEffect(() => { dispatch(fetchBonsCommande()) }, [dispatch])

  const filtered = useMemo(() => {
    let list = activeTab === 'tous'
      ? bonsCommande
      : bonsCommande.filter(b => b.statut === activeTab)
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(b =>
        b.reference?.toLowerCase().includes(q) ||
        (b.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [bonsCommande, activeTab, search])

  const counts = useMemo(() => ({
    tous:       bonsCommande.length,
    en_attente: bonsCommande.filter(b => b.statut === 'en_attente').length,
    confirme:   bonsCommande.filter(b => b.statut === 'confirme').length,
    livre:      bonsCommande.filter(b => b.statut === 'livre').length,
    annule:     bonsCommande.filter(b => b.statut === 'annule').length,
  }), [bonsCommande])

  const doAction = async (thunk, id, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return
    setActionId(id)
    try {
      await dispatch(thunk(id)).unwrap()
    } catch (err) {
      alert(err?.detail ?? JSON.stringify(err))
    } finally {
      setActionId(null)
    }
  }

  const openNew  = () => { setEditBC(null); setShowForm(true) }
  const openEdit = bc => { setEditBC(bc);   setShowForm(true) }
  const closeForm = () => { setShowForm(false); setEditBC(null) }

  if (loading) return <p className="page-loading">Chargement des bons de commande...</p>
  if (error)   return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Bons de commande
          {bonsCommande.length > 0 && (
            <span className="count-badge">{bonsCommande.length}</span>
          )}
        </h2>
        <div className="page-header-actions">
          <input
            className="search-input"
            type="search"
            placeholder="Référence, client…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button className="btn btn-primary" onClick={openNew}>
            + Nouveau BC
          </button>
        </div>
      </div>

      {showForm && (
        <BCForm
          bc={editBC}
          onClose={closeForm}
          onSaved={() => { dispatch(fetchBonsCommande()); closeForm() }}
        />
      )}

      <div className="status-tabs">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`status-tab${activeTab === t.key ? ' active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
            {counts[t.key] > 0 && (
              <span className="tab-count">{counts[t.key]}</span>
            )}
          </button>
        ))}
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Référence</th>
            <th>Client</th>
            <th>Devis</th>
            <th>Livraison prévue</th>
            <th>Statut</th>
            <th>Facture</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(bc => {
            const meta = STATUT_META[bc.statut] ?? STATUT_META.en_attente
            const busy = actionId === bc.id
            return (
              <tr key={bc.id}>
                <td><strong>{bc.reference}</strong></td>
                <td>{bc.client_nom ?? '—'}</td>
                <td>{bc.devis_reference ?? <span className="text-muted">—</span>}</td>
                <td>
                  {bc.date_livraison_prevue
                    ? new Date(bc.date_livraison_prevue).toLocaleDateString('fr-FR')
                    : '—'}
                </td>
                <td>
                  <span className="badge" style={{ background: meta.bg, color: meta.color }}>
                    {meta.label}
                  </span>
                </td>
                <td>
                  {bc.has_facture
                    ? <span className="badge" style={{ background: '#dcfce7', color: '#15803d' }}>Oui</span>
                    : <span className="text-muted">—</span>}
                </td>
                <td>
                  <div className="actions-cell">
                    {(bc.statut === 'en_attente' || bc.statut === 'confirme') && (
                      <button className="btn btn-sm btn-outline" onClick={() => openEdit(bc)}>
                        Éditer
                      </button>
                    )}
                    {bc.statut === 'en_attente' && (
                      <button
                        className="btn btn-sm btn-primary"
                        disabled={busy}
                        onClick={() => doAction(confirmerBC, bc.id)}
                      >
                        {busy ? '...' : 'Confirmer'}
                      </button>
                    )}
                    {bc.statut === 'confirme' && (
                      <button
                        className="btn btn-sm btn-success"
                        disabled={busy}
                        onClick={() => doAction(marquerLivreBC, bc.id, `Marquer le BC ${bc.reference} comme livré ?`)}
                      >
                        {busy ? '...' : 'Livrer'}
                      </button>
                    )}
                    {(bc.statut === 'confirme' || bc.statut === 'livre') && !bc.has_facture && (
                      <button
                        className="btn btn-sm btn-outline"
                        disabled={busy}
                        onClick={() => doAction(creerFactureFromBC, bc.id, `Créer une facture pour ${bc.reference} ?`)}
                      >
                        {busy ? '...' : '+ Facture'}
                      </button>
                    )}
                    {bc.statut !== 'livre' && bc.statut !== 'annule' && (
                      <button
                        className="btn btn-sm btn-outline"
                        disabled={busy}
                        onClick={() => doAction(annulerBC, bc.id, `Annuler le BC ${bc.reference} ?`)}
                      >
                        Annuler
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {filtered.length === 0 && !loading && (
        <p className="empty-state">
          {search
            ? `Aucun résultat pour « ${search} »`
            : activeTab !== 'tous'
              ? 'Aucun BC dans cet onglet.'
              : 'Aucun bon de commande. Créez-en un ou convertissez un devis.'}
        </p>
      )}
    </div>
  )
}

// ── Formulaire BC (création / édition) ─────────────────────────────────────────

function BCForm({ bc = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!bc

  const [clients, setClients] = useState([])
  const [saving, setSaving]   = useState(false)
  const [errors, setErrors]   = useState({})

  const [fields, setFields] = useState({
    client:               bc ? String(bc.client) : '',
    date_livraison_prevue: bc?.date_livraison_prevue ?? '',
    note:                 bc?.note ?? '',
  })

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const validate = () => {
    const e = {}
    if (!fields.client) e.client = 'Client requis'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        client:               parseInt(fields.client),
        date_livraison_prevue: fields.date_livraison_prevue || null,
        note:                 fields.note || null,
      }
      if (isEdit) {
        await dispatch(updateBonCommande({ id: bc.id, data: payload })).unwrap()
      } else {
        await dispatch(createBonCommande(payload)).unwrap()
      }
      onSaved()
    } catch (err) {
      const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
      setErrors(prev => ({ ...prev, submit: msg }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? `Éditer — ${bc.reference}` : 'Nouveau bon de commande'}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label">Client <span className="req">*</span></label>
              <select
                className={`form-select${errors.client ? ' is-invalid' : ''}`}
                value={fields.client}
                onChange={e => setField('client', e.target.value)}
                disabled={isEdit}
              >
                <option value="">— Sélectionner un client —</option>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                  </option>
                ))}
              </select>
              {errors.client && <div className="form-feedback">{errors.client}</div>}
            </div>

            <div className="form-group">
              <label className="form-label">Date de livraison prévue</label>
              <input
                type="date"
                className="form-control"
                value={fields.date_livraison_prevue}
                onChange={e => setField('date_livraison_prevue', e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Note</label>
              <textarea
                className="form-control"
                rows={3}
                value={fields.note}
                onChange={e => setField('note', e.target.value)}
                placeholder="Instructions, remarques..."
              />
            </div>

            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le BC')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
