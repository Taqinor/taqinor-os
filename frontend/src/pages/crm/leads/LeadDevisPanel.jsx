/* Panneau devis INLINE de la fiche lead (style Odoo : slide-over plein écran
   au-dessus de la fiche). Tout se passe sans quitter le lead : créer (auto ou
   modifiable), voir l'aperçu PDF et le télécharger. On RÉUTILISE le générateur
   existant (DevisGenerator embarqué) et le calcul auto partagé (autoQuote.js) —
   aucune logique de prix ni de PDF dupliquée. Le PDF vient du chemin canonique
   /proposal (CLAUDE.md règle #4). */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Download, ExternalLink, Pencil, Zap,
} from 'lucide-react'
import stockApi from '../../../api/stockApi'
import ventesApi from '../../../api/ventesApi'
import { createAutoQuote } from '../../../features/ventes/autoQuote'
import { proposalParams, pdfBlob } from '../../../features/ventes/previewPdf'
import { usePdfPreview } from '../../../features/ventes/usePdfPreview'
import PdfPreviewBody from '../../../features/ventes/PdfPreviewBody'
import DevisGenerator from '../../ventes/DevisGenerator'
import { peutEditerDevis, peutReviserDevis } from '../../../features/ventes/devisStatuts'
import { reviserEtOuvrir } from '../../../features/ventes/reviserDevis'
// QJR589 — la bannière de dérive lead → devis (mêmes gestes que l'Édition complète).
import BandeauDeriveLead from '../../../features/ventes/quote/BandeauDeriveLead'
import { downloadBlobInGesture, filenameFromResponse } from '../../../utils/downloadBlob'
import { openPdfInGesture } from '../../../utils/pdfBlob'
import { fetchAllPages } from '../../../utils/fetchAllPages'
import {
  Button, Input, Spinner, Segmented, Checkbox, Sheet, SheetContent,
} from '../../../ui'

// L'aperçu PDF vient de usePdfPreview + PdfPreviewBody (le même moteur que
// PdfPreviewSheet) : octets en BLOB via axios — MÊME chemin que « Télécharger »
// —, dessinés par PDF.js sur canvas (jamais un cadre embarqué bloquable), refresh
// silencieux du token rejoué, annulation réelle des rendus longs.

const TITLES = {
  auto: 'Devis automatique',
  remise: 'Devis automatique avec remise',
  onepage: 'Devis 1 page',
  premium: 'Devis premium',
  edit: 'Édition complète du devis',
  view: 'Devis',
}

