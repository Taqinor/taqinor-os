/* Panneau devis INLINE de la fiche lead (style Odoo : slide-over plein écran
   au-dessus de la fiche). Tout se passe sans quitter le lead : créer (auto ou
   modifiable), voir l'aperçu PDF et le télécharger. On RÉUTILISE le générateur
   existant (DevisGenerator embarqué) et le calcul auto partagé (autoQuote.js) —
   aucune logique de prix ni de PDF dupliquée. Le PDF vient du chemin canonique
   /proposal (CLAUDE.md règle #4). */
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import {
  Download, ExternalLink, Pencil, RotateCw, TriangleAlert, WifiOff, Zap,
} from 'lucide-react'
import stockApi from '../../../api/stockApi'
import ventesApi from '../../../api/ventesApi'
import { createAutoQuote } from '../../../features/ventes/autoQuote'
import {
  proposalParams, pdfBlob, previewView, classifyFetchError, PREVIEW_VIEW,
} from '../../../features/ventes/previewPdf'
import DevisGenerator from '../../ventes/DevisGenerator'
import { filenameFromResponse } from '../../../utils/downloadBlob'
import { openPdfInGesture } from '../../../utils/pdfBlob'
import {
  Button, Input, Spinner, Segmented, Checkbox, EmptyState, Sheet, SheetContent,
} from '../../../ui'

// Le rendu PDF.js (canvas) est chargé à la demande (gros module) : il ne pèse
// sur le bundle que quand on ouvre réellement un aperçu.
const PdfCanvas = lazy(() => import('../../../features/ventes/PdfCanvas'))

