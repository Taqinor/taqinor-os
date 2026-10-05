import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  Plus, Check,
  Copy, X, AlertTriangle,
} from 'lucide-react'
import {
  fetchDevis,
  convertirDevisEnBC,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import {
  Button, Card, EmptyState, Spinner,
  Skeleton, SkeletonTableRow,
  RadioGroup, RadioGroupItem, Checkbox, Label, Input, toast,
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
  Textarea,
} from '../../ui'
// VX236 — `?equipe=<id>` (lien depuis MesEquipesCard) filtre la liste sur les
// membres de cette équipe — filtre client-side, aucun endpoint nouveau.
import { useEquipeMembreIds } from '../../hooks/useEquipeMembreIds'
import { useServerSavedViews } from '../../features/uxviews/useServerSavedViews'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import { useHasPermission, useCanValiderVente, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import useDocumentTitle from '../../hooks/useDocumentTitle'
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
import {
  peutEditerDevis, chantierEnCours,
} from '../../features/ventes/devisStatuts'
// SPL203 — la ligne de la liste vit dans son propre fichier (move only).
import DevisRow from './devisList/DevisRow.jsx'
import { STATUT_DISPLAY, DL_ECRAN } from './devisList/devisListConstants.js'
// SPL204 — flux PDF et son dialogue (move only).
import { useDevisPdf } from './devisList/useDevisPdf.js'
import DevisPdfDialog from './devisList/DevisPdfDialog.jsx'
import { frenchError, useDevisListSynthese } from './devisList/devisListHelpers.js'
// SPL205 — parcours d'envoi et ses dialogues (move only).
import { useDevisEnvoi } from './devisList/useDevisEnvoi.js'
import EnvoiDialogs from './devisList/EnvoiDialogs.jsx'
// SPL206 — en-tête de page (titre, synthèse KPI, filtres, barre de lot).
import DevisListChrome, { DevisPageHeader } from './devisList/DevisListChrome.jsx'

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

  // SPL205 — parcours d'envoi (email, liens, WhatsApp + relance, EZ3, supérieur).
  const {
    emailTarget,
    emailAddress,
    setEmailAddress,
    emailBusy,
    openEmailModal,
    closeEmailModal,
    submitEmail,
    copierLienInterne,
    shareBusyId,
    handleCopierApercuInterne,
    handleCopierLienProposition,
    waTarget,
    waData,
    waSending,
    relanceMode,
    waGammeEnvoi,
    setWaGammeEnvoi,
    handleEnvoyer,
    handleRelancer,
    closeWaModal,
    openWhatsApp,
    superieurBusyId,
    superieurStatus,
    handleContacterSuperieur,
  } = useDevisEnvoi({
    dispatch, setPreviewDevis, setStatutActionId,
    highlightId, highlightedDevis, loading, searchParams, setSearchParams,
  })

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

  // SPL206 — dérivés de la synthèse (T6 / T15 / T16), déplacés avec l'en-tête.
  const { summary, expiringSoon, batteryInsight } = useDevisListSynthese(devis, effStatutOf)

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
    <DevisPageHeader
      devis={devis}
      expiringSoon={expiringSoon}
      loading={loading}
      error={error}
      xlsxBusy={xlsxBusy}
      setXlsxBusy={setXlsxBusy}
      openNew={openNew}
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

      {/* SPL206 — en-tête de page : synthèse, filtres, barre de lot (move only). */}
      <DevisListChrome
        devis={devis}
        summary={summary}
        batteryInsight={batteryInsight}
        expiringSoon={expiringSoon}
        statutFilter={statutFilter}
        setStatutFilter={setStatutFilter}
        query={query}
        setQuery={setQuery}
        saveCurrentDevisView={saveCurrentDevisView}
        applyDevisView={applyDevisView}
        supersededCount={supersededCount}
        showSuperseded={showSuperseded}
        setShowSuperseded={setShowSuperseded}
        viewMode={viewMode}
        setViewMode={setViewMode}
        selectedIds={selectedIds}
        setSelectedIds={setSelectedIds}
        openBatchPdfModal={openBatchPdfModal}
      />

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

      {/* SPL205 — dialogues d'envoi (email + WhatsApp), JSX déplacé. */}
      <EnvoiDialogs
        emailTarget={emailTarget}
        emailAddress={emailAddress}
        setEmailAddress={setEmailAddress}
        emailBusy={emailBusy}
        closeEmailModal={closeEmailModal}
        submitEmail={submitEmail}
        waTarget={waTarget}
        waData={waData}
        waSending={waSending}
        relanceMode={relanceMode}
        waGammeEnvoi={waGammeEnvoi}
        setWaGammeEnvoi={setWaGammeEnvoi}
        closeWaModal={closeWaModal}
        openWhatsApp={openWhatsApp}
      />

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