// EZ5 — `targetKwc` : puissance cible (kWc) demandée pour CE devis depuis la
// fiche lead (« Devis automatique »). Optionnelle ; vide = comportement
// historique (taille souhaitée du lead, sinon facture d'hiver). Elle n'écrit
// RIEN sur le lead — c'est un paramètre de dimensionnement ponctuel.
export default function LeadDevisPanel({ lead, mode, onClose, onDevisChanged, existingDevisId = null, targetKwc = null }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  // phase: 'remise-input' | 'creating' | 'edit' | 'preview' | 'error'
  const [phase, setPhase] = useState(
    existingDevisId ? (mode === 'edit' ? 'edit' : 'preview')
      : mode === 'remise' ? 'remise-input'
        : mode === 'edit' ? 'edit'
          : 'creating')
  const [discount, setDiscount] = useState('0')
  const [errorMsg, setErrorMsg] = useState(null)
  // AGR126 — alertes renvoyées par le serveur avec le devis automatique
  // (agricole : étude pompage, articles « prix à renseigner » omis).
  const [alertes, setAlertes] = useState([])
  const [devisId, setDevisId] = useState(existingDevisId || null)
  const [devisRef, setDevisRef] = useState('')
  // QJR534 — le devis CHARGÉ (droits `modifiable` / `revision_possible` lus du
  // serveur, QJR516) : « Édition complète » seulement si modifiable, sinon
  // « Réviser ». Tant qu'il n'est pas chargé (ou sans devis), le geste
  // historique reste offert (le générateur refuse lui-même avec la raison).
  const [devisRecord, setDevisRecord] = useState(null)
  const editable = !devisRecord || peutEditerDevis(devisRecord)
  const revisable = !editable && peutReviserDevis(devisRecord)
  const reviser = () => reviserEtOuvrir({
    devis: { ...devisRecord, id: devisId },
    navigate,
    onApres: () => onDevisChanged?.(),
  })

  // QJR602 suivi (D-QJR5-13) — une taille explicite est respectée telle
  // quelle : plus d'arrondi au palier de 5 kWc, donc plus d'avis de palier.

  // Format d'aperçu PDF
  const [pdfMode, setPdfMode] = useState(mode === 'onepage' ? 'onepage' : 'full')
  const [includeEtude, setIncludeEtude] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const produitsRef = useRef(null)
  const marquesRef = useRef(undefined) // PVMRQ — cache du réglage marques
  const startedRef = useRef(false)

  // Octets du PDF : récupérés par usePdfPreview (MÊME source que le
  // téléchargement) ; changer de format ou fermer le panneau avorte le rendu
  // en vol (APXTMO : les rendus à froid ~26 s ne s'empilent pas sur gunicorn).
  const fetchPreviewBlob = useCallback(
    (signal) => ventesApi.getProposalPdf(
      devisId, proposalParams(pdfMode, includeEtude), { signal })
      .then((res) => pdfBlob(res.data)),
    [devisId, pdfMode, includeEtude])
  const preview = usePdfPreview(fetchPreviewBlob, {
    enabled: phase === 'preview' && !!devisId,
  })
  const previewBlob = preview.blob

  // « Réessayer l'aperçu » : on relance fetch + rendu depuis zéro.
  const reloadPreview = () => {
    setErrorMsg(null)
    preview.reload()
  }

  // ── Création auto (auto / onepage / premium : pas de saisie préalable) ──
  const doCreateAuto = async (discountStr) => {
    setPhase('creating')
    setErrorMsg(null)
    try {
      if (!produitsRef.current) {
        // RÉGRESSION CONFIRMÉE (CI run 32200473257, e2e devis.spec.js E4) —
        // `stockApi.getProduits()` SANS paramètre ne renvoie que la PAGE 1
        // (50 produits, triés par nom). Dès que le catalogue dépasse 50
        // références, une famille de produits triée alphabétiquement APRÈS
        // la coupure (ex. « Panneau… ») disparaît silencieusement du
        // dimensionnement automatique — `autoFillLines` la voit comme
        // ABSENTE DU STOCK et jette « aucun panneau du stock ne correspond »
        // alors que le catalogue en porte réellement. Trace réseau du run
        // rouge : count=101, page 1 s'arrête à « Onduleur réseau… », les DEUX
        // panneaux tombent en page 2. `fetchAllPages` (VX54, déjà le chemin
        // correct de stockSlice.js pour StockList/DevisList/FactureList/
        // Dashboard) lit le catalogue ENTIER, en parallèle borné.
        produitsRef.current = await fetchAllPages(
          (page) => stockApi.getProduits({ page }).then((r) => r.data))
      }
      // PVMRQ — les marques épinglées (Paramètres → Gammes) s'appliquent AUSSI
      // au devis automatique du lead : sans ce fil, ce chemin rapide recomposait
      // hors préférence (le trou « panneau 500 W » par la porte de côté). Best-
      // effort : réglage illisible → aucune préférence, jamais un échec du devis.
      if (marquesRef.current === undefined) {
        try {
          const r = await ventesApi.getParametresGammes()
          marquesRef.current = (r.data?.marques || {})['Essentielle'] || null
        } catch {
          marquesRef.current = null
        }
      }
      setAlertes([])
      const id = await createAutoQuote({
        lead, produits: produitsRef.current, discountStr, dispatch, targetKwc,
        marques: marquesRef.current || undefined,
        onAlertes: setAlertes,
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
      .then(({ data }) => {
        setDevisRef(data.reference || `Devis_${devisId}`)
        setDevisRecord(data)
      })
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
    // QJR652 — fenêtre ouverte dans le geste, avant le premier await (iOS / PWA).
    const pending = downloadBlobInGesture()
    try {
      const res = await ventesApi.getProposalPdf(
        devisId, proposalParams(pdfMode, includeEtude))
      // QD2 — nom cohérent posé par le serveur (repli sur la référence).
      pending.deliver(res.data, filenameFromResponse(res, `${devisRef || 'Devis'}.pdf`))
    } catch {
      try { pending.win?.close() } catch { /* fenêtre déjà fermée */ }
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
      <SheetContent side="right" showClose={false} className="w-[min(1500px,100%)] gap-0 p-0 sm:max-w-none">
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
                {editable && (
                  <Button type="button" onClick={() => setPhase('edit')}>
                    Ouvrir l'édition complète
                  </Button>
                )}
                {revisable && (
                  <Button type="button" onClick={reviser}>
                    Réviser (nouvelle version)
                  </Button>
                )}
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
              {/* AGR126 — ce que le devis automatique serveur signale (jamais
                  un chiffre inventé : le message du serveur, tel quel). */}
              {alertes.length > 0 && (
                <div className="form-error-box" role="status" data-testid="ldp-alertes-auto">
                  <strong>Alertes du devis automatique :</strong>
                  <ul>
                    {alertes.map((a, i) => (
                      <li key={`${a.code || 'alerte'}-${i}`}>{a.message || a.code}</li>
                    ))}
                  </ul>
                </div>
              )}
              {/* QJR589 — dérive lead → devis : reprendre / garder, sur place
                  (envoyé : le client verra la version corrigée) ; figé →
                  « Réviser ». Le détail est déjà lu (getDevisById). */}
              {devisRecord && (
                <BandeauDeriveLead
                  devisId={devisId}
                  statut={devisRecord.statut}
                  champs={devisRecord.lead_valeurs_modifiees}
                  onResolu={(data) => {
                    if (data?.devis) setDevisRecord(data.devis)
                    onDevisChanged?.()
                  }}
                  onReviser={revisable ? reviser : undefined}
                />
              )}
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
                  {editable && (
                    <Button type="button" variant="outline" size="sm"
                            onClick={() => setPhase('edit')}>
                      <Pencil /> Édition complète
                    </Button>
                  )}
                  {revisable && (
                    <Button type="button" variant="outline" size="sm" onClick={reviser}>
                      <Pencil /> Réviser (nouvelle version)
                    </Button>
                  )}
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

                <PdfPreviewBody
                  blob={preview.blob}
                  loading={preview.loading}
                  errorKind={preview.errorKind}
                  errorMessage={preview.errorMessage}
                  renderFailed={preview.renderFailed}
                  onRenderError={preview.onRenderError}
                  onReload={reloadPreview}
                  reloadKey={preview.reloadKey}
                  loadingText="Chargement de l'aperçu… La première génération d'un devis peut prendre ~30 secondes."
                  serverMessage={"Le serveur n'a pas pu générer ce PDF. Ouvrez l'édition complète "
                    + 'pour vérifier le devis, puis réessayez.'}
                  serverActions={(
                    <>
                      {editable && (
                        <Button type="button" size="sm" onClick={() => setPhase('edit')}>
                          Ouvrir l'édition complète
                        </Button>
                      )}
                      {revisable && (
                        <Button type="button" size="sm" onClick={reviser}>
                          Réviser (nouvelle version)
                        </Button>
                      )}
                    </>
                  )}
                  fallbackDescription="Vérifiez votre connexion. Vous pouvez réessayer ou télécharger le devis directement."
                  fallbackActions={(
                    <>
                      <Button type="button" size="sm"
                              onClick={handleDownload} loading={downloading} disabled={downloading}>
                        {!downloading && <Download />}
                        {downloading ? '…' : 'Télécharger le PDF'}
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={handleOpenNewTab}>
                        <ExternalLink /> Ouvrir dans un nouvel onglet
                      </Button>
                    </>
                  )}
                />
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
