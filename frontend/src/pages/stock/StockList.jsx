import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchProduits,
  fetchProduitsArchived,
  fetchCategories,
  updateProduit,
  deleteProduit,
  unarchiveProduit,
  forceDeleteArchivedProduit,
} from '../../features/stock/store/stockSlice'
import stockApi from '../../api/stockApi'
import ExportButton from '../../components/ExportButton'
import ProduitForm from './ProduitForm'
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
} from '../../features/stock/catalogue'
import { validateInline } from '../../features/stock/bulkOps'

// ── Cellule éditable en ligne (Odoo-style edit-in-place) ───────────────────
// field ∈ prix_vente | quantite_stock | categorie_id. Valide côté client puis
// PATCH le champ seul ; le serveur revalide (source de vérité).
function InlineCell({ p, field, type, categories, onSave, children }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const start = () => {
    setErr(null)
    if (field === 'categorie_id') setVal(p.categorie?.id ?? '')
    else setVal(p[field] ?? '')
    setEditing(true)
  }

  const commit = async () => {
    const res = validateInline(field, val)
    if (!res.ok) { setErr(res.error); return }
    setSaving(true)
    try {
      await onSave(p, field, res.value)
      setEditing(false)
    } catch (e) {
      setErr(e?.detail ?? 'Erreur d\'enregistrement.')
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    return (
      <span className="cat-inline-view" title="Cliquer pour éditer"
            onClick={start} style={{ cursor: 'pointer' }}>
        {children}
      </span>
    )
  }

  return (
    <span className="cat-inline-edit" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
      {field === 'categorie_id' ? (
        <select className="form-control" style={{ height: 30, minWidth: 130 }}
                value={val} autoFocus disabled={saving}
                onChange={e => setVal(e.target.value)}>
          <option value="">— sans catégorie —</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
      ) : (
        <input className="form-control" style={{ height: 30, width: 90 }}
               type={type ?? 'text'} step="any" value={val} autoFocus disabled={saving}
               onChange={e => setVal(e.target.value)}
               onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(false) }} />
      )}
      <button className="btn btn-sm btn-primary" disabled={saving} onClick={commit}>✓</button>
      <button className="btn btn-sm btn-outline" disabled={saving} onClick={() => setEditing(false)}>✕</button>
      {err && <span className="text-danger" style={{ fontSize: '0.7rem' }}>{err}</span>}
    </span>
  )
}

