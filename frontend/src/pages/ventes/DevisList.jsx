import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  Download, Plus, FileText, FileDown, Check, ArrowRight, HardHat, FileStack,
  Copy, Send, X, Eye, Search, AlertTriangle, Box, ExternalLink,
  Link2, FolderKanban, MoreHorizontal, Printer, Bell, Share2,
  LayoutList, LayoutGrid,
} from 'lucide-react'
import {
  fetchDevis,
  genererPdfDevis,
  convertirDevisEnBC,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import installationsApi from '../../api/installationsApi'
import gestionProjetApi from '../../api/gestionProjetApi'
import crmApi from '../../api/crmApi'
import importApi from '../../api/importApi'
import DevisForm from './DevisForm'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  // APX12 — le langage UNIQUE des KPI d'argent.
  Stat,
  Skeleton, SkeletonTableRow,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  RadioGroup, RadioGroupItem, Checkbox, Label, Input, Segmented, toast,
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
  Textarea,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel,
  // APX17 — les signaux secondaires du statut passent dans un Popover.
  Popover, PopoverTrigger, PopoverContent,
} from '../../ui'
import { formatMAD, formatDateTime } from '../../lib/format'
// VX156 — le devis envoyé porte la voix Taqinor (moment « devis envoyé »).
import { voice } from '../../lib/voice'
// VX155 — jalon « devis envoyé » : un cran au-dessus du toast succès plat.
import { toastMilestone } from '../../lib/toast'
// VX236 — `?equipe=<id>` (lien depuis MesEquipesCard) filtre la liste sur les
// membres de cette équipe — filtre client-side, aucun endpoint nouveau.
import { useEquipeMembreIds } from '../../hooks/useEquipeMembreIds'
import { filenameFromResponse, downloadBlobInGesture } from '../../utils/downloadBlob'
import { openPdfBlob } from '../../utils/pdfBlob'
import { proposalParams, pdfBlob } from '../../features/ventes/previewPdf'
import { useServerSavedViews } from '../../features/uxviews/useServerSavedViews'
import ViewsManagerPopover from '../../features/uxviews/ViewsManagerPopover'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import { useRotatingLabel } from '../../hooks/useRotatingLabel'
import { useHasPermission, useCanValiderVente, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import useDocumentTitle from '../../hooks/useDocumentTitle'
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'
// VX248 — raccourci d'ACTION sur le devis focalisé (le deep-link ?devis=,
// même « record focalisé » que la surbrillance de ligne existante).
import { useFocusedRecordShortcuts } from '../../providers/focusedRecordShortcuts'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
// VX155 — la carte de victoire (enrichit VX40) remplace le toast plat +
// celebrateDealSigned() appelés directement d'ici ; le burst reste posé,
// mais DEPUIS <DealSignedCelebration> lui-même.
import DealSignedCelebration from '../../ui/DealSignedCelebration'
import { DataTable } from '../../ui/datatable'
import RoofViewer from './RoofViewer'
// WIR96 — panneau « Suivi du partage » (ouvertures du lien + relances).
import DevisSuiviPartagePanel from './DevisSuiviPartagePanel'
// PV43 — panneau « Conception électrique » (chaînes/conformité/schéma/surcharges).
import ConceptionElectrique from '../../features/ventes/ConceptionElectrique'
// PV76 — carte « Étude bancable » (P50/P90/PR/cascade/payback/VAN/TRI).
import EtudeBancable from '../../features/ventes/EtudeBancable'
import { StateBlock } from '../../components/StateBlock'
import DocumentStageTrack from '../../ui/DocumentStageTrack'
// APX13 — la piste devis→BC→facture, définie UNE fois pour les 3 écrans.
import { DOC_STATUT_TRACK } from '../../features/ventes/documentChain'
// APX14 — aperçu PDF INLINE (panneau latéral) : plus d'onglet à quitter.
import PdfPreviewSheet from '../../features/ventes/PdfPreviewSheet'
// APX15 — le VRAI board Ventes : les devis par statut DOCUMENT (règle #4).
import DevisKanbanBoard from './DevisKanbanBoard'
// APX17 — confirmation maison (VX19/L152), jamais une popup du système.
import { useConfirmDialog } from '../../ui/confirm'
// APX11 — l'en-tête UNIQUE de l'app (VX28) remplace l'idiome legacy.
import { PageHeader } from '../../ui/PageHeader'
// APX11 — identité Ventes : accent brass posé sur l'en-tête des écrans de flux.
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'

// J141 — Squelette de la liste : reprend les 8 colonnes du vrai tableau pour que
// la mise en page ne saute pas à l'arrivée des données. Affiché dans la même
// carte que le tableau réel, en gardant l'en-tête de page visible.
function DevisTableSkeleton() {
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-8" />
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
            {Array.from({ length: 6 }).map((unused, i) => (
              <SkeletonTableRow key={i} columns={8} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

// WIR21 — vues sauvegardées côté serveur (apps.uxviews.SavedView, NTUX1/2).
const DL_ECRAN = 'ventes.devis'

// VX132 — chargement long CONSCIENT : la génération du devis PDF premium est
// la latence connue la plus longue de l'app (schémas, produits, chiffrage) ;
// un spinner MUET pendant tout ce temps ne dit rien d'utile. Libellés
// honnêtes qui tournent pendant l'attente — ne touche QUE ce bouton côté
// client, jamais le moteur `apps/ventes/quote_engine/` (règle #4).
const PDF_GENERATION_LABELS = [
  'Génération du PDF…',
  'Mise en page des schémas…',
  'Calcul du système…',
  'Finalisation du document…',
]

// VX216(a) — un chantier « en cours » a sa nomenclature (bom) GELÉE : éditer
// le devis lié APRÈS ce point crée un écart devis↔chantier invisible côté
// vendeur (l'installateur seul le voyait, InstallationDetail.jsx `devisDivergent`).
// Statuts avant réception/clôture/annulation = composition encore gelée et
// potentiellement engagée sur le terrain (miroir Installation.Statut ordonné,
// apps/installations/models_installation.py).
const CHANTIER_EN_COURS_STATUTS = [
  'signe', 'materiel_commande', 'planifie', 'en_cours', 'installe',
  // Statuts hérités équivalents (LEGACY_STATUT_MAP backend).
  'a_planifier', 'pose_en_cours', 'pose', 'raccordement_onee', 'mise_en_service',
]
const chantierEnCours = (chantier) =>
  !!chantier && CHANTIER_EN_COURS_STATUTS.includes(chantier.statut)

// ── ARC49 — Colonnes du frame `ui/datatable` en mode « ligne custom ».
// L'écran rend chaque ligne via `renderRow` (<DevisRow>), donc ces définitions
// ne servent qu'à décrire la grille au moteur (identité de colonnes) : aucun
// `cell` n'est utilisé, le tri/filtre/pagination sont désactivés (seams manuels).
// Le rendu réel (cellules, boutons, panneaux) reste 100 % dans <DevisRow>.
const DEVIS_DT_COLUMNS = [
  { id: 'reference', header: 'Référence', sortable: false, hideable: false, reorderable: false },
  { id: 'client', header: 'Client', sortable: false, hideable: false, reorderable: false },
  { id: 'date_creation', header: 'Créé le', sortable: false, hideable: false, reorderable: false },
  { id: 'date_validite', header: 'Validité', sortable: false, hideable: false, reorderable: false },
  { id: 'total_ttc', header: 'Total TTC', align: 'right', sortable: false, hideable: false, reorderable: false },
  { id: 'statut', header: 'Statut', sortable: false, hideable: false, reorderable: false },
  { id: 'actions', header: 'Actions', sortable: false, hideable: false, reorderable: false },
]

const STATUT_DISPLAY = {
  brouillon: 'Brouillon',
  envoye:    'Envoyé',
  accepte:   'Accepté',
  refuse:    'Refusé',
  expire:    'Expiré',
}

// VX141 — piste `<DocumentStageTrack>` : couche STATUTS DOCUMENT (règle #4)
// uniquement — brouillon/envoyé/accepté puis BC/facturé/chantier. Jamais les
// stages STAGES.py du funnel CRM (règle #2) : aucune clé de stage n'est
// importée ici, les deux couches ne se mélangent jamais.
// APX13 — la piste est désormais partagée avec FactureList et la liste des
// bons de commande (`features/ventes/documentChain.js`) : UNE définition.

// Filtres segmentés (statut) : « Tous » + les 5 statuts visibles.
const STATUT_FILTERS = [
  { value: 'tous',      label: 'Tous' },
  { value: 'brouillon', label: 'Brouillon' },
  { value: 'envoye',    label: 'Envoyé' },
  { value: 'accepte',   label: 'Accepté' },
  { value: 'refuse',    label: 'Refusé' },
  { value: 'expire',    label: 'Expiré' },
]

// Extrait un message d'erreur lisible (français) d'une réponse DRF. Couvre
// {detail}, les erreurs de champ ({statut: [...]} — ex. garde de remise T17),
// et retombe sur un message générique sinon. Ne JAMAIS afficher de JSON brut.
function frenchError(err, fallback) {
  const data = err?.response?.data ?? err
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    if (data.detail) return String(data.detail)
    const first = Object.values(data).find(Boolean)
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}

// Nombre de jours calendaires entre aujourd'hui et une date ISO (peut être
// négatif). null si la date est absente/invalide.
function daysUntil(isoDate) {
  if (!isoDate) return null
  const target = new Date(isoDate)
  if (Number.isNaN(target.getTime())) return null
  const today = new Date()
  const a = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate())
  const b = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((a - b) / 86400000)
}

// VX222 — « Relancer ce devis » : à partir de l'aperçu WhatsApp EXISTANT (même
// modale, mêmes données), on remplace UNIQUEMENT le texte du message wa.me par
// un RAPPEL (« petit rappel concernant votre devis ») au lieu de l'envoi
// initial. On réutilise le numéro déjà normalisé côté serveur (base de
// `waData.wa_url`, avant le `?text=`) + le lien public déjà émis (`waData.url`),
// donc aucun backend ni duplication de logique de téléphone. Aperçu-puis-clic :
// rien n'est envoyé automatiquement (règle manuel-wa.me fondateur).
function buildRelanceMessage(waData, reference) {
  const lien = waData?.url || ''
  return `Bonjour, petit rappel concernant votre devis ${reference || ''}${lien ? ' : ' + lien : ''}`.trim()
}
function buildRelanceWaUrl(waData, reference) {
  if (!waData?.wa_url) return null
  const base = waData.wa_url.split('?')[0]   // https://wa.me/<numéro normalisé>
  return `${base}?text=${encodeURIComponent(buildRelanceMessage(waData, reference))}`
}

// XSAL16 — libellés FR des sections suivies sur la proposition web (miroir de
// `_ENGAGEMENT_SECTIONS` côté serveur, apps/ventes/public_views.py).
// source-choix: ventes.public_views._ENGAGEMENT_SECTIONS
const ENGAGEMENT_LABELS = {
  hero: 'accueil', prix: 'prix', etude: 'étude', garanties: 'garanties', signature: 'signature',
}

// Résume l'engagement par section en une phrase courte (« 2 min sur le prix,
// 30 s sur l'étude ») — null sans aucune section suivie (comportement QJ1
// inchangé, aucun badge affiché).
function engagementSummary(engagement) {
  const entries = Object.entries(engagement || {}).filter(([, v]) => v?.seconds > 0)
  if (entries.length === 0) return null
  entries.sort((a, b) => b[1].seconds - a[1].seconds)
  return entries.map(([section, v]) => {
    const label = ENGAGEMENT_LABELS[section] ?? section
    const mins = Math.round(v.seconds / 60)
    const duree = mins >= 1 ? `${mins} min` : `${v.seconds} s`
    return `${duree} sur ${label}`
  }).join(' · ')
}

// ── ARC49 — Modale de génération PDF de la LISTE (formats du simulateur). ──
// Extraite telle quelle de DevisList (« lignes divisées ») : mêmes contrôles,
// mêmes libellés, MÊMES options envoyées à `generer-pdf`/`clean_pdf_options`
// (règle #4 — la migration ne touche QUE le découpage du rendu, jamais le flux
// PDF). Toute la logique de valeur reste dans `buildPdfOptions` côté parent.
function DevisPdfDialog({
  pdfTarget, batchPdf, selectedIds,
  pdfMode, setPdfMode, targetIsAgricole,
  showMonthly, setShowMonthly,
  targetHasEtude, includeEtude, setIncludeEtude,
  devisFinal, setDevisFinal,
  paymentMode, setPaymentMode,
  customAcompte, setCustomAcompte,
  onClose, onGenererLot, onGenererUn,
}) {
  return (
    <ResponsiveDialog
      open={!!pdfTarget || batchPdf}
      onOpenChange={(o) => { if (!o) onClose() }}
      title={batchPdf
        ? `Générer le PDF — ${selectedIds.length} devis (format partagé)`
        : `Générer le PDF — ${pdfTarget?.reference}`}
      footer={(
        <>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={() => (batchPdf ? onGenererLot() : onGenererUn(pdfTarget))}>
            <FileText /> Générer
          </Button>
        </>
      )}
    >
        <div className="flex flex-col gap-4">
          <div className="grid gap-2">
            <Label>Format</Label>
            <RadioGroup value={pdfMode} onValueChange={setPdfMode} className="flex flex-col gap-2">
              <label className="flex items-start gap-2 text-sm">
                <RadioGroupItem value="full" className="mt-0.5" />
                <span>
                  {targetIsAgricole
                    ? 'Devis premium (4 pages — étude, schéma, rentabilité, garanties)'
                    : 'Devis premium (3 pages — options, analyse, garanties)'}
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <RadioGroupItem value="onepage" className="mt-0.5" />
                <span>Devis une page (liste produits uniquement, sans graphiques)</span>
              </label>
            </RadioGroup>
          </div>

          {pdfMode === 'full' && !targetIsAgricole && (
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={showMonthly} onCheckedChange={v => setShowMonthly(!!v)} className="mt-0.5" />
              <span>Économies mensuelles <span className="text-muted-foreground">(graphique mensuel page 2)</span></span>
            </label>
          )}

          {pdfMode === 'full' && !batchPdf && !targetIsAgricole && (
            <label className="flex items-start gap-2 text-sm aria-disabled:opacity-50" aria-disabled={!targetHasEtude}>
              {/* T13 — case désactivée sans données d'étude (note explicative). */}
              <Checkbox
                checked={includeEtude && targetHasEtude}
                disabled={!targetHasEtude}
                onCheckedChange={v => setIncludeEtude(!!v)}
                className="mt-0.5"
              />
              <span>
                Inclure l'étude <span className="text-muted-foreground">(page autoconsommation — devis industriel)</span>
                {!targetHasEtude && (
                  <span className="block text-xs text-muted-foreground">
                    Aucune donnée d'étude sur ce devis — option indisponible.
                  </span>
                )}
              </span>
            </label>
          )}

          <label className="flex items-start gap-2 text-sm">
            <Checkbox checked={devisFinal} onCheckedChange={v => setDevisFinal(!!v)} className="mt-0.5" />
            <span>Devis Final <span className="text-muted-foreground">(ajoute modalités de paiement + RIB)</span></span>
          </label>

          {devisFinal && (
            <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3">
              <RadioGroup value={paymentMode} onValueChange={setPaymentMode} className="flex flex-col gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <RadioGroupItem value="standard" />
                  <span>Standard (30/60/10)</span>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <RadioGroupItem value="custom" />
                  <span>Acompte personnalisé</span>
                </label>
              </RadioGroup>
              {paymentMode === 'custom' && (
                <div className="grid gap-1.5">
                  <Label htmlFor="pdf-acompte">Montant acompte (MAD)</Label>
                  <Input id="pdf-acompte" type="number" min="0" step="any"
                         value={customAcompte} onChange={e => setCustomAcompte(e.target.value)} />
                </div>
              )}
            </div>
          )}
        </div>
    </ResponsiveDialog>
  )
}

// ── ARC49 — Ligne de la liste des devis (« lignes divisées »). Extraite VERBATIM
// du corps de `filteredDevis.map(...)` : mêmes `<tr>`, mêmes `data-label`, mêmes
// boutons d'action VISIBLES (états `loading` individuels), mêmes deux panneaux
// dépliables (versions / design 3D), mêmes appels API. Tout l'état et les
// handlers viennent du parent via `ctx` — aucune logique n'est déplacée ni
// modifiée. Le tableau reste `table.data-table` (contrat de test + carte mobile).
function DevisRow({ d, ctx }) {
  const {
    selectedIds, toggleSelected,
    versionsOpenId, setVersionsOpenId, roofOpenId, setRoofOpenId,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    suiviOpenId, toggleSuiviPartage, suiviCache, suiviLoadingId,
    conceptionOpenId, setConceptionOpenId,
    etudeOpenId, setEtudeOpenId,
    versionChain, effStatutOf,
    navigate, dispatch,
    role, canDelete, canValiderVente, canSeePublicite, highlightId,
    deletingId, statutActionId, superieurBusyId, superieurStatus, shareBusyId, previewingId,
    pdfGenerating, pdfDownloading, pdfSlowPoll, convertingId, chantierBusy, projetBusy, factureGenId,
    openEdit, openVarianteModal, openGammeModal, handleDelete, handleEnvoyer, handleRelancer,
    handleContacterSuperieur,
    openEmailModal, handleCopierLienProposition, copierLienInterne, handlePreview, openPdfModal,
    handleTelechargerPdf, handlePartagerPdf, openAcceptModal, openRefusModal, handleConvertBC,
    handleProformaPdf, handleBonCommandePdf,
    handleChantier, handleCreerProjet, handleGenererFacture,
  } = ctx
  // Expiration calculée à la volée (T7) : un devis en attente dont la
  // date de validité est dépassée s'affiche « Expiré » sans changer
  // son statut stocké ni l'étape du lead.
  const effStatut = d.is_expired ? 'expire' : d.statut
  // VX141 — parcours DOCUMENT (règle #4) affiché par <DocumentStageTrack> à
  // côté du StatusPill : brouillon/envoyé sont pilotés par `d.statut` ; passé
  // l'acceptation, `d.statut` reste figé à 'accepte' (règle #4 — les statuts
  // Devis/BC/Facture sont préservés 1:1) donc la piste avance via la présence
  // du BC / d'une facture liée / d'un chantier, jamais via `d.statut` lui-même.
  // refuse/expire = statuts terminaux NÉGATIFS : la piste s'arrête au dernier
  // jalon positif (envoyé) sans jamais franchir « Accepté ».
  const docTrackCurrent = (d.statut === 'refuse' || d.statut === 'expire' || d.is_expired)
    ? 'envoye'
    : d.statut === 'brouillon' ? 'brouillon'
      : d.statut === 'envoye' ? 'envoye'
        : chantierEnCours(d.chantier) ? 'chantier'
          : (d.factures_liees?.length > 0) ? 'facture'
            : d.bon_commande_etat?.exists ? 'bc'
              : 'accepte'
  const docTrackBlocked = d.bon_commande_etat?.mismatch ? ['bc'] : []

  // APX17 — les signaux SECONDAIRES du statut, rassemblés au lieu d'être
  // empilés dans la cellule (hauteur de ligne stable + scroll juste au-delà
  // de ~100 devis). Aucun signal n'est perdu : ils sont tous dans le Popover
  // « Détails », et l'anomalie de BC reste visible sur la ligne elle-même.
  const statutDetails = [
    d.statut === 'accepte' && d.option_acceptee ? (
      <span className="text-success">
        Option : {d.option_acceptee === 'avec_batterie' ? 'Avec batterie' : 'Sans batterie'}
      </span>
    ) : null,
    /* QJ22 — « Proposition signée » : un DevisSignature (loi 53-05) existe. */
    d.est_signe ? (
      <span className="inline-flex items-center gap-1 font-medium text-success">
        <Check className="size-3" aria-hidden="true" />
        Proposition signée
        {d.signature_info?.signataire_nom ? ` — ${d.signature_info.signataire_nom}` : ''}
        {d.signature_info?.signed_at ? ` le ${formatDateTime(d.signature_info.signed_at)}` : ''}
      </span>
    ) : null,
    /* U8 — état du bon de commande lié (lecture seule, OneToOne existant). */
    d.bon_commande_etat?.exists ? (
      <span className="text-muted-foreground">BC : {d.bon_commande_etat.statut_display}</span>
    ) : null,
    d.bon_commande_etat?.mismatch ? (
      <span className="inline-flex items-start gap-1 font-medium text-warning">
        <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
        {d.bon_commande_etat.exists
          ? 'Devis accepté mais BC annulé'
          : 'Devis accepté sans bon de commande'}
      </span>
    ) : null,
    /* VX215 — boucle « pris en charge » après « Contacter mon supérieur ». */
    superieurStatus[d.id]?.requested ? (
      <span
        data-testid={`superieur-status-${d.id}`}
        className={`inline-flex items-center gap-1 font-medium ${
          superieurStatus[d.id].seen ? 'text-success' : 'text-muted-foreground'
        }`}
      >
        {superieurStatus[d.id].seen ? <Check className="size-3 shrink-0" aria-hidden="true" /> : null}
        {superieurStatus[d.id].seen
          ? `Pris en charge${superieurStatus[d.id].seen_by?.[0] ? ' par ' + superieurStatus[d.id].seen_by[0] : ''}`
          : 'Avis demandé — en attente'}
      </span>
    ) : null,
  ].filter(Boolean)

  const isGenerating = pdfGenerating[d.id]
  // VX132 — chargement long conscient : libellés honnêtes qui tournent
  // pendant la génération du PDF premium (jamais de fausse barre de progression).
  const pdfLabel = useRotatingLabel(PDF_GENERATION_LABELS, { active: !!isGenerating })
  const isDownloading = pdfDownloading[d.id]
  // QX21 — passé 30 s, on n'abandonne plus le suivi : ce badge reste visible
  // tant que le polling se poursuit (aucun second job n'est jamais relancé
  // en dessous).
  const isSlowPolling = !!pdfSlowPoll[d.id]
  return (
    <Fragment key={d.id}>
    {/* QX12 — deep-link ?devis=<pk> : la ligne ciblée porte un id ancrable et
        un surlignage temporaire (l'effet de page scrolle jusqu'à cet id). */}
    <tr id={`devis-row-${d.id}`}
        style={highlightId === d.id
          ? { outline: '2px solid var(--color-primary, #2563eb)', outlineOffset: '-2px' }
          : undefined}>
      <td>
        <Checkbox
          checked={selectedIds.includes(d.id)}
          onCheckedChange={() => toggleSelected(d.id)}
          aria-label={`Sélectionner ${d.reference}`}
        />
      </td>
      <td data-testid={`ref-cell-${d.id}`}>
        {/* VX140 — cellule Référence à 2 niveaux : ligne 1 = référence + badges
            de version en gras ; ligne 2 = métadonnées compactes (versions,
            consultation, engagement) séparées par « · », muted, text-xs ;
            chips de documents liés en dessous (rendues, pas title-only, pour
            ne pas casser les tests U5 qui vérifient leur texte visible). */}
        <div className="text-sm font-semibold">
          {d.reference}
          {d.version > 1 && (
            <Badge tone="primary" className="ml-1.5">v{d.version}</Badge>
          )}
          {/* U7 — une révision remplacée (is_active=False) porte un
              badge « Remplacé » explicite ; le lien ouvre l'historique
              des versions (qui pointe vers la version courante). */}
          {d.is_active === false && (
            <Badge tone="neutral" className="ml-1.5">Remplacé</Badge>
          )}
        </div>
        {(d.superseded_by_ref
          || d.version > 1 || d.version_parent_ref
          || d.deja_consulte || engagementSummary(d.engagement)) && (
          <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
            {d.superseded_by_ref && (
              <span className="text-warning">
                remplacé par{' '}
                <button
                  type="button"
                  className="font-medium underline hover:no-underline"
                  onClick={() => setVersionsOpenId(
                    versionsOpenId === d.id ? null : d.id)}
                  title="Voir la version qui remplace ce devis"
                >
                  {d.superseded_by_ref}
                </button>
              </span>
            )}
            {d.superseded_by_ref
              && (d.version > 1 || d.version_parent_ref || d.deja_consulte
                || engagementSummary(d.engagement)) && <span aria-hidden="true">·</span>}
            {(d.version > 1 || d.superseded_by_ref || d.version_parent_ref) && (
              <button
                type="button"
                className="text-primary hover:underline"
                onClick={() => setVersionsOpenId(
                  versionsOpenId === d.id ? null : d.id)}
              >
                {versionsOpenId === d.id ? 'Masquer les versions' : 'Voir les versions'}
              </button>
            )}
            {(d.version > 1 || d.version_parent_ref)
              && (d.deja_consulte || engagementSummary(d.engagement)) && <span aria-hidden="true">·</span>}
            {/* QJ1 — Badge de consultation : affiché quand le lien public
                a été ouvert au moins une fois. Nombre de vues + date. */}
            {d.deja_consulte && (
              <span
                className="inline-flex items-center gap-1 font-medium text-primary"
                title={d.derniere_consultation
                  ? `Dernière ouverture : ${formatDateTime(d.derniere_consultation)}`
                  : 'Document consulté'}
              >
                <Eye className="size-3" aria-hidden="true" />
                Consulté ×{d.nombre_vues ?? 1}
              </span>
            )}
            {d.deja_consulte && engagementSummary(d.engagement) && <span aria-hidden="true">·</span>}
            {/* XSAL16 — résumé d'engagement par section de la proposition
                web (« a passé 2 min sur le prix, n'a pas ouvert l'étude »).
                Vide sans beacon (déjà serialisé, comportement QJ1 inchangé). */}
            {engagementSummary(d.engagement) && (
              <span title="Temps passé par section sur la proposition en ligne">
                {engagementSummary(d.engagement)}
              </span>
            )}
          </div>
        )}
        {/* U5 — Documents générés depuis ce devis : factures (chips
            cliquables → liste Factures) + bon de commande (→ BC).
            Lecture seule, données du serializer. */}
        {(d.factures_liees?.length > 0 || d.bon_commande_etat?.exists) && (
          <div
            className="mt-1 flex flex-wrap gap-1"
            title="Documents liés à ce devis"
          >
            {d.bon_commande_etat?.exists && (
              <button
                type="button"
                onClick={() => navigate('/ventes/bons-commande')}
                title={`Bon de commande ${d.bon_commande_etat.reference} — ${d.bon_commande_etat.statut_display}`}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2 py-0.5 text-xs font-medium hover:bg-muted"
              >
                <FileStack className="size-3" aria-hidden="true" />
                {d.bon_commande_etat.reference}
              </button>
            )}
            {(d.factures_liees ?? []).map(f => (
              <button
                key={f.id}
                type="button"
                onClick={() => navigate('/ventes/factures')}
                title={`Facture ${f.reference} — ${f.statut_display}`}
                className="inline-flex items-center gap-1 rounded-full border border-success/40 bg-success/10 px-2 py-0.5 text-xs font-medium text-success hover:bg-success/20"
              >
                <FileText className="size-3" aria-hidden="true" />
                {f.reference} · {f.statut_display}
              </button>
            ))}
          </div>
        )}
        {/* VX216(a) — rend le seam devis↔chantier VISIBLE côté vendeur (avant,
            seul InstallationDetail.jsx le détectait). Un chantier en cours a
            sa nomenclature (bom) GELÉE : éditer ce devis maintenant crée un
            écart que l'installateur découvrira seul sur le terrain. */}
        {chantierEnCours(d.chantier) && (
          <div
            className="mt-1 inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning"
            title="La nomenclature de ce chantier est gelée — éditer ce devis peut créer un écart devis↔chantier"
          >
            <AlertTriangle className="size-3" aria-hidden="true" />
            Chantier en cours (compo gelée)
          </div>
        )}
      </td>
      <td data-label="Client">
        {/* VX7 — calm color : le nom client est une donnée PRIMAIRE (contraste
            plein + poids medium), il ressort du chrome désaturé environnant. */}
        <span className="font-medium text-foreground">{d.client_nom ?? '—'}</span>
        {d.lead && (
          <div className="mt-1">
            <button
              type="button"
              title={[
                'Ouvrir le lead lié',
                d.lead_type_installation
                  ? `Type : ${d.lead_type_installation}` : null,
                d.lead_facture_hiver != null
                  ? `Facture hiver : ${formatMAD(d.lead_facture_hiver)}` : null,
              ].filter(Boolean).join('\n')}
              onClick={() => navigate(`/crm/leads?lead=${d.lead}`)}
              className="inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning hover:bg-warning/20"
            >
              ↗ {d.lead_nom ?? 'Lead'}
            </button>
            {/* PUB53 — traçabilité retour : ce devis vient (via son lead) d'une
                ad Meta → lien direct vers sa fiche « histoire complète »
                (PUB44). Gaté aux rôles qui voient /publicite. */}
            {d.lead_meta_ad_id && canSeePublicite && (
              <a
                href={`/publicite/ad/${encodeURIComponent(d.lead_meta_ad_id)}`}
                target="_blank"
                rel="noopener noreferrer"
                title="Ouvrir la fiche de l'annonce Meta à l'origine de ce lead"
                className="ml-1 inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary hover:bg-primary/20"
              >
                📣 Vient de la pub
              </a>
            )}
          </div>
        )}
      </td>
      {/* VX7 — calm color : les dates sont des métadonnées secondaires → mutées
          (le contraste plein est réservé au client, au total TTC et au statut). */}
      <td data-label="Créé le" className="text-muted-foreground">{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
      <td className="m-hide text-muted-foreground">
        {d.date_validite
          ? new Date(d.date_validite).toLocaleDateString('fr-FR')
          : '—'}
      </td>
      <td className="ta-right tabular-nums" data-label="Total TTC">
        {/* PVAB (fondateur 20/08) — devis à deux options : les DEUX totaux,
            « sans / avec » batterie, jamais un montant qui n'existe dans aucun
            document. Repli : total_affiche (option 1), puis total stocké. */}
        {d.nb_options === 2
         && d.comparaison_options?.sans?.ttc != null
         && d.comparaison_options?.avec?.ttc != null
          ? `${formatMAD(d.comparaison_options.sans.ttc)} / ${formatMAD(d.comparaison_options.avec.ttc)}`
          : ((d.total_affiche ?? d.total_ttc) != null
              ? formatMAD(d.total_affiche ?? d.total_ttc)
              : '—')}
        {d.nb_options === 2 && (
          <Badge tone="warning" className="ml-1.5"
                 title="Devis à deux options — sans batterie / avec batterie, remise incluse">
            2 options
          </Badge>
        )}
        {d.solde && (
          <div className="mt-1 text-xs text-muted-foreground">
            Facturé {d.solde.facture} / Payé {d.solde.paye} / Restant {d.solde.restant} MAD
          </div>
        )}
      </td>
      {/* APX17 — la cellule Statut empilait jusqu'à SIX blocs (pastille,
          piste, option acceptée, proposition signée, état du BC, incohérence
          BC, boucle « pris en charge ») : la hauteur de ligne variait du
          simple au triple. Comme la liste tourne sur le moteur `ui/datatable`,
          qui ESTIME une hauteur constante au-delà de ~100 lignes, cette
          variabilité décalait aussi le scroll. La cellule est désormais
          PLAFONNÉE à StatusPill + piste documentaire ; tout le reste vit dans
          un Popover « Détails » — aucun CSS `<td>` artisanal, le contenu est
          simplement borné. */}
      <td data-label="Statut">
        <StatusPill status={effStatut} label={STATUT_DISPLAY[effStatut] ?? STATUT_DISPLAY.brouillon} />
        {/* VX141 — le StatusPill est un fait isolé ; la piste ci-dessous
            visualise la CHAÎNE complète (un devis accepté sans BC actif est
            maintenant signalé visuellement, pas seulement en texte L563+). */}
        <DocumentStageTrack
          className="mt-1"
          stages={DOC_STATUT_TRACK}
          current={docTrackCurrent}
          blocked={docTrackBlocked}
        />
        {statutDetails.length > 0 && (
          <Popover>
            <PopoverTrigger
              className="mt-1 inline-flex cursor-pointer items-center gap-1 rounded-md border border-border bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground"
              aria-label={`Détails du statut — ${statutDetails.length} information(s)`}
            >
              Détails ({statutDetails.length})
              {/* L'anomalie ne se cache JAMAIS : elle reste signalée sur la
                  ligne, même repliée. */}
              {d.bon_commande_etat?.mismatch && (
                <AlertTriangle className="size-3 text-warning" aria-hidden="true" />
              )}
            </PopoverTrigger>
            <PopoverContent className="max-w-xs space-y-1.5 text-xs">
              {statutDetails.map((node, i) => <div key={i}>{node}</div>)}
            </PopoverContent>
          </Popover>
        )}
      </td>
      <td>
        <div className="flex flex-wrap items-center gap-2">
          {/* VX20 — « soupe d'actions » réduite : 2-3 actions primaires
              contextuelles restent des boutons directs (PDF, Envoyer/
              Accepter/Refuser selon statut, Générer facture) ; tout le reste
              (Éditer, Lien interne, Variante, Supprimer, Copier le lien,
              Design 3D, Aperçu, Télécharger, BC, Chantier, Créer projet, +
              l'ancien menu « Autres actions ») vit dans UN SEUL menu « ⋯ ».
              Anatomie de rangée Linear/Attio — actions révélées, jamais
              empilées. Hauteur de ligne stable, aucun bouton perdu. */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => openPdfModal(d)}
            loading={isGenerating}
            title="Générer le PDF (choix du format)"
          >
            <FileText /> {isGenerating ? pdfLabel : 'PDF'}
          </Button>
          {/* QX21 — passé 30 s, on n'abandonne plus le suivi : ce badge reste
              visible tant que le polling se poursuit (aucun second job
              n'est jamais relancé en dessous). */}
          {isSlowPolling && (
            <Badge tone="warning" title="Le PDF est toujours en cours de génération côté serveur — la page continue de vérifier automatiquement.">
              PDF toujours en cours…
            </Badge>
          )}

          {d.statut === 'brouillon' && (
            <Button
              size="sm"
              variant="outline"
              loading={statutActionId === d.id}
              onClick={() => handleEnvoyer(d)}
              title="Envoyer par WhatsApp (message + lien de proposition) — marque le devis « Envoyé »"
            >
              <Send /> Envoyer
            </Button>
          )}
          {/* VX222 — « Relancer » : pendant devis de la relance facture. Rouvre
              le flux WhatsApp EXISTANT en mode rappel (aperçu-puis-clic, jamais
              d'envoi auto) + consigne la relance au chatter. N'apparaît que sur
              un devis « Envoyé ». */}
          {d.statut === 'envoye' && (
            <Button
              size="sm"
              variant="outline"
              loading={statutActionId === d.id}
              onClick={() => handleRelancer(d)}
              title="Relancer ce devis par WhatsApp (message de rappel + note au chatter)"
            >
              <Bell /> Relancer
            </Button>
          )}
          {d.statut === 'envoye' && canValiderVente && (
            <Button
              size="sm"
              title="Marquer accepté (date + nom + option) — déclenche la création du chantier"
              onClick={() => openAcceptModal(d)}
            >
              <Check /> Accepter
            </Button>
          )}
          {d.statut === 'envoye' && canValiderVente && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => openRefusModal(d)}
              className="border-destructive/40 text-destructive hover:bg-destructive/10"
              title="Marquer ce devis comme refusé (motif obligatoire)"
            >
              <X /> Refuser
            </Button>
          )}

          {/* « Générer facture » TOUJOURS visible, pour montrer que
              c'est ici qu'un devis devient des factures. Désactivé
              tant que le devis n'est pas « Accepté », avec un indice
              VISIBLE (pas seulement au survol → lisible sur mobile). */}
          {d.statut !== 'accepte' ? (
            <div className="flex flex-col gap-0.5">
              <Button size="sm" variant="outline" disabled>
                Générer facture
              </Button>
              <span className="max-w-[190px] text-xs leading-tight text-muted-foreground">
                Passez le devis en « Accepté » pour générer les factures.
              </span>
            </div>
          ) : d.solde && d.solde.tranches_facturees >= d.solde.tranches_total ? (
            <Button size="sm" variant="outline" disabled
                    title="Toutes les tranches ont été facturées">
              Échéancier complet
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => handleGenererFacture(d)}
              loading={factureGenId === d.id}
              title="Générer la prochaine tranche de facture"
            >
              Générer facture
            </Button>
          )}

          {/* VX20 — menu « Plus » unique : regroupe TOUTES les actions
              secondaires (précédemment jusqu'à 10 boutons par ligne). */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="ghost" aria-label={`Plus d'actions — ${d.reference}`}>
                <MoreHorizontal className="size-4" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Plus d'actions</DropdownMenuLabel>
              <DropdownMenuItem
                disabled={d.statut !== 'brouillon'}
                onSelect={() => openEdit(d)}
              >
                Éditer
              </DropdownMenuItem>
              {/* VX79 — « Copier le lien interne » : URL de l'ERP partageable
                  (/ventes/devis?devis=<pk>) à envoyer à un collègue. Distinct
                  du lien PUBLIC de proposition (règle #4) plus bas — celui-ci
                  ouvre le devis DANS l'ERP, toujours disponible quel que soit
                  le statut. */}
              <DropdownMenuItem onSelect={() => copierLienInterne(d)}>
                <Link2 className="size-3.5" aria-hidden="true" />
                Lien interne
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={previewingId === d.id}
                onSelect={() => handlePreview(d)}
              >
                <Eye className="size-3.5" aria-hidden="true" />
                {previewingId === d.id ? 'Aperçu du PDF…' : 'Aperçu du PDF'}
              </DropdownMenuItem>
              {d.fichier_pdf && (
                <DropdownMenuItem
                  disabled={isDownloading}
                  onSelect={() => handleTelechargerPdf(d)}
                >
                  <FileDown className="size-3.5" aria-hidden="true" />
                  {isDownloading ? 'Téléchargement…' : 'Télécharger le dernier PDF'}
                </DropdownMenuItem>
              )}
              {/* VX44 — partage natif du PDF (feuille de partage iOS/Android →
                  WhatsApp/e-mail), repli téléchargement. */}
              {d.fichier_pdf && (
                <DropdownMenuItem
                  disabled={isDownloading}
                  onSelect={() => handlePartagerPdf(d)}
                >
                  <Share2 className="size-3.5" aria-hidden="true" />
                  Partager le PDF
                </DropdownMenuItem>
              )}
              {/* WR2 — Copier le lien de proposition (share_link) :
                  surface la fonctionnalité serveur invisible, sans passer
                  par un envoi email/WhatsApp. */}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem
                  disabled={shareBusyId === d.id}
                  onSelect={() => handleCopierLienProposition(d)}
                >
                  <Link2 className="size-3.5" aria-hidden="true" />
                  Copier le lien de la proposition{shareBusyId === d.id ? '…' : ''}
                </DropdownMenuItem>
              )}
              {/* QG10/QJ15 — « Variante » : ouvre une modale pour
                  confirmer/éditer le pourcentage (défaut = config société),
                  créer les 3 variantes puis router vers la comparaison
                  côte-à-côte. */}
              {d.statut === 'brouillon' && (
                <DropdownMenuItem onSelect={() => openVarianteModal(d)}>
                  <Copy className="size-3.5" aria-hidden="true" />
                  Variante
                </DropdownMenuItem>
              )}
              {/* GAMMES — « Créer une variante de gamme » : crée le devis
                  FRÈRE d'une seconde gamme (composition et prix propres, à
                  retoucher ensuite). Le libellé est libre — aucune marque
                  codée en dur ; défauts proposés : Essentielle / Premium. */}
              {d.statut === 'brouillon' && (
                <DropdownMenuItem onSelect={() => openGammeModal(d)}>
                  <Copy className="size-3.5" aria-hidden="true" />
                  Créer une variante de gamme
                </DropdownMenuItem>
              )}
              {/* PV23 — porte d'entrée du CALEPINAGE depuis la liste. Un devis
                  encore ouvert (brouillon / envoyé) se CONÇOIT — l'écran de
                  conception resynchronise ses lignes (PV21). Un devis figé ne
                  se conçoit plus : il se CONSULTE, et seulement s'il porte
                  réellement un plan (`roof_layout`, exposé par le serializer —
                  aucun champ backend ajouté pour cette entrée). */}
              {(effStatut === 'brouillon' || effStatut === 'envoye') && (
                <DropdownMenuItem
                  onSelect={() => navigate(`/ventes/devis/${d.id}/design`)}
                  aria-label={`Concevoir la toiture 3D de ${d.reference}`}
                >
                  <Box className="size-3.5" aria-hidden="true" />
                  Concevoir en 3D
                </DropdownMenuItem>
              )}
              {effStatut !== 'brouillon' && effStatut !== 'envoye' && d.roof_layout && (
                <DropdownMenuItem
                  onSelect={() => navigate(`/ventes/devis/${d.id}/3d`)}
                  aria-label={`Voir le design 3D de ${d.reference}`}
                >
                  <Box className="size-3.5" aria-hidden="true" />
                  Voir le design 3D
                </DropdownMenuItem>
              )}
              {/* QG11/QG12 — « Voir le design 3D » : ouvre le plan de toiture
                  (roof_layout) en lecture seule dans le détail, ou dans une
                  fenêtre séparée. N'apparaît que si un plan existe. */}
              {d.roof_layout && (
                <DropdownMenuItem onSelect={() => setRoofOpenId(
                  roofOpenId === d.id ? null : d.id)}>
                  <Box className="size-3.5" aria-hidden="true" />
                  Design 3D
                </DropdownMenuItem>
              )}
              {d.roof_layout && (
                <DropdownMenuItem
                  onSelect={() => window.open(`/ventes/devis/${d.id}/3d`, '_blank', 'noopener')}
                  aria-label={`Ouvrir le design 3D de ${d.reference} dans une fenêtre`}
                >
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                  Design 3D — nouvelle fenêtre
                </DropdownMenuItem>
              )}
              {d.statut === 'accepte' && (
                <DropdownMenuItem
                  disabled={convertingId === d.id}
                  onSelect={() => handleConvertBC(d)}
                >
                  <ArrowRight className="size-3.5" aria-hidden="true" />
                  Convertir en bon de commande
                </DropdownMenuItem>
              )}
              {d.statut === 'accepte' && (
                <DropdownMenuItem
                  disabled={chantierBusy === d.id}
                  onSelect={() => handleChantier(d)}
                >
                  <HardHat className="size-3.5" aria-hidden="true" />
                  {d.chantier ? `Voir le chantier ${d.chantier.reference}` : 'Créer le chantier'}
                </DropdownMenuItem>
              )}
              {/* XPRJ21 — Créer un projet (gestion de projet) depuis ce devis accepté. */}
              {d.statut === 'accepte' && (
                <DropdownMenuItem
                  disabled={projetBusy === d.id}
                  onSelect={() => handleCreerProjet(d)}
                >
                  <FolderKanban className="size-3.5" aria-hidden="true" />
                  Créer projet
                </DropdownMenuItem>
              )}
              {/* VX97 — journal des changements (qui/quand/ancien→nouveau),
                  section repliable ; distinct de la chaîne de versions. */}
              <DropdownMenuItem onSelect={() => toggleHistorique(d.id)}>
                {histoOpenId === d.id ? "Masquer l'historique" : "Historique des modifications"}
              </DropdownMenuItem>
              {/* WIR103/XFAC10 — proforma PDF (aucun impact comptable). */}
              <DropdownMenuItem onSelect={() => handleProformaPdf(d)}>
                Proforma (PDF)
              </DropdownMenuItem>
              {/* ZSAL8 — PDF du bon de commande lié (client `getBonCommandePdf`
                  déjà présent dans ventesApi.js, jamais appelé). Endpoint BC
                  distinct, ne touche pas au rendu /proposal du devis (règle #4). */}
              {d.bon_commande_etat?.exists && (
                <DropdownMenuItem onSelect={() => handleBonCommandePdf(d)}>
                  Bon de commande (PDF)
                </DropdownMenuItem>
              )}
              {/* WIR96 — suivi du partage : « vu le … » (OuverturePartage)
                  + relances consignées (RelanceDevisAbandonne). */}
              <DropdownMenuItem onSelect={() => toggleSuiviPartage(d.id)}>
                {suiviOpenId === d.id ? 'Masquer le suivi du partage' : 'Suivi du partage'}
              </DropdownMenuItem>
              {/* PV43 — étude électrique agrégée (chaînes/conformité/schéma
                  unifilaire/surcharges DC-AC-phases), calculée depuis les
                  lignes + le calepinage du devis. */}
              <DropdownMenuItem onSelect={() => setConceptionOpenId(
                conceptionOpenId === d.id ? null : d.id)}>
                {conceptionOpenId === d.id
                  ? 'Masquer la conception électrique' : 'Conception électrique'}
              </DropdownMenuItem>
              {/* PV76 — carte « Étude bancable » (P50/P90/PR/cascade des
                  pertes/payback/VAN/TRI), lecture de `etude_params.simulation`. */}
              <DropdownMenuItem onSelect={() => setEtudeOpenId(
                etudeOpenId === d.id ? null : d.id)}>
                {etudeOpenId === d.id ? "Masquer l'étude bancable" : 'Étude bancable'}
              </DropdownMenuItem>
              {/* QX27 — actions historiquement dans « Autres actions » :
                  Réviser, Approuver remise, Contacter mon supérieur, Email. */}
              {d.is_active && d.statut !== 'brouillon' && (
                <DropdownMenuItem onSelect={() => {
                  // VX216(a) — « Réviser » est le chemin d'édition réel d'un
                  // devis accepté : avertit AVANT si un chantier en cours
                  // (nomenclature gelée) est lié, pour éviter un écart
                  // devis↔chantier découvert seul par l'installateur.
                  if (chantierEnCours(d.chantier)) {
                    toast.warning(
                      `Le chantier ${d.chantier.reference} lié à ${d.reference} est en cours — sa nomenclature est gelée.`,
                    )
                  }
                  ventesApi.reviserDevis(d.id)
                    .then(() => dispatch(fetchDevis()))
                    .catch(() => {})
                }}>
                  Réviser (nouvelle version)
                </DropdownMenuItem>
              )}
              {role === 'admin' && d.statut === 'brouillon'
                && parseFloat(d.remise_globale) > 0 && !d.remise_approuvee && (
                <DropdownMenuItem onSelect={() => {
                  ventesApi.approuverRemise(d.id)
                    .then(() => dispatch(fetchDevis())).catch(() => {})
                }}>
                  Approuver la remise
                </DropdownMenuItem>
              )}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem
                  disabled={superieurBusyId === d.id}
                  onSelect={() => handleContacterSuperieur(d)}
                >
                  Contacter mon supérieur
                </DropdownMenuItem>
              )}
              {(d.statut === 'brouillon' || d.statut === 'envoye') && (
                <DropdownMenuItem onSelect={() => openEmailModal(d)}>
                  Envoyer par email
                </DropdownMenuItem>
              )}
              {canDelete && (
                <DropdownMenuItem
                  destructive
                  disabled={deletingId === d.id}
                  onSelect={(e) => { e.preventDefault(); handleDelete(d) }}
                >
                  Supprimer
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </td>
    </tr>
    {versionsOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Historique des versions
            </p>
            {versionChain.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Aucune autre version trouvée parmi les devis chargés.
              </p>
            ) : (
              <ul className="space-y-1 text-sm">
                {versionChain.map(v => (
                  <li key={v.id}
                      className="flex flex-wrap items-center gap-2">
                    <Badge tone={v.id === d.id ? 'primary' : 'neutral'}>
                      v{v.version || 1}
                    </Badge>
                    <strong>{v.reference}</strong>
                    <span className="text-xs text-muted-foreground">
                      {STATUT_DISPLAY[effStatutOf(v)] ?? v.statut}
                      {v.date_creation
                        ? ` · ${new Date(v.date_creation).toLocaleDateString('fr-FR')}` : ''}
                    </span>
                    {v.id === d.id && (
                      <span className="text-xs text-primary">(version affichée)</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </td>
      </tr>
    )}
    {/* VX97 — Panneau « Historique » : journal des changements du devis
        (DevisActivity). Qui / quand / ancien→nouveau. `prix_achat` jamais
        rendu (le journal ne le porte pas). */}
    {histoOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Historique des modifications — {d.reference}
            </p>
            {histoLoadingId === d.id ? (
              <p className="text-xs text-muted-foreground">Chargement…</p>
            ) : (histoCache[d.id]?.length ?? 0) === 0 ? (
              <p className="text-xs text-muted-foreground">
                Aucune modification consignée.
              </p>
            ) : (
              <ul className="space-y-1 text-sm">
                {histoCache[d.id].map(a => (
                  <li key={a.id} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="text-xs text-muted-foreground">
                      {a.created_at ? formatDateTime(a.created_at) : '—'}
                      {a.user_nom ? ` · ${a.user_nom}` : ''}
                    </span>
                    <span>
                      {a.body
                        ? a.body
                        : (
                          <>
                            <strong>{a.field_label || a.field}</strong>
                            {' : '}
                            <span className="text-muted-foreground">{a.old_value || '—'}</span>
                            {' → '}
                            <span>{a.new_value || '—'}</span>
                          </>
                        )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </td>
      </tr>
    )}
    {/* WIR96 — Panneau « Suivi du partage » : ouverture du lien de
        proposition + relances consignées côté marketing. */}
    {suiviOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-2">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Suivi du partage — {d.reference}
            </p>
            <DevisSuiviPartagePanel
              data={suiviCache[d.id]}
              loading={suiviLoadingId === d.id}
            />
          </div>
        </td>
      </tr>
    )}
    {/* QG11 — Panneau « Voir le design 3D » : rendu LECTURE
        SEULE du plan de toiture stocké (roof_layout). */}
    {roofOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs font-medium text-muted-foreground">
                Design 3D de la toiture — {d.reference}
              </p>
              <div className="flex items-center gap-2">
                {/* PV23 — depuis l'aperçu, reprendre le calepinage (devis
                    encore ouvert seulement : au-delà, le document est figé). */}
                {(effStatut === 'brouillon' || effStatut === 'envoye') && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate(`/ventes/devis/${d.id}/design`)}
                    title="Reprendre le calepinage de cette toiture"
                  >
                    Concevoir en 3D
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => window.open(`/ventes/devis/${d.id}/3d`, '_blank', 'noopener')}
                  title="Ouvrir dans une nouvelle fenêtre"
                >
                  <ExternalLink className="size-3.5 mr-1" aria-hidden="true" />
                  Ouvrir dans une fenêtre
                </Button>
              </div>
            </div>
            <div className="max-w-2xl">
              <RoofViewer
                layout={d.roof_layout}
                clientNom={d.client_nom}
                leadNom={d.lead_nom}
                lignes={d.lignes}
              />
            </div>
          </div>
        </td>
      </tr>
    )}
    {/* PV43 — Panneau « Conception électrique » : chaînes par MPPT,
        conformité, aperçu du schéma unifilaire, surcharges DC/AC/phases. */}
    {conceptionOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Conception électrique — {d.reference}
            </p>
            <ConceptionElectrique devisId={d.id} />
          </div>
        </td>
      </tr>
    )}
    {/* PV76 — Carte « Étude bancable » : lecture de
        `etude_params.simulation`, recalcul asynchrone (PV74). */}
    {etudeOpenId === d.id && (
      <tr>
        <td colSpan={8} className="bg-muted/30">
          <div className="px-3 py-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Étude bancable — {d.reference}
            </p>
            <EtudeBancable devis={d} onRefresh={() => dispatch(fetchDevis())} />
          </div>
        </td>
      </tr>
    )}
    </Fragment>
  )
}

export default function DevisList() {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant).
  useDocumentTitle('Devis')
  const dispatch = useDispatch()
  const navigate = useNavigate()
  // APX17 — confirmations maison (VX19/L152) : plus une seule popup du système.
  const { confirm, confirmDelete } = useConfirmDialog()
  const [searchParams, setSearchParams] = useSearchParams()
  const { devis, loading, error } = useSelector(s => s.ventes)
  const role = useSelector(s => s.auth.role)
  const canDelete = role === 'admin'  // règle existante : destroy = admin
  // QG10 — seul le Directeur / Commercial responsable peut MODIFIER le
  // pourcentage des variantes (le backend variante-config renvoie 403 sinon).
  // Les autres rôles voient la valeur par défaut en lecture seule.
  const canEditVariantePct = useHasPermission(null, ['Directeur', 'Commercial responsable'])
  // VX199 — accepter/refuser un devis exige la permission ERP fine
  // `ventes_valider` (garde backend HasPermissionOrLegacy) : on cache
  // l'affordance pour les rôles « lecture + une écriture » (ex. Commercial)
  // qui recevraient sinon 403 sur l'appel direct.
  const canValiderVente = useCanValiderVente()
  // PUB53 — badge « Vient de la pub » (lien retour vers /publicite/ad/:id) sur
  // une ligne dont le lead lié est un lead Meta : gaté aux mêmes rôles que le
  // module Publicité (responsable/admin — module.config.jsx).
  const canSeePublicite = useIsAdminOrResponsable()
  // J141 — chargement différé anti-scintillement : spinner discret puis squelette.
  const { showSpinner, showSkeleton } = useDelayedLoading(loading)

  const [showForm, setShowForm]       = useState(false)
  const [editDevis, setEditDevis]     = useState(null)
  const [convertingId, setConvertingId] = useState(null)
  const [factureGenId, setFactureGenId] = useState(null) // devis id en cours de facturation
  const [pdfGenerating, setPdfGenerating] = useState({}) // id → true
  // QX21 — au-delà de 30 s, la génération n'est PAS abandonnée : elle reste
  // visible comme « toujours en cours » (le job Celery continue côté serveur)
  // et le polling se poursuit à un rythme plus espacé, sans jamais relancer un
  // second job (un seul dispatch(genererPdfDevis) par appel de genererUnPdf).
  const [pdfSlowPoll, setPdfSlowPoll] = useState({}) // id → true
  const [pdfDownloading, setPdfDownloading] = useState({}) // id → true
  const [statutActionId, setStatutActionId] = useState(null) // envoi/refus en cours
  // APX14 — le devis dont l'aperçu inline est ouvert (null = panneau fermé).
  // `previewingId` en dérive pour que le libellé « Aperçu du PDF… » de la
  // ligne reste exactement celui d'avant.
  const [previewDevis, setPreviewDevis] = useState(null)
  const previewingId = previewDevis?.id ?? null
  // APX15(b) — mode d'affichage de la liste : tableau ou board par statut
  // DOCUMENT. Parité exacte avec la bascule Liste/Kanban des factures.
  const [viewMode, setViewMode] = useState('liste')
  // Panneau « historique des versions » : id du devis dont la chaîne est ouverte.
  // QG10 — deep-link ?variantes=<id> ouvre directement la comparaison au montage.
  const [versionsOpenId, setVersionsOpenId] = useState(() => {
    const v = searchParams.get('variantes')
    return v ? Number(v) : null
  })

  // ── QG10 — Modale « Variantes » : confirmer / éditer le pourcentage avant
  //    de créer les 3 variantes (−p / standard / +p) puis router vers la
  //    comparaison côte-à-côte (panneau versions de la liste). ──
  const [varianteTarget, setVarianteTarget] = useState(null) // devis source
  const [variantePct, setVariantePct] = useState('20')       // % éditable
  const [varianteBusy, setVarianteBusy] = useState(false)
  const [varianteLoadingCfg, setVarianteLoadingCfg] = useState(false)

  // ── GAMMES (fondateur 2026-08-18) — Modale « Créer une variante de gamme » :
  //    crée le devis FRÈRE d'une seconde gamme (mécanique de variantes QJ15).
  //    Les libellés sont LIBRES ; « Essentielle » / « Premium » ne sont que des
  //    défauts proposés, jamais une marque imposée. ──
  const [gammeTarget, setGammeTarget] = useState(null)
  const [gammeNom, setGammeNom] = useState('Premium')
  const [gammeNomSource, setGammeNomSource] = useState('Essentielle')
  const [gammeRecommandee, setGammeRecommandee] = useState(false)
  const [gammeBusy, setGammeBusy] = useState(false)

  // ── QG11/QG12 — Panneau « Voir le design 3D » : id du devis dont le plan de
  //    toiture (roof_layout) est ouvert en lecture seule dans le détail.
  //    Deep-link ?design3d=<id> l'ouvre directement au montage. ──
  const [roofOpenId, setRoofOpenId] = useState(() => {
    const r = searchParams.get('design3d')
    return r ? Number(r) : null
  })

  // VX97 — Panneau « Historique » (journal des changements DevisActivity : qui a
  // fait quoi / ancien→nouveau) — distinct de la chaîne de VERSIONS ci-dessus.
  // Feed existant monté en section repliable ; migrera vers ChatterTimeline (VX23)
  // quand il atterrira. `prix_achat` n'apparaît jamais (le journal ne le porte pas).
  const [histoOpenId, setHistoOpenId] = useState(null)
  const [histoCache, setHistoCache] = useState({})   // id → entrées
  const [histoLoadingId, setHistoLoadingId] = useState(null)
  const toggleHistorique = (id) => {
    if (histoOpenId === id) { setHistoOpenId(null); return }
    setHistoOpenId(id)
    if (histoCache[id] === undefined) {
      setHistoLoadingId(id)
      ventesApi.historiqueDevis(id)
        .then(res => setHistoCache(c => ({ ...c, [id]: res.data || [] })))
        .catch(() => setHistoCache(c => ({ ...c, [id]: [] })))
        .finally(() => setHistoLoadingId(l => (l === id ? null : l)))
    }
  }

  // WIR96 — Panneau « Suivi du partage » : ouverture du lien de proposition
  // (marketing.OuverturePartage, « vu le … ») + relances consignées
  // (marketing.RelanceDevisAbandonne). Même patron repliable que l'historique.
  const [suiviOpenId, setSuiviOpenId] = useState(null)
  const [suiviCache, setSuiviCache] = useState({})   // id → {ouverture, relances}
  const [suiviLoadingId, setSuiviLoadingId] = useState(null)
  const toggleSuiviPartage = (id) => {
    if (suiviOpenId === id) { setSuiviOpenId(null); return }
    setSuiviOpenId(id)
    if (suiviCache[id] === undefined) {
      setSuiviLoadingId(id)
      ventesApi.getSuiviPartageDevis(id)
        .then(res => setSuiviCache(c => ({ ...c, [id]: res.data || null })))
        .catch(() => setSuiviCache(c => ({ ...c, [id]: null })))
        .finally(() => setSuiviLoadingId(l => (l === id ? null : l)))
    }
  }

  // PV43 — Panneau « Conception électrique » : id du devis dont l'étude
  // électrique (chaînes/conformité/schéma/surcharges) est ouverte. Le
  // composant `<ConceptionElectrique>` gère lui-même son chargement/cache —
  // ce state ne fait QUE basculer sa visibilité (même patron que roofOpenId).
  const [conceptionOpenId, setConceptionOpenId] = useState(null)

  // PV76 — Carte « Étude bancable » : id du devis dont la carte
  // P50/P90/PR/cascade/payback/VAN/TRI est ouverte. `<EtudeBancable>` lit
  // `d.etude_params.simulation` directement (déjà porté par la ligne, comme
  // `roof_layout`) — aucun cache séparé nécessaire ici.
  const [etudeOpenId, setEtudeOpenId] = useState(null)

  // ── Filtre statut + recherche (référence / client) ──
  // QX12 — deep-link ?statut=<key> pré-règle le filtre au montage (liens de
  // notification / Dashboard). Une valeur inconnue retombe sur « tous ».
  const [statutFilter, setStatutFilter] = useState(() => {
    const s = searchParams.get('statut')
    return s && (s === 'tous' || STATUT_DISPLAY[s]) ? s : 'tous'
  })
  // VX250 — deep-link ?q=<texte> pré-règle la recherche (référence/client) au
  // montage — même convention que ?statut= ci-dessus. Jusqu'ici posé par
  // LIST_ROUTE.devis (entityRoutes.js, « voir tout » de GlobalSearch/⌘K) et
  // RelationCounters (fiches 360°) sans jamais être lu : le lien n'atterrissait
  // que sur la liste NUE. Le filtre `query` existant fait déjà exactement
  // référence/client (ligne ci-dessous) — aucune nouvelle logique de filtre.
  const [query, setQuery] = useState(() => searchParams.get('q') ?? '')
  // QX12 — deep-link ?devis=<pk> ouvre/surligne ce devis précis au montage
  // (notifications « Devis accepté »/« Devis expiré » qui pointaient vers une
  // route inexistante /devis/{pk} — le producteur redirige maintenant ici).
  const [highlightId] = useState(() => {
    const v = searchParams.get('devis')
    return v ? Number(v) : null
  })
  // U7 — masque par défaut les révisions remplacées (is_active=False) pour
  // qu'un devis révisé n'apparaisse plus comme un doublon « vivant ». Un
  // bouton « voir les versions remplacées » les réaffiche, toujours badgées
  // « Remplacé » + lien vers la version courante.
  const [showSuperseded, setShowSuperseded] = useState(false)
  // WIR21 — vues sauvegardées côté serveur (remplace le localStorage FG11 :
  // vues EQUIPE désormais visibles par l'équipe, cf. ViewsManagerPopover).
  const { createView: createDevisView } = useServerSavedViews(DL_ECRAN)
  const saveCurrentDevisView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    const trimmed = (name || '').trim()
    if (!trimmed) return
    createDevisView({
      nom: trimmed, configuration: { statutFilter, query }, visibilite: 'PERSONNELLE',
    }).catch(() => toast.error('Enregistrement de la vue impossible.'))
  }
  const applyDevisView = (configuration) => {
    if (configuration?.statutFilter !== undefined) setStatutFilter(configuration.statutFilter)
    if (configuration?.query !== undefined) setQuery(configuration.query)
  }

  // ── Sélection multiple pour génération PDF par lot ──
  const [selectedIds, setSelectedIds] = useState([]) // ids cochés
  const [batchPdf, setBatchPdf] = useState(false) // la modale PDF vise le lot

  // ── Choix du format PDF (parité simulateur) ──
  const [pdfTarget, setPdfTarget] = useState(null) // devis ciblé par la modale
  const [pdfMode, setPdfMode] = useState('full')
  const [showMonthly, setShowMonthly] = useState(true)
  const [devisFinal, setDevisFinal] = useState(false)
  const [paymentMode, setPaymentMode] = useState('standard')
  const [customAcompte, setCustomAcompte] = useState('')
  const [includeEtude, setIncludeEtude] = useState(false)

  // ── Modale d'acceptation inline (nom / date / option) ──
  const [acceptTarget, setAcceptTarget] = useState(null) // devis en cours d'acceptation
  const [acceptNom, setAcceptNom] = useState('')
  const [acceptDate, setAcceptDate] = useState('')
  const [acceptOption, setAcceptOption] = useState('sans_batterie')
  const [acceptBusy, setAcceptBusy] = useState(false)
  // VX155 — carte de victoire (montant réel ; pas de kWc ici, la vue liste ne
  // porte pas les lignes du devis — jamais un chiffre inventé).
  const [dealCelebration, setDealCelebration] = useState(null)

  // QJ14 — Modale « Envoyer par email » (PDF premium + lien tokenisé → client).
  const [emailTarget, setEmailTarget]   = useState(null)
  const [emailAddress, setEmailAddress] = useState('')
  const [emailBusy, setEmailBusy]       = useState(false)

  const openEmailModal = (d) => {
    setEmailTarget(d)
    setEmailAddress(d.client_email || '')
  }
  const closeEmailModal = () => { setEmailTarget(null); setEmailAddress('') }
  const submitEmail = async () => {
    if (!emailTarget) return
    setEmailBusy(true)
    try {
      const payload = emailAddress ? { to_email: emailAddress } : {}
      await ventesApi.envoyerEmailDevis(emailTarget.id, payload)
      closeEmailModal()
      dispatch(fetchDevis())
      // VX156/VX155 — moment « devis envoyé » : un jalon (toastMilestone), pas
      // un succès plat — réf/client/montant + la voix Taqinor en description.
      toastMilestone(`Devis ${emailTarget.reference} envoyé par email.`, {
        description: [emailTarget.client_nom, formatMAD(emailTarget.total_affiche ?? emailTarget.total_ttc), voice.devisSent]
          .filter(Boolean).join(' · '),
      })
    } catch (err) {
      toast.error(frenchError(err, 'Envoi email impossible.'))
    } finally {
      setEmailBusy(false)
    }
  }

  // T13 — la case « Inclure l'étude » n'a de sens qu'avec des données d'étude.
  const targetHasEtude = !!(pdfTarget?.etude_params
    && Object.keys(pdfTarget.etude_params).length > 0)
  // T14 — le format premium « full » n'est pas pertinent pour le pompage agricole.
  const targetIsAgricole = pdfTarget?.mode_installation === 'agricole'

  const openPdfModal = (d) => {
    setBatchPdf(false)
    setPdfTarget(d)
    // Agricole a désormais son propre format premium (4 pages) — défaut « full ».
    setPdfMode('full')
    setShowMonthly(true)
    setDevisFinal(false)
    setPaymentMode('standard')
    setCustomAcompte('')
    // T12/T13 — étude cochée par défaut pour un devis industriel disposant de
    // données d'étude ; sinon décochée (et désactivée plus bas si absente).
    const hasEtude = !!(d?.etude_params && Object.keys(d.etude_params).length > 0)
    setIncludeEtude(d?.mode_installation === 'industriel' && hasEtude)
  }

  // VX248 — « a » génère le PDF du devis FOCALISÉ (le deep-link ?devis=<pk>
  // déjà surligné/scrollé — même record que highlightId ci-dessus, jamais un
  // second concept de « devis actif »). Absent hors deep-link (liste nue) :
  // aucun devis n'est « focalisé » sans lien profond.
  const highlightedDevis = highlightId ? devis.find(d => d.id === highlightId) : null
  useFocusedRecordShortcuts(
    'devisDetail',
    { a: () => openPdfModal(highlightedDevis) },
    !!highlightedDevis,
  )

  // Ouvre la modale PDF pour le lot sélectionné (format partagé).
  const openBatchPdfModal = () => {
    setBatchPdf(true)
    setPdfTarget(null)
    setPdfMode('full')
    setShowMonthly(true)
    setDevisFinal(false)
    setPaymentMode('standard')
    setCustomAcompte('')
    setIncludeEtude(false)
  }

  const openAcceptModal = (d) => {
    setAcceptTarget(d)
    setAcceptNom('')
    setAcceptDate(new Date().toISOString().slice(0, 10))
    setAcceptOption('sans_batterie')
    setAcceptBusy(false)
  }

  // QG10 — ouvre la modale Variantes : pré-remplit le pourcentage depuis la
  // config société (CompanyProfile.variante_pct via GET variante-config), avec
  // repli à 20 % si la lecture échoue. La saisie n'est autorisée que pour le
  // Directeur / Commercial responsable (sinon champ en lecture seule).
  const openVarianteModal = async (d) => {
    setVarianteTarget(d)
    setVariantePct('20')
    setVarianteBusy(false)
    setVarianteLoadingCfg(true)
    try {
      const res = await ventesApi.getVarianteConfig()
      const pct = res?.data?.variante_pct
      if (pct != null) {
        // Le backend renvoie une chaîne décimale (« 20.00 ») — on l'arrondit.
        const n = Math.round(parseFloat(pct))
        if (Number.isFinite(n)) setVariantePct(String(n))
      }
    } catch { /* repli : 20 % par défaut déjà posé */ } finally {
      setVarianteLoadingCfg(false)
    }
  }
  const closeVarianteModal = () => { setVarianteTarget(null); setVarianteBusy(false) }

  // QG10 — crée les 3 variantes avec le pourcentage confirmé, puis navigue vers
  // la comparaison côte-à-côte : la liste avec le panneau « versions » du devis
  // source déplié (les variantes partagent son version_parent → elles y
  // apparaissent groupées). On passe le % en override de requête ; le backend
  // reste seul juge des rôles (403 si écriture non autorisée — ici on n'écrit
  // pas la config, on override juste la génération, ouverte aux responsables).
  const submitVariante = async () => {
    const d = varianteTarget
    if (!d) return
    setVarianteBusy(true)
    try {
      const pct = parseFloat(variantePct)
      const payload = (Number.isFinite(pct) && pct > 0 && pct < 100)
        ? { variante_pct: pct } : {}
      await ventesApi.dupliquerVariante(d.id, payload)
      dispatch(fetchDevis())
      toast.success(`Variantes créées pour ${d.reference}.`)
      closeVarianteModal()
      // Route vers la comparaison : panneau versions du devis source ouvert.
      setVersionsOpenId(d.id)
      setSearchParams({ variantes: String(d.id) }, { replace: true })
    } catch (err) {
      toast.error(frenchError(err, 'Création variantes impossible.'))
    } finally {
      setVarianteBusy(false)
    }
  }

  // GAMMES — ouvre la modale « Créer une variante de gamme ». Les deux libellés
  // sont pré-remplis avec les défauts proposés et restent librement éditables.
  const openGammeModal = (d) => {
    setGammeTarget(d)
    setGammeNom('Premium')
    setGammeNomSource(d?.etude_params?.gamme?.nom || 'Essentielle')
    setGammeRecommandee(false)
    setGammeBusy(false)
  }
  const closeGammeModal = () => { setGammeTarget(null); setGammeBusy(false) }

  // GAMMES — crée le devis frère de la seconde gamme puis ouvre la comparaison
  // côte-à-côte (les deux gammes partagent version_parent → panneau versions).
  const submitGamme = async () => {
    const d = gammeTarget
    if (!d) return
    const nom = (gammeNom || '').trim()
    if (!nom) { toast.error('Donnez un nom à la gamme.'); return }
    setGammeBusy(true)
    try {
      await ventesApi.dupliquerVarianteGamme(d.id, {
        nom,
        nom_source: (gammeNomSource || '').trim() || undefined,
        recommandee: gammeRecommandee,
      })
      dispatch(fetchDevis())
      toast.success(`Gamme « ${nom} » créée pour ${d.reference}.`)
      closeGammeModal()
      setVersionsOpenId(d.id)
      setSearchParams({ variantes: String(d.id) }, { replace: true })
    } catch (err) {
      toast.error(frenchError(err, 'Création de la gamme impossible.'))
    } finally {
      setGammeBusy(false)
    }
  }

  // VX55 — annule la requête en vol au démontage : sans ça, une réponse tardive
  // (3G qui cale) peut écraser l'état d'un AUTRE écran après navigation.
  useEffect(() => {
    const thunk = dispatch(fetchDevis())
    return () => thunk?.abort?.()
  }, [dispatch])

  // QX12 — une fois les devis chargés, fait défiler jusqu'à la ligne ciblée par
  // ?devis=<pk> et efface le paramètre après un court délai (la surbrillance
  // CSS reste tant que highlightId est posé ; on ne la clignote pas plus).
  useEffect(() => {
    if (!highlightId || loading) return
    const row = document.getElementById(`devis-row-${highlightId}`)
    if (row) row.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [highlightId, loading, devis])

  // VX79 — lien INTERNE partageable d'un devis : /ventes/devis?devis=<pk> (miroir
  // du deep-link QX12 déjà supporté au montage). Distinct du lien PUBLIC de
  // proposition (règle #4 — handleCopierLienProposition, intouché) : celui-ci
  // pointe vers l'ERP, à envoyer à un collègue (« regarde CE devis »).
  const copierLienInterne = async (d) => {
    const url = `${window.location.origin}/ventes/devis?devis=${d.id}`
    try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
    toast.success('Lien interne du devis copié.')
  }

  // WR2 — « Copier le lien proposition » : (re)mint le lien public tokenisé du
  // devis (DevisViewSet.share_link) et le copie au presse-papier, sans passer
  // par l'envoi email/WhatsApp. Surface une fonctionnalité serveur jusqu'ici
  // invisible côté ERP. Aucun statut ne bouge (le backend ne fait que produire
  // le lien).
  const [shareBusyId, setShareBusyId] = useState(null)
  const handleCopierLienProposition = async (d) => {
    setShareBusyId(d.id)
    try {
      const res = await ventesApi.shareLinkDevis(d.id)
      // Le backend renvoie {token, path} (path = /proposition/<slug-client>/
      // <token>, PV84 — slug cosmétique, jamais vérifié côté serveur) — on
      // reconstruit l'URL publique complète (site public, cf. VITE_PUBLIC_SITE_URL).
      // Le repli sans slug (token seul) ne sert que si le backend omettait
      // exceptionnellement `path` : il reste une route valide côté site.
      const path = res?.data?.path || (res?.data?.token ? `/proposition/${res.data.token}` : null)
      if (path) {
        const base = (import.meta.env.VITE_PUBLIC_SITE_URL || 'https://taqinor.ma').replace(/\/+$/, '')
        const url = `${base}${path.startsWith('/') ? path : `/${path}`}`
        try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
        toast.success('Lien de la proposition copié.')
      } else {
        toast.error('Lien de proposition indisponible.')
      }
    } catch (err) {
      toast.error(frenchError(err, 'Génération du lien impossible.'))
    } finally {
      setShareBusyId(null)
    }
  }

  // Création ET édition passent par la page générateur solaire (l'ancien
  // modal DevisForm est conservé mais n'est plus le chemin d'édition).
  const openNew  = () => navigate('/ventes/devis/nouveau')
  const openEdit = (d) => {
    if (d.statut !== 'brouillon') return
    // VX216(a) — garde défensive : un devis normalement brouillon ne porte
    // pas encore de chantier, mais si un lien existe malgré tout (ex. flux
    // hérité), le vendeur est prévenu avant d'éditer une composition gelée.
    if (chantierEnCours(d.chantier)) {
      toast.warning(
        `Le chantier ${d.chantier.reference} lié à ${d.reference} est en cours — sa nomenclature est gelée.`,
      )
    }
    navigate(`/ventes/devis/nouveau?edit=${d.id}`)
  }
  const closeForm = () => { setShowForm(false); setEditDevis(null) }
  const onSaved  = () => dispatch(fetchDevis())

  const [deletingId, setDeletingId] = useState(null)
  // APX17 — la confirmation de suppression passe par le dialogue maison
  // (AlertDialog Radix), plus par la popup du système. Elle vit ICI plutôt
  // que dans la ligne : une seule définition, un seul libellé.
  const handleDelete = async (d) => {
    const ok = await confirmDelete({
      title: `Supprimer le devis ${d.reference} ?`,
      description: 'Cette action est définitive et irréversible.',
    })
    if (!ok) return
    setDeletingId(d.id)
    try {
      await ventesApi.deleteDevis(d.id)
      dispatch(fetchDevis())
      toast.success(`Devis ${d.reference} supprimé.`)
    } catch (err) {
      toast.error(frenchError(err, 'Suppression impossible.'))
    } finally {
      setDeletingId(null)
    }
  }

  // QG8/QX22 — « Envoyer » = flux WhatsApp des leads (aperçu du message + lien
  // tokenisé). La modale se peuple désormais depuis une action de PRÉVISUALISATION
  // en LECTURE SEULE (whatsappPreviewDevis) — ouvrir-puis-fermer sans cliquer ne
  // marque plus rien « Envoyé ». Le devis n'est marqué « Envoyé » que sur le clic
  // réel vers wa.me (mark_devis_sent côté serveur, appelé par openWhatsApp).
  const [waTarget, setWaTarget] = useState(null)   // devis ciblé
  const [waData, setWaData] = useState(null)        // { wa_url, message, url }
  const [waSending, setWaSending] = useState(false)
  // VX222 — la même modale WhatsApp bascule en mode « relance » (message de
  // rappel + note au chatter) au lieu de l'envoi initial. Réinitialisé à la
  // fermeture pour qu'un « Envoyer » ultérieur reparte en mode initial.
  const [relanceMode, setRelanceMode] = useState(false)
  // GAMMES — ENVOI À LA CARTE : quand le devis appartient à une paire de
  // gammes, le vendeur choisit ici d'envoyer CETTE gamme seule ou LES DEUX
  // (défaut fondateur : les deux, comme l'axe batterie). Le mode part avec
  // l'envoi et vit ensuite sur le devis. `null` = devis sans gamme → la modale
  // est exactement celle d'aujourd'hui.
  const [waGammeEnvoi, setWaGammeEnvoi] = useState('les_deux')
  const handleEnvoyer = async (d) => {
    setStatutActionId(d.id)
    try {
      const res = await ventesApi.whatsappPreviewDevis(d.id)
      setWaTarget(d)
      setWaData(res.data)
      setWaGammeEnvoi(res?.data?.gamme?.envoi || 'les_deux')
      // Aperçu seul — AUCUNE mutation de statut ici (fermer la modale sans
      // cliquer « Ouvrir WhatsApp » laisse le devis brouillon).
    } catch (err) {
      toast.error(frenchError(err, 'Préparation WhatsApp impossible.'))
    } finally {
      setStatutActionId(null)
    }
  }
  // VX222 — « Relancer » un devis envoyé : rouvre la MÊME modale d'aperçu
  // WhatsApp (whatsappPreviewDevis, lecture seule) mais en mode relance. Aucune
  // mutation tant que le vendeur n'a pas cliqué « Ouvrir WhatsApp ».
  const handleRelancer = (d) => { setRelanceMode(true); handleEnvoyer(d) }

  // EZ3 — le panneau de succès du générateur enchaîne DIRECTEMENT sur l'action
  // suivante : `?envoyer=1` ouvre l'aperçu WhatsApp du devis ciblé, `?apercu=1`
  // ouvre l'aperçu PDF inline (APX14). Ce sont les flux EXISTANTS de cet écran
  // — aucun second chemin d'envoi ni de PDF n'est créé. Ne se déclenche
  // qu'UNE fois (le paramètre est consommé). Placé APRÈS `handleEnvoyer` :
  // un effet ne doit pas référencer une liaison déclarée plus bas.
  const enchaineFait = useRef(false)
  useEffect(() => {
    if (enchaineFait.current || !highlightId || loading) return
    if (!highlightedDevis) return
    const envoyer = searchParams.get('envoyer') === '1'
    const apercu = searchParams.get('apercu') === '1'
    if (!envoyer && !apercu) return
    enchaineFait.current = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- enchaînement d'un deep-link, une seule exécution gardée par enchaineFait
    if (envoyer) handleEnvoyer(highlightedDevis)
    else setPreviewDevis(highlightedDevis)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('envoyer')
      next.delete('apercu')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- enchaînement à UNE seule exécution
  }, [highlightId, highlightedDevis, loading])

  const closeWaModal = () => {
    setWaTarget(null); setWaData(null); setWaSending(false); setRelanceMode(false)
  }
  // QX22 — clic réel sur « Ouvrir WhatsApp » : ouvre wa.me PUIS marque le devis
  // « Envoyé » côté serveur (whatsappDevis, l'action d'envoi véritable — jamais
  // au moment de l'ouverture de la modale). Le lien s'ouvre même si le marquage
  // échoue (le message a déjà été montré au vendeur ; on prévient de l'échec).
  const openWhatsApp = async () => {
    if (!waTarget) return
    // VX222 — mode relance : le lien wa.me porte un message de RAPPEL ; sinon,
    // le lien d'aperçu initial (QX22) inchangé.
    if (relanceMode) {
      const rUrl = buildRelanceWaUrl(waData, waTarget.reference)
      if (rUrl) window.open(rUrl, '_blank', 'noopener')
    } else if (waData?.wa_url) window.open(waData.wa_url, '_blank', 'noopener')
    setWaSending(true)
    try {
      // GAMMES — le mode d'envoi choisi part AVEC l'envoi (le backend l'écrit
      // sur les deux gammes). Omis quand le devis n'appartient à aucune paire.
      await ventesApi.whatsappDevis(
        waTarget.id,
        waData?.gamme ? { gamme_envoi: waGammeEnvoi } : {},
      )
      // VX222 — consigne la relance au chatter du devis (DevisActivity, VX97) ;
      // best-effort, ne bloque jamais l'ouverture WhatsApp déjà effectuée.
      if (relanceMode) {
        ventesApi.noterDevis(
          waTarget.id, `Relance du devis ${waTarget.reference} envoyée par WhatsApp.`,
        ).catch(() => {})
      }
      dispatch(fetchDevis())
    } catch (err) {
      toast.error(frenchError(err, 'Le marquage « Envoyé » a échoué — vérifiez le devis.'))
    } finally {
      setWaSending(false)
      closeWaModal()
    }
  }

  // QJ28 — « Contacter mon supérieur » : notifie le supérieur du vendeur
  // (in-app + canaux configurés) avec un lien vers ce devis. Manuel, jamais
  // automatique — un clic = une notification.
  const [superieurBusyId, setSuperieurBusyId] = useState(null)
  // VX215 — boucle de retour « pris en charge » : { [devisId]: { requested,
  // seen, seen_by } }, sondée (VX56 useVisibilityAwarePolling) tant qu'une
  // demande reste non vue — jamais de polling une fois « vu ».
  const [superieurStatus, setSuperieurStatus] = useState({})
  const refreshSuperieurStatus = async (devisId) => {
    try {
      const res = await ventesApi.superiorContactStatus(devisId)
      setSuperieurStatus((prev) => ({ ...prev, [devisId]: res.data }))
    } catch {
      // Best-effort — un sondage manqué n'affiche simplement rien de nouveau.
    }
  }
  const pendingSuperieurIds = useMemo(
    () => Object.entries(superieurStatus)
      .filter(([, s]) => s?.requested && !s.seen)
      .map(([id]) => id),
    [superieurStatus],
  )
  useVisibilityAwarePolling(
    [{ fn: () => pendingSuperieurIds.forEach(refreshSuperieurStatus), intervalMs: 20000 }],
    { enabled: pendingSuperieurIds.length > 0 },
  )
  const handleContacterSuperieur = async (d) => {
    setSuperieurBusyId(d.id)
    try {
      await ventesApi.contacterSuperieur(d.id)
      toast.success('Votre supérieur a été notifié.')
      refreshSuperieurStatus(d.id)
    } catch (err) {
      toast.error(frenchError(err, 'Notification du supérieur impossible.'))
    } finally {
      setSuperieurBusyId(null)
    }
  }

  // WR1/QX26 — Refuser un devis envoyé : passe par l'action dédiée `refuser`
  // (motif/date/chatter + événement devis_refused qui clôt le lead), plus
  // JAMAIS un PATCH statut direct qui contournait ce chemin (funnel intact).
  // QX26 — le motif n'est plus un window.prompt optionnel (perdu, illisible en
  // reporting) : une modale OBLIGATOIRE impose un motif de la taxonomie
  // MotifPerte (partagée avec le CRM, endpoint company-scoped existant) + une
  // note libre optionnelle. Sans motif sélectionné, la confirmation reste
  // bloquée — les données de perte redeviennent exploitables.
  const [refusTarget, setRefusTarget] = useState(null)
  const [motifsPerte, setMotifsPerte] = useState([])
  const [refusMotifId, setRefusMotifId] = useState('')
  const [refusNote, setRefusNote] = useState('')
  const [refusBusy, setRefusBusy] = useState(false)
  // VX172 — pending visible sur « Exporter Excel » (VX49 pose déjà le toast
  // d'erreur ; ceci ajoute juste l'état chargement manquant).
  const [xlsxBusy, setXlsxBusy] = useState(false)

  const openRefusModal = (d) => {
    setRefusTarget(d)
    setRefusMotifId('')
    setRefusNote('')
    setRefusBusy(false)
    crmApi.getMotifsPerte()
      .then(r => setMotifsPerte(r.data?.results ?? r.data ?? []))
      .catch(() => setMotifsPerte([]))
  }
  const closeRefusModal = () => { setRefusTarget(null); setRefusBusy(false) }

  const submitRefus = async () => {
    const d = refusTarget
    if (!d || !refusMotifId) return
    setRefusBusy(true)
    try {
      await ventesApi.refuserDevis(d.id, {
        motif_perte: refusMotifId,
        motif: refusNote.trim() || undefined,
      })
      dispatch(fetchDevis())
      toast.success(`Devis ${d.reference} marqué « Refusé ».`)
      closeRefusModal()
    } catch (err) {
      toast.error(frenchError(err, 'Refus impossible.'))
    } finally {
      setRefusBusy(false)
    }
  }

  // T9 — Acceptation via la modale inline (nom / date / option).
  const submitAccept = async () => {
    const d = acceptTarget
    if (!d) return
    setAcceptBusy(true)
    try {
      await ventesApi.accepterDevis(d.id, {
        nom: acceptNom,
        date: acceptDate,
        option: d.nb_options === 2 ? acceptOption : '',
      })
      setAcceptTarget(null)
      dispatch(fetchDevis())
      // VX40/VX155 — le SEUL moment célébré de l'app : devis envoyé→accepté
      // (rare, lié au revenu). La carte de victoire remplace le toast plat
      // (montant réel ; pas de kWc dans la vue liste — jamais inventé).
      setDealCelebration({
        reference: d.reference,
        montantTtc: parseFloat(d.total_affiche ?? d.total_ttc) || 0,
        kwc: null,
      })
    } catch (err) {
      toast.error(frenchError(err, 'Acceptation impossible.'))
    } finally {
      setAcceptBusy(false)
    }
  }

  // T10 — Aperçu PDF en application : récupère le blob /proposal et l'ouvre dans
  // un nouvel onglet (mêmes params que la modale d'aperçu de la fiche lead).
  // VX48 — l'onglet est pré-ouvert SYNCHRONE dans le geste (avant l'await),
  // sinon Safari iOS bloque silencieusement le window.open post-await.
  // APX14 — « Aperçu » ne QUITTE plus l'écran : il ouvre le panneau inline
  // (PdfCanvas, déjà consommé par 4 autres écrans, jamais par celui-ci).
  // La SOURCE reste le moteur vendorisé `/proposal` — aucun chemin PDF
  // nouveau, aucun changement de statut (règle #4). Télécharger et Ouvrir
  // dans un onglet restent offerts DANS le panneau, en repli.
  const handlePreview = (d) => { setPreviewDevis(d) }

  // Récupère les octets du PDF de proposition du devis en aperçu. Passée au
  // panneau, qui ne connaît aucune URL. Le message d'erreur reste celui,
  // français, que la liste sait déjà produire (T11 — moteur sans onduleur).
  const fetchDevisPreviewBlob = useCallback(async () => {
    const d = previewDevis
    if (!d) return null
    try {
      const params = proposalParams(
        'full',
        d.mode_installation === 'industriel'
          && !!(d.etude_params && Object.keys(d.etude_params).length > 0),
      )
      const res = await ventesApi.getProposalPdf(d.id, params)
      return pdfBlob(res.data)
    } catch (err) {
      const msg = frenchError(err, '')
      if (/onduleur|inverter/i.test(msg)) {
        throw new Error('Ce devis n\'a aucun onduleur — choisissez le format une page.')
      }
      throw new Error(msg || 'Aperçu du PDF indisponible.')
    }
  }, [previewDevis])

  const [chantierBusy, setChantierBusy] = useState(null)
  // « Créer le chantier » sur un devis accepté : crée (ou ouvre s'il existe
  // déjà) le chantier pré-rempli, puis navigue vers la page Chantiers.
  const handleChantier = async (d) => {
    if (d.chantier) { navigate('/chantiers'); return }
    setChantierBusy(d.id)
    try {
      await installationsApi.createFromDevis(d.id)
      dispatch(fetchDevis())
      navigate('/chantiers')
    } catch (err) {
      toast.error(frenchError(err, 'Création du chantier impossible.'))
    } finally {
      setChantierBusy(null)
    }
  }

  // XPRJ21 — « Créer un projet » depuis un devis accepté : action utilisateur
  // explicite (jamais automatique sur devis_accepted — le chantier auto
  // existe déjà côté installations). Crée le Projet + son lien + un budget v1
  // pré-ventilé depuis les lignes du devis, puis navigue vers le module Projets.
  const [projetBusy, setProjetBusy] = useState(null)
  const handleCreerProjet = async (d) => {
    setProjetBusy(d.id)
    try {
      const res = await gestionProjetApi.creerProjetDepuisDevis(d.id)
      toast.success(`Projet ${res.data.code} créé.`)
      navigate(`/projets/${res.data.id}`)
    } catch (err) {
      toast.error(frenchError(err, 'Création du projet impossible.'))
    } finally {
      setProjetBusy(null)
    }
  }

  const handleConvertBC = async (d) => {
    const ok = await confirm({
      title: `Convertir « ${d.reference} » en bon de commande ?`,
      confirmLabel: 'Convertir',
      destructive: false,
    })
    if (!ok) return
    setConvertingId(d.id)
    try {
      await dispatch(convertirDevisEnBC(d.id)).unwrap()
      dispatch(fetchDevis())
      toast.success(`Bon de commande créé depuis ${d.reference}.`)
    } catch (err) {
      toast.error(frenchError(err, 'Conversion en bon de commande impossible.'))
    } finally {
      setConvertingId(null)
    }
  }

  const handleGenererFacture = async (d) => {
    setFactureGenId(d.id)
    try {
      const res = await ventesApi.genererFacture(d.id)
      const f = res.data
      toast.success(`${f.type_facture_display ?? 'Facture'} ${f.reference} créée.`)
      dispatch(fetchDevis())
    } catch (err) {
      toast.error(frenchError(err, 'Génération de facture impossible.'))
    } finally {
      setFactureGenId(null)
    }
  }

  // Construit les options PDF depuis l'état de la modale (partagé une page / lot).
  const buildPdfOptions = (d) => ({
    pdf_mode: pdfMode,
    show_monthly: showMonthly,
    devis_final: devisFinal,
    payment_mode: paymentMode,
    custom_acompte: (devisFinal && paymentMode === 'custom' && customAcompte !== '')
      ? parseFloat(customAcompte) : null,
    // T12/T13 — étude uniquement si premium ET données d'étude présentes.
    include_etude: pdfMode === 'full' && includeEtude
      && !!(d?.etude_params && Object.keys(d.etude_params).length > 0),
  })

  // QG1 — Lance la génération d'un PDF + polling silencieux jusqu'à fichier
  // prêt. Le PDF s'ouvre/télécharge AUTOMATIQUEMENT dès qu'il est prêt (plus
  // besoin d'un second clic sur le bouton vert, qui reste disponible pour
  // re-télécharger). Renvoie une promesse résolue quand la génération est
  // acceptée (pas attendue jusqu'au fichier final), pour permettre
  // l'enchaînement par lot.
  const genererUnPdf = async (d, { autoOpen = true } = {}) => {
    setPdfGenerating(prev => ({ ...prev, [d.id]: true }))
    setPdfSlowPoll(prev => ({ ...prev, [d.id]: false }))
    try {
      await dispatch(genererPdfDevis({ id: d.id, options: buildPdfOptions(d) })).unwrap()
      let attempts = 0
      // QX21 — 15 tentatives × 2 s = 30 s au rythme rapide ; passé ce cap, le
      // job Celery n'est PAS relancé (un seul dispatch a eu lieu ci-dessus) —
      // on continue simplement à interroger, plus espacé (10 s), et on affiche
      // « toujours en cours » au lieu d'abandonner silencieusement.
      const FAST_ATTEMPTS = 15
      const poll = async () => {
        const slow = attempts >= FAST_ATTEMPTS
        attempts += 1
        if (slow && !pdfSlowPoll[d.id]) {
          setPdfSlowPoll(prev => ({ ...prev, [d.id]: true }))
          if (autoOpen) {
            toast(`${d.reference} : le PDF est toujours en cours de génération — la page continue de vérifier automatiquement.`)
          }
        }
        try {
          const res = await ventesApi.getDevisById(d.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchDevis())
            setPdfSlowPoll(prev => ({ ...prev, [d.id]: false }))
            if (autoOpen) {
              // VX48 — l'auto-open existant (QG1) reste l'expérience PAR
              // DÉFAUT et se déclenche EN PREMIER ; on n'affiche le toast
              // d'action « Ouvrir » (tap = geste frais, seul geste que
              // Safari iOS honore après ce polling asynchrone) que si le
              // téléchargement/l'ouverture automatique échoue.
              try {
                const pdfRes = await ventesApi.telechargerPdfDevis(d.id)
                openPdfBlob(pdfRes.data, filenameFromResponse(pdfRes, `${d.reference}.pdf`))
              } catch {
                toast.error(`${d.reference} : PDF prêt — l'ouverture automatique a échoué.`, {
                  action: {
                    label: 'Ouvrir',
                    onClick: async () => {
                      try {
                        const pdfRes = await ventesApi.telechargerPdfDevis(d.id)
                        openPdfBlob(pdfRes.data, filenameFromResponse(pdfRes, `${d.reference}.pdf`))
                      } catch {
                        toast.error(`${d.reference} : PDF indisponible — utilisez le bouton de téléchargement.`)
                      }
                    },
                  },
                })
              }
            }
          } else {
            setTimeout(poll, slow ? 10000 : 2000)
          }
        } catch { /* ignore poll errors — la boucle continue */ }
      }
      setTimeout(poll, 2000)
      return true
    } catch (err) {
      // T11 — surface claire de l'absence d'onduleur (ValueError moteur premium).
      const msg = frenchError(err, '')
      if (/onduleur|inverter/i.test(msg)) {
        toast.error(`${d.reference} : ce devis n'a aucun onduleur — choisissez le format une page.`)
      } else {
        toast.error(`${d.reference} : ${msg || 'erreur lors de la génération PDF.'}`)
      }
      return false
    } finally {
      setPdfGenerating(prev => ({ ...prev, [d.id]: false }))
    }
  }

  const handleGenererPdf = async (d) => {
    setPdfTarget(null)
    await genererUnPdf(d)
  }

  // T7 — Génération PDF par lot : même format pour tous les devis sélectionnés.
  // QG1 — pas d'ouverture automatique par lot (N devis => N ouvertures serait
  // intrusif) : chacun reste téléchargeable via son bouton vert une fois prêt.
  const handleGenererPdfLot = async () => {
    const cibles = devis.filter(d => selectedIds.includes(d.id))
    setBatchPdf(false)
    let ok = 0
    for (const d of cibles) {
      if (await genererUnPdf(d, { autoOpen: false })) ok += 1
    }
    if (ok > 0) toast.success(`Génération lancée pour ${ok} devis.`)
    setSelectedIds([])
  }

  // WIR103/XFAC10 — Proforma PDF : document sans aucun impact comptable
  // (jamais une facture, jamais une écriture). Le backend était complet et
  // testé mais n'avait AUCUN appelant côté client. Le POST renvoie le PDF.
  const handleProformaPdf = async (d) => {
    try {
      const res = await ventesApi.getProformaPdf(d.id)
      openPdfBlob(res.data, `Proforma_${d.reference}.pdf`)
    } catch {
      toast.error('Proforma indisponible.')
    }
  }

  // ZSAL8 — PDF du bon de commande lié (endpoint GET .../pdf/ backend
  // complet, jamais appelé côté client).
  const handleBonCommandePdf = async (d) => {
    const bcId = d.bon_commande_etat?.id
    if (!bcId) return
    try {
      const res = await ventesApi.getBonCommandePdf(bcId)
      openPdfBlob(res.data, filenameFromResponse(res, `${d.bon_commande_etat.reference}.pdf`))
    } catch {
      toast.error('PDF du bon de commande indisponible.')
    }
  }

  const handleTelechargerPdf = async (d) => {
    setPdfDownloading(prev => ({ ...prev, [d.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfDevis(d.id)
      // QD2 — nom cohérent posé par le serveur (repli sur la référence).
      openPdfBlob(res.data, filenameFromResponse(res, `${d.reference}.pdf`))
    } catch {
      toast.error('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [d.id]: false }))
    }
  }

  // VX44 — « Partager le PDF » : quand la Web Share API accepte les fichiers
  // (iOS 15+, Android Chrome), le PDF du devis part directement dans la feuille
  // de partage native (WhatsApp, e-mail…) ; sinon repli propre sur le
  // téléchargement. Aucun nouveau chemin PDF — c'est le PDF existant du devis
  // (règle #4 : le rendu /proposal n'est pas touché).
  const handlePartagerPdf = async (d) => {
    setPdfDownloading(prev => ({ ...prev, [d.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfDevis(d.id)
      const filename = filenameFromResponse(res, `${d.reference}.pdf`)
      const file = new File([res.data], filename, { type: 'application/pdf' })
      const shareData = { files: [file], title: `Devis ${d.reference}` }
      if (navigator.canShare?.(shareData) && navigator.share) {
        try {
          await navigator.share(shareData)
        } catch (err) {
          // L'utilisateur a annulé la feuille de partage : ne rien signaler.
          if (err?.name !== 'AbortError') {
            openPdfBlob(res.data, filename)
          }
        }
      } else {
        // Pas de partage natif de fichiers : repli sur le téléchargement.
        openPdfBlob(res.data, filename)
      }
    } catch {
      toast.error('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [d.id]: false }))
    }
  }

  // Statut effectif : un devis dont la validité est dépassée s'affiche « Expiré »
  // sans changer son statut stocké (logique T7, partagée filtre/résumé/tableau).
  const effStatutOf = (d) => (d.is_expired ? 'expire' : d.statut)

  // VX236 — `?equipe=<id>` (lien depuis MesEquipesCard) : filtre additif sur
  // les membres de l'équipe (commercial créateur du devis).
  const equipeId = searchParams.get('equipe')
  const equipeMembreIds = useEquipeMembreIds(equipeId)

  // T5 — Liste filtrée (statut effectif) + recherche (référence / client).
  // U7 — les révisions remplacées (is_active === false) sont masquées tant que
  // le bouton « voir les versions remplacées » n'est pas activé.
  const filteredDevis = useMemo(() => {
    const q = query.trim().toLowerCase()
    return devis.filter(d => {
      if (!showSuperseded && d.is_active === false) return false
      if (statutFilter !== 'tous' && effStatutOf(d) !== statutFilter) return false
      if (equipeId && equipeMembreIds && !equipeMembreIds.has(d.created_by)) return false
      if (!q) return true
      const ref = String(d.reference ?? '').toLowerCase()
      const client = String(d.client_nom ?? '').toLowerCase()
      return ref.includes(q) || client.includes(q)
    })
  }, [devis, statutFilter, query, showSuperseded, equipeId, equipeMembreIds])

  // VX79 — lien profond ?devis=<pk> pointant vers un devis introuvable parmi
  // ceux chargés (une fois le chargement terminé) : signalé par un EmptyState
  // inline, jamais une page blanche. Un devis masqué (révision remplacée) reste
  // « trouvé » — on cherche dans TOUS les devis chargés, pas seulement filtrés.
  const highlightMissing = !!highlightId && !loading
    && !devis.some(d => d.id === highlightId)

  // U7 — nombre de révisions remplacées actuellement masquées (pour le bouton
  // de bascule + le compteur).
  const supersededCount = useMemo(
    () => devis.filter(d => d.is_active === false).length,
    [devis],
  )

  // Chaîne de révisions d'un devis : remonte version_parent_ref jusqu'au plus
  // ancien, puis ajoute la version courante et descend via superseded_by_ref.
  // Triée par numéro de version croissant pour un affichage lisible.
  const versionChain = useMemo(() => {
    if (versionsOpenId == null) return []
    const byRef = new Map(devis.map(d => [d.reference, d]))
    const cur = devis.find(d => d.id === versionsOpenId)
    if (!cur) return []
    const seen = new Set()
    const chain = []
    // Remonter vers les versions plus anciennes.
    let node = cur
    while (node && !seen.has(node.id)) {
      seen.add(node.id)
      chain.push(node)
      node = node.version_parent_ref ? byRef.get(node.version_parent_ref) : null
    }
    // Descendre vers les versions plus récentes (remplaçantes).
    node = cur.superseded_by_ref ? byRef.get(cur.superseded_by_ref) : null
    while (node && !seen.has(node.id)) {
      seen.add(node.id)
      chain.push(node)
      node = node.superseded_by_ref ? byRef.get(node.superseded_by_ref) : null
    }
    return chain.sort((a, b) => (a.version || 1) - (b.version || 1))
  }, [versionsOpenId, devis])

  // T6 — Résumé : nombre + total TTC par statut effectif (sur les devis chargés).
  const summary = useMemo(() => {
    const acc = {}
    for (const key of Object.keys(STATUT_DISPLAY)) acc[key] = { count: 0, total: 0 }
    for (const d of devis) {
      const key = effStatutOf(d)
      if (!acc[key]) acc[key] = { count: 0, total: 0 }
      acc[key].count += 1
      acc[key].total += Number(d.total_affiche ?? d.total_ttc ?? 0) || 0
    }
    return acc
  }, [devis])

  // T15 — Devis envoyés expirant dans ≤ 7 jours (et pas encore expirés).
  const expiringSoon = useMemo(() => devis.filter(d => {
    if (d.statut !== 'envoye' || d.is_expired) return false
    const days = daysUntil(d.date_expiration)
    return days !== null && days >= 0 && days <= 7
  }), [devis])

  // T16 — Répartition batterie sur les devis acceptés (option_acceptee).
  const batteryInsight = useMemo(() => {
    let avec = 0; let sans = 0
    for (const d of devis) {
      if (d.statut !== 'accepte') continue
      if (d.option_acceptee === 'avec_batterie') avec += 1
      else if (d.option_acceptee === 'sans_batterie') sans += 1
    }
    return { avec, sans }
  }, [devis])

  const toggleSelected = (id) => setSelectedIds(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  const allFilteredSelected = filteredDevis.length > 0
    && filteredDevis.every(d => selectedIds.includes(d.id))
  const toggleSelectAll = () => setSelectedIds(prev => (
    allFilteredSelected
      ? prev.filter(id => !filteredDevis.some(d => d.id === id))
      : [...new Set([...prev, ...filteredDevis.map(d => d.id)])]
  ))

  // ── ARC49 — Sac de contexte passé à chaque <DevisRow> (« lignes divisées »).
  // Regroupe l'état + les handlers que la ligne utilisait déjà depuis la clôture ;
  // aucune valeur n'est transformée. `versionChain` est mémoïsé plus haut sur
  // `versionsOpenId` (seule la ligne ouverte le rend), donc le partager est sûr.
  const rowCtx = {
    selectedIds, toggleSelected,
    versionsOpenId, setVersionsOpenId, roofOpenId, setRoofOpenId,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    suiviOpenId, toggleSuiviPartage, suiviCache, suiviLoadingId,
    conceptionOpenId, setConceptionOpenId,
    etudeOpenId, setEtudeOpenId,
    versionChain, effStatutOf,
    navigate, dispatch,
    role, canDelete, canValiderVente, canSeePublicite, highlightId,
    deletingId, statutActionId, superieurBusyId, superieurStatus, shareBusyId, previewingId,
    pdfGenerating, pdfDownloading, pdfSlowPoll, convertingId, chantierBusy, projetBusy, factureGenId,
    openEdit, openVarianteModal, openGammeModal, handleDelete, handleEnvoyer, handleRelancer,
    handleContacterSuperieur,
    openEmailModal, handleCopierLienProposition, copierLienInterne, handlePreview, openPdfModal,
    handleTelechargerPdf, handlePartagerPdf, openAcceptModal, openRefusModal, handleConvertBC,
    handleProformaPdf, handleBonCommandePdf,
    handleChantier, handleCreerProjet, handleGenererFacture,
  }

  // ── ARC49 — Rangée d'en-tête du tableau (8 colonnes), partagée par le cas
  //    « filtre sans résultat » (rendu direct) et le mode `renderRow` du moteur
  //    (via `renderHeaderRow` → ses enfants <th>). Mêmes libellés/classes/case
  //    « tout sélectionner » que l'écran historique — DOM inchangé. ──
  const devisHeaderRow = (
    <tr>
      <th className="w-8">
        {/* T7 — tout sélectionner (devis affichés / filtrés). */}
        <Checkbox
          checked={allFilteredSelected}
          onCheckedChange={toggleSelectAll}
          aria-label="Tout sélectionner"
        />
      </th>
      <th>Référence</th>
      <th>Client</th>
      <th>Créé le</th>
      <th>Validité</th>
      <th className="ta-right">Total TTC</th>
      <th>Statut</th>
      <th>Actions</th>
    </tr>
  )

  // J141 — l'en-tête de page reste TOUJOURS visible (chargement, erreur, données)
  // pour éviter le saut de mise en page. Le contenu interne varie selon l'état.
  // APX11 — l'en-tête unique de l'app (VX28, `<h2>` conservé donc les ancres
  // e2e `getByRole('heading')` sont inchangées) + icône et accent du module :
  // l'œil doit dire « je suis dans Ventes » sans lire le fil d'Ariane.
  const pageHeader = (
    <PageHeader
      style={VENTES_ACCENT_STYLE}
      className="app-accent-rail"
      icon={FileText}
      title="Devis"
      subtitle={
        expiringSoon.length > 0
          ? `${devis.length} devis · ${expiringSoon.length} à relancer (validité ≤ 7 jours)`
          : `${devis.length} devis`
      }
      actions={(
        <>
          <Button size="sm" variant="outline" disabled={loading || !!error || xlsxBusy}
                  onClick={() => {
                    const pending = downloadBlobInGesture()
                    setXlsxBusy(true)
                    importApi.exportList('devis', devis.map(d => d.id))
                      .then(r => pending.deliver(r.data, 'devis.xlsx'))
                      .catch(() => {})
                      .finally(() => setXlsxBusy(false))
                  }}>
            {xlsxBusy ? <Spinner /> : <Download />} Exporter Excel
          </Button>
          {/* VX80 — impression navigateur (feuille print.css : chrome masqué,
              noir-sur-blanc, table complète). Distinct des PDF WeasyPrint. */}
          <Button size="sm" variant="outline" onClick={() => window.print()}>
            <Printer /> Imprimer
          </Button>
          <Button onClick={openNew}><Plus /> Nouveau devis</Button>
        </>
      )}
    />
  )

  if (loading) {
    return (
      <div className="page">
        {pageHeader}
        {showSpinner && (
          <div className="mt-4 flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Spinner /> Chargement des devis…
          </div>
        )}
        {showSkeleton && (
          <>
            {/* Bandeau de résumé squelette (5 cartes statut). */}
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              {Array.from({ length: 5 }).map((unused, i) => (
                <div key={i} className="rounded-lg border border-border bg-card p-3">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="mt-2 h-3 w-16" />
                </div>
              ))}
            </div>
            <DevisTableSkeleton />
          </>
        )}
      </div>
    )
  }
  if (error) {
    // VX67 — StateBlock unifie l'état d'erreur avec un bouton « Réessayer »
    // (relance le même thunk que le montage initial), là où l'ancien
    // EmptyState d'erreur n'offrait aucun moyen de réessayer sans recharger
    // la page entière.
    // VX63 — plus de JSON brut à l'écran : le payload d'erreur (chaîne OU objet
    // DRF `{detail}`/`{champ:[...]}`) est traduit en message FR lisible via
    // `frenchError`, au lieu d'un « Erreur de chargement. » générique qui
    // masquait la vraie cause.
    return (
      <div className="page">
        {pageHeader}
        <StateBlock
          className="mt-4"
          error={frenchError(error, 'Erreur de chargement.')}
          onRetry={() => dispatch(fetchDevis())}
        />
      </div>
    )
  }

  return (
    <div className="page">
      {pageHeader}

      {showForm && (
        <DevisForm devis={editDevis} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── T6 — Résumé par statut (nombre + total TTC des devis chargés) ──
          APX12 — les 5 cartes étaient des `<div>` nus : elles passent au
          langage UNIQUE des KPI d'argent (`<Stat>`, chiffres `.num`
          tabulaires), comme le cockpit trésorerie et le rail du générateur. */}
      {devis.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {Object.keys(STATUT_DISPLAY).map(key => (
            <Stat
              key={key}
              className="p-3 sm:p-3"
              label={(
                // `normal-case` : le libellé de Stat est en majuscules, la
                // pastille de statut garde sa casse d'origine (« Brouillon »).
                <StatusPill status={key} label={STATUT_DISPLAY[key]} className="normal-case tracking-normal" />
              )}
              value={summary[key]?.count ?? 0}
              hint={formatMAD(summary[key]?.total ?? 0)}
            />
          ))}
        </div>
      )}

      {/* ── T16 — Répartition batterie sur les devis acceptés ── */}
      {(batteryInsight.avec > 0 || batteryInsight.sans > 0) && (
        <p className="mt-2 text-xs text-muted-foreground">
          Devis acceptés — option choisie :{' '}
          <span className="font-medium text-success">{batteryInsight.avec} avec batterie</span>
          {' · '}
          <span className="font-medium text-foreground">{batteryInsight.sans} sans batterie</span>
        </p>
      )}

      {/* ── T15 — Rappel : devis envoyés expirant dans ≤ 7 jours ── */}
      {expiringSoon.length > 0 && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div>
            <strong>{expiringSoon.length} devis expirant bientôt</strong> (validité ≤ 7 jours) :{' '}
            {expiringSoon.map(d => d.reference).join(', ')}.
          </div>
        </div>
      )}

      {/* ── T5 — Filtre statut + recherche (référence / client) ── */}
      {devis.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Segmented
            options={STATUT_FILTERS}
            value={statutFilter}
            onChange={setStatutFilter}
            size="sm"
          />
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              type="search"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Rechercher (référence ou client)…"
              className="pl-8 sm:w-64"
              aria-label="Rechercher un devis"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <Button type="button" variant="link" size="sm" onClick={saveCurrentDevisView}>
              ⭐ Enregistrer cette vue
            </Button>
            <ViewsManagerPopover ecran={DL_ECRAN} onApply={applyDevisView} />
          </div>
          {/* U7 — bascule pour réafficher les révisions remplacées (masquées
              par défaut). N'apparaît que s'il y en a au moins une. */}
          {supersededCount > 0 && (
            <Button type="button" variant="link" size="sm"
                    onClick={() => setShowSuperseded(s => !s)}>
              {showSuperseded
                ? `Masquer les versions remplacées (${supersededCount})`
                : `Voir les versions remplacées (${supersededCount})`}
            </Button>
          )}
          {/* APX15(b) — bascule Liste/Board, parité exacte avec celle des
              factures (ZFAC9). Le board consomme `filteredDevis`, déjà en
              mémoire : aucune donnée nouvelle, aucun appel réseau. */}
          <div className="ml-auto flex items-center gap-1 rounded-md border border-border p-0.5"
               role="group" aria-label="Mode d’affichage">
            <Button
              type="button" size="sm"
              variant={viewMode === 'liste' ? 'secondary' : 'ghost'}
              aria-pressed={viewMode === 'liste'}
              onClick={() => setViewMode('liste')}
            >
              <LayoutList className="size-4" aria-hidden="true" /> Liste
            </Button>
            <Button
              type="button" size="sm"
              variant={viewMode === 'board' ? 'secondary' : 'ghost'}
              aria-pressed={viewMode === 'board'}
              onClick={() => setViewMode('board')}
            >
              <LayoutGrid className="size-4" aria-hidden="true" /> Board
            </Button>
          </div>
        </div>
      )}

      {/* ── T7 — Barre d'action du lot sélectionné ── */}
      {selectedIds.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-2 text-sm">
          <span className="font-medium">{selectedIds.length} devis sélectionné(s)</span>
          <Button size="sm" onClick={openBatchPdfModal}>
            <FileText /> Générer les PDF
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedIds([])}>
            Effacer la sélection
          </Button>
        </div>
      )}

      {/* ── ARC49 — Modale de génération PDF (extraite en composant ; flux PDF
          inchangé, règle #4). MB4 — ResponsiveDialog → tiroir bas sur mobile. ── */}
      <DevisPdfDialog
        pdfTarget={pdfTarget}
        batchPdf={batchPdf}
        selectedIds={selectedIds}
        pdfMode={pdfMode}
        setPdfMode={setPdfMode}
        targetIsAgricole={targetIsAgricole}
        showMonthly={showMonthly}
        setShowMonthly={setShowMonthly}
        targetHasEtude={targetHasEtude}
        includeEtude={includeEtude}
        setIncludeEtude={setIncludeEtude}
        devisFinal={devisFinal}
        setDevisFinal={setDevisFinal}
        paymentMode={paymentMode}
        setPaymentMode={setPaymentMode}
        customAcompte={customAcompte}
        setCustomAcompte={setCustomAcompte}
        onClose={() => { setPdfTarget(null); setBatchPdf(false) }}
        onGenererLot={handleGenererPdfLot}
        onGenererUn={handleGenererPdf}
      />

      {/* ── T9 — Modale d'acceptation inline (nom / date / option) — MB4
          ResponsiveDialog (tiroir bas plein écran sur mobile) ── */}
      <ResponsiveDialog
        open={!!acceptTarget}
        onOpenChange={(o) => { if (!o) setAcceptTarget(null) }}
        title={`Accepter le devis — ${acceptTarget?.reference ?? ''}`}
        footer={(
          <>
            <Button variant="ghost" onClick={() => setAcceptTarget(null)}>Annuler</Button>
            <Button onClick={submitAccept} loading={acceptBusy}>
              <Check /> Confirmer l'acceptation
            </Button>
          </>
        )}
      >
          <div className="flex flex-col gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="accept-nom">Nom de la personne qui accepte</Label>
              <Input id="accept-nom" value={acceptNom}
                     onChange={e => setAcceptNom(e.target.value)}
                     placeholder="Nom et prénom" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="accept-date">Date d'acceptation</Label>
              <Input id="accept-date" type="date" value={acceptDate}
                     onChange={e => setAcceptDate(e.target.value)} />
            </div>
            {acceptTarget?.nb_options === 2 && (
              <div className="grid gap-2">
                <Label>Option retenue par le client</Label>
                <RadioGroup value={acceptOption} onValueChange={setAcceptOption} className="flex flex-col gap-2">
                  <label className="flex items-center gap-2 text-sm">
                    <RadioGroupItem value="sans_batterie" />
                    <span>Sans batterie</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <RadioGroupItem value="avec_batterie" />
                    <span>Avec batterie</span>
                  </label>
                </RadioGroup>
              </div>
            )}
          </div>
      </ResponsiveDialog>

      {/* APX14 — l'aperçu du PDF de proposition, INLINE. Même source
          `/proposal` que le téléchargement (règle #4 : le moteur vendorisé
          reste le SEUL chemin PDF devis client, et il ne fait que RENDRE). */}
      <PdfPreviewSheet
        open={!!previewDevis}
        onOpenChange={(o) => { if (!o) setPreviewDevis(null) }}
        title={`Aperçu — ${previewDevis?.reference ?? ''}`}
        description="Proposition client. Téléchargeable ou ouvrable dans un onglet."
        filename={previewDevis ? `${previewDevis.reference}.pdf` : undefined}
        fetchBlob={fetchDevisPreviewBlob}
      />

      {/* VX155 — carte de victoire posée sur l'acceptation inline (montant
          réel ; pas de kWc dans cette vue liste). */}
      <DealSignedCelebration
        open={!!dealCelebration}
        reference={dealCelebration?.reference}
        montantTtc={dealCelebration?.montantTtc}
        kwc={dealCelebration?.kwc}
        onClose={() => setDealCelebration(null)}
      />

      {/* QX26 — Modale de refus OBLIGATOIRE : motif MotifPerte (taxonomie
          partagée CRM) + note libre optionnelle. Le bouton de confirmation
          reste désactivé tant qu'aucun motif n'est choisi — plus de refus
          « silencieux » (données de perte enfin exploitables en reporting). */}
      <ResponsiveDialog
        open={!!refusTarget}
        onOpenChange={(o) => { if (!o) closeRefusModal() }}
        title={`Refuser le devis — ${refusTarget?.reference ?? ''}`}
        description="Le motif est obligatoire — il alimente le reporting des pertes."
        footer={(
          <>
            <Button variant="ghost" onClick={closeRefusModal} disabled={refusBusy}>Annuler</Button>
            <Button
              onClick={submitRefus}
              loading={refusBusy}
              disabled={!refusMotifId}
              className="border-destructive/40 text-destructive hover:bg-destructive/10"
            >
              <X className="size-4 mr-1" aria-hidden="true" />
              Confirmer le refus
            </Button>
          </>
        )}
      >
          <div className="flex flex-col gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="refus-motif">Motif du refus</Label>
              <Select value={refusMotifId} onValueChange={setRefusMotifId}>
                <SelectTrigger id="refus-motif">
                  <SelectValue placeholder="Choisir un motif…" />
                </SelectTrigger>
                <SelectContent>
                  {motifsPerte.map(m => (
                    <SelectItem key={m.id} value={String(m.id)}>{m.nom ?? m.libelle}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {motifsPerte.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  Aucun motif configuré — ajoutez-en dans les paramètres CRM.
                </p>
              )}
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="refus-note">Détail (optionnel)</Label>
              <Textarea id="refus-note" value={refusNote}
                        onChange={e => setRefusNote(e.target.value)}
                        placeholder="Précisions sur le refus…" rows={3} />
            </div>
          </div>
      </ResponsiveDialog>

      {/* QJ14 — Modale « Envoyer par email » : PDF premium + lien de proposition
          (MB4 — ResponsiveDialog → tiroir bas plein écran sur mobile) */}
      <ResponsiveDialog
        open={!!emailTarget}
        onOpenChange={(o) => { if (!o) closeEmailModal() }}
        title={`Envoyer par email — ${emailTarget?.reference ?? ''}`}
        footer={(
          <>
            <Button variant="outline" onClick={closeEmailModal} disabled={emailBusy}>
              Annuler
            </Button>
            <Button onClick={submitEmail} loading={emailBusy}>
              <Send className="size-4 mr-1" aria-hidden="true" />
              Envoyer
            </Button>
          </>
        )}
      >
          <div className="flex flex-col gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="email-address">Adresse email du destinataire</Label>
              <Input
                id="email-address"
                type="email"
                placeholder="client@exemple.ma"
                value={emailAddress}
                onChange={e => setEmailAddress(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Laissez vide pour utiliser l'email du client enregistré.
                Le PDF de la proposition et le lien de signature seront joints.
              </p>
            </div>
          </div>
      </ResponsiveDialog>

      {/* QG8 — Aperçu du message WhatsApp avant ouverture (le devis est déjà
          marqué « envoyé » côté serveur ; on ouvre wa.me au clic). */}
      <Dialog open={!!waTarget} onOpenChange={(o) => { if (!o) closeWaModal() }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {relanceMode ? 'Relancer par WhatsApp' : 'Envoyer par WhatsApp'} — {waTarget?.reference}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              {relanceMode
                ? 'Vérifiez le message de rappel ci-dessous puis ouvrez WhatsApp — vous appuierez vous-même sur Envoyer.'
                : 'Le devis est marqué « Envoyé ». Vérifiez le message ci-dessous puis ouvrez WhatsApp — vous appuierez vous-même sur Envoyer.'}
            </p>
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
              {relanceMode
                ? buildRelanceMessage(waData, waTarget?.reference)
                : (waData?.message || '…')}
            </div>
            {/* GAMMES — ENVOI À LA CARTE (fondateur 2026-08-18). Affiché
                uniquement quand ce devis appartient à une paire de gammes :
                envoyer CETTE gamme seule (le lien rend le devis comme
                aujourd'hui) ou LES DEUX (le client choisit, badge
                « Recommandé » sur celle désignée). Défaut : les deux. */}
            {waData?.gamme && !relanceMode && (
              <fieldset className="rounded-lg border border-border p-3">
                <legend className="px-1 text-sm font-medium">Gammes à envoyer</legend>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="gamme-envoi"
                    value="les_deux"
                    checked={waGammeEnvoi === 'les_deux'}
                    onChange={() => setWaGammeEnvoi('les_deux')}
                  />
                  <span>
                    Envoyer les deux
                    {waData.gamme.recommandee
                      ? ` (recommandée : ${waData.gamme.recommandee})`
                      : ''}
                  </span>
                </label>
                <label className="mt-2 flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="gamme-envoi"
                    value="seule"
                    checked={waGammeEnvoi === 'seule'}
                    onChange={() => setWaGammeEnvoi('seule')}
                  />
                  <span>
                    Envoyer cette gamme seule
                    {waData.gamme.nom ? ` (${waData.gamme.nom})` : ''}
                  </span>
                </label>
              </fieldset>
            )}
            {!waData?.wa_url && (
              <p className="text-sm text-destructive">
                Aucun numéro de téléphone : le message ne peut pas être ouvert
                dans WhatsApp.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeWaModal} disabled={waSending}>Fermer</Button>
            <Button onClick={openWhatsApp} disabled={!waData?.wa_url} loading={waSending}>
              <Send className="size-4 mr-1" aria-hidden="true" />
              Ouvrir WhatsApp
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* QG10 — Modale « Variantes » : confirmer / éditer le pourcentage puis
          créer les 3 variantes et router vers la comparaison. Le champ % n'est
          éditable que pour le Directeur / Commercial responsable. */}
      <ResponsiveDialog
        open={!!varianteTarget}
        onOpenChange={(o) => { if (!o) closeVarianteModal() }}
        title={`Créer des variantes — ${varianteTarget?.reference ?? ''}`}
        description="Trois variantes de taille sont générées : réduite (−p %), standard, et augmentée (+p %), pour une comparaison côte-à-côte."
        footer={(
          <>
            <Button variant="ghost" onClick={closeVarianteModal} disabled={varianteBusy}>
              Annuler
            </Button>
            <Button onClick={submitVariante} loading={varianteBusy} disabled={varianteLoadingCfg}>
              <Copy className="size-4 mr-1" aria-hidden="true" />
              Créer les variantes
            </Button>
          </>
        )}
      >
        <div className="flex flex-col gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="variante-pct">Pourcentage de variation (%)</Label>
            <Input
              id="variante-pct"
              type="number"
              min="1"
              max="99"
              step="any"
              value={variantePct}
              onChange={e => setVariantePct(e.target.value)}
              readOnly={!canEditVariantePct}
              aria-readonly={!canEditVariantePct}
              disabled={varianteLoadingCfg}
            />
            <p className="text-xs text-muted-foreground">
              {canEditVariantePct
                ? 'Par défaut, la valeur de la société. Modifiez-la pour cette génération uniquement.'
                : 'Valeur par défaut de la société (modification réservée au Directeur et au Commercial responsable).'}
            </p>
            {/* Aperçu des 3 échelles dérivées du pourcentage. */}
            {(() => {
              const p = parseFloat(variantePct)
              if (!Number.isFinite(p) || !(p > 0 && p < 100)) return null
              return (
                <p className="text-xs text-muted-foreground">
                  Échelles : <strong>−{p} %</strong> · <strong>Standard</strong> · <strong>+{p} %</strong>
                </p>
              )
            })()}
          </div>
        </div>
      </ResponsiveDialog>

      {/* GAMMES (fondateur 2026-08-18) — Modale « Créer une variante de gamme » :
          crée le devis FRÈRE d'une seconde gamme (composition et prix propres,
          à retoucher ensuite). Les deux libellés sont LIBRES ; « Essentielle » /
          « Premium » ne sont que des défauts proposés. */}
      <ResponsiveDialog
        open={!!gammeTarget}
        onOpenChange={(o) => { if (!o) closeGammeModal() }}
        title={`Créer une variante de gamme — ${gammeTarget?.reference ?? ''}`}
        description="Une seconde gamme est créée comme devis frère : mêmes lignes au départ, à retoucher ensuite (composition et prix propres). Le client choisira au moment de la signature si vous envoyez les deux."
        footer={(
          <>
            <Button variant="ghost" onClick={closeGammeModal} disabled={gammeBusy}>
              Annuler
            </Button>
            <Button onClick={submitGamme} loading={gammeBusy}>
              <Copy className="size-4 mr-1" aria-hidden="true" />
              Créer la gamme
            </Button>
          </>
        )}
      >
        <div className="flex flex-col gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="gamme-nom-source">Nom de la gamme de ce devis</Label>
            <Input
              id="gamme-nom-source"
              value={gammeNomSource}
              onChange={e => setGammeNomSource(e.target.value)}
              placeholder="Essentielle"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gamme-nom">Nom de la nouvelle gamme</Label>
            <Input
              id="gamme-nom"
              value={gammeNom}
              onChange={e => setGammeNom(e.target.value)}
              placeholder="Premium"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={gammeRecommandee}
              onChange={e => setGammeRecommandee(e.target.checked)}
            />
            <span>Recommander la nouvelle gamme (badge « Recommandé » côté client)</span>
          </label>
          <p className="text-xs text-muted-foreground">
            Sans cette case, c’est ce devis-ci qui porte la recommandation.
          </p>
        </div>
      </ResponsiveDialog>

      {/* VX79 — lien profond ?devis=<pk> ciblant un devis introuvable :
          EmptyState inline (jamais une page blanche). */}
      {highlightMissing && (
        <EmptyState
          icon={AlertTriangle}
          title="Devis introuvable"
          description="Le devis de ce lien n'existe plus ou n'est pas accessible."
          className="mt-4 border-warning/40"
        />
      )}

      {devis.length === 0 ? (
        <EmptyState
          illustrated
          title="Aucun devis"
          description="Créez votre premier devis depuis le générateur solaire."
          action={<Button onClick={openNew}><Plus /> Nouveau devis</Button>}
          className="mt-4"
        />
      ) : viewMode === 'board' ? (
        /* APX15(b) — LE board Ventes : colonnes = statuts DOCUMENT (règle #4),
           montant en héros, et AUCUNE action d'état par glisser-déposer —
           accepter/refuser restent des actions explicites de la vue liste. */
        <div className="mt-4">
          <DevisKanbanBoard devis={filteredDevis} onOpenDevis={openEdit} />
        </div>
      ) : (
        <Card className="mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            {filteredDevis.length === 0 ? (
              /* ── ARC49 — Filtre sans résultat : ligne pleine largeur conservée
                  à l'identique (le moteur ne rend renderRow que pour ≥1 ligne). ── */
              <table className="data-table">
                <thead>{devisHeaderRow}</thead>
                <tbody>
                  <tr>
                    <td colSpan={8} className="py-6 text-center text-sm text-muted-foreground">
                      Aucun devis ne correspond à ces filtres.
                    </td>
                  </tr>
                </tbody>
              </table>
            ) : (
              /* ── ARC49 — Tableau sur le frame `ui/datatable` (mode ligne custom).
                  L'écran garde 100 % de son DOM : `table.data-table`, son en-tête
                  8 colonnes, `<DevisRow>` verbatim (boutons à état, menu « Plus »
                  VX20, confirmation maison à la suppression (APX17),
                  panneaux versions/3D pilotés par l'état de page + deep-links), sa
                  sélection propre (`selectedIds`) et son flux PDF (règle #4). Le
                  moteur ne fait que dérouler le pipeline de lignes ; il n'ajoute
                  aucune cellule technique, ni tri client, ni pagination, ni carte
                  mobile, ni barre d'outils (seams manuels + hideToolbar). ── */
              <DataTable
                data={filteredDevis}
                columns={DEVIS_DT_COLUMNS}
                getRowId={d => d.id}
                manualSorting
                manualFiltering
                manualPagination
                rowCount={filteredDevis.length}
                pageSize={filteredDevis.length}
                pageSizeOptions={[filteredDevis.length]}
                searchable={false}
                hideToolbar
                hidePagination
                tableClassName="data-table calm-list"
                aria-label="Devis"
                renderHeaderRow={() => devisHeaderRow.props.children}
                renderRow={d => <DevisRow key={d.id} d={d} ctx={rowCtx} />}
              />
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
