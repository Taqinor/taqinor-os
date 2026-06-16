import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchFactures,
  emettreFacture,
  marquerPayeeFacture,
  annulerFacture,
  genererPdfFacture,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import ExportButton from '../../components/ExportButton'
import FactureForm from './FactureForm'

const STATUT_META = {
  brouillon: { label: 'Brouillon', bg: '#f1f5f9', color: '#64748b' },
  emise:     { label: 'Émise',     bg: '#dbeafe', color: '#1d4ed8' },
  payee:     { label: 'Payée',     bg: '#dcfce7', color: '#15803d' },
  en_retard: { label: 'En retard', bg: '#fee2e2', color: '#b91c1c' },
  annulee:   { label: 'Annulée',   bg: '#f1f5f9', color: '#94a3b8' },
}

const TABS = [
  { key: 'toutes',    label: 'Toutes' },
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'emise',     label: 'Émises' },
  { key: 'overdue',   label: 'En retard' },
  { key: 'payee',     label: 'Payées' },
  { key: 'annulee',   label: 'Annulées' },
]

const MODES_PAIEMENT = [
  { value: 'especes',     label: 'Espèces' },
  { value: 'virement',    label: 'Virement' },
  { value: 'cheque',      label: 'Chèque' },
  { value: 'carte',       label: 'Carte' },
  { value: 'prelevement', label: 'Prélèvement' },
  { value: 'autre',       label: 'Autre' },
]

const today = new Date().toISOString().slice(0, 10)
const isOverdue = f =>
  f.is_overdue ||
  (f.statut === 'emise' && f.date_echeance && f.date_echeance < today)

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

