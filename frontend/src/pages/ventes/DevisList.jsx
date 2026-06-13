import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchDevis,
  genererPdfDevis,
  convertirDevisEnBC,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import DevisForm from './DevisForm'

const STATUT_META = {
  brouillon: { label: 'Brouillon', bg: '#f1f5f9', color: '#64748b' },
  envoye:    { label: 'Envoyé',    bg: '#dbeafe', color: '#1d4ed8' },
  accepte:   { label: 'Accepté',   bg: '#dcfce7', color: '#15803d' },
  refuse:    { label: 'Refusé',    bg: '#fee2e2', color: '#b91c1c' },
  expire:    { label: 'Expiré',    bg: '#fef3c7', color: '#b45309' },
}

function openPdfBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.target = '_blank'
  a.rel = 'noopener'
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

export default function DevisList() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { devis, loading, error } = useSelector(s => s.ventes)
  const role = useSelector(s => s.auth.role)
  const canDelete = role === 'admin'  // règle existante : destroy = admin

  const [showForm, setShowForm]       = useState(false)
  const [editDevis, setEditDevis]     = useState(null)
  const [convertingId, setConvertingId] = useState(null)
  const [factureGenId, setFactureGenId] = useState(null) // devis id en cours de facturation
  const [pdfGenerating, setPdfGenerating] = useState({}) // id → true
  const [pdfDownloading, setPdfDownloading] = useState({}) // id → true

  // ── Choix du format PDF (parité simulateur) ──
  const [pdfTarget, setPdfTarget] = useState(null) // devis ciblé par la modale
  const [pdfMode, setPdfMode] = useState('full')
  const [showMonthly, setShowMonthly] = useState(true)
  const [devisFinal, setDevisFinal] = useState(false)
  const [paymentMode, setPaymentMode] = useState('standard')
  const [customAcompte, setCustomAcompte] = useState('')
  const [includeEtude, setIncludeEtude] = useState(false)

  const openPdfModal = (d) => {
    setPdfTarget(d)
    setPdfMode('full')
    setShowMonthly(true)
    setDevisFinal(false)
    setPaymentMode('standard')
    setCustomAcompte('')
    setIncludeEtude(false)
  }

  useEffect(() => { dispatch(fetchDevis()) }, [dispatch])

  // Création ET édition passent par la page générateur solaire (l'ancien
  // modal DevisForm est conservé mais n'est plus le chemin d'édition).
  const openNew  = () => navigate('/ventes/devis/nouveau')
  const openEdit = (d) => {
    if (d.statut !== 'brouillon') return
    navigate(`/ventes/devis/nouveau?edit=${d.id}`)
  }
  const closeForm = () => { setShowForm(false); setEditDevis(null) }
  const onSaved  = () => dispatch(fetchDevis())

  const [deletingId, setDeletingId] = useState(null)
  const handleDelete = async (d) => {
    if (!window.confirm(`Supprimer définitivement le devis ${d.reference} ?`)) return
    setDeletingId(d.id)
    try {
      await ventesApi.deleteDevis(d.id)
      dispatch(fetchDevis())
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Suppression impossible.')
    } finally {
      setDeletingId(null)
    }
  }

  const handleConvertBC = async (d) => {
    if (!window.confirm(`Convertir « ${d.reference} » en bon de commande ?`)) return
    setConvertingId(d.id)
    try {
      await dispatch(convertirDevisEnBC(d.id)).unwrap()
      dispatch(fetchDevis())
    } catch (err) {
      alert(err?.detail ?? JSON.stringify(err))
    } finally {
      setConvertingId(null)
    }
  }

  const handleGenererFacture = async (d) => {
    setFactureGenId(d.id)
    try {
      const res = await ventesApi.genererFacture(d.id)
      const f = res.data
      alert(`${f.type_facture_display ?? 'Facture'} ${f.reference} créée.`)
      dispatch(fetchDevis())
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Génération de facture impossible.')
    } finally {
      setFactureGenId(null)
    }
  }

  const handleGenererPdf = async (d) => {
    const options = {
      pdf_mode: pdfMode,
      show_monthly: showMonthly,
      devis_final: devisFinal,
      payment_mode: paymentMode,
      custom_acompte: (devisFinal && paymentMode === 'custom' && customAcompte !== '')
        ? parseFloat(customAcompte) : null,
      include_etude: pdfMode === 'full' && includeEtude,
    }
    setPdfTarget(null)
    setPdfGenerating(prev => ({ ...prev, [d.id]: true }))
    try {
      await dispatch(genererPdfDevis({ id: d.id, options })).unwrap()
      // Poll until fichier_pdf is ready (max 30s, every 2s)
      let attempts = 0
      const poll = async () => {
        if (attempts++ > 15) {
          alert('La génération PDF prend plus de temps que prévu. Réessayez dans quelques instants.')
          return
        }
        try {
          const res = await ventesApi.getDevisById(d.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchDevis())
          } else {
            setTimeout(poll, 2000)
          }
        } catch {
          // ignore poll errors
        }
      }
      setTimeout(poll, 2000)
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors de la génération PDF.')
    } finally {
      setPdfGenerating(prev => ({ ...prev, [d.id]: false }))
    }
  }

  const handleTelechargerPdf = async (d) => {
    setPdfDownloading(prev => ({ ...prev, [d.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfDevis(d.id)
      openPdfBlob(res.data, `${d.reference}.pdf`)
    } catch {
      alert('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [d.id]: false }))
    }
  }

  if (loading) return <p className="page-loading">Chargement des devis...</p>
  if (error)   return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      <div className="page-header">
        <h2>Devis</h2>
        <button className="btn btn-primary" onClick={openNew}>+ Nouveau devis</button>
      </div>

      {showForm && (
        <DevisForm devis={editDevis} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Modale de génération PDF : formats du simulateur ── */}
      {pdfTarget && (
        <div className="modal-overlay" onClick={() => setPdfTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">📄 Générer le PDF — {pdfTarget.reference}</h3>
              <button type="button" className="modal-close" onClick={() => setPdfTarget(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label className="form-label">Format</label>
                <div className="pdf-format-options">
                  <label className={`gen-radio${pdfMode === 'full' ? ' selected' : ''}`}>
                    <input type="radio" name="pdf-mode" value="full"
                           checked={pdfMode === 'full'} onChange={() => setPdfMode('full')} />
                    Devis premium (3 pages — options, analyse, garanties)
                  </label>
                  <label className={`gen-radio${pdfMode === 'onepage' ? ' selected' : ''}`}>
                    <input type="radio" name="pdf-mode" value="onepage"
                           checked={pdfMode === 'onepage'} onChange={() => setPdfMode('onepage')} />
                    Devis une page (liste produits uniquement, sans graphiques)
                  </label>
                </div>
              </div>

              {pdfMode === 'full' && (
                <label className="pdf-toggle">
                  <input type="checkbox" checked={showMonthly}
                         onChange={e => setShowMonthly(e.target.checked)} />
                  <span>Économies mensuelles <small>(graphique mensuel page 2)</small></span>
                </label>
              )}

              {pdfMode === 'full' && (
                <label className="pdf-toggle">
                  <input type="checkbox" checked={includeEtude}
                         onChange={e => setIncludeEtude(e.target.checked)} />
                  <span>Inclure l'étude <small>(page autoconsommation — devis industriel)</small></span>
                </label>
              )}

              <label className="pdf-toggle">
                <input type="checkbox" checked={devisFinal}
                       onChange={e => setDevisFinal(e.target.checked)} />
                <span>Devis Final <small>(ajoute modalités de paiement + RIB)</small></span>
              </label>

              {devisFinal && (
                <div className="pdf-payment-box">
                  <label className="pdf-toggle">
                    <input type="radio" name="payment-mode" value="standard"
                           checked={paymentMode === 'standard'}
                           onChange={() => setPaymentMode('standard')} />
                    <span>Standard (30/60/10)</span>
                  </label>
                  <label className="pdf-toggle">
                    <input type="radio" name="payment-mode" value="custom"
                           checked={paymentMode === 'custom'}
                           onChange={() => setPaymentMode('custom')} />
                    <span>Acompte personnalisé</span>
                  </label>
                  {paymentMode === 'custom' && (
                    <div className="form-group" style={{ marginTop: 8 }}>
                      <label className="form-label">Montant acompte (MAD)</label>
                      <input type="number" min="0" step="any" className="form-control"
                             value={customAcompte}
                             onChange={e => setCustomAcompte(e.target.value)} />
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-outline" onClick={() => setPdfTarget(null)}>
                Annuler
              </button>
              <button type="button" className="btn btn-primary"
                      onClick={() => handleGenererPdf(pdfTarget)}>
                📄 Générer
              </button>
            </div>
          </div>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Référence</th>
            <th>Client</th>
            <th>Créé le</th>
            <th>Validité</th>
            <th className="ta-right">Total TTC</th>
            <th>Statut</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {devis.map(d => {
            const meta = STATUT_META[d.statut] ?? STATUT_META.brouillon
            const isGenerating = pdfGenerating[d.id]
            const isDownloading = pdfDownloading[d.id]
            return (
              <tr key={d.id}>
                <td><strong>{d.reference}</strong></td>
                <td data-label="Client">
                  {d.client_nom ?? '—'}
                  {d.lead && (
                    <div>
                      <button
                        type="button"
                        title="Ouvrir le lead lié"
                        onClick={() => navigate(`/crm/leads?lead=${d.lead}`)}
                        style={{
                          background: '#fdf3e0', color: '#92400e',
                          border: '1px solid #f5d9a8', borderRadius: 10,
                          padding: '1px 8px', fontSize: '0.68rem',
                          fontWeight: 600, cursor: 'pointer', marginTop: 3,
                        }}
                      >
                        ↗ {d.lead_nom ?? 'Lead'}
                      </button>
                    </div>
                  )}
                </td>
                <td data-label="Créé le">{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                <td className="m-hide">
                  {d.date_validite
                    ? new Date(d.date_validite).toLocaleDateString('fr-FR')
                    : '—'}
                </td>
                <td className="ta-right" data-label="Total TTC">
                  {(d.total_affiche ?? d.total_ttc) != null
                    ? `${parseFloat(d.total_affiche ?? d.total_ttc).toFixed(2)} DH`
                    : '—'}
                  {d.nb_options === 2 && (
                    <span className="badge" title="Devis à deux options — total affiché : option 1 (sans batterie), remise incluse"
                          style={{ background: '#fdf3e0', color: '#92400e', marginLeft: 6, fontSize: '0.65rem' }}>
                      2 options
                    </span>
                  )}
                  {d.solde && (
                    <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 3 }}>
                      Facturé {d.solde.facture} / Payé {d.solde.paye} / Restant {d.solde.restant} MAD
                    </div>
                  )}
                </td>
                <td data-label="Statut">
                  <span className="badge" style={{ background: meta.bg, color: meta.color }}>
                    {meta.label}
                  </span>
                </td>
                <td>
                  <div className="actions-cell">
                    <button
                      className="btn btn-sm btn-outline"
                      onClick={() => openEdit(d)}
                      disabled={d.statut !== 'brouillon'}
                      title={d.statut === 'brouillon'
                        ? 'Ouvrir dans le générateur'
                        : 'Devis envoyé/clôturé — non modifiable (dupliquez-le depuis le générateur si besoin)'}
                    >
                      Éditer
                    </button>
                    {canDelete && (
                      <button
                        className="btn btn-sm btn-outline btn-danger-outline"
                        onClick={() => handleDelete(d)}
                        disabled={deletingId === d.id}
                        title="Supprimer ce devis"
                      >
                        {deletingId === d.id ? '...' : 'Supprimer'}
                      </button>
                    )}

                    <button
                      className="btn btn-sm btn-outline"
                      onClick={() => openPdfModal(d)}
                      disabled={isGenerating}
                      title="Générer le PDF (choix du format)"
                    >
                      {isGenerating ? 'PDF...' : 'PDF'}
                    </button>
                    {d.fichier_pdf && (
                      <button
                        className="btn btn-sm btn-success"
                        onClick={() => handleTelechargerPdf(d)}
                        disabled={isDownloading}
                        title="Télécharger le dernier PDF généré"
                      >
                        {isDownloading ? '...' : '↓'}
                      </button>
                    )}

                    {d.statut === 'accepte' && (
                      <button
                        className="btn btn-sm btn-success"
                        onClick={() => handleConvertBC(d)}
                        disabled={convertingId === d.id}
                        title="Convertir en bon de commande"
                      >
                        {convertingId === d.id ? '...' : '→ BC'}
                      </button>
                    )}

                    {/* « Générer facture » TOUJOURS visible, pour montrer que
                        c'est ici qu'un devis devient des factures. Désactivé
                        tant que le devis n'est pas « Accepté », avec un indice
                        VISIBLE (pas seulement au survol → lisible sur mobile). */}
                    {d.statut !== 'accepte' ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <button className="btn btn-sm btn-outline" disabled>
                          Générer facture
                        </button>
                        <span style={{ fontSize: '0.68rem', color: '#64748b', maxWidth: 190, lineHeight: 1.2 }}>
                          Passez le devis en « Accepté » pour générer les factures.
                        </span>
                      </div>
                    ) : d.solde && d.solde.tranches_facturees >= d.solde.tranches_total ? (
                      <button
                        className="btn btn-sm btn-outline"
                        disabled
                        title="Toutes les tranches ont été facturées"
                      >
                        Échéancier complet
                      </button>
                    ) : (
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => handleGenererFacture(d)}
                        disabled={factureGenId === d.id}
                        title="Générer la prochaine tranche de facture"
                      >
                        {factureGenId === d.id ? '...' : 'Générer facture'}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {devis.length === 0 && !loading && (
        <p className="empty-state">Aucun devis. Créez votre premier devis.</p>
      )}
    </div>
  )
}
