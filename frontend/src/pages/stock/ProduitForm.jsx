import { useState, useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  createProduit,
  updateProduit,
  fetchCategories,
  fetchFournisseurs,
  createCategorie,
  createFournisseur,
} from '../../features/stock/store/stockSlice'

export default function ProduitForm({ produit = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const { categories, fournisseurs } = useSelector(s => s.stock)
  const isEdit = !!produit

  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const [newCatName, setNewCatName] = useState('')
  const [showNewCat, setShowNewCat] = useState(false)
  const [catSaving, setCatSaving] = useState(false)
  const [catError, setCatError] = useState(null)
  const newCatRef = useRef(null)

  const [newFouName, setNewFouName] = useState('')
  const [showNewFou, setShowNewFou] = useState(false)
  const [fouSaving, setFouSaving] = useState(false)
  const [fouError, setFouError] = useState(null)
  const newFouRef = useRef(null)

  const [fields, setFields] = useState({
    nom:            produit?.nom            ?? '',
    sku:            produit?.sku            ?? '',
    description:    produit?.description    ?? '',
    prix_vente:     String(produit?.prix_vente  ?? ''),
    prix_achat:     String(produit?.prix_achat  ?? '0'),
    quantite_stock: String(produit?.quantite_stock ?? '0'),
    seuil_alerte:   String(produit?.seuil_alerte  ?? '0'),
    categorie_id:   produit?.categorie?.id  ? String(produit.categorie.id) : '',
    fournisseur_id: produit?.fournisseur?.id ? String(produit.fournisseur.id) : '',
  })

  useEffect(() => {
    dispatch(fetchCategories())
    dispatch(fetchFournisseurs())
  }, [dispatch])

  useEffect(() => {
    if (showNewCat) newCatRef.current?.focus()
  }, [showNewCat])

  useEffect(() => {
    if (showNewFou) newFouRef.current?.focus()
  }, [showNewFou])

  const handleCreateCategorie = async () => {
    const nom = newCatName.trim()
    if (!nom) return
    setCatSaving(true)
    setCatError(null)
    try {
      const result = await dispatch(createCategorie({ nom })).unwrap()
      setField('categorie_id', String(result.id))
      setNewCatName('')
      setShowNewCat(false)
    } catch (err) {
      setCatError(err?.nom?.[0] ?? err?.detail ?? 'Erreur lors de la création.')
    } finally {
      setCatSaving(false)
    }
  }

  const handleCreateFournisseur = async () => {
    const nom = newFouName.trim()
    if (!nom) return
    setFouSaving(true)
    setFouError(null)
    try {
      const result = await dispatch(createFournisseur({ nom })).unwrap()
      setField('fournisseur_id', String(result.id))
      setNewFouName('')
      setShowNewFou(false)
    } catch (err) {
      setFouError(err?.nom?.[0] ?? err?.detail ?? 'Erreur lors de la création.')
    } finally {
      setFouSaving(false)
    }
  }

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const validate = () => {
    const e = {}
    if (!fields.nom.trim())               e.nom        = 'Nom requis'
    if (!fields.prix_vente || isNaN(parseFloat(fields.prix_vente)))
                                           e.prix_vente = 'Prix de vente requis'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        nom:            fields.nom.trim(),
        sku:            fields.sku.trim() || null,
        description:    fields.description.trim() || null,
        prix_vente:     fields.prix_vente,
        prix_achat:     fields.prix_achat,
        quantite_stock: parseInt(fields.quantite_stock) || 0,
        seuil_alerte:   parseInt(fields.seuil_alerte)   || 0,
        categorie_id:   fields.categorie_id   ? parseInt(fields.categorie_id)   : null,
        fournisseur_id: fields.fournisseur_id ? parseInt(fields.fournisseur_id) : null,
      }
      if (isEdit) {
        await dispatch(updateProduit({ id: produit.id, data: payload })).unwrap()
      } else {
        await dispatch(createProduit(payload)).unwrap()
      }
      onSaved?.()
      onClose()
    } catch (err) {
      const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
      setErrors(prev => ({ ...prev, submit: msg }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? `Éditer — ${produit.nom}` : 'Nouveau produit'}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Nom <span className="req">*</span></label>
                <input
                  className={`form-control${errors.nom ? ' is-invalid' : ''}`}
                  value={fields.nom}
                  onChange={e => setField('nom', e.target.value)}
                  placeholder="Nom du produit"
                />
                {errors.nom && <div className="form-feedback">{errors.nom}</div>}
              </div>
              <div className="form-group">
                <label className="form-label">SKU / Référence</label>
                <input
                  className="form-control"
                  value={fields.sku}
                  onChange={e => setField('sku', e.target.value)}
                  placeholder="REF-001"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Catégorie</label>
                {showNewCat ? (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      ref={newCatRef}
                      className="form-control"
                      value={newCatName}
                      onChange={e => setNewCatName(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateCategorie() } }}
                      placeholder="Nom de la catégorie"
                      style={{ flex: 1 }}
                    />
                    <button type="button" className="btn btn-primary" disabled={catSaving || !newCatName.trim()}
                      onClick={handleCreateCategorie}
                      style={{ padding: '6px 12px', fontSize: 13 }}>
                      {catSaving ? '…' : 'Créer'}
                    </button>
                    <button type="button" className="btn btn-outline"
                      onClick={() => { setShowNewCat(false); setNewCatName(''); setCatError(null) }}
                      style={{ padding: '6px 10px', fontSize: 13 }}>
                      ✕
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <select
                      className="form-select"
                      value={fields.categorie_id}
                      onChange={e => setField('categorie_id', e.target.value)}
                      style={{ flex: 1 }}
                    >
                      <option value="">— Aucune catégorie —</option>
                      {categories.map(c => (
                        <option key={c.id} value={c.id}>{c.nom}</option>
                      ))}
                    </select>
                    <button type="button" className="btn btn-outline"
                      onClick={() => setShowNewCat(true)}
                      title="Créer une nouvelle catégorie"
                      style={{ padding: '6px 11px', fontSize: 16, lineHeight: 1, flexShrink: 0 }}>
                      +
                    </button>
                  </div>
                )}
                {catError && <div className="form-feedback" style={{ display: 'block' }}>{catError}</div>}
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Fournisseur</label>
                {showNewFou ? (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      ref={newFouRef}
                      className="form-control"
                      value={newFouName}
                      onChange={e => setNewFouName(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleCreateFournisseur() } }}
                      placeholder="Nom du fournisseur"
                      style={{ flex: 1 }}
                    />
                    <button type="button" className="btn btn-primary" disabled={fouSaving || !newFouName.trim()}
                      onClick={handleCreateFournisseur}
                      style={{ padding: '6px 12px', fontSize: 13 }}>
                      {fouSaving ? '…' : 'Créer'}
                    </button>
                    <button type="button" className="btn btn-outline"
                      onClick={() => { setShowNewFou(false); setNewFouName(''); setFouError(null) }}
                      style={{ padding: '6px 10px', fontSize: 13 }}>
                      ✕
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <select
                      className="form-select"
                      value={fields.fournisseur_id}
                      onChange={e => setField('fournisseur_id', e.target.value)}
                      style={{ flex: 1 }}
                    >
                      <option value="">— Aucun fournisseur —</option>
                      {fournisseurs.map(f => (
                        <option key={f.id} value={f.id}>{f.nom}</option>
                      ))}
                    </select>
                    <button type="button" className="btn btn-outline"
                      onClick={() => setShowNewFou(true)}
                      title="Créer un nouveau fournisseur"
                      style={{ padding: '6px 11px', fontSize: 16, lineHeight: 1, flexShrink: 0 }}>
                      +
                    </button>
                  </div>
                )}
                {fouError && <div className="form-feedback" style={{ display: 'block' }}>{fouError}</div>}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea
                className="form-control"
                rows={2}
                value={fields.description}
                onChange={e => setField('description', e.target.value)}
                placeholder="Description optionnelle..."
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Prix de vente HT <span className="req">*</span></label>
                <input
                  type="number" min="0" step="0.01"
                  className={`form-control${errors.prix_vente ? ' is-invalid' : ''}`}
                  value={fields.prix_vente}
                  onChange={e => setField('prix_vente', e.target.value)}
                />
                {errors.prix_vente && <div className="form-feedback">{errors.prix_vente}</div>}
              </div>
              <div className="form-group">
                <label className="form-label">Prix d'achat HT</label>
                <input
                  type="number" min="0" step="0.01"
                  className="form-control"
                  value={fields.prix_achat}
                  onChange={e => setField('prix_achat', e.target.value)}
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Quantité en stock</label>
                <input
                  type="number" min="0" step="1"
                  className="form-control"
                  value={fields.quantite_stock}
                  onChange={e => setField('quantite_stock', e.target.value)}
                  disabled={isEdit}
                  title={isEdit ? 'Utilisez un mouvement de stock pour modifier la quantité' : ''}
                />
                {isEdit && (
                  <div className="form-hint">Modifiez via un mouvement de stock</div>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Seuil d'alerte</label>
                <input
                  type="number" min="0" step="1"
                  className="form-control"
                  value={fields.seuil_alerte}
                  onChange={e => setField('seuil_alerte', e.target.value)}
                />
              </div>
            </div>

            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le produit')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
