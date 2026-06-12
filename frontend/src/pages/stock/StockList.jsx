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
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
} from '../../features/stock/catalogue'

// ── Ligne article du catalogue (hoistée : identité stable entre rendus) ─────
function CatalogueRow({ p, canWrite, canDelete, onEdit, onDelete }) {
  const spec = keySpec(p)
  const ttc = prixTtc(p)
  return (
    <div className={`cat-row${p.is_low_stock ? ' cat-row-low' : ''}`}>
      <div className="cat-row-id">
        <div className="cat-row-nom">{p.nom}</div>
        <div className="cat-row-sub">
          {p.sku && <span className="mono-text">{p.sku}</span>}
          {parseFloat(p.prix_achat) > 0 && (
            <span> · achat {parseFloat(p.prix_achat).toFixed(2)} DH HT</span>
          )}
        </div>
      </div>
      <div className="cat-row-spec">{spec && <span className="cat-spec-chip">{spec}</span>}</div>
      <div className="cat-row-prix">
        {sansPrix(p)
          ? <span className="cat-badge cat-badge-prix">prix à renseigner</span>
          : (
            <>
              <div className="cat-prix-ttc">{ttc.toLocaleString('fr-MA')} DH <span>TTC</span></div>
              <div className="cat-prix-ht">{parseFloat(p.prix_vente).toFixed(2)} HT · TVA {parseFloat(p.tva ?? 20)}%</div>
            </>
          )}
      </div>
      <div className="cat-row-stock">
        <span className={p.is_low_stock ? 'text-danger' : ''}>
          <strong>{p.quantite_stock}</strong> en stock
        </span>
        {p.is_low_stock && <span className="cat-badge cat-badge-low">⚠ seuil {p.seuil_alerte}</span>}
      </div>
      <div className="cat-row-actions">
        {canWrite && (
          <button className="btn btn-sm btn-outline" onClick={() => onEdit(p)}>Éditer</button>
        )}
        {canDelete && (
          <button className="btn btn-sm btn-outline btn-danger-outline"
                  onClick={() => onDelete(p)}>Supprimer</button>
        )}
      </div>
    </div>
  )
}

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
  const permissions = useSelector(s => s.auth.permissions)
  // Rôle fin (ex. « Commerciale » lecture seule) : les permissions priment ;
  // comptes hérités sans rôle fin : comportement historique par rôle.
  const canWrite = permissions.length
    ? permissions.includes('stock_modifier')
    : (role === 'responsable' || role === 'admin')
  const canDelete = role === 'admin'

  const [search, setSearch]           = useState('')
  const [showForm, setShowForm]       = useState(false)
  const [editProduit, setEditProduit] = useState(null)
  const [filterLow, setFilterLow]     = useState(false)
  const [activeCat, setActiveCat]     = useState('')   // '' = tout le catalogue
  const [showArchived, setShowArchived]   = useState(false)
  const [archiveNotif, setArchiveNotif]   = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting]           = useState(false)

  useEffect(() => { dispatch(fetchProduits()) }, [dispatch])

  useEffect(() => {
    if (showArchived) dispatch(fetchProduitsArchived())
  }, [showArchived, dispatch])

  // Catalogue hiérarchisé : la recherche traverse TOUT (nom, SKU, marque,
  // catégorie, spec) ; sans recherche, le rail filtre par catégorie.
  const actifs = useMemo(() => produits.filter(p => !p.is_archived), [produits])
  const searching = search.trim().length > 0
  const filtered = useMemo(() => {
    let list = filterLow ? actifs.filter(p => p.is_low_stock) : actifs
    list = searchCatalogue(list, search)
    return list
  }, [actifs, search, filterLow])
  const allGroups = useMemo(() => groupCatalogue(actifs), [actifs])
  const groups = useMemo(() => {
    const g = groupCatalogue(filtered)
    if (searching || !activeCat) return g
    return g.filter(c => c.nom === activeCat)
  }, [filtered, searching, activeCat])

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
          {canWrite && (
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

      <div className="cat-layout">
        <aside className="cat-rail">
          <input
            className="form-control cat-rail-search"
            type="search"
            placeholder="Chercher partout…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button type="button"
                  className={`cat-rail-item${!activeCat && !searching ? ' active' : ''}`}
                  onClick={() => { setActiveCat(''); setSearch('') }}>
            <span>Tout le catalogue</span>
            <span className="cat-rail-count">{actifs.length}</span>
          </button>
          {allGroups.map(c => (
            <button key={c.nom} type="button"
                    className={`cat-rail-item${activeCat === c.nom && !searching ? ' active' : ''}`}
                    onClick={() => { setActiveCat(c.nom); setSearch('') }}>
              <span>{c.nom}</span>
              <span className="cat-rail-count">{c.count}</span>
            </button>
          ))}
        </aside>

        <main className="cat-main">
          {searching && (
            <div className="cat-search-note">
              {filtered.length} résultat{filtered.length !== 1 ? 's' : ''} pour
              « {search} » dans tout le catalogue
            </div>
          )}
          {groups.map(c => (
            <section key={c.nom} className="cat-section">
              <h3 className="cat-section-title">
                {c.nom} <span className="cat-rail-count">{c.count}</span>
              </h3>
              {c.brands.map(b => (
                <div key={b.marque} className="cat-brand">
                  <div className="cat-brand-header">
                    <span className="cat-brand-name">{b.marque}</span>
                    <span className="cat-brand-rule" />
                    <span className="cat-brand-count">{b.items.length} article{b.items.length !== 1 ? 's' : ''}</span>
                  </div>
                  {b.items.map(p => (
                    <CatalogueRow key={p.id} p={p} canWrite={canWrite} canDelete={canDelete}
                                  onEdit={openEdit} onDelete={handleDelete} />
                  ))}
                </div>
              ))}
            </section>
          ))}
          {filtered.length === 0 && !loading && (
            <p className="empty-state">
              {filterLow
                ? 'Aucun produit en stock bas.'
                : search
                  ? `Aucun résultat pour « ${search} »`
                  : 'Aucun produit. Créez votre premier produit.'}
            </p>
          )}
        </main>
      </div>

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