export default function FactureList() {
  const dispatch = useDispatch()
  const { factures, loading, error } = useSelector(s => s.ventes)
  const isAdmin = useSelector(s => s.auth.role) === 'admin'

  const creerAvoir = async (f) => {
    const motif = window.prompt(
      `Créer un avoir TOTAL pour la facture ${f.reference} ?\n`
      + 'Motif (optionnel) :', '')
    if (motif === null) return
    try {
      await ventesApi.creerAvoir(f.id, { motif })
      dispatch(fetchFactures())
      alert('Avoir créé. Retrouvez-le dans Ventes → Avoirs.')
    } catch (err) {
      alert(err?.response?.data?.detail ?? "Création de l'avoir impossible.")
    }
  }

  const [showForm, setShowForm]       = useState(false)
  const [editFacture, setEditFacture] = useState(null)
  const [activeTab, setActiveTab]     = useState('toutes')
  const [search, setSearch]           = useState('')
  const [actionId, setActionId]       = useState(null)
  const [pdfGenerating, setPdfGenerating] = useState({})
  const [pdfDownloading, setPdfDownloading] = useState({})
  const [waBusyId, setWaBusyId] = useState(null)

  // ── Enregistrement de paiement ──
  const [payTarget, setPayTarget] = useState(null) // facture ciblée
  const [paySaving, setPaySaving] = useState(false)
  const [payMontant, setPayMontant] = useState('')
  const [payDate, setPayDate] = useState(today)
  const [payMode, setPayMode] = useState('virement')
  const [payReference, setPayReference] = useState('')

  const openPayModal = (f) => {
    setPayTarget(f)
    setPayMontant(f.montant_du ?? '')
    setPayDate(today)
    setPayMode('virement')
    setPayReference('')
  }

  const handleEnregistrerPaiement = async (e) => {
    e.preventDefault()
    if (!payTarget) return
    setPaySaving(true)
    try {
      await ventesApi.enregistrerPaiement(payTarget.id, {
        montant: parseFloat(payMontant),
        date_paiement: payDate,
        mode: payMode,
        reference: payReference || undefined,
      })
      setPayTarget(null)
      dispatch(fetchFactures())
      alert('Paiement enregistré.')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Enregistrement du paiement impossible.')
    } finally {
      setPaySaving(false)
    }
  }

  useEffect(() => { dispatch(fetchFactures()) }, [dispatch])

  const filtered = useMemo(() => {
    let list = factures
    if (activeTab === 'overdue') {
      list = list.filter(isOverdue)
    } else if (activeTab !== 'toutes') {
      list = list.filter(f => f.statut === activeTab)
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(f =>
        f.reference?.toLowerCase().includes(q) ||
        (f.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [factures, activeTab, search])

  const counts = useMemo(() => ({
    toutes:    factures.length,
    brouillon: factures.filter(f => f.statut === 'brouillon').length,
    emise:     factures.filter(f => f.statut === 'emise' && !isOverdue(f)).length,
    overdue:   factures.filter(isOverdue).length,
    payee:     factures.filter(f => f.statut === 'payee').length,
    annulee:   factures.filter(f => f.statut === 'annulee').length,
  }), [factures])

  const openNew   = () => { setEditFacture(null); setShowForm(true) }
  const openEdit  = f  => { setEditFacture(f);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);   setEditFacture(null) }
  const onSaved   = () => dispatch(fetchFactures())

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

  const handleGenererPdf = async (f) => {
    setPdfGenerating(prev => ({ ...prev, [f.id]: true }))
    try {
      await dispatch(genererPdfFacture(f.id)).unwrap()
      let attempts = 0
      const poll = async () => {
        if (attempts++ > 15) {
          alert('La génération PDF prend plus de temps que prévu. Réessayez dans quelques instants.')
          return
        }
        try {
          const res = await ventesApi.getFacture(f.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchFactures())
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
      setPdfGenerating(prev => ({ ...prev, [f.id]: false }))
    }
  }

  const handleTelechargerPdf = async (f) => {
    setPdfDownloading(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfFacture(f.id)
      openPdfBlob(res.data, `${f.reference}.pdf`)
    } catch {
      alert('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // Envoyer par WhatsApp : ouvre WhatsApp avec le message + lien public (PDF
  // client) pré-rempli ; le commercial appuie lui-même sur Envoyer.
  const handleWhatsApp = async (f, modele = 'facture') => {
    setWaBusyId(f.id)
    try {
      const res = await ventesApi.whatsappFacture(f.id, { modele })
      if (res.data?.wa_url) window.open(res.data.wa_url, '_blank', 'noopener')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusyId(null)
    }
  }

  if (loading) return <p className="page-loading">Chargement des factures...</p>
  if (error)   return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Factures
          {factures.length > 0 && (
            <span className="count-badge">{factures.length}</span>
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
          <ExportButton
            fetcher={ventesApi.exportFactures}
            params={search.trim() ? { search: search.trim() } : {}}
            filename="factures.xlsx"
          />
          <button className="btn btn-primary" onClick={openNew}>
            + Nouvelle facture
          </button>
        </div>
      </div>

      {showForm && (
        <FactureForm facture={editFacture} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Modale d'enregistrement de paiement ── */}
      {payTarget && (
        <div className="modal-overlay" onClick={() => setPayTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <form onSubmit={handleEnregistrerPaiement}>
              <div className="modal-header">
                <h3 className="modal-title">Enregistrer un paiement — {payTarget.reference}</h3>
                <button type="button" className="modal-close" onClick={() => setPayTarget(null)}>✕</button>
              </div>
              <div className="modal-body">
                <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 0 }}>
                  Payé {payTarget.montant_paye} / Dû {payTarget.montant_du} MAD
                </p>
                <div className="form-group">
                  <label className="form-label">Montant (MAD)</label>
                  <input type="number" min="0" step="any" className="form-control" required
                         value={payMontant} onChange={e => setPayMontant(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Date de paiement</label>
                  <input type="date" className="form-control" required
                         value={payDate} onChange={e => setPayDate(e.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">Mode</label>
                  <select className="form-control" value={payMode} onChange={e => setPayMode(e.target.value)}>
                    {MODES_PAIEMENT.map(m => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Référence (optionnel)</label>
                  <input type="text" className="form-control"
                         value={payReference} onChange={e => setPayReference(e.target.value)} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setPayTarget(null)}>
                  Annuler
                </button>
                <button type="submit" className="btn btn-primary" disabled={paySaving}>
                  {paySaving ? '...' : 'Enregistrer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="status-tabs">
        {TABS.map(t => (
          <button
            key={t.key}
            className={`status-tab${activeTab === t.key ? ' active' : ''}${t.key === 'overdue' && counts.overdue > 0 ? ' overdue' : ''}`}
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
            <th>Émission</th>
            <th>Échéance</th>
            <th className="ta-right">Total TTC</th>
            <th>Statut</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map(f => {
            const overdue = isOverdue(f)
            const meta = overdue && f.statut === 'emise'
              ? STATUT_META.en_retard
              : (STATUT_META[f.statut] ?? STATUT_META.brouillon)
            const busy = actionId === f.id
            const isGenerating = pdfGenerating[f.id]
            const isDownloading = pdfDownloading[f.id]

            return (
              <tr key={f.id} className={overdue ? 'row-overdue' : ''}>
                <td>
                  <strong>{f.reference}</strong>
                  {f.type_facture_display && (
                    <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 2 }}>
                      {f.type_facture_display}
                    </div>
                  )}
                </td>
                <td>{f.client_nom ?? '—'}</td>
                <td>{new Date(f.date_emission).toLocaleDateString('fr-FR')}</td>
                <td>
                  <span className={overdue ? 'text-danger' : ''}>
                    {f.date_echeance
                      ? new Date(f.date_echeance).toLocaleDateString('fr-FR')
                      : '—'}
                  </span>
                </td>
                <td className="ta-right">
                  {f.total_ttc != null
                    ? `${parseFloat(f.total_ttc).toFixed(2)} DH`
                    : '—'}
                  {(f.montant_paye != null || f.montant_du != null) && (
                    <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: 2 }}>
                      Payé {f.montant_paye} / Dû {f.montant_du} MAD
                    </div>
                  )}
                </td>
                <td>
                  <span className="badge" style={{ background: meta.bg, color: meta.color }}>
                    {meta.label}
                  </span>
                </td>
                <td>
                  <div className="actions-cell">
                    {f.statut === 'brouillon' && (
                      <button className="btn btn-sm btn-outline" onClick={() => openEdit(f)}>
                        Éditer
                      </button>
                    )}
                    {f.statut === 'brouillon' && (
                      <button
                        className="btn btn-sm btn-primary"
                        disabled={busy}
                        onClick={() => doAction(emettreFacture, f.id)}
                      >
                        {busy ? '...' : 'Émettre'}
                      </button>
                    )}
                    {(f.statut === 'emise' || f.statut === 'en_retard' || overdue) && (
                      <button
                        className="btn btn-sm btn-success"
                        disabled={busy}
                        onClick={() => doAction(marquerPayeeFacture, f.id, `Marquer la facture ${f.reference} comme payée ?`)}
                      >
                        {busy ? '...' : '✓ Payée'}
                      </button>
                    )}
                    {parseFloat(f.montant_du ?? 0) > 0 && f.statut !== 'annulee' && (
                      <button
                        className="btn btn-sm btn-outline"
                        onClick={() => openPayModal(f)}
                        title="Enregistrer un paiement"
                      >
                        Enregistrer paiement
                      </button>
                    )}
                    {f.statut !== 'payee' && f.statut !== 'annulee' && (
                      <button
                        className="btn btn-sm btn-outline"
                        disabled={busy}
                        onClick={() => doAction(annulerFacture, f.id, `Annuler la facture ${f.reference} ?`)}
                      >
                        Annuler
                      </button>
                    )}
                    {isAdmin && ['emise', 'payee', 'en_retard'].includes(f.statut) && (
                      <button
                        className="btn btn-sm btn-outline"
                        onClick={() => creerAvoir(f)}
                        title="Créer un avoir (note de crédit)"
                      >
                        Avoir
                      </button>
                    )}

                    {['emise', 'payee', 'en_retard'].includes(f.statut) && (
                      <button
                        className="btn btn-sm btn-outline"
                        onClick={() => handleWhatsApp(f, 'facture')}
                        disabled={waBusyId === f.id}
                        title="Envoyer par WhatsApp (lien vers le PDF client)"
                      >
                        {waBusyId === f.id ? '...' : '🟢 WhatsApp'}
                      </button>
                    )}

                    {f.fichier_pdf ? (
                      <button
                        className="btn btn-sm btn-success"
                        onClick={() => handleTelechargerPdf(f)}
                        disabled={isDownloading}
                        title="Télécharger le PDF"
                      >
                        {isDownloading ? '...' : '↓ PDF'}
                      </button>
                    ) : (
                      <button
                        className="btn btn-sm btn-outline"
                        onClick={() => handleGenererPdf(f)}
                        disabled={isGenerating}
                        title="Générer le PDF"
                      >
                        {isGenerating ? 'PDF...' : 'PDF'}
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
            : activeTab !== 'toutes'
              ? 'Aucune facture dans cet onglet.'
              : 'Aucune facture. Créez votre première facture.'}
        </p>
      )}
    </div>
  )
}
