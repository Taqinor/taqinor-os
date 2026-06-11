import { useState, useEffect } from 'react'
import { useDispatch } from 'react-redux'
import {
  createFacture,
  updateFacture,
  addLigneFacture,
  updateLigneFacture,
  removeLigneFacture,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'

let _keyCounter = 0
const newKey = () => ++_keyCounter

const emptyLine = () => ({
  _key: newKey(),
  id: null,
  produit: '',
  designation: '',
  quantite: '1',
  prix_unitaire: '0',
  remise: '0',
})

export default function FactureForm({ facture = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!facture

  const [clients, setClients]           = useState([])
  const [produits, setProduits]         = useState([])
  const [bonsCommande, setBonsCommande] = useState([])
  const [saving, setSaving]             = useState(false)
  const [errors, setErrors]             = useState({})

  const [fields, setFields] = useState({
    client:          facture?.client          ?? '',
    bon_commande:    facture?.bon_commande     ?? '',
    statut:          facture?.statut           ?? 'brouillon',
    date_echeance:   facture?.date_echeance    ?? '',
    taux_tva:        String(facture?.taux_tva        ?? '20.00'),
    remise_globale:  String(facture?.remise_globale  ?? '0'),
    note:            facture?.note             ?? '',
  })

  const [lines, setLines] = useState(
    facture?.lignes?.length
      ? facture.lignes.map(l => ({
          _key: newKey(),
          id: l.id,
          produit: String(l.produit),
          designation: l.designation,
          quantite: String(l.quantite),
          prix_unitaire: String(l.prix_unitaire),
          remise: String(l.remise),
        }))
      : [emptyLine()]
  )

  const [removedLineIds, setRemovedLineIds] = useState([])

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
    ventesApi.getBonsCommande().then(r => setBonsCommande(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Live totals
  const remGlobal   = parseFloat(fields.remise_globale) || 0
  const tva         = parseFloat(fields.taux_tva) || 0

  const subtotalHT = lines.reduce((sum, l) => {
    const qte = parseFloat(l.quantite)      || 0
    const pu  = parseFloat(l.prix_unitaire) || 0
    const rem = parseFloat(l.remise)        || 0
    return sum + qte * pu * (1 - rem / 100)
  }, 0)

  const totalHT  = subtotalHT * (1 - remGlobal / 100)
  const totalTVA = totalHT * (tva / 100)
  const totalTTC = totalHT + totalTVA

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const onBcChange = (bcId) => {
    setField('bon_commande', bcId)
    if (bcId) {
      const bc = bonsCommande.find(b => String(b.id) === String(bcId))
      if (bc) setField('client', String(bc.client))
    }
  }

  const setLine = (key, k, v) =>
    setLines(ls => ls.map(l => l._key === key ? { ...l, [k]: v } : l))

  const onProduitChange = (key, produitId) => {
    const p = produits.find(p => String(p.id) === String(produitId))
    setLines(ls => ls.map(l =>
      l._key === key
        ? { ...l, produit: produitId, designation: p?.nom ?? '', prix_unitaire: p ? String(p.prix_vente) : '0' }
        : l
    ))
  }

  const addLine    = () => setLines(ls => [...ls, emptyLine()])
  const removeLine = key => {
    const line = lines.find(l => l._key === key)
    if (line?.id) setRemovedLineIds(ids => [...ids, line.id])
    setLines(ls => ls.filter(l => l._key !== key))
  }

  const validate = () => {
    const e = {}
    if (!fields.client)          e.client = 'Client requis'
    if (lines.length === 0)      e.lines  = 'Au moins une ligne est requise'
    else if (lines.some(l => !l.produit)) e.lines = 'Chaque ligne doit avoir un produit'
    else if (lines.some(l => !(parseFloat(l.quantite) > 0))) e.lines = 'Quantité invalide (doit être > 0)'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        client:         parseInt(fields.client),
        bon_commande:   fields.bon_commande ? parseInt(fields.bon_commande) : null,
        statut:         fields.statut,
        date_echeance:  fields.date_echeance  || null,
        taux_tva:       fields.taux_tva,
        remise_globale: fields.remise_globale,
        note:           fields.note || null,
      }

      let factureId
      if (isEdit) {
        const res = await dispatch(updateFacture({ id: facture.id, data: payload })).unwrap()
        factureId = res.id
      } else {
        const res = await dispatch(createFacture(payload)).unwrap()
        factureId = res.id
      }

      // Lignes supprimées
      await Promise.all(
        removedLineIds.map(id => dispatch(removeLigneFacture(id)).unwrap())
      )
      // Lignes existantes → update
      await Promise.all(
        lines.filter(l => l.id).map(l =>
          dispatch(updateLigneFacture({
            id: l.id,
            data: {
              facture:       factureId,
              produit:       parseInt(l.produit),
              designation:   l.designation,
              quantite:      l.quantite,
              prix_unitaire: l.prix_unitaire,
              remise:        l.remise,
            },
          })).unwrap()
        )
      )
      // Nouvelles lignes → create
      await Promise.all(
        lines.filter(l => !l.id).map(l =>
          dispatch(addLigneFacture({
            facture:       factureId,
            produit:       parseInt(l.produit),
            designation:   l.designation,
            quantite:      l.quantite,
            prix_unitaire: l.prix_unitaire,
            remise:        l.remise,
          })).unwrap()
        )
      )

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
      <div className="modal modal-xl" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? `Éditer — ${facture.reference}` : 'Nouvelle facture'}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {/* ── Infos générales ── */}
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Client <span className="req">*</span></label>
                <select
                  className={`form-select${errors.client ? ' is-invalid' : ''}`}
                  value={fields.client}
                  onChange={e => setField('client', e.target.value)}
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

              <div className="form-group fg-grow">
                <label className="form-label">Bon de commande (optionnel)</label>
                <select
                  className="form-select"
                  value={fields.bon_commande}
                  onChange={e => onBcChange(e.target.value)}
                >
                  <option value="">— Aucun BC —</option>
                  {bonsCommande.map(bc => (
                    <option key={bc.id} value={bc.id}>
                      {bc.reference} — {bc.client_nom}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Date d'échéance</label>
                <input
                  type="date"
                  className="form-control"
                  value={fields.date_echeance}
                  onChange={e => setField('date_echeance', e.target.value)}
                />
              </div>

              {isEdit && (
                <div className="form-group">
                  <label className="form-label">Statut</label>
                  <select
                    className="form-select"
                    value={fields.statut}
                    onChange={e => setField('statut', e.target.value)}
                  >
                    <option value="brouillon">Brouillon</option>
                    <option value="emise">Émise</option>
                    <option value="payee">Payée</option>
                    <option value="en_retard">En retard</option>
                    <option value="annulee">Annulée</option>
                  </select>
                </div>
              )}

              <div className="form-group fg-sm">
                <label className="form-label">TVA (%)</label>
                <input
                  type="number" min="0" max="100" step="0.01"
                  className="form-control"
                  value={fields.taux_tva}
                  onChange={e => setField('taux_tva', e.target.value)}
                />
              </div>

              <div className="form-group fg-sm">
                <label className="form-label">Remise globale (%)</label>
                <input
                  type="number" min="0" max="100" step="0.01"
                  className="form-control"
                  value={fields.remise_globale}
                  onChange={e => setField('remise_globale', e.target.value)}
                />
              </div>
            </div>

            {/* ── Lignes ── */}
            <div className="form-section">
              <div className="form-section-header">
                <span className="form-section-title">Lignes de la facture</span>
                <button type="button" className="btn btn-sm btn-outline" onClick={addLine}>
                  + Ajouter une ligne
                </button>
              </div>

              {errors.lines && <div className="form-feedback mb-8">{errors.lines}</div>}

              <div className="lines-table-wrap">
                <table className="lines-table">
                  <thead>
                    <tr>
                      <th style={{ minWidth: 160 }}>Produit</th>
                      <th>Désignation</th>
                      <th className="col-num">Qté</th>
                      <th className="col-num">Prix HT (DH)</th>
                      <th className="col-num">Rem. %</th>
                      <th className="col-num">Total HT</th>
                      <th className="col-del"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map(l => {
                      const lineTotal =
                        (parseFloat(l.quantite)      || 0) *
                        (parseFloat(l.prix_unitaire) || 0) *
                        (1 - (parseFloat(l.remise)   || 0) / 100)
                      return (
                        <tr key={l._key}>
                          <td>
                            <select
                              className="form-select form-select-sm"
                              value={l.produit}
                              onChange={e => onProduitChange(l._key, e.target.value)}
                            >
                              <option value="">— Produit —</option>
                              {produits.map(p => (
                                <option key={p.id} value={p.id}>{p.nom}</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input
                              className="form-control form-control-sm"
                              value={l.designation}
                              onChange={e => setLine(l._key, 'designation', e.target.value)}
                              placeholder="Désignation"
                            />
                          </td>
                          <td>
                            <input
                              type="number" min="0.01" step="0.01"
                              className="form-control form-control-sm ta-right"
                              value={l.quantite}
                              onChange={e => setLine(l._key, 'quantite', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number" min="0" step="0.01"
                              className="form-control form-control-sm ta-right"
                              value={l.prix_unitaire}
                              onChange={e => setLine(l._key, 'prix_unitaire', e.target.value)}
                            />
                          </td>
                          <td>
                            <input
                              type="number" min="0" max="100" step="0.01"
                              className="form-control form-control-sm ta-right"
                              value={l.remise}
                              onChange={e => setLine(l._key, 'remise', e.target.value)}
                            />
                          </td>
                          <td className="line-total">{lineTotal.toFixed(2)} DH</td>
                          <td>
                            {lines.length > 1 && (
                              <button
                                type="button"
                                className="btn-icon-danger"
                                onClick={() => removeLine(l._key)}
                                title="Supprimer"
                              >✕</button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── Totaux ── */}
            <div className="devis-totals">
              <div className="devis-total-row">
                <span>Sous-total HT</span>
                <span>{subtotalHT.toFixed(2)} DH</span>
              </div>
              {remGlobal > 0 && (
                <div className="devis-total-row devis-total-discount">
                  <span>Remise globale ({remGlobal}%)</span>
                  <span>−{(subtotalHT * remGlobal / 100).toFixed(2)} DH</span>
                </div>
              )}
              <div className="devis-total-row">
                <span>Total HT</span>
                <strong>{totalHT.toFixed(2)} DH</strong>
              </div>
              <div className="devis-total-row">
                <span>TVA ({tva}%)</span>
                <span>{totalTVA.toFixed(2)} DH</span>
              </div>
              <div className="devis-total-row devis-total-ttc">
                <span>Total TTC</span>
                <strong>{totalTTC.toFixed(2)} DH</strong>
              </div>
            </div>

            {/* ── Note ── */}
            <div className="form-group mt-16">
              <label className="form-label">Note interne</label>
              <textarea
                className="form-control"
                rows={3}
                value={fields.note}
                onChange={e => setField('note', e.target.value)}
                placeholder="Conditions de paiement, remarques..."
              />
            </div>

            {errors.submit && (
              <div className="form-error-box">{errors.submit}</div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer la facture')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
