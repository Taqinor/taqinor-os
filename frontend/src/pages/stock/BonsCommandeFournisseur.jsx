import { useEffect, useMemo, useState } from 'react'
import stockApi from '../../api/stockApi'
import ProduitPicker from '../../components/ProduitPicker'
import { downloadBlob } from '../../utils/downloadBlob'
import {
  BCF_STATUTS,
  bcfStatutLabel,
  totalAchat,
  quantiteRestante,
  buildReceptionPayload,
} from '../../features/stock/procurement'

// Page de gestion des bons de commande FOURNISSEUR (achats — N11).
// Le prix d'ACHAT est INTERNE : cette page n'est jamais un document client.

const STATUT_COLORS = {
  brouillon: '#64748b',
  envoye: '#2563eb',
  recu: '#16a34a',
  annule: '#b91c1c',
}

const fmtMad = (v) => {
  const n = Number(v) || 0
  return `${n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`
}
const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

function StatutBadge({ statut }) {
  const c = STATUT_COLORS[statut] ?? '#64748b'
  return (
    <span className="badge" style={{
      background: `${c}22`, color: c, padding: '2px 8px',
      borderRadius: 6, fontSize: 12, whiteSpace: 'nowrap', fontWeight: 600,
    }}>
      {bcfStatutLabel(statut)}
    </span>
  )
}