// ── Ligne article du catalogue (hoistée : identité stable entre rendus) ─────
function CatalogueRow({
  p, canWrite, canDelete, onEdit, onDelete,
  selected, onToggleSelect, categories, onInlineSave,
}) {
  const spec = keySpec(p)
  const ttc = prixTtc(p)
  return (
    <div className={`cat-row${p.is_low_stock ? ' cat-row-low' : ''}${selected ? ' cat-row-selected' : ''}`}>
      {canWrite && (
        <div className="cat-row-select">
          <input type="checkbox" checked={selected}
                 aria-label={`Sélectionner ${p.nom}`}
                 onChange={() => onToggleSelect(p.id)} />
        </div>
      )}
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
        {canWrite ? (
          <InlineCell p={p} field="prix_vente" type="number" categories={categories} onSave={onInlineSave}>
            {sansPrix(p)
              ? <span className="cat-badge cat-badge-prix">prix à renseigner</span>
              : (
                <>
                  <div className="cat-prix-ttc">{ttc.toLocaleString('fr-MA')} DH <span>TTC</span></div>
                  <div className="cat-prix-ht">{parseFloat(p.prix_vente).toFixed(2)} HT · TVA {parseFloat(p.tva ?? 20)}%</div>
                </>
              )}
          </InlineCell>
        ) : (
          sansPrix(p)
            ? <span className="cat-badge cat-badge-prix">prix à renseigner</span>
            : (
              <>
                <div className="cat-prix-ttc">{ttc.toLocaleString('fr-MA')} DH <span>TTC</span></div>
                <div className="cat-prix-ht">{parseFloat(p.prix_vente).toFixed(2)} HT · TVA {parseFloat(p.tva ?? 20)}%</div>
              </>
            )
        )}
      </div>
      <div className="cat-row-stock">
        {canWrite ? (
          <InlineCell p={p} field="quantite_stock" type="number" categories={categories} onSave={onInlineSave}>
            <span className={p.is_low_stock ? 'text-danger' : ''}>
              <strong>{p.quantite_stock}</strong> en stock
            </span>
          </InlineCell>
        ) : (
          <span className={p.is_low_stock ? 'text-danger' : ''}>
            <strong>{p.quantite_stock}</strong> en stock
          </span>
        )}
        {p.is_low_stock && <span className="cat-badge cat-badge-low">⚠ seuil {p.seuil_alerte}</span>}
        {canWrite && (
          <div className="cat-row-cat-inline" style={{ marginTop: 4, fontSize: '0.75rem' }}>
            <InlineCell p={p} field="categorie_id" categories={categories} onSave={onInlineSave}>
              <span className="cat-spec-chip">{p.categorie?.nom ?? 'sans catégorie'}</span>
            </InlineCell>
          </div>
        )}
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

// ── Modal d'édition groupée (prix de vente, garantie, catégorie, marque) ────
function BulkEditModal({ count, categories, onClose, onApply, running }) {
  const [op, setOp] = useState('change_prix')
  const [mode, setMode] = useState('percent')
  const [valeur, setValeur] = useState('')
  const [garantieMois, setGarantieMois] = useState('')
  const [garantieProd, setGarantieProd] = useState('')
  const [categorieId, setCategorieId] = useState('')
  const [marque, setMarque] = useState('')

  const submit = () => {
    if (op === 'change_prix') onApply('change_prix', { mode, valeur })
    else if (op === 'set_garantie') {
      const params = {}
      if (garantieMois !== '') params.garantie_mois = garantieMois
      if (garantieProd !== '') params.garantie_production_mois = garantieProd
      onApply('set_garantie', params)
    } else if (op === 'set_categorie') onApply('set_categorie', { categorie_id: categorieId || null })
    else if (op === 'set_marque') onApply('set_marque', { marque })
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: '#fff', borderRadius: 12, padding: '2rem', width: '100%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.25)' }}>
        <h3 style={{ margin: '0 0 1rem' }}>Édition groupée — {count} produit{count !== 1 ? 's' : ''}</h3>

        <label className="form-label">Action</label>
        <select className="form-control" value={op} onChange={e => setOp(e.target.value)} style={{ marginBottom: '1rem' }}>
          <option value="change_prix">Modifier le prix de vente</option>
          <option value="set_garantie">Définir la garantie</option>
          <option value="set_categorie">Réaffecter la catégorie</option>
          <option value="set_marque">Réaffecter la marque</option>
        </select>

        {op === 'change_prix' && (
          <div style={{ display: 'flex', gap: 8, marginBottom: '1rem' }}>
            <select className="form-control" value={mode} onChange={e => setMode(e.target.value)} style={{ flex: 1 }}>
              <option value="percent">Pourcentage (%)</option>
              <option value="fixed">Montant fixe (DH)</option>
            </select>
            <input className="form-control" type="number" step="any" placeholder={mode === 'percent' ? '+10 ou -5' : '+100 ou -50'}
                   value={valeur} onChange={e => setValeur(e.target.value)} style={{ flex: 1 }} />
          </div>
        )}
        {op === 'set_garantie' && (
          <div style={{ marginBottom: '1rem' }}>
            <label className="form-label">Garantie équipement (mois)</label>
            <input className="form-control" type="number" step="any" value={garantieMois}
                   onChange={e => setGarantieMois(e.target.value)} placeholder="laisser vide pour ignorer" />
            <label className="form-label" style={{ marginTop: 8 }}>Garantie production (mois)</label>
            <input className="form-control" type="number" step="any" value={garantieProd}
                   onChange={e => setGarantieProd(e.target.value)} placeholder="laisser vide pour ignorer" />
          </div>
        )}
        {op === 'set_categorie' && (
          <select className="form-control" value={categorieId} onChange={e => setCategorieId(e.target.value)} style={{ marginBottom: '1rem' }}>
            <option value="">— sans catégorie —</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}
          </select>
        )}
        {op === 'set_marque' && (
          <input className="form-control" value={marque} onChange={e => setMarque(e.target.value)}
                 placeholder="Nom de la marque" style={{ marginBottom: '1rem' }} />
        )}

        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-outline" onClick={onClose} disabled={running}>Annuler</button>
          <button className="btn btn-primary" onClick={submit} disabled={running}>
            {running ? 'Application...' : 'Appliquer'}
          </button>
        </div>
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
  const { produits, produitsArchived, categories, loading, error } = useSelector(s => s.stock)
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
  // Sélection multiple + édition groupée
  const [selectedIds, setSelectedIds]   = useState(() => new Set())
  const [showBulk, setShowBulk]         = useState(false)
  const [bulkRunning, setBulkRunning]   = useState(false)
  const [bulkNotif, setBulkNotif]       = useState(null)

  useEffect(() => { dispatch(fetchProduits()); dispatch(fetchCategories()) }, [dispatch])

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

  // ── Sélection multiple ───────────────────────────────────────────────────
  const toggleSelect = (id) => setSelectedIds(prev => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })
  const clearSelection = () => setSelectedIds(new Set())
  const selectAllVisible = () => {
    const ids = filtered.map(p => p.id)
    setSelectedIds(new Set(ids))
  }

  // ── Édition en ligne : PATCH d'un seul champ, revalidé serveur ────────────
  const handleInlineSave = async (p, field, value) => {
    try {
      await dispatch(updateProduit({ id: p.id, data: { [field]: value } })).unwrap()
    } catch (err) {
      throw (err && typeof err === 'object') ? { detail: Object.values(err)[0] } : { detail: String(err) }
    }
  }

  // ── Application d'une action groupée ──────────────────────────────────────
  const applyBulk = async (action, params) => {
    setBulkRunning(true)
    try {
      const ids = [...selectedIds]
      const res = await stockApi.bulkProduits(action, ids, params)
      setShowBulk(false)
      setBulkNotif(res.data?.detail ?? 'Modification appliquée.')
      setTimeout(() => setBulkNotif(null), 5000)
      clearSelection()
      dispatch(fetchProduits())
      dispatch(fetchCategories())
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Erreur lors de l\'édition groupée.')
    } finally {
      setBulkRunning(false)
    }
  }

  const exportSelection = async () => {
    try {
      const res = await stockApi.exportProduitsXlsx([...selectedIds])
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'catalogue.xlsx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      alert('Erreur lors de l\'export.')
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

      {showBulk && (
        <BulkEditModal
          count={selectedIds.size}
          categories={categories}
          running={bulkRunning}
          onClose={() => setShowBulk(false)}
          onApply={applyBulk}
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
          <ExportButton
            fetcher={stockApi.exportProduitsList}
            params={{
              ...(search.trim() ? { search: search.trim() } : {}),
              ...(showArchived ? { show_archived: 'true' } : {}),
            }}
            filename="catalogue.xlsx"
          />
          {canWrite && (
            <button className="btn btn-primary" onClick={openNew}>
              + Nouveau produit
            </button>
          )}
        </div>
      </div>

      {bulkNotif && (
        <div className="alert alert-success" style={{ marginBottom: '1rem' }}>
          {bulkNotif}
        </div>
      )}

      {canWrite && selectedIds.size > 0 && (
        <div className="cat-bulk-toolbar alert"
             style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', background: '#eef2ff', border: '1px solid #c7d2fe' }}>
          <strong>{selectedIds.size} sélectionné{selectedIds.size !== 1 ? 's' : ''}</strong>
          <button className="btn btn-sm btn-outline" onClick={selectAllVisible}>Tout sélectionner ({filtered.length})</button>
          <button className="btn btn-sm btn-outline" onClick={clearSelection}>Effacer</button>
          <span style={{ flex: 1 }} />
          <button className="btn btn-sm btn-primary" onClick={() => setShowBulk(true)}>Éditer en lot</button>
          <button className="btn btn-sm btn-outline" onClick={exportSelection}>Export .xlsx</button>
        </div>
      )}

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
                                  onEdit={openEdit} onDelete={handleDelete}
                                  selected={selectedIds.has(p.id)} onToggleSelect={toggleSelect}
                                  categories={categories} onInlineSave={handleInlineSave} />
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
