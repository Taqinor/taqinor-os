import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  Download, Plus, FileText, Check,
  Copy, Send, X, Search, AlertTriangle,
  Printer,
  LayoutList, LayoutGrid,
} from 'lucide-react'
import {
  fetchDevis,
  convertirDevisEnBC,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import importApi from '../../api/importApi'
import {
  Button, StatusPill, Card, EmptyState, Spinner,
  // APX12 — le langage UNIQUE des KPI d'argent.
  Stat,
  Skeleton, SkeletonTableRow,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  RadioGroup, RadioGroupItem, Checkbox, Label, Input, Segmented, toast,
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
  Textarea,
} from '../../ui'
import { formatMAD } from '../../lib/format'
// VX156 — le devis envoyé porte la voix Taqinor (moment « devis envoyé »).
import { voice } from '../../lib/voice'
// VX155 — jalon « devis envoyé » : un cran au-dessus du toast succès plat.
import { toastMilestone } from '../../lib/toast'
// VX236 — `?equipe=<id>` (lien depuis MesEquipesCard) filtre la liste sur les
// membres de cette équipe — filtre client-side, aucun endpoint nouveau.
import { useEquipeMembreIds } from '../../hooks/useEquipeMembreIds'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import { clientProposalUrl } from '../../features/ventes/clientProposalLink'
import { useServerSavedViews } from '../../features/uxviews/useServerSavedViews'
import ViewsManagerPopover from '../../features/uxviews/ViewsManagerPopover'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
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
import { StateBlock } from '../../components/StateBlock'
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
import {
  peutEditerDevis, chantierEnCours, STATUT_DEVIS_FILTRES,
} from '../../features/ventes/devisStatuts'
// SPL203 — la ligne de la liste vit dans son propre fichier (move only).
import DevisRow from './devisList/DevisRow.jsx'
import { STATUT_DISPLAY } from './devisList/devisListConstants.js'
// SPL204 — flux PDF et son dialogue (move only).
import { useDevisPdf } from './devisList/useDevisPdf.js'
import DevisPdfDialog from './devisList/DevisPdfDialog.jsx'
import { frenchError } from './devisList/devisListHelpers.js'

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

// VX141 — piste `<DocumentStageTrack>` : couche STATUTS DOCUMENT (règle #4)
// uniquement — brouillon/envoyé/accepté puis BC/facturé/chantier. Jamais les
// stages STAGES.py du funnel CRM (règle #2) : aucune clé de stage n'est
// importée ici, les deux couches ne se mélangent jamais.
// APX13 — la piste est désormais partagée avec FactureList et la liste des
// bons de commande (`features/ventes/documentChain.js`) : UNE définition.

// Filtres segmentés (statut) : « Tous » + les 5 statuts visibles.
const STATUT_FILTERS = STATUT_DEVIS_FILTRES

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
  // ANALYT1 (audit item 64) — « Lecture par le client » (visites distinctes
  // par section + alerte de friction) n'est chargée QUE pour ce rôle — même
  // périmètre que la garde serveur (IsResponsableOrAdmin sur
  // `lecture-client/`) : un rôle sans ce droit ne déclenche même pas l'appel.
  const canSeeLectureClient = useIsAdminOrResponsable()
  // J141 — chargement différé anti-scintillement : spinner discret puis squelette.
  const { showSpinner, showSkeleton } = useDelayedLoading(loading)

  const [convertingId, setConvertingId] = useState(null)
  const [factureGenId, setFactureGenId] = useState(null) // devis id en cours de facturation
  const [statutActionId, setStatutActionId] = useState(null) // envoi/refus en cours
  // APX15(b) — mode d'affichage de la liste : tableau ou board par statut
  // DOCUMENT. Parité exacte avec la bascule Liste/Kanban des factures.
  const [viewMode, setViewMode] = useState('liste')
  // Panneau « historique des versions » : id du devis dont la chaîne est ouverte.
  // QG10 — deep-link ?variantes=<id> ouvre directement la comparaison au montage.
  const [versionsOpenId, setVersionsOpenId] = useState(() => {
    const v = searchParams.get('variantes')
    return v ? Number(v) : null
  })

  /* ── WIR225 — Le panneau de comparaison est alimenté par le SERVEUR ───────
     `GET /ventes/devis/<id>/variantes/` (QJ15) renvoie le groupe COMPLET de
     variantes (même `version_parent`, actives) — il n'avait aucun appelant.
     Le panneau se contentait de `versionChain`, une chaîne reconstruite
     LOCALEMENT à partir des devis DÉJÀ CHARGÉS dans la liste : une variante
     hors page (pagination, filtre de statut, recherche) en disparaissait
     purement et simplement, et la promesse de comparaison n'était pas tenue.
     On interroge donc le serveur, seul à connaître le groupe entier. */
  const [variantesEtat, setVariantesEtat] = useState({
    id: null, rows: [], loading: false, error: false,
  })
  const variantesRef = useRef(null)

  const chargerVariantes = (id) => {
    variantesRef.current = id
    if (id == null) {
      setVariantesEtat({ id: null, rows: [], loading: false, error: false })
      return
    }
    setVariantesEtat({ id, rows: [], loading: true, error: false })
    ventesApi.getVariantes(id)
      .then((r) => {
        if (variantesRef.current !== id) return
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results ?? [])
        setVariantesEtat({ id, rows, loading: false, error: false })
      })
      .catch(() => {
        if (variantesRef.current !== id) return
        setVariantesEtat({ id, rows: [], loading: false, error: true })
      })
  }

  // Bascule du panneau : un seul chemin, partagé par le bouton de ligne, le
  // deep-link `?variantes=` et les deux créations (variantes / gamme).
  const basculerVersions = (id) => {
    const cible = versionsOpenId === id ? null : id
    setVersionsOpenId(cible)
    chargerVariantes(cible)
  }

  // Deep-link `?variantes=<id>` : charger le groupe au MONTAGE (l'état initial
  // ci-dessus pose déjà l'id ; il ne déclenche aucun chargement à lui seul).
  useEffect(() => {
    if (versionsOpenId == null) return undefined
    // Déféré d'un tick : un `setState` SYNCHRONE dans un effet déclenche des
    // rendus en cascade (react-hooks/set-state-in-effect). Le timer est
    // annulé au démontage — aucun chargement orphelin.
    const tick = setTimeout(() => chargerVariantes(versionsOpenId), 0)
    return () => clearTimeout(tick)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
  // `prix_achat` n'apparaît jamais (le journal ne le porte pas).
  //
  // WIR274 — le commentaire annonçait une migration vers `ChatterTimeline`
  // « quand il atterrira » : il a atterri (VX23, `components/ChatterTimeline`),
  // et cette note était donc périmée. La migration n'est PAS faite ici, et
  // volontairement : ce composant attend la forme `crm.LeadActivity` (avec
  // `kind`), que `DevisActivity` ne porte pas — le brancher tel quel rendrait
  // TOUTE entrée comme une note manuelle. Le rendu ci-dessous distingue déjà
  // note et changement de champ. Ce qui manquait vraiment, c'est le
  // COMPOSEUR : `noterDevis` n'était appelé que par l'auto-note de relance
  // WhatsApp (VX222) — personne ne pouvait écrire une note à la main.
  const [histoOpenId, setHistoOpenId] = useState(null)
  const [histoCache, setHistoCache] = useState({})   // id → entrées
  const [histoLoadingId, setHistoLoadingId] = useState(null)

  // Recharge le fil DEPUIS LE SERVEUR (jamais un ajout optimiste local : la
  // note doit être vue telle que le serveur l'a enregistrée, horodatage et
  // auteur compris).
  const rechargerHistorique = (id) => {
    setHistoLoadingId(id)
    return ventesApi.historiqueDevis(id)
      .then(res => setHistoCache(c => ({ ...c, [id]: res.data || [] })))
      .catch(() => setHistoCache(c => ({ ...c, [id]: c[id] ?? [] })))
      .finally(() => setHistoLoadingId(l => (l === id ? null : l)))
  }

  const toggleHistorique = (id) => {
    if (histoOpenId === id) { setHistoOpenId(null); return }
    setHistoOpenId(id)
    if (histoCache[id] === undefined) rechargerHistorique(id)
  }

  // WIR274 — composeur de note manuelle. Réservé au palier responsable/admin,
  // comme la garde serveur de l'action `noter`.
  const peutNoter = ['admin', 'responsable'].includes(role)
  const [noteBrouillon, setNoteBrouillon] = useState({}) // id → texte
  const [noteBusyId, setNoteBusyId] = useState(null)
  const ecrireNote = (id, texte) =>
    setNoteBrouillon(b => ({ ...b, [id]: texte }))
  const publierNote = async (id) => {
    const texte = (noteBrouillon[id] || '').trim()
    if (!texte) return
    setNoteBusyId(id)
    try {
      await ventesApi.noterDevis(id, texte)
      setNoteBrouillon(b => ({ ...b, [id]: '' }))
      await rechargerHistorique(id)
    } catch (err) {
      toast.error(frenchError(err, "La note n'a pas pu être ajoutée."))
    } finally {
      setNoteBusyId(null)
    }
  }

  // ANALYT1 — panneau « Lecture par le client » : id → {sections, friction}
  // (voir DevisSuiviPartagePanel). N'est chargé QUE pour un rôle responsable/
  // admin (canSeeLectureClient) — un rôle sans ce droit n'émet même pas
  // l'appel (qui recevrait de toute façon 403 côté serveur). Même patron
  // repliable que l'historique.
  const [suiviOpenId, setSuiviOpenId] = useState(null)
  const [lectureClientCache, setLectureClientCache] = useState({})
  const toggleSuiviPartage = (id) => {
    if (suiviOpenId === id) { setSuiviOpenId(null); return }
    setSuiviOpenId(id)
    if (canSeeLectureClient && lectureClientCache[id] === undefined) {
      ventesApi.getLectureClientDevis(id)
        .then(res => setLectureClientCache(c => ({ ...c, [id]: res.data || null })))
        .catch(() => setLectureClientCache(c => ({ ...c, [id]: null })))
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
  // SPL204 — flux PDF (format, génération + sondage WIR217, aperçu, partage).
  const {
    pdfGenerating,
    pdfSlowPoll,
    pdfDownloading,
    previewDevis,
    setPreviewDevis,
    previewingId,
    batchPdf,
    setBatchPdf,
    pdfTarget,
    setPdfTarget,
    pdfMode,
    setPdfMode,
    showMonthly,
    setShowMonthly,
    devisFinal,
    setDevisFinal,
    paymentMode,
    setPaymentMode,
    customAcompte,
    setCustomAcompte,
    includeEtude,
    setIncludeEtude,
    includeCalepinage,
    setIncludeCalepinage,
    pdfModeAutoOnepage,
    targetHasEtude,
    targetIsAgricole,
    openPdfModal,
    openBatchPdfModal,
    handlePreview,
    fetchDevisPreviewBlob,
    handleGenererPdf,
    handleGenererPdfLot,
    handleProformaPdf,
    handleBonCommandePdf,
    handleTelechargerPdf,
    handlePartagerPdf,
  } = useDevisPdf({ dispatch, devis, selectedIds, setSelectedIds })

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
      chargerVariantes(d.id)
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
      chargerVariantes(d.id)
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

  const [shareBusyId, setShareBusyId] = useState(null)

  // L-INTPREV/QJ1bis — « Copier l'aperçu interne » : la MÊME page publique
  // que le client, servie par le jeton INTERNE (ShareLink.token_interne) —
  // aucune notification, aucun compteur de vues, aucune note chatter, aucune
  // avance de funnel. C'est le lien que Reda/Meryem ouvrent pour vérifier ;
  // le lien CLIENT (WR2 ci-dessous) reste le seul à envoyer.
  const handleCopierApercuInterne = async (d) => {
    setShareBusyId(d.id)
    try {
      const res = await ventesApi.shareLinkDevis(d.id)
      const path = res?.data?.path_interne
      if (path) {
        const url = clientProposalUrl(path, import.meta.env.VITE_PUBLIC_SITE_URL)
        try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
        toast.success('Aperçu interne copié — ne l’envoyez jamais au client (aucune notification).')
      } else {
        toast.error('Aperçu interne indisponible.')
      }
    } catch (err) {
      toast.error(frenchError(err, 'Génération de l’aperçu interne impossible.'))
    } finally {
      setShareBusyId(null)
    }
  }

  // WR2 — « Copier le lien proposition » : (re)mint le lien public tokenisé du
  // devis (DevisViewSet.share_link) et le copie au presse-papier.
  // QJR531 (D-QJR5-3) — copier le lien CLIENT = ENVOI, comme depuis la fiche
  // lead (DevisTab.copierPageClient) : `envoi: true` → mark_devis_sent côté
  // serveur (le devis passe « envoyé », le funnel avance), puis la liste est
  // rechargée. « Copier l'aperçu interne » ci-dessus reste SANS envoi.
  const handleCopierLienProposition = async (d) => {
    setShareBusyId(d.id)
    try {
      const res = await ventesApi.shareLinkDevis(d.id, { envoi: true })
      dispatch(fetchDevis())
      // Le backend renvoie {token, path} (path = /proposition/<slug-client>/
      // <token>, PV84 — slug cosmétique, jamais vérifié côté serveur) — on
      // reconstruit l'URL publique complète (site public, cf. VITE_PUBLIC_SITE_URL).
      // Le repli sans slug (token seul) ne sert que si le backend omettait
      // exceptionnellement `path` : il reste une route valide côté site.
      const path = res?.data?.path || (res?.data?.token ? `/proposition/${res.data.token}` : null)
      if (path) {
        const url = clientProposalUrl(path, import.meta.env.VITE_PUBLIC_SITE_URL)
        try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
        toast.success('Lien copié — devis marqué envoyé.')
      } else {
        toast.error('Lien de proposition indisponible.')
      }
    } catch (err) {
      toast.error(frenchError(err, 'Génération du lien impossible.'))
    } finally {
      setShareBusyId(null)
    }
  }

  // Création ET édition passent par la page générateur solaire (QJR540 :
  // l'ancien modal d'édition est supprimé, ses blocs vivent dans l'Édition
  // complète).
  const openNew  = () => navigate('/ventes/devis/nouveau')
  const openEdit = (d) => {
    // QJR532 — un devis figé (accepté, remplacé) dit POURQUOI au lieu de
    // sortir en silence ; un envoyé s'ouvre (D-QJR5-1).
    if (!peutEditerDevis(d)) {
      toast.error(d.raison_non_modifiable
        || 'Ce devis ne peut plus être modifié — révisez-le pour créer une nouvelle version.')
      return
    }
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
      dispatch(fetchDevis())
      setAcceptTarget(null)
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

  const [chantierBusy, setChantierBusy] = useState(null)
  // « Créer le chantier » sur un devis accepté : crée (ou ouvre s'il existe
  // déjà) le chantier pré-rempli, puis navigue DIRECTEMENT sur SA fiche
  // (CHT21 — la liste nue `/chantiers` forçait à re-sélectionner le chantier
  // qu'on venait pourtant de désigner ; patron `?id=` déjà lu par
  // InstallationsPage.jsx:343).
  const handleChantier = async (d) => {
    if (d.chantier) { navigate(`/chantiers?id=${d.chantier.id}`); return }
    setChantierBusy(d.id)
    try {
      const res = await installationsApi.createFromDevis(d.id)
      dispatch(fetchDevis())
      navigate(`/chantiers?id=${res.data.id}`)
    } catch (err) {
      toast.error(frenchError(err, 'Création du chantier impossible.'))
    } finally {
      setChantierBusy(null)
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

  // WIR225 — la chaîne de révisions reconstruite LOCALEMENT (`versionChain`)
  // a été retirée : elle ne voyait que les devis déjà chargés dans la page, et
  // le panneau lit désormais le groupe complet servi par `getVariantes`.

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
  // aucune valeur n'est transformée. L'état des variantes est chargé sur
  // `versionsOpenId` (seule la ligne ouverte le rend), donc le partager est sûr.
  const rowCtx = {
    selectedIds, toggleSelected,
    versionsOpenId, setVersionsOpenId, roofOpenId, setRoofOpenId,
    // WIR225 - comparaison des variantes servie par le serveur.
    variantesEtat, basculerVersions,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    // WIR274 - composeur de note manuelle sur le panneau Historique.
    peutNoter, noteBrouillon, ecrireNote, publierNote, noteBusyId,
    suiviOpenId, toggleSuiviPartage,
    lectureClientCache, canSeeLectureClient,
    conceptionOpenId, setConceptionOpenId,
    etudeOpenId, setEtudeOpenId,
    effStatutOf,
    navigate, dispatch,
    role, canDelete, canValiderVente, canSeePublicite, highlightId,
    deletingId, statutActionId, superieurBusyId, superieurStatus, shareBusyId, previewingId,
    pdfGenerating, pdfDownloading, pdfSlowPoll, convertingId, chantierBusy, factureGenId,
    openEdit, openVarianteModal, openGammeModal, handleDelete, handleEnvoyer, handleRelancer,
    handleContacterSuperieur,
    openEmailModal, handleCopierLienProposition, handleCopierApercuInterne, copierLienInterne, handlePreview, openPdfModal,
    handleTelechargerPdf, handlePartagerPdf, openAcceptModal, openRefusModal, handleConvertBC,
    handleProformaPdf, handleBonCommandePdf,
    handleChantier, handleGenererFacture,
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
        pdfModeAutoOnepage={pdfModeAutoOnepage}
        targetIsAgricole={targetIsAgricole}
        showMonthly={showMonthly}
        setShowMonthly={setShowMonthly}
        targetHasEtude={targetHasEtude}
        includeEtude={includeEtude}
        setIncludeEtude={setIncludeEtude}
        includeCalepinage={includeCalepinage}
        setIncludeCalepinage={setIncludeCalepinage}
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

      {/* QG8 — Aperçu du message WhatsApp avant ouverture. L'aperçu est une
          LECTURE (whatsapp-preview) : le devis n'est marqué « Envoyé » qu'au
          clic « Ouvrir WhatsApp » (action whatsapp). ERR-QAH-VENTES-ENVOYE-
          FAUX-STATUT — le texte ne prétend jamais un statut non encore posé. */}
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
                : 'Vérifiez le message ci-dessous puis ouvrez WhatsApp — vous appuierez vous-même sur Envoyer. Le devis passera « Envoyé » quand vous ouvrirez WhatsApp ; fermer cette fenêtre le laisse en brouillon.'}
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