// ── Modal de création / consultation / réception d'un BCF ──
function BcfDetail({ bcf, fournisseurs, produits, onClose, onSaved }) {
  const isNew = !bcf?.id
  const statut = bcf?.statut ?? 'brouillon'
  const editableLignes = isNew || statut === 'brouillon'

  const [fournisseur, setFournisseur] = useState(bcf?.fournisseur ?? '')
  const [dateCommande, setDateCommande] = useState(bcf?.date_commande ?? '')
  const [note, setNote] = useState(bcf?.note ?? '')
  const [lignes, setLignes] = useState(
    (bcf?.lignes ?? []).map((l) => ({ ...l })))
  // Saisies de réception : { [ligneId]: quantité }
  const [receptions, setReceptions] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const total = useMemo(() => totalAchat(lignes), [lignes])

  const setLigne = (idx, patch) =>
    setLignes((ls) => ls.map((l, i) => (i === idx ? { ...l, ...patch } : l)))
  const addLigne = () =>
    setLignes((ls) => [...ls, { produit: '', quantite: 1, prix_achat_unitaire: '' }])
  const removeLigne = (idx) =>
    setLignes((ls) => ls.filter((_, i) => i !== idx))

  const buildPayload = () => ({
    fournisseur: fournisseur || null,
    date_commande: dateCommande || null,
    note: note || null,
    lignes: lignes
      .filter((l) => l.produit)
      .map((l) => ({
        produit: l.produit,
        quantite: Number(l.quantite) || 0,
        prix_achat_unitaire: l.prix_achat_unitaire === '' || l.prix_achat_unitaire == null
          ? 0 : Number(l.prix_achat_unitaire),
      })),
  })

  const save = async () => {
    setError(null)
    const payload = buildPayload()
    if (!payload.fournisseur) { setError('Choisissez un fournisseur.'); return }
    if (payload.lignes.length === 0) { setError('Ajoutez au moins une ligne.'); return }
    setBusy(true)
    try {
      if (isNew) await stockApi.createBonCommandeFournisseur(payload)
      else await stockApi.updateBonCommandeFournisseur(bcf.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally { setBusy(false) }
  }

  const envoyer = async () => {
    setBusy(true); setError(null)
    try {
      // En brouillon, on enregistre d'abord d'éventuelles modifications.
      if (!isNew) await stockApi.updateBonCommandeFournisseur(bcf.id, buildPayload())
      let id = bcf?.id
      if (isNew) {
        const r = await stockApi.createBonCommandeFournisseur(buildPayload())
        id = r.data.id
      }
      await stockApi.envoyerBcf(id)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally { setBusy(false) }
  }

  const recevoir = async () => {
    const payload = buildReceptionPayload(bcf.lignes, receptions)
    if (payload.length === 0) { setError('Saisissez au moins une quantité à recevoir.'); return }
    setBusy(true); setError(null)
    try {
      await stockApi.recevoirBcf(bcf.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally { setBusy(false) }
  }

  const annuler = async () => {
    if (!window.confirm('Annuler ce bon de commande ?')) return
    setBusy(true); setError(null)
    try {
      await stockApi.annulerBcf(bcf.id)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally { setBusy(false) }
  }

  const telechargerPdf = async () => {
    try {
      const r = await stockApi.bcfPdf(bcf.id)
      downloadBlob(r.data, `${bcf.reference ?? 'BCF'}.pdf`)
    } catch { alert('PDF indisponible.') }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            {isNew ? 'Nouveau bon de commande fournisseur'
              : `Bon de commande — ${bcf.reference ?? ''}`}
            {!isNew && <span style={{ marginLeft: 8 }}><StatutBadge statut={statut} /></span>}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <p className="gen-hint" style={{ marginTop: 0 }}>
            Document <strong>interne</strong> : les prix d'achat n'apparaissent
            jamais sur un document client.
          </p>

          <div className="form-row">
            <div className="form-group fg-grow">
              <label className="form-label">Fournisseur</label>
              <select className="form-select" value={fournisseur}
                      disabled={!editableLignes}
                      onChange={(e) => setFournisseur(e.target.value)}>
                <option value="">— Choisir un fournisseur —</option>
                {fournisseurs.map((f) => (
                  <option key={f.id} value={f.id}>{f.nom}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Date de commande</label>
              <input type="date" className="form-control" value={dateCommande ?? ''}
                     disabled={!editableLignes}
                     onChange={(e) => setDateCommande(e.target.value)} />
            </div>
          </div>

          {/* ── Lignes ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">📦 Lignes</span>
              {editableLignes && (
                <button type="button" className="btn btn-sm btn-outline" onClick={addLigne}>
                  + Ajouter une ligne
                </button>
              )}
            </div>
            <table className="lines-table">
              <thead>
                <tr>
                  <th style={{ minWidth: 220 }}>Article</th>
                  <th>Quantité</th>
                  <th>Prix achat U. (interne)</th>
                  <th>Total HT</th>
                  {!isNew && <th>Reçu</th>}
                  {!isNew && statut === 'envoye' && <th>À recevoir</th>}
                  {editableLignes && <th></th>}
                </tr>
              </thead>
              <tbody>
                {lignes.length === 0 && (
                  <tr><td colSpan={7} className="gen-hint">Aucune ligne.</td></tr>
                )}
                {lignes.map((l, idx) => {
                  const lineTotal = (Number(l.quantite) || 0) * (Number(l.prix_achat_unitaire) || 0)
                  const restante = quantiteRestante(l)
                  return (
                    <tr key={l.id ?? `new-${idx}`}>
                      <td>
                        {editableLignes ? (
                          <ProduitPicker produits={produits} value={l.produit}
                                         onChange={(v) => setLigne(idx, { produit: v })} />
                        ) : (
                          <span>{l.produit_nom ?? '—'}{l.produit_sku ? ` (${l.produit_sku})` : ''}</span>
                        )}
                      </td>
                      <td>
                        {editableLignes ? (
                          <input type="number" step="any" className="form-control"
                                 style={{ width: 90 }} value={l.quantite ?? ''}
                                 onChange={(e) => setLigne(idx, { quantite: e.target.value })} />
                        ) : l.quantite}
                      </td>
                      <td>
                        {editableLignes ? (
                          <input type="number" step="any" className="form-control"
                                 style={{ width: 130 }} value={l.prix_achat_unitaire ?? ''}
                                 onChange={(e) => setLigne(idx, { prix_achat_unitaire: e.target.value })} />
                        ) : fmtMad(l.prix_achat_unitaire)}
                      </td>
                      <td>{fmtMad(lineTotal)}</td>
                      {!isNew && <td>{l.quantite_recue ?? 0}</td>}
                      {!isNew && statut === 'envoye' && (
                        <td>
                          {restante > 0 ? (
                            <input type="number" min="0" max={restante} className="form-control"
                                   style={{ width: 90 }}
                                   placeholder={`/${restante}`}
                                   value={receptions[l.id] ?? ''}
                                   onChange={(e) => setReceptions((r) => ({ ...r, [l.id]: e.target.value }))} />
                          ) : <span className="gen-hint">soldée</span>}
                        </td>
                      )}
                      {editableLignes && (
                        <td>
                          <button type="button" className="btn btn-sm btn-outline"
                                  onClick={() => removeLigne(idx)}>✕</button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <div style={{ textAlign: 'right', marginTop: 8, fontWeight: 700 }}>
              Total achat HT (interne) : {fmtMad(total)}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Note</label>
            <textarea className="form-control" rows={2} value={note ?? ''}
                      disabled={!editableLignes && statut !== 'envoye'}
                      onChange={(e) => setNote(e.target.value)} />
          </div>

          {error && <div className="form-error-box" role="alert">{error}</div>}
        </div>

        <div className="modal-footer">
          {!isNew && statut !== 'annule' && (
            <button type="button" className="btn btn-outline" onClick={telechargerPdf}>
              📄 PDF (interne)
            </button>
          )}
          {!isNew && (statut === 'brouillon' || statut === 'envoye') && (
            <button type="button" className="btn btn-danger" disabled={busy} onClick={annuler}>
              Annuler le BC
            </button>
          )}
          <button type="button" className="btn btn-outline" onClick={onClose}>Fermer</button>
          {editableLignes && (
            <>
              <button type="button" className="btn btn-outline" disabled={busy} onClick={save}>
                {busy ? '…' : 'Enregistrer'}
              </button>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={envoyer}>
                {busy ? '…' : 'Envoyer au fournisseur'}
              </button>
            </>
          )}
          {!isNew && statut === 'envoye' && (
            <button type="button" className="btn btn-success" disabled={busy} onClick={recevoir}>
              {busy ? '…' : 'Recevoir les quantités'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function BonsCommandeFournisseur() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [fournisseurs, setFournisseurs] = useState([])
  const [produits, setProduits] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState(null) // bcf object or {} for new

  // setState arrive dans les callbacks asynchrones (jamais synchrone dans
  // l'effet) : l'état initial loading=true couvre le premier chargement.
  const reload = () => {
    stockApi.getBonsCommandeFournisseur()
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    stockApi.getFournisseurs().then((r) => setFournisseurs(r.data?.results ?? r.data ?? [])).catch(() => {})
    stockApi.getProduits({ page_size: 1000 }).then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return items.filter((b) => {
      if (statutFiltre && b.statut !== statutFiltre) return false
      if (!needle) return true
      return (b.reference ?? '').toLowerCase().includes(needle)
        || (b.fournisseur_nom ?? '').toLowerCase().includes(needle)
    })
  }, [items, statutFiltre, q])

  // Ouvre le détail en rechargeant la version complète (lignes à jour).
  const openBcf = async (b) => {
    try {
      const r = await stockApi.getBonCommandeFournisseur(b.id)
      setSelected(r.data)
    } catch { setSelected(b) }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Bons de commande fournisseur</h1>
        <div className="page-subtitle">{rows.length} bon(s) de commande</div>
        <button type="button" className="btn btn-sm btn-primary"
                onClick={() => setSelected({})}>
          + Nouveau bon de commande
        </button>
      </div>

      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="form-control" placeholder="Rechercher (référence, fournisseur)…"
               value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: '1 1 220px' }} />
        <select className="form-select" value={statutFiltre} onChange={(e) => setStatutFiltre(e.target.value)}>
          <option value="">Tous les statuts</option>
          {Object.entries(BCF_STATUTS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        {(q || statutFiltre) && (
          <button type="button" className="btn btn-sm btn-outline"
                  onClick={() => { setQ(''); setStatutFiltre('') }}>Réinitialiser</button>
        )}
      </div>

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="gen-hint">Aucun bon de commande fournisseur. Créez-en un avec « Nouveau bon de commande »
          ou depuis le besoin matériel d'un chantier.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Référence</th>
                <th>Fournisseur</th>
                <th>Statut</th>
                <th>Date</th>
                <th>Lignes</th>
                <th>Total achat HT (interne)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr key={b.id} onClick={() => openBcf(b)} style={{ cursor: 'pointer' }}>
                  <td>{b.reference}</td>
                  <td>{b.fournisseur_nom ?? '—'}</td>
                  <td><StatutBadge statut={b.statut} /></td>
                  <td>{fmtDateFR(b.date_commande)}</td>
                  <td>{(b.lignes ?? []).length}</td>
                  <td>{fmtMad(b.total_achat)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <BcfDetail bcf={selected} fournisseurs={fournisseurs} produits={produits}
                   onClose={() => setSelected(null)} onSaved={reload} />
      )}
    </div>
  )
}
