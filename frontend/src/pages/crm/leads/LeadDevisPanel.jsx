/* Panneau devis INLINE de la fiche lead (style Odoo : slide-over plein écran
   au-dessus de la fiche). Tout se passe sans quitter le lead : créer (auto ou
   modifiable), voir l'aperçu PDF et le télécharger. On RÉUTILISE le générateur
   existant (DevisGenerator embarqué) et le calcul auto partagé (autoQuote.js) —
   aucune logique de prix ni de PDF dupliquée. Le PDF vient du chemin canonique
   /proposal (CLAUDE.md règle #4). */
import { useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import stockApi from '../../../api/stockApi'
import ventesApi from '../../../api/ventesApi'
import { createAutoQuote } from '../../../features/ventes/autoQuote'
import { proposalParams, pdfBlob } from '../../../features/ventes/previewPdf'
import DevisGenerator from '../../ventes/DevisGenerator'

// L'aperçu PDF est récupéré en BLOB via axios (MÊME chemin que le bouton
// « Télécharger » qui marche), puis affiché dans l'iframe via une URL blob.
// On NE pointe PLUS l'iframe directement sur /proposal : une requête native
// d'iframe ne peut pas rejouer le refresh silencieux du token (401 → icône
// « fichier cassé ») et n'affiche aucune erreur lisible si le moteur PDF
// refuse le devis. Passer par axios règle les deux : refresh auto + message FR.

const TITLES = {
  auto: 'Devis automatique',
  remise: 'Devis automatique avec remise',
  onepage: 'Devis 1 page',
  premium: 'Devis premium',
  edit: 'Édition complète du devis',
  view: 'Devis',
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function LeadDevisPanel({ lead, mode, onClose, onDevisChanged, existingDevisId = null }) {
  const dispatch = useDispatch()

  // phase: 'remise-input' | 'creating' | 'edit' | 'preview' | 'error'
  const [phase, setPhase] = useState(
    existingDevisId ? 'preview'
      : mode === 'remise' ? 'remise-input'
        : mode === 'edit' ? 'edit'
          : 'creating')
  const [discount, setDiscount] = useState('0')
  const [errorMsg, setErrorMsg] = useState(null)
  const [devisId, setDevisId] = useState(existingDevisId || null)
  const [devisRef, setDevisRef] = useState('')

  // Format d'aperçu PDF
  const [pdfMode, setPdfMode] = useState(mode === 'onepage' ? 'onepage' : 'full')
  const [includeEtude, setIncludeEtude] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const produitsRef = useRef(null)
  const startedRef = useRef(false)

  // Aperçu PDF en blob (URL d'objet), récupéré via axios — voir l'en-tête.
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState(null)

  useEffect(() => {
    if (phase !== 'preview' || !devisId) return undefined
    let cancelled = false
    let objectUrl = null
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewLoading(true)
    setPreviewError(null)
    ventesApi.getProposalPdf(devisId, proposalParams(pdfMode, includeEtude))
      .then((res) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(pdfBlob(res.data))
        setPreviewUrl(objectUrl)
      })
      .catch(() => {
        if (cancelled) return
        setPreviewError(
          "Aperçu du PDF indisponible. Réessayez ou ouvrez l'édition complète.")
        setPreviewUrl(null)
      })
      .finally(() => { if (!cancelled) setPreviewLoading(false) })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [phase, devisId, pdfMode, includeEtude])

  // ── Création auto (auto / onepage / premium : pas de saisie préalable) ──
  const doCreateAuto = async (discountStr) => {
    setPhase('creating')
    setErrorMsg(null)
    try {
      if (!produitsRef.current) {
        const r = await stockApi.getProduits()
        produitsRef.current = r.data.results ?? r.data
      }
      const id = await createAutoQuote({
        lead, produits: produitsRef.current, discountStr, dispatch,
      })
      setDevisId(id)
      onDevisChanged?.()
      setPhase('preview')
    } catch (err) {
      setErrorMsg(typeof err?.detail === 'string'
        ? err.detail
        : "Le devis automatique a échoué — vérifiez la fiche du lead et réessayez.")
      setPhase('error')
    }
  }

  useEffect(() => {
    if (startedRef.current) return
    if (mode === 'auto' || mode === 'onepage' || mode === 'premium') {
      startedRef.current = true
      // eslint-disable-next-line react-hooks/set-state-in-effect
      doCreateAuto('0')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Référence (pour le nom du fichier) une fois le devis connu.
  useEffect(() => {
    if (!devisId) return
    ventesApi.getDevisById(devisId)
      .then(({ data }) => setDevisRef(data.reference || `Devis_${devisId}`))
      .catch(() => setDevisRef(`Devis_${devisId}`))
  }, [devisId])

  const onEditDone = (id) => {
    if (id) setDevisId(id)
    onDevisChanged?.()
    setPhase('preview')
  }

  // Téléchargement : MÊME source que l'aperçu (/proposal), récupérée en blob
  // via axios (cookie httpOnly) — aperçu et téléchargement concordent.
  const handleDownload = async () => {
    if (!devisId) return
    setDownloading(true)
    try {
      const res = await ventesApi.getProposalPdf(
        devisId, proposalParams(pdfMode, includeEtude))
      downloadBlob(res.data, `${devisRef || 'Devis'}.pdf`)
    } catch {
      setErrorMsg('Téléchargement du PDF indisponible. Réessayez.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="ldp-overlay" onClick={onClose}>
      <div className="ldp-panel" onClick={e => e.stopPropagation()}>
        <div className="ldp-header">
          <h3 className="ldp-title">
            {TITLES[mode] || 'Devis'} — {lead.nom} {lead.prenom || ''}
            {devisRef && <span className="ldp-ref">{devisRef}</span>}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="ldp-body">
          {phase === 'remise-input' && (
            <div className="ldp-center">
              <p className="gen-hint">
                Entrez la remise à appliquer, puis le devis sera dimensionné
                automatiquement depuis les données du lead.
              </p>
              <div className="form-group" style={{ maxWidth: 220 }}>
                <label className="form-label">Remise (%)</label>
                <input type="number" min="0" max="100" step="any"
                       className="form-control" value={discount} autoFocus
                       onChange={e => setDiscount(e.target.value)} />
              </div>
              <div className="ldp-actions">
                <button type="button" className="btn btn-outline" onClick={onClose}>
                  Annuler
                </button>
                <button type="button" className="btn btn-primary"
                        onClick={() => { startedRef.current = true; doCreateAuto(discount || '0') }}>
                  ⚡ Créer le devis
                </button>
              </div>
            </div>
          )}

          {phase === 'creating' && (
            <div className="ldp-center">
              <p className="gen-hint">⏳ Création du devis et dimensionnement automatique…</p>
            </div>
          )}

          {phase === 'error' && (
            <div className="ldp-center">
              <div className="form-error-box" role="alert">{errorMsg}</div>
              <div className="ldp-actions">
                <button type="button" className="btn btn-outline" onClick={onClose}>Fermer</button>
                <button type="button" className="btn btn-primary"
                        onClick={() => setPhase('edit')}>
                  Ouvrir l'édition complète
                </button>
              </div>
            </div>
          )}

          {phase === 'edit' && (
            <div className="ldp-edit">
              <DevisGenerator
                embedded
                leadId={lead.id}
                editId={devisId || null}
                onDone={onEditDone}
                onCancel={() => (devisId ? setPhase('preview') : onClose())}
              />
            </div>
          )}

          {phase === 'preview' && (
            <div className="ldp-preview">
              <div className="ldp-toolbar">
                <div className="ldp-format">
                  <label className={`gen-radio${pdfMode === 'full' ? ' selected' : ''}`}>
                    <input type="radio" name="ldp-pdf" checked={pdfMode === 'full'}
                           onChange={() => setPdfMode('full')} />
                    Premium
                  </label>
                  <label className={`gen-radio${pdfMode === 'onepage' ? ' selected' : ''}`}>
                    <input type="radio" name="ldp-pdf" checked={pdfMode === 'onepage'}
                           onChange={() => setPdfMode('onepage')} />
                    1 page
                  </label>
                  {pdfMode === 'full' && (
                    <label className="pdf-toggle" style={{ marginLeft: 8 }}>
                      <input type="checkbox" checked={includeEtude}
                             onChange={e => setIncludeEtude(e.target.checked)} />
                      <span>Inclure l'étude</span>
                    </label>
                  )}
                </div>
                <div className="ldp-toolbar-actions">
                  <button type="button" className="btn btn-outline btn-sm"
                          onClick={() => setPhase('edit')}>
                    ✏️ Édition complète
                  </button>
                  <button type="button" className="btn btn-primary btn-sm"
                          onClick={handleDownload} disabled={downloading}>
                    {downloading ? '…' : '⬇ Télécharger le PDF'}
                  </button>
                </div>
              </div>
              <div className="ldp-pdf-area">
                {errorMsg && <div className="form-error-box ldp-pdf-loading" role="alert">{errorMsg}</div>}
                {previewError && (
                  <div className="form-error-box ldp-pdf-loading" role="alert">{previewError}</div>
                )}
                {previewLoading && !previewError && (
                  <p className="gen-hint ldp-pdf-loading">⏳ Chargement de l'aperçu…</p>
                )}
                {previewUrl && !previewLoading && !previewError && (
                  <iframe
                    title="Aperçu du devis"
                    key={previewUrl}
                    src={previewUrl}
                    className="ldp-iframe"
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
