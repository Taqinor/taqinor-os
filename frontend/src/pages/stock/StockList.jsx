import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchProduits,
  fetchProduitsArchived,
  deleteProduit,
  unarchiveProduit,
  forceDeleteArchivedProduit,
} from '../../features/stock/store/stockSlice'
import ProduitForm from './ProduitForm'

// ── Modal confirmation suppression définitive ──────────────────────────────
function ForceDeleteModal({ produit, onCancel, onConfirm, loading }) {
  const [typed, setTyped] = useState('')
  const expected = produit.sku || produit.nom
  const isValid  = typed.trim() === expected.trim()

  const fmtDate = (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: '2rem',
        width: '100%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.25)',
      }}>
        <h3 style={{ margin: '0 0 0.25rem', color: '#dc2626', fontSize: '1.1rem' }}>
          Suppression définitive
        </h3>
        <p style={{ margin: '0 0 1.25rem', color: '#64748b', fontSize: '0.875rem' }}>
          Cette action supprimera le produit et tout son historique de mouvements.
          Elle est <strong>irréversible</strong>.
        </p>

        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.875rem 1rem', marginBottom: '1.25rem', fontSize: '0.875rem', lineHeight: 1.7 }}>
          <div><span style={{ color: '#94a3b8', minWidth: 140, display: 'inline-block' }}>Produit</span><strong>{produit.nom}</strong></div>
          <div><span style={{ color: '#94a3b8', minWidth: 140, display: 'inline-block' }}>SKU / Référence</span><code style={{ background: '#e2e8f0', padding: '1px 5px', borderRadius: 4 }}>{produit.sku || '—'}</code></div>
          <div><span style={{ color: '#94a3b8', minWidth: 140, display: 'inline-block' }}>Créé le</span>{fmtDate(produit.date_creation)}</div>
          {produit.nb_mouvements != null && (
            <div><span style={{ color: '#94a3b8', minWidth: 140, display: 'inline-block' }}>Mouvements</span>
              {produit.nb_mouvements} mouvement{produit.nb_mouvements !== 1 ? 's' : ''}
              {produit.premiere_date_mouvement && (
                <span style={{ color: '#64748b' }}> ({fmtDate(produit.premiere_date_mouvement)} → {fmtDate(produit.derniere_date_mouvement)})</span>
              )}
            </div>
          )}
        </div>

        <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.4rem', color: '#374151' }}>
          Tapez <code style={{ background: '#fee2e2', padding: '1px 5px', borderRadius: 4, color: '#dc2626' }}>{expected}</code> pour confirmer
        </label>
        <input
          type="text"
          className="form-control"
          value={typed}
          onChange={e => setTyped(e.target.value)}
          placeholder={`Saisir : ${expected}`}
          autoFocus
          style={{ marginBottom: '1.25rem' }}
        />

        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-outline" onClick={onCancel} disabled={loading}>
            Annuler
          </button>
          <button
            className="btn btn-danger"
            onClick={() => onConfirm(produit)}
            disabled={!isValid || loading}
            style={{ background: isValid && !loading ? '#dc2626' : undefined }}
          >
            {loading ? 'Suppression...' : 'Supprimer définitivement'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Page principale ────────────────────────────────────────────────────────
export default function StockList() {
  const dispatch = useDispatch()
  const { produits, produitsArchived, loading, error } = useSelector(s => s.stock)
  const role = useSelector(s => s.auth.role)

  const [search, setSearch]           = useState('')
  const [showForm, setShowForm]       = useState(false)
  const [editProduit, setEditProduit] = useState(null)
  const [filterLow, setFilterLow]     = useState(false)
  const [showArchived, setShowArchived]   = useState(false)
  const [archiveNotif, setArchiveNotif]   = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting]           = useState(false)

  useEffect(() => { dispatch(fetchProduits()) }, [dispatch])

  useEffect(() => {
    if (showArchived) dispatch(fetchProduitsArchived())
  }, [showArchived, dispatch])

  const filtered = useMemo(() => {
    let list = filterLow
      ? produits.filter(p => p.is_low_stock && !p.is_archived)
      : produits.filter(p => !p.is_archived)
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(p =>
        p.nom.toLowerCase().includes(q) ||
        (p.sku ?? '').toLowerCase().includes(q) ||
        (p.categorie?.nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [produits, search, filterLow])

  const lowCount = useMemo(
    () => produits.filter(p => p.is_low_stock && !p.is_archived).length,
    [produits]
  )

  const openNew   = () => { setEditProduit(null); setShowForm(true) }
  const openEdit  = p  => { setEditProduit(p);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);   setEditProduit(null) }
  const onSaved   = () => {
    dispatch(fetchProduits())
    if (showArchived) dispatch(fetchProduitsArchived())
  }

  const handleDelete = async (p) => {
    if (!window.confirm(`Supprimer le produit « ${p.nom} » ?`)) return
    try {
      const result = await dispatch(deleteProduit(p.id)).unwrap()
      if (result.archived) {
        setArchiveNotif(result.detail)
        setTimeout(() => setArchiveNotif(null), 6000)
      }
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors de la suppression.')
    }
  }

  const handleUnarchive = async (p) => {
    if (!window.confirm(`Désarchiver le produit « ${p.nom} » ?`)) return
    try {
      await dispatch(unarchiveProduit(p.id)).unwrap()
      dispatch(fetchProduitsArchived())
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors du désarchivage.')
    }
  }

  const handleForceDelete = async (p) => {
    setDeleting(true)
    try {
      await dispatch(forceDeleteArchivedProduit(p.id)).unwrap()
      setConfirmDelete(null)
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors de la suppression définitive.')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <p className="page-loading">Chargement des produits...</p>
  if (error)   return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      {confirmDelete && (
        <ForceDeleteModal
          produit={confirmDelete}
          loading={deleting}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={handleForceDelete}
        />
      )}

      <div className="page-header">
        <h2>
          Produits en stock
          {produits.filter(p => !p.is_archived).length > 0 && (
            <span className="count-badge">{produits.filter(p => !p.is_archived).length}</span>
          )}
        </h2>
        <div className="page-header-actions">
          <input
            className="search-input"
            type="search"
            placeholder="Nom, SKU, catégorie…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {lowCount > 0 && (
            <button
              className={`btn btn-sm${filterLow ? ' btn-danger' : ' btn-outline'}`}
              onClick={() => setFilterLow(v => !v)}
              title="Filtrer les produits en rupture ou sous le seuil d'alerte"
            >
              ⚠ Stock bas ({lowCount})
            </button>
          )}
          {role === 'admin' && (
            <button
              className={`btn btn-sm${showArchived ? ' btn-warning' : ' btn-outline'}`}
              onClick={() => setShowArchived(v => !v)}
            >
              {showArchived ? 'Masquer archivés' : `Archivés${produitsArchived.length > 0 ? ` (${produitsArchived.length})` : ''}`}
            </button>
          )}
          {(role === 'responsable' || role === 'admin') && (
            <button className="btn btn-primary" onClick={openNew}>
              + Nouveau produit
            </button>
          )}
        </div>
      </div>

      {archiveNotif && (
        <div className="alert alert-warning" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>📦</span>
          <span>{archiveNotif}</span>
          <button
            className="btn btn-sm btn-outline"
            style={{ marginLeft: 'auto' }}
            onClick={() => { setShowArchived(true); setArchiveNotif(null) }}
          >
            Voir les archivés
          </button>
        </div>
      )}

      {showForm && (
        <ProduitForm produit={editProduit} onClose={closeForm} onSaved={onSaved} />
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Nom</th>
            <th>Catégorie</th>
            <th>Fournisseur</th>
            <th className="ta-right">Stock</th>
            <th className="ta-right">Seuil</th>
            <th className="ta-right">Prix vente HT</th>
            <th className="ta-right">Prix achat HT</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(p => (
            <tr key={p.id} className={p.is_low_stock ? 'row-low-stock' : ''}>
              <td><span className="mono-text">{p.sku ?? '—'}</span></td>
              <td>
                <strong>{p.nom}</strong>
                {p.is_low_stock && (
                  <span className="low-stock-badge" title="Stock bas">⚠</span>
                )}
              </td>
              <td>{p.categorie?.nom ?? <span className="text-muted">—</span>}</td>
              <td>{p.fournisseur?.nom ?? <span className="text-muted">—</span>}</td>
              <td className={`ta-right${p.is_low_stock ? ' text-danger' : ''}`}>
                <strong>{p.quantite_stock}</strong>
              </td>
              <td className="ta-right text-muted">{p.seuil_alerte || '—'}</td>
              <td className="ta-right">{parseFloat(p.prix_vente).toFixed(2)} DH</td>
              <td className="ta-right">{parseFloat(p.prix_achat).toFixed(2)} DH</td>
              <td>
                <div className="actions-cell">
                  {(role === 'responsable' || role === 'admin') && (
                    <button className="btn btn-sm btn-outline" onClick={() => openEdit(p)}>
                      Éditer
                    </button>
                  )}
                  {role === 'admin' && (
                    <button
                      className="btn btn-sm btn-outline btn-danger-outline"
                      onClick={() => handleDelete(p)}
                    >
                      Supprimer
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
          {filterLow
            ? 'Aucun produit en stock bas.'
            : search
              ? `Aucun résultat pour « ${search} »`
              : 'Aucun produit. Créez votre premier produit.'}
        </p>
      )}

      {showArchived && (
        <div style={{ marginTop: '2rem' }}>
          <h3 style={{ color: 'var(--text-muted, #888)', marginBottom: '0.75rem' }}>
            Produits archivés
            {produitsArchived.length > 0 && (
              <span className="count-badge" style={{ background: 'var(--color-warning, #f59e0b)' }}>
                {produitsArchived.length}
              </span>
            )}
          </h3>
          {produitsArchived.length === 0 ? (
            <p className="empty-state">Aucun produit archivé.</p>
          ) : (
            <table className="data-table" style={{ opacity: 0.8 }}>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Nom</th>
                  <th>Catégorie</th>
                  <th>Fournisseur</th>
                  <th className="ta-right">Stock</th>
                  <th className="ta-right">Mouvements</th>
                  <th className="ta-right">Prix vente HT</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {produitsArchived.map(p => (
                  <tr key={p.id} style={{ color: 'var(--text-muted, #888)' }}>
                    <td><span className="mono-text" style={{ textDecoration: 'line-through' }}>{p.sku ?? '—'}</span></td>
                    <td style={{ textDecoration: 'line-through' }}>{p.nom}</td>
                    <td>{p.categorie?.nom ?? '—'}</td>
                    <td>{p.fournisseur?.nom ?? '—'}</td>
                    <td className="ta-right">{p.quantite_stock}</td>
                    <td className="ta-right">
                      {p.nb_mouvements != null ? (
                        <span title={p.premiere_date_mouvement
                          ? `${new Date(p.premiere_date_mouvement).toLocaleDateString('fr-FR')} → ${new Date(p.derniere_date_mouvement).toLocaleDateString('fr-FR')}`
                          : ''}>
                          {p.nb_mouvements}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="ta-right">{parseFloat(p.prix_vente).toFixed(2)} DH</td>
                    <td>
                      <div className="actions-cell">
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => openEdit(p)}
                        >
                          Éditer
                        </button>
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => handleUnarchive(p)}
                        >
                          Désarchiver
                        </button>
                        <button
                          className="btn btn-sm btn-outline btn-danger-outline"
                          onClick={() => setConfirmDelete(p)}
                        >
                          Supprimer
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
