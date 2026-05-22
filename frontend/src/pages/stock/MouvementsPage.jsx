import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchMouvements,
  fetchProduits,
  createMouvement,
} from '../../features/stock/store/stockSlice'

const TYPE_META = {
  entree:     { label: 'Entrée',      bg: '#dcfce7', color: '#15803d' },
  sortie:     { label: 'Sortie',      bg: '#fee2e2', color: '#b91c1c' },
  ajustement: { label: 'Ajustement',  bg: '#fef9c3', color: '#a16207' },
  transfert:  { label: 'Transfert',   bg: '#dbeafe', color: '#1d4ed8' },
}

const TABS = [
  { key: 'tous',       label: 'Tous' },
  { key: 'entree',     label: 'Entrées' },
  { key: 'sortie',     label: 'Sorties' },
  { key: 'ajustement', label: 'Ajustements' },
]

export default function MouvementsPage() {
  const dispatch = useDispatch()
  const { mouvements, produits, loading, error } = useSelector(s => s.stock)
  const role = useSelector(s => s.auth.role)

  const [activeTab, setActiveTab] = useState('tous')
  const [search, setSearch]       = useState('')
  const [showForm, setShowForm]   = useState(false)

  useEffect(() => {
    dispatch(fetchMouvements())
    if (!produits.length) dispatch(fetchProduits())
  }, [dispatch, produits.length])

  const filtered = useMemo(() => {
    let list = activeTab === 'tous'
      ? mouvements
      : mouvements.filter(m => m.type_mouvement === activeTab)
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(m =>
        (m.produit_nom ?? '').toLowerCase().includes(q) ||
        (m.reference ?? '').toLowerCase().includes(q) ||
        (m.note ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [mouvements, activeTab, search])

  const counts = useMemo(() => ({
    tous:       mouvements.length,
    entree:     mouvements.filter(m => m.type_mouvement === 'entree').length,
    sortie:     mouvements.filter(m => m.type_mouvement === 'sortie').length,
    ajustement: mouvements.filter(m => m.type_mouvement === 'ajustement').length,
  }), [mouvements])

  if (loading) return <p className="page-loading">Chargement des mouvements...</p>
  if (error)   return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Mouvements de stock
          {mouvements.length > 0 && (
            <span className="count-badge">{mouvements.length}</span>
          )}
        </h2>
        <div className="page-header-actions">
          <input
            className="search-input"
            type="search"
            placeholder="Produit, référence, note…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {(role === 'responsable' || role === 'admin') && (
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>
              + Saisir mouvement
            </button>
          )}
        </div>
      </div>

      {showForm && (
        <MouvementForm
          produits={produits}
          onClose={() => setShowForm(false)}
          onSaved={() => { dispatch(fetchMouvements()); setShowForm(false) }}
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
            <th>Date</th>
            <th>Produit</th>
            <th>Type</th>
            <th className="ta-right">Avant</th>
            <th className="ta-right">Mouvement</th>
            <th className="ta-right">Après</th>
            <th>Référence</th>
            <th>Note</th>
            <th>Par</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(m => {
            const meta = TYPE_META[m.type_mouvement] ?? TYPE_META.entree
            const delta = m.quantite_apres - m.quantite_avant
            return (
              <tr key={m.id}>
                <td>
                  {new Date(m.date).toLocaleDateString('fr-FR')}{' '}
                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                    {new Date(m.date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </td>
                <td><strong>{m.produit_nom ?? m.produit}</strong></td>
                <td>
                  <span className="badge" style={{ background: meta.bg, color: meta.color }}>
                    {meta.label}
                  </span>
                </td>
                <td className="ta-right text-muted">{m.quantite_avant}</td>
                <td className="ta-right">
                  <span className={delta >= 0 ? 'text-success' : 'text-danger'}>
                    {delta >= 0 ? '+' : ''}{delta}
                  </span>
                </td>
                <td className="ta-right"><strong>{m.quantite_apres}</strong></td>
                <td>
                  <span className="mono-text">{m.reference ?? <span className="text-muted">—</span>}</span>
                </td>
                <td className="text-truncate" style={{ maxWidth: 160 }}>
                  {m.note ?? <span className="text-muted">—</span>}
                </td>
                <td className="text-muted">{m.created_by_username ?? '—'}</td>
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
              ? 'Aucun mouvement dans cet onglet.'
              : 'Aucun mouvement de stock enregistré.'}
        </p>
      )}
    </div>
  )
}

// ── Formulaire mouvement ────────────────────────────────────────────────────────

function MouvementForm({ produits, onClose, onSaved }) {
  const dispatch = useDispatch()
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const [fields, setFields] = useState({
    produit:        '',
    type_mouvement: 'entree',
    quantite:       '1',
    reference:      '',
    note:           '',
  })

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const selectedProduit = produits.find(p => String(p.id) === String(fields.produit))

  const previewApres = useMemo(() => {
    if (!selectedProduit) return null
    const qte = parseInt(fields.quantite) || 0
    if (fields.type_mouvement === 'entree')     return selectedProduit.quantite_stock + qte
    if (fields.type_mouvement === 'sortie')     return selectedProduit.quantite_stock - qte
    if (fields.type_mouvement === 'ajustement') return qte
    return null
  }, [selectedProduit, fields.quantite, fields.type_mouvement])

  const validate = () => {
    const e = {}
    if (!fields.produit)                          e.produit  = 'Produit requis'
    if (!(parseInt(fields.quantite) > 0))         e.quantite = 'Quantité invalide (> 0)'
    if (fields.type_mouvement === 'sortie' && selectedProduit) {
      if (parseInt(fields.quantite) > selectedProduit.quantite_stock)
        e.quantite = `Stock insuffisant (disponible : ${selectedProduit.quantite_stock})`
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      await dispatch(createMouvement({
        produit:        parseInt(fields.produit),
        type_mouvement: fields.type_mouvement,
        quantite:       parseInt(fields.quantite),
        reference:      fields.reference.trim() || null,
        note:           fields.note.trim()      || null,
      })).unwrap()
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
          <h3 className="modal-title">Saisir un mouvement de stock</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label">Produit <span className="req">*</span></label>
              <select
                className={`form-select${errors.produit ? ' is-invalid' : ''}`}
                value={fields.produit}
                onChange={e => setField('produit', e.target.value)}
              >
                <option value="">— Sélectionner un produit —</option>
                {produits.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.nom}{p.sku ? ` (${p.sku})` : ''} — stock : {p.quantite_stock}
                  </option>
                ))}
              </select>
              {errors.produit && <div className="form-feedback">{errors.produit}</div>}
            </div>

            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Type de mouvement</label>
                <select
                  className="form-select"
                  value={fields.type_mouvement}
                  onChange={e => setField('type_mouvement', e.target.value)}
                >
                  <option value="entree">Entrée (ajoute au stock)</option>
                  <option value="sortie">Sortie (retire du stock)</option>
                  <option value="ajustement">Ajustement (fixe le stock)</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">
                  {fields.type_mouvement === 'ajustement' ? 'Nouvelle quantité' : 'Quantité'}
                  <span className="req"> *</span>
                </label>
                <input
                  type="number" min="0" step="1"
                  className={`form-control${errors.quantite ? ' is-invalid' : ''}`}
                  value={fields.quantite}
                  onChange={e => setField('quantite', e.target.value)}
                />
                {errors.quantite && <div className="form-feedback">{errors.quantite}</div>}
              </div>
            </div>

            {selectedProduit && previewApres !== null && (
              <div className="stock-preview">
                <span>Stock actuel : <strong>{selectedProduit.quantite_stock}</strong></span>
                <span className="stock-arrow">→</span>
                <span>
                  Après : <strong className={previewApres < 0 ? 'text-danger' : ''}>
                    {previewApres}
                  </strong>
                </span>
              </div>
            )}

            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Référence</label>
                <input
                  className="form-control"
                  value={fields.reference}
                  onChange={e => setField('reference', e.target.value)}
                  placeholder="Numéro BL, facture fournisseur..."
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Note</label>
              <textarea
                className="form-control"
                rows={2}
                value={fields.note}
                onChange={e => setField('note', e.target.value)}
                placeholder="Raison du mouvement..."
              />
            </div>

            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : 'Enregistrer le mouvement'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
