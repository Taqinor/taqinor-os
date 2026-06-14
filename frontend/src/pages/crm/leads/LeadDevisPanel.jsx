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
import { originFrom } from '../../../api/origin'
import { createAutoQuote } from '../../../features/ventes/autoQuote'
import DevisGenerator from '../../ventes/DevisGenerator'

// Même origine que l'app (chemins relatifs via nginx/Caddy). Le PDF est servi
// par le MÊME endpoint Django que les devis PDF qui marchent (/proposal) ;
// l'iframe pointe DIRECTEMENT dessus (cookie httpOnly envoyé automatiquement),
// jamais sur une URL MinIO interne ni un blob (que le navigateur refuse de
// rendre en cadre avec X-Content-Type-Options: nosniff).
const API_ORIGIN = originFrom(import.meta.env.VITE_API_URL)
const proposalUrl = (devisId, pdfMode, includeEtude) =>
  `${API_ORIGIN}/api/django/ventes/devis/${devisId}/proposal/`
  + `?pdf_mode=${pdfMode}&include_etude=${includeEtude ? 1 : 0}`

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

  // URL d'aperçu : endpoint /proposal direct (cadre natif du navigateur).
  const pdfUrl = (phase === 'preview' && devisId)
    ? proposalUrl(devisId, pdfMode, includeEtude) : null

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
      const res = await ventesApi.getProposalPdf(devisId, {
        pdf_mode: pdfMode, include_etude: includeEtude ? 1 : 0,
      })
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
                {pdfUrl && (
                  <iframe
                    title="Aperçu du devis"
                    key={pdfUrl}
                    src={pdfUrl}
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
