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

  const [showForm, setShowForm]       = useState(false)
  const [editDevis, setEditDevis]     = useState(null)
  const [convertingId, setConvertingId] = useState(null)
  const [pdfGenerating, setPdfGenerating] = useState({}) // id → true
  const [pdfDownloading, setPdfDownloading] = useState({}) // id → true

  useEffect(() => { dispatch(fetchDevis()) }, [dispatch])

  // Création : nouvelle page générateur solaire. L'ancien formulaire modal
  // (DevisForm) ne sert plus qu'à l'édition d'un devis existant.
  const openNew  = () => navigate('/ventes/devis/nouveau')
  const openEdit = (d) => { setEditDevis(d);   setShowForm(true) }
  const closeForm = () => { setShowForm(false); setEditDevis(null) }
  const onSaved  = () => dispatch(fetchDevis())

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

  const handleGenererPdf = async (d) => {
    setPdfGenerating(prev => ({ ...prev, [d.id]: true }))
    try {
      await dispatch(genererPdfDevis(d.id)).unwrap()
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
                <td>{d.client_nom ?? '—'}</td>
                <td>{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                <td>
                  {d.date_validite
                    ? new Date(d.date_validite).toLocaleDateString('fr-FR')
                    : '—'}
                </td>
                <td className="ta-right">
                  {d.total_ttc != null
                    ? `${parseFloat(d.total_ttc).toFixed(2)} DH`
                    : '—'}
                </td>
                <td>
                  <span className="badge" style={{ background: meta.bg, color: meta.color }}>
                    {meta.label}
                  </span>
                </td>
                <td>
                  <div className="actions-cell">
                    <button className="btn btn-sm btn-outline" onClick={() => openEdit(d)}>
                      Éditer
                    </button>

                    {d.fichier_pdf ? (
                      <button
                        className="btn btn-sm btn-success"
                        onClick={() => handleTelechargerPdf(d)}
                        disabled={isDownloading}
                        title="Télécharger le PDF"
                      >
                        {isDownloading ? '...' : '↓ PDF'}
                      </button>
                    ) : (
                      <button
                        className="btn btn-sm btn-outline"
                        onClick={() => handleGenererPdf(d)}
                        disabled={isGenerating}
                        title="Générer le PDF"
                      >
                        {isGenerating ? 'PDF...' : 'PDF'}
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