// L'aperçu PDF est récupéré en BLOB via axios (MÊME chemin que le bouton
// « Télécharger » qui marche), puis DESSINÉ avec PDF.js sur des canvas.
// On NE pointe PLUS un cadre embarqué (iframe/embed) vers le PDF : un bloqueur
// de pub ou la politique PDF de Chrome peut le bloquer (cadre « contenu
// bloqué »). PDF.js rend depuis les octets authentifiés -> rien ne peut le
// bloquer, et le refresh silencieux du token (axios) reste rejoué + message
// d'erreur FR lisible.

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

  // Octets du PDF (Blob) récupérés via axios — voir l'en-tête. PDF.js les
  // dessine sur canvas, et c'est la MÊME source que le téléchargement.
  const [previewBlob, setPreviewBlob] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  // serverError : vrai échec de génération (4xx/5xx) -> message clair distinct.
  const [serverError, setServerError] = useState(null)
  // networkFailed : le fetch des octets a échoué (réseau/timeout, pas de réponse).
  const [networkFailed, setNetworkFailed] = useState(false)
  // renderFailed : PDF.js n'a pas pu dessiner les octets (cas rare).
  const [renderFailed, setRenderFailed] = useState(false)
  // Compteur de « Réessayer » : relance le fetch + le rendu.
  const [previewReloadKey, setPreviewReloadKey] = useState(0)

  // Récupération des octets du PDF. Distingue un VRAI échec serveur d'un échec
  // réseau : le 1er garde un message d'erreur, le 2nd bascule sur le repli.
  useEffect(() => {
    if (phase !== 'preview' || !devisId) return undefined
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewLoading(true)
    setServerError(null)
    setNetworkFailed(false)
    setRenderFailed(false)
    setPreviewBlob(null)
    ventesApi.getProposalPdf(devisId, proposalParams(pdfMode, includeEtude))
      .then((res) => {
        if (cancelled) return
        setPreviewBlob(pdfBlob(res.data))
      })
      .catch((err) => {
        if (cancelled) return
        if (classifyFetchError(err) === 'server') {
          setServerError(
            "Le serveur n'a pas pu générer ce PDF. Ouvrez l'édition complète "
            + 'pour vérifier le devis, puis réessayez.')
        } else {
          // réseau / timeout : repli gracieux, le PDF reste téléchargeable.
          setNetworkFailed(true)
        }
      })
      .finally(() => { if (!cancelled) setPreviewLoading(false) })
    return () => { cancelled = true }
  }, [phase, devisId, pdfMode, includeEtude, previewReloadKey])

  // « Réessayer l'aperçu » : on relance fetch + rendu depuis zéro.
  const reloadPreview = () => {
    setPreviewBlob(null)
    setNetworkFailed(false)
    setRenderFailed(false)
    setServerError(null)
    setErrorMsg(null)
    setPreviewReloadKey((k) => k + 1)
  }

  // blocked (dérivé) : échec réseau du fetch OU échec de rendu PDF.js -> repli
  // gracieux téléchargeable dans les deux cas.
  const blocked = networkFailed || renderFailed
  const previewState = previewView({
    loading: previewLoading,
    serverError: !!serverError,
    blocked,
    hasUrl: !!previewBlob,
  })

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
      // QD2 — nom cohérent posé par le serveur (repli sur la référence).
      downloadBlob(res.data, filenameFromResponse(res, `${devisRef || 'Devis'}.pdf`))
    } catch {
      setErrorMsg('Téléchargement du PDF indisponible. Réessayez.')
    } finally {
      setDownloading(false)
    }
  }

  // « Ouvrir dans un nouvel onglet » : on ouvre le MÊME PDF authentifié via une
  // URL blob (donc indépendante d'un bloqueur sur l'embed inline). On réutilise
  // le blob déjà récupéré ; sinon on le récupère d'abord.
  // VX48 — onglet pré-ouvert SYNCHRONE dans le geste de tap, avant tout await
  // (Safari iOS bloque silencieusement un window.open() post-await).
  const handleOpenNewTab = async () => {
    if (!devisId) return
    const pending = openPdfInGesture()
    try {
      let blob = previewBlob
      if (!blob) {
        const res = await ventesApi.getProposalPdf(
          devisId, proposalParams(pdfMode, includeEtude))
        blob = pdfBlob(res.data)
      }
      if (!pending.deliver(blob, `${devisRef || 'Devis'}.pdf`)) {
        setErrorMsg('Ouverture bloquée par le navigateur. Téléchargez le PDF.')
      }
    } catch {
      setErrorMsg('Ouverture impossible. Réessayez ou téléchargez le PDF.')
    }
  }

  return (
    // VX133 — migré du `.ldp-overlay`/`.ldp-panel` bespoke (pop centré) vers
    // Sheet side="right" : le panneau glisse depuis son bord réel au lieu de
    // « pop » du centre de l'écran. Le bouton ✕ reste celui du header
    // ldp-* existant (showClose désactivé pour ne pas en dupliquer un).
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" showClose={false} className="w-[min(1100px,100%)] gap-0 p-0 sm:max-w-none">
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
                <Input type="number" min="0" max="100" step="any"
                       value={discount} autoFocus
                       onChange={e => setDiscount(e.target.value)} />
              </div>
              <div className="ldp-actions">
                <Button type="button" variant="outline" onClick={onClose}>
                  Annuler
                </Button>
                <Button type="button"
                        onClick={() => { startedRef.current = true; doCreateAuto(discount || '0') }}>
                  <Zap /> Créer le devis
                </Button>
              </div>
            </div>
          )}

          {phase === 'creating' && (
            <div className="ldp-center">
              <p className="gen-hint"><Spinner /> Création du devis et dimensionnement automatique…</p>
            </div>
          )}

          {phase === 'error' && (
            <div className="ldp-center">
              <div className="form-error-box" role="alert">{errorMsg}</div>
              <div className="ldp-actions">
                <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
                <Button type="button" onClick={() => setPhase('edit')}>
                  Ouvrir l'édition complète
                </Button>
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
                  <Segmented
                    size="sm"
                    value={pdfMode}
                    onChange={setPdfMode}
                    options={[
                      { value: 'full', label: 'Premium' },
                      { value: 'onepage', label: '1 page' },
                    ]}
                  />
                  {pdfMode === 'full' && (
                    <label className="ldp-etude-toggle">
                      <Checkbox
                        checked={includeEtude}
                        onCheckedChange={v => setIncludeEtude(v === true)}
                      />
                      <span>Inclure l'étude</span>
                    </label>
                  )}
                </div>
                <div className="ldp-toolbar-actions">
                  <Button type="button" variant="outline" size="sm"
                          onClick={() => setPhase('edit')}>
                    <Pencil /> Édition complète
                  </Button>
                  <Button type="button" size="sm"
                          onClick={handleDownload} loading={downloading} disabled={downloading}>
                    {!downloading && <Download />}
                    {downloading ? '…' : 'Télécharger le PDF'}
                  </Button>
                </div>
              </div>
              <div className="ldp-pdf-area">
                {errorMsg && (
                  <div className="form-error-box ldp-pdf-loading" role="alert">{errorMsg}</div>
                )}

                {previewState === PREVIEW_VIEW.LOADING && (
                  <p className="ldp-pdf-loading">
                    <Spinner /> Chargement de l'aperçu…
                  </p>
                )}

                {/* Vrai échec serveur (4xx/5xx) : message clair, distinct du repli. */}
                {previewState === PREVIEW_VIEW.ERROR && (
                  <EmptyState
                    role="alert"
                    className="ldp-fallback"
                    icon={TriangleAlert}
                    title="Aperçu indisponible"
                    description={serverError}
                    action={(
                      <div className="ldp-fallback-actions">
                        <Button type="button" size="sm" onClick={() => setPhase('edit')}>
                          Ouvrir l'édition complète
                        </Button>
                        <Button type="button" variant="outline" size="sm" onClick={reloadPreview}>
                          <RotateCw /> Réessayer
                        </Button>
                      </div>
                    )}
                  />
                )}

                {/* Repli : la récupération des octets a échoué (réseau/timeout).
                    Le rendu PDF.js lui-même n'est pas blocable. */}
                {previewState === PREVIEW_VIEW.FALLBACK && (
                  <EmptyState
                    className="ldp-fallback"
                    icon={WifiOff}
                    title="Aperçu indisponible"
                    description="Vérifiez votre connexion. Vous pouvez réessayer ou télécharger le devis directement."
                    action={(
                      <div className="ldp-fallback-stack">
                        <div className="ldp-fallback-actions">
                          <Button type="button" size="sm"
                                  onClick={handleDownload} loading={downloading} disabled={downloading}>
                            {!downloading && <Download />}
                            {downloading ? '…' : 'Télécharger le PDF'}
                          </Button>
                          <Button type="button" variant="outline" size="sm" onClick={handleOpenNewTab}>
                            <ExternalLink /> Ouvrir dans un nouvel onglet
                          </Button>
                        </div>
                        <Button type="button" variant="link" size="sm"
                                className="ldp-fallback-retry" onClick={reloadPreview}>
                          Réessayer l'aperçu
                        </Button>
                      </div>
                    )}
                  />
                )}

                {previewState === PREVIEW_VIEW.PDF && (
                  <Suspense
                    fallback={(
                      <p className="ldp-pdf-loading">
                        <Spinner /> Chargement de l'aperçu…
                      </p>
                    )}
                  >
                    <PdfCanvas
                      key={previewReloadKey}
                      blob={previewBlob}
                      onError={() => setRenderFailed(true)}
                    />
                  </Suspense>
                )}
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
