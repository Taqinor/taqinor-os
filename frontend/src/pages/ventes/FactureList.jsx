import { Fragment, useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search, Plus, Download, BookText, ListChecks, FileWarning,
  Code2, Check, FileText, ReceiptText, MoreHorizontal,
  CreditCard, ShieldCheck, X, LayoutList, LayoutGrid, Printer, Zap, Receipt, Eye,
} from 'lucide-react'
import {
  fetchFactures,
  fetchFacturesKpis,
  emettreFacture,
  marquerPayeeFacture,
  annulerFacture,
} from '../../features/ventes/store/ventesSlice'
import ventesApi from '../../api/ventesApi'
import { frenchError } from '../../lib/frenchError'
import api from '../../api/axios'
import importApi from '../../api/importApi'
import FactureForm from './FactureForm'
import ListeTableSkeleton from './ListeTableSkeleton'
import FactureKanbanBoard from './FactureKanbanBoard'
import FactureRow from './factureList/FactureRow'
// SPL212 — exports comptables (état, gestes, dialogues) extraits en factureList/.
import useFactureCompta from './factureList/useFactureCompta.js'
import ComptaDialogs from './factureList/ComptaDialogs.jsx'
// VNT102 — sélection/masse, documents, gestes et dialogues extraits en factureList/.
import useFactureLot from './factureList/useFactureLot.js'
import useFactureDocuments from './factureList/useFactureDocuments.js'
import useFactureGestes from './factureList/useFactureGestes.js'
import DialoguesFacture from './factureList/DialoguesFacture.jsx'
import { isPartiallyPaid, isOverdue, today, STATUTS_HORS_ENCAISSEMENT } from './factureList/factureHelpers.js'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  // APX12 — le langage UNIQUE des KPI d'argent.
  Stat,
  Skeleton,
  Tabs, TabsList, TabsTrigger,
  Input, Checkbox,
  FormField,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  Popover, PopoverTrigger, PopoverContent,
  toast,
} from '../../ui'
import { LangueWhatsApp, BasculeAffichage, OngletCompteur, PageListeChargement } from './ElementsListeVentes'
import { formatMAD, toNumber } from '../../lib/format'
// APX11 — en-tête unique VX28 + accent de module (identité Ventes).
// APX13 — la chaîne documentaire devis→BC→facture, visible ici aussi.
import DocumentStageTrack from '../../ui/DocumentStageTrack'
import { DOC_STATUT_TRACK } from '../../features/ventes/documentChain'
// APX14 — aperçu PDF INLINE (panneau latéral) : plus d'onglet à quitter.
import PdfPreviewSheet from '../../features/ventes/PdfPreviewSheet'
// APX17 — confirmation maison (VX19/L152), jamais une popup du système.
import { useConfirmDialog } from '../../ui/confirm'
// EZ13 — confirmation À SÉVÉRITÉ (VX244) pour le marquage sec « payée ».
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import PaiementDialog from './PaiementDialog'
// WIR103/ZFAC4 — modale « Note de débit » (création + téléchargement PDF).
import NoteDebitDialog from './NoteDebitDialog'
// PACT121 — modale « Payer en ligne » (core.PaymentTransaction, CMI/Payzone).
// À DISTINGUER de « Encaisser » (règlement déjà reçu) ET du lien FG53
// ci-dessus : ici on demande un paiement carte à un prestataire.
import PaiementEnLigneDialog from '../../features/ventes/PaiementEnLigneDialog'
import { useServerSavedViews } from '../../features/uxviews/useServerSavedViews'
import ViewsManagerPopover from '../../features/uxviews/ViewsManagerPopover'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import useDocumentTitle from '../../hooks/useDocumentTitle'
// VX248 — raccourci d'ACTION sur la facture focalisée (la modale d'édition
// ouverte — seule vue « fiche » qui existe pour une facture, cf. VX220).
import { useFocusedRecordShortcuts } from '../../providers/focusedRecordShortcuts'
import { DataTable } from '../../ui/datatable'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import EnteteVentes from '../../features/ventes/EnteteVentes'

// VX21 — squelette de la liste (parité DevisList/DevisTableSkeleton) : reprend
// les 8 colonnes du vrai tableau pour que la mise en page ne saute pas à
// l'arrivée des données. Affiché dans la même carte que le tableau réel, en
// gardant l'en-tête de page visible.
const FACTURETABLESKELETON_ENTETES = [['Référence'], ['Client'], ['Émission'], ['Échéance'], ['Total TTC', 'ta-right'], ['Statut'], ['Actions']]

function FactureTableSkeleton() {
  return <ListeTableSkeleton largeurSelection="w-10" entetes={FACTURETABLESKELETON_ENTETES} />
}

// WIR21 — vues sauvegardées côté serveur (apps.uxviews.SavedView, NTUX1/2).
const FL_ECRAN = 'ventes.factures'

// ── ARC53 — Colonnes du frame `ui/datatable` en mode « ligne custom ».
// L'écran rend chaque ligne via `renderRow` (<FactureRow>) ; ces définitions ne
// décrivent que la grille au moteur (aucun `cell` n'est utilisé, tri/filtre/
// pagination désactivés via seams manuels). Le rendu réel reste 100 % dans
// <FactureRow> (mêmes cellules, boutons à état, menu « Actions », édition inline).
const FACTURE_DT_COLUMNS = [
  { id: 'reference', header: 'Référence', sortable: false, hideable: false, reorderable: false },
  { id: 'client', header: 'Client', sortable: false, hideable: false, reorderable: false },
  { id: 'date_emission', header: 'Émission', sortable: false, hideable: false, reorderable: false },
  { id: 'date_echeance', header: 'Échéance', sortable: false, hideable: false, reorderable: false },
  { id: 'total_ttc', header: 'Total TTC', align: 'right', sortable: false, hideable: false, reorderable: false },
  { id: 'statut', header: 'Statut', sortable: false, hideable: false, reorderable: false },
  { id: 'actions', header: 'Actions', sortable: false, hideable: false, reorderable: false },
]

const TABS = [
  { key: 'toutes',    label: 'Toutes' },
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'emise',     label: 'Émises' },
  { key: 'overdue',   label: 'En retard' },
  { key: 'partielle', label: 'Partiellement payées' },
  { key: 'payee',     label: 'Payées' },
  { key: 'annulee',   label: 'Annulées' },
]

// Filtre par type de facture d'échéancier (champ type_facture du modèle).
const TYPES_FACTURE = [
  { value: '',             label: 'Tous les types' },
  { value: 'complete',     label: 'Complète' },
  { value: 'acompte',      label: 'Acompte' },
  { value: 'intermediaire', label: 'Intermédiaire' },
  { value: 'solde',        label: 'Solde' },
]


// VX230 — MODES_PAIEMENT + défauts intelligents VX92/VX93 (localStorage) ont
// suivi la modale de paiement dans le composant partagé PaiementDialog.jsx.

export default function FactureList() {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant).
  useDocumentTitle('Factures')
  const dispatch = useDispatch()
  // APX17 — confirmations maison (VX19/L152) : plus une seule popup du système.
  const { confirm } = useConfirmDialog()
  const [searchParams, setSearchParams] = useSearchParams()
  const { factures, loading, error, facturesKpis } = useSelector(s => s.ventes)
  const isAdmin = useSelector(s => s.auth.role) === 'admin'
  // VX21 — chargement différé anti-scintillement (parité DevisList) : spinner
  // discret puis squelette, en-tête de page toujours visible.
  const { showSpinner, showSkeleton } = useDelayedLoading(loading)

  // ── WIR103/ZFAC4 — Note de débit (pendant de l'avoir) : modale de
  // création + téléchargement PDF. Le backend était complet et testé mais
  // n'avait aucun écran ; c'est ici qu'il en gagne un.
  const [noteDebitTarget, setNoteDebitTarget] = useState(null)
  const openNoteDebit = (f) => setNoteDebitTarget(f)

  // ── PACT121 — Demande de paiement carte au client (core.PaymentTransaction).
  // Sans compte marchand configuré, la création reste propre et sans effet :
  // la modale affiche « prestataire non configuré », jamais une erreur brute.
  const [paiementEnLigneTarget, setPaiementEnLigneTarget] = useState(null)
  const openPaiementEnLigne = (f) => setPaiementEnLigneTarget(f)

  // VNT102 (patron SPL212) — sélection/actions en masse, documents et gestes
  // extraits en factureList/ (move only) ; leurs noms sont re-déstructurés ici
  // pour que le sac de contexte des lignes et le JSX restent identiques.
  const lot = useFactureLot({ factures, dispatch })
  const {
    selectedIds, setSelectedIds, toggleSelect, clearSelection, bulkBusy,
    BULK_LABELS, handleBulkAction, facturesEncaissables, clientSelectionUnique,
  } = lot
  const docs = useFactureDocuments({ dispatch })
  const {
    pdfGenerating, pdfDownloading, handleGenererPdf, handleTelechargerPdf,
    previewFacture, setPreviewFacture, openPreview, fetchFacturePreviewBlob,
    waBusy, waLangue, setWaLangue, handleWhatsApp, handleUbl,
    payLinkBusy, handleLienPaiement, dgiActif, dgiBusy, handleDgiExport, handleDgiConformite,
  } = docs
  const gestes = useFactureGestes({ dispatch, confirm, lot })
  const {
    canManage, wir183Busy, handleRemettreBrouillon, handleFacturerPenalites,
    openAbandonSolde, openRetourClient, openConsolider, openEncaissementGroupe,
    openAvoirModal, actionId, doAction, demanderAnnulation,
    payeeSecheTarget, setPayeeSecheTarget, payeeSecheMotif, setPayeeSecheMotif, openMarquerPayee,
  } = gestes

  const [showForm, setShowForm]       = useState(false)
  const [editFacture, setEditFacture] = useState(null)
  // VX231(a) — deep-link ?facture=<id> (émis par PaiementsPage/Encaissements) :
  // atterrir sur la BONNE facture surlignée. On force l'onglet « toutes » pour
  // qu'elle ne soit jamais masquée par un filtre d'onglet, puis on la surligne
  // + scrolle 3 s (voir l'effet plus bas).
  const [highlightFactureId, setHighlightFactureId] = useState(
    () => searchParams.get('facture') || null)
  const [activeTab, setActiveTab]     = useState('toutes')
  // VX250 — deep-link ?q=<texte> pré-règle la recherche (référence/client) au
  // montage — posé par LIST_ROUTE.facture (entityRoutes.js) et RelationCounters
  // (fiches 360°) sans jamais être lu jusqu'ici. Le filtre `search` existant
  // fait déjà exactement référence/client (ci-dessous) — aucune nouvelle
  // logique de filtre.
  const [search, setSearch]           = useState(() => searchParams.get('q') ?? '')
  const [typeFilter, setTypeFilter]   = useState('')
  // ZFAC9 — bascule Liste/Kanban (wiring/données only, réutilise `filtered`).
  const [viewMode, setViewMode]       = useState('liste')
  // WIR21 — vues sauvegardées côté serveur (remplace le localStorage FG11 :
  // vues EQUIPE désormais visibles par l'équipe, cf. ViewsManagerPopover).
  const { createView: createFactView } = useServerSavedViews(FL_ECRAN)
  const saveCurrentFactView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    const trimmed = (name || '').trim()
    if (!trimmed) return
    createFactView({
      nom: trimmed, configuration: { activeTab, typeFilter }, visibilite: 'PERSONNELLE',
    }).catch(() => toast.error('Enregistrement de la vue impossible.'))
  }
  const applyFactView = (configuration) => {
    if (configuration?.activeTab !== undefined) setActiveTab(configuration.activeTab)
    if (configuration?.typeFilter !== undefined) setTypeFilter(configuration.typeFilter)
  }
  const compta = useFactureCompta()
  const {
    auditBusy, xlsxBusy, setXlsxBusy,
    setJournalOpen, setExportComptableOpen, handleAuditNumerotation,
  } = compta


  // ── Enregistrement de paiement (VX230 — modale extraite en PaiementDialog) ──
  // FactureList ne garde que la facture CIBLÉE ; tout l'état de saisie, l'arrondi
  // ZFAC11 et le chatter vivent désormais dans PaiementDialog (partagé avec
  // RelancesPage). `onSaved` rafraîchit la liste après chaque encaissement.
  const [payTarget, setPayTarget] = useState(null) // facture ciblée
  const openPayModal = (f) => setPayTarget(f)

  // VX97 — Panneau « Historique » repliable dans le détail facture : journal des
  // changements (FactureActivity) — qui/quand/ancien→nouveau — sur le document
  // au plus gros blast-radius financier. Feed existant monté ; migrera vers
  // ChatterTimeline (VX23). `prix_achat` jamais rendu (le journal ne le porte pas).
  const [histoOpenId, setHistoOpenId] = useState(null)
  const [histoCache, setHistoCache] = useState({})   // id → entrées
  const [histoLoadingId, setHistoLoadingId] = useState(null)
  const toggleHistorique = (id) => {
    if (histoOpenId === id) { setHistoOpenId(null); return }
    setHistoOpenId(id)
    if (histoCache[id] === undefined) {
      setHistoLoadingId(id)
      api.get(`/ventes/factures/${id}/historique/`)
        .then(res => setHistoCache(c => ({ ...c, [id]: res.data || [] })))
        .catch(() => setHistoCache(c => ({ ...c, [id]: [] })))
        .finally(() => setHistoLoadingId(l => (l === id ? null : l)))
    }
  }

  // ── Édition inline de la date d'échéance (facture émise) ──
  const [echeanceEditId, setEcheanceEditId] = useState(null)
  const [echeanceValue, setEcheanceValue]   = useState('')
  const [echeanceSaving, setEcheanceSaving] = useState(false)

  const startEditEcheance = (f) => {
    setEcheanceEditId(f.id)
    setEcheanceValue(f.date_echeance ?? '')
  }
  const saveEcheance = async (f) => {
    setEcheanceSaving(true)
    try {
      await ventesApi.patchFacture(f.id, { date_echeance: echeanceValue || null })
      setEcheanceEditId(null)
      dispatch(fetchFactures())
    } catch (err) {
      toast.error(frenchError(err, 'Mise à jour de l’échéance impossible.'))
    } finally {
      setEcheanceSaving(false)
    }
  }

  useEffect(() => { dispatch(fetchFactures()) }, [dispatch])
  // AUD157 (FAC-13) — LES KPI D'ARGENT VIENNENT DU SERVEUR, en UN appel.
  // Ils etaient sommes ici a partir des factures chargees, sans filtrer le
  // statut des paiements : un cheque revenu impaye comptait comme encaisse,
  // et la definition divergeait de `Facture.montant_paye`. L'ecran ne calcule
  // plus aucun montant : il formate ce que le serveur lui donne.
  useEffect(() => { dispatch(fetchFacturesKpis()) }, [dispatch])

  // VX231(a) — une fois les factures chargées, si un ?facture=<id> est ciblé,
  // scrolle la ligne au centre et retire la surbrillance après 3 s (le repère
  // visuel a fait son office). Ne se déclenche qu'une fois (la surbrillance se
  // vide elle-même).
  useEffect(() => {
    if (!highlightFactureId || factures.length === 0) return undefined
    const el = document.getElementById(`facture-row-${highlightFactureId}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    const t = setTimeout(() => setHighlightFactureId(null), 3000)
    return () => clearTimeout(t)
  }, [highlightFactureId, factures.length])

  const filtered = useMemo(() => {
    let list = factures
    if (activeTab === 'overdue') {
      list = list.filter(isOverdue)
    } else if (activeTab === 'partielle') {
      list = list.filter(isPartiallyPaid)
    } else if (activeTab !== 'toutes') {
      list = list.filter(f => f.statut === activeTab)
    }
    if (typeFilter) {
      list = list.filter(f => f.type_facture === typeFilter)
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(f =>
        f.reference?.toLowerCase().includes(q) ||
        (f.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [factures, activeTab, search, typeFilter])

  // VX230 — total « reste à encaisser » de la SÉLECTION filtrée courante (onglet
  // + type + recherche), dérivé de `filtered` déjà en mémoire (zéro appel
  // réseau). Répond au manque : le cockpit montre « Encaissé ce mois » mais
  // jamais le dû de l'onglet « Partiellement payées » sous les yeux.
  const resteAEncaisserOnglet = useMemo(
    () => filtered.reduce((s, f) => (STATUTS_HORS_ENCAISSEMENT.includes(f.statut)
      ? s : s + (toNumber(f.montant_du) || 0)), 0),
    [filtered])

  const counts = useMemo(() => ({
    toutes:    factures.length,
    brouillon: factures.filter(f => f.statut === 'brouillon').length,
    emise:     factures.filter(f => f.statut === 'emise' && !isOverdue(f)).length,
    overdue:   factures.filter(isOverdue).length,
    partielle: factures.filter(isPartiallyPaid).length,
    payee:     factures.filter(f => f.statut === 'payee').length,
    annulee:   factures.filter(f => f.statut === 'annulee').length,
  }), [factures])

  // AUD157 (FAC-13) — LES CINQ CHIFFRES D'ARGENT DE L'EN-TETE VIENNENT DU
  // SERVEUR, plus d'une somme faite ici. « Encaisse ce mois » sommait
  // `p.montant` de tous les paiements des factures chargees SANS filtrer
  // `p.statut` : l'ecran comptait des cheques revenus impayes, avec une
  // definition differente de `Facture.montant_paye` (qui exclut les paiements
  // rejetes — YLEDG5 — et compte l'escompte — XFAC12). Le proprietaire unique
  // est desormais `ventes.selectors.kpis_factures` ; l'ecran FORMATE, il ne
  // calcule plus. Contrat PACT10 :
  // backend/django_core/apps/ventes/contract_samples/factures_kpis.json
  const encaisseMois = toNumber(facturesKpis?.encaisse_mois) || 0
  const encaisseMoisPrecedent = toNumber(facturesKpis?.encaisse_mois_precedent) || 0
  const totalDu = toNumber(facturesKpis?.total_du) || 0
  const impayeesCount = facturesKpis?.nb_impayees ?? 0
  const totalEnRetard = toNumber(facturesKpis?.total_en_retard) || 0
  const countEnRetard = facturesKpis?.nb_en_retard ?? 0
  const totalAEcheoirSoon = toNumber(facturesKpis?.total_a_echoir_7j) || 0
  // Le decompte des factures a echoir se lit sur la page chargee (aucun
  // montant : c'est un simple cardinal d'affichage).
  const nbAEcheoirSoon = useMemo(() => factures.filter(f =>
    f.statut === 'emise' && !isOverdue(f) && f.date_echeance
    && f.date_echeance >= today).length, [factures])
  const openNew   = () => { setEditFacture(null); setShowForm(true) }
  const openEdit  = f  => { setEditFacture(f);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);   setEditFacture(null) }
  const onSaved   = () => dispatch(fetchFactures())

  // VX220 — lien profond ?id=<pk> (patron VX79 déjà lu par InstallationsPage.jsx/
  // TicketsPage.jsx) : la palette de commandes (⌘K) ouvre désormais la FACTURE
  // exacte — la modale d'édition est la seule vue « fiche » qui existe pour une
  // facture, donc c'est elle qui joue le rôle du panneau détail. Posé une fois
  // les factures chargées (jamais avant, la recherche échouerait toujours) ;
  // id introuvable → silencieux (jamais un crash). Le paramètre est retiré dans
  // tous les cas pour ne pas rouvrir la modale à chaque re-render.
  useEffect(() => {
    const wantedId = searchParams.get('id')
    if (!wantedId || loading) return
    const match = factures.find(f => String(f.id) === String(wantedId))
    // eslint-disable-next-line react-hooks/set-state-in-effect -- ouverture one-shot pilotée par ?id= (D-ENF22)
    if (match) openEdit(match)
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      next.delete('id')
      return next
    }, { replace: true })
  }, [searchParams, loading, factures, setSearchParams])



  // VX248 — « a » génère le PDF de la facture FOCALISÉE (la modale d'édition
  // ouverte via `?id=` (VX220) ou un clic « Modifier » — `editFacture` est la
  // seule notion de « fiche » qui existe pour une facture). Absent quand
  // aucune facture n'est ouverte (liste nue).
  useFocusedRecordShortcuts(
    'factureDetail',
    { a: () => editFacture && handleGenererPdf(editFacture) },
    !!editFacture,
  )


  // EZ12 — L'ENCAISSEMENT OFFRE SA SUITE. Le parcours d'encaissement est le
  // meilleur de l'app (3 clics) mais il s'arrêtait sec : rien n'était offert
  // après. La suite HONNÊTE est la page des Encaissements filtrée sur le
  // client — PAS le rapprochement bancaire, qui est « strictement distinct
  // de l'import de paiements clients » (compta/models.py) : un paiement
  // fraîchement encaissé n'y apparaît PAS tant que le relevé n'est pas importé.
  const [dernierEncaissement, setDernierEncaissement] = useState(null)





  // ── ARC53 — Sac de contexte passé à chaque <FactureRow> (« lignes divisées »).
  // Regroupe l'état + les handlers que la ligne utilisait déjà depuis la clôture ;
  // aucune valeur n'est transformée ni aucun flux modifié.
  const rowCtx = {
    selectedIds, toggleSelect,
    echeanceEditId, echeanceValue, setEcheanceValue, echeanceSaving,
    saveEcheance, setEcheanceEditId, startEditEcheance,
    dgiActif, isAdmin,
    actionId, pdfGenerating, pdfDownloading, waBusy, payLinkBusy, dgiBusy,
    openEdit, doAction, emettreFacture, annulerFacture,
    openPayModal, handleLienPaiement, handleTelechargerPdf, handleGenererPdf,
    openAvoirModal, handleWhatsApp, handleUbl, handleDgiExport, handleDgiConformite,
    histoOpenId, toggleHistorique, histoCache, histoLoadingId,
    openNoteDebit,
    // PACT121 - ouvre la demande de paiement carte (prestataire).
    openPaiementEnLigne,
    // APX14 - ouvre l'apercu PDF inline de cette facture.
    openPreview,
    // EZ13 - marquage sec, relegue au menu et explique.
    openMarquerPayee,
    highlightFactureId,
    // WIR183 - les quatre actions de fiche, jusqu'ici sans point d'entree.
    canManage, wir183Busy,
    handleRemettreBrouillon, handleFacturerPenalites,
    openAbandonSolde, openRetourClient,
    demanderAnnulation,
  }

  // VX21 — l'en-tête de page reste TOUJOURS visible (chargement, erreur,
  // données), parité DevisList/J141 : la mise en page ne saute plus au retour
  // des données (plus de spinner plein écran qui remplace toute la page).
  // APX11 — en-tête unique VX28 + icône/accent du module (le `<h2>` et son
  // badge sont conservés tels quels : ancres e2e inchangées).
  const pageHeader = (
    <EnteteVentes
      icon={Receipt}
      title={(
        <>
          Factures
          {factures.length > 0 && (
            <Badge tone="primary" className="ml-2 align-middle">{factures.length}</Badge>
          )}
        </>
      )}
      subtitle={
        impayeesCount > 0
          ? `${impayeesCount} facture${impayeesCount > 1 ? 's' : ''} à encaisser`
          : 'Facturation, encaissements et avoirs'
      }
      actions={(
        <>
        <Input
          type="search"
          className="w-full sm:w-56"
          leading={<Search />}
          placeholder="Référence, client…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <Select value={typeFilter || 'all'}
                onValueChange={v => setTypeFilter(v === 'all' ? '' : v)}>
          <SelectTrigger className="w-full sm:w-44" title="Filtrer par type de facture">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TYPES_FACTURE.map(t => (
              <SelectItem key={t.value || 'all'} value={t.value || 'all'}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* VX80 — impression navigateur (feuille print.css : chrome masqué,
            noir-sur-blanc, table complète). Distinct des PDF WeasyPrint. */}
        <Button size="sm" variant="outline" onClick={() => window.print()}>
          <Printer /> Imprimer
        </Button>
        {/* VX142(a) — toolbar à 5 groupes : recherche+filtre, imprimer,
            EXPORTER (menu unique, remplace 4 boutons à plat + le
            window.prompt() du Journal comptable), langue WhatsApp, Nouvelle
            facture. */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline">
              <Download /> Exporter
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem
              disabled={xlsxBusy}
              onSelect={() => {
                const pending = downloadBlobInGesture()
                setXlsxBusy(true)
                importApi.exportList('factures', factures.map(f => f.id))
                  .then(r => pending.deliver(r.data, 'factures.xlsx'))
                  .catch(() => {})
                  .finally(() => setXlsxBusy(false))
              }}>
              {xlsxBusy ? <Spinner className="size-3.5" /> : <Download className="size-3.5" aria-hidden="true" />} Exporter Excel
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setJournalOpen(true)}>
              <BookText className="size-3.5" aria-hidden="true" /> Journal comptable…
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setExportComptableOpen(true)}>
              <Download className="size-3.5" aria-hidden="true" /> Export comptable…
            </DropdownMenuItem>
            {isAdmin && (
              <DropdownMenuItem disabled={auditBusy} onSelect={handleAuditNumerotation}>
                <ListChecks className="size-3.5" aria-hidden="true" /> Audit numérotation
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        {/* L851 — langue des messages WhatsApp (FR par défaut). */}
        <LangueWhatsApp waLangue={waLangue} setWaLangue={setWaLangue}
          ariaLabel="Langue des messages WhatsApp"
          className="inline-flex items-center gap-1"
          title="Langue du message « Envoyer par WhatsApp »" />
        {/* WIR183/XFAC11 — UNE facture consolidée à partir de plusieurs devis
            acceptés du MÊME client. L'action consomme des ids de DEVIS, pas la
            sélection de factures : elle vit donc ici, avec son propre
            sélecteur, et non sur la barre de masse (qui produirait un 400). */}
        {canManage && (
          <Button size="sm" variant="outline" onClick={openConsolider}>
            Consolider des devis
          </Button>
        )}
        <Button onClick={openNew}><Plus /> Nouvelle facture</Button>
        </>
      )}
    >
      <ComptaDialogs compta={compta} />
    </EnteteVentes>
  )

  if (loading) {
    return (
      <PageListeChargement pageHeader={pageHeader} showSpinner={showSpinner}
        showSkeleton={showSkeleton} libelle="Chargement des factures…">
        {/* Rangée de cartes trésorerie squelette (parité KPI ci-dessous). */}
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((unused, i) => (
            <div key={i} className="rounded-lg border border-border bg-card p-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-2 h-6 w-20" />
              <Skeleton className="mt-1.5 h-3 w-16" />
            </div>
          ))}
        </div>
        <FactureTableSkeleton />
      </PageListeChargement>
    )
  }
  if (error) {
    return (
      <div className="page">
        {pageHeader}
        <EmptyState className="mt-4" icon={FileWarning} title="Erreur de chargement"
                    description="Impossible de charger les factures. Réessayez." />
      </div>
    )
  }

  return (
    <div className="page">
      {pageHeader}

      {/* EZ13 — le marquage sec explique CE QU'ON PERD, et offre le chemin
          riche en échappatoire (« Encaisser » capture mode/date/référence). */}
      <ConfirmDialog
        open={!!payeeSecheTarget}
        onOpenChange={(o) => { if (!o) { setPayeeSecheTarget(null); setPayeeSecheMotif('') } }}
        severity="medium"
        title={`Marquer ${payeeSecheTarget?.reference ?? ''} payée sans détail ?`}
        description="Le MODE de règlement, la DATE et la RÉFÉRENCE ne seront pas enregistrés : la facture passera à « payée » sans trace d'encaissement. Préférez « Encaisser » si vous avez ces informations."
        confirmLabel="Marquer payée quand même"
        onConfirm={() => {
          const f = payeeSecheTarget
          const motif = payeeSecheMotif.trim()
          setPayeeSecheTarget(null)
          setPayeeSecheMotif('')
          if (!motif) {
            toast.error('Motif obligatoire : dites pourquoi cette facture est soldée sans encaissement.')
            return
          }
          if (f) doAction(marquerPayeeFacture, { id: f.id, motif })
        }}
      >
        {/* AUD124 — sans motif, ce geste faisait disparaître une créance de
            la balance âgée sans que rien ne dise qui, quand ni pourquoi. */}
        <FormField label="Motif (obligatoire)" htmlFor="motif-payee-seche">
          <Input
            id="motif-payee-seche"
            value={payeeSecheMotif}
            onChange={(e) => setPayeeSecheMotif(e.target.value)}
            placeholder="Ex. : virement encaissé hors ERP, constaté au relevé"
          />
        </FormField>
      </ConfirmDialog>

      {/* EZ12 — après l'encaissement, l'action SUIVANTE est offerte : voir
          l'encaissement dans les Encaissements, filtré sur ce client
          (`PaiementsPage` lit déjà `?client=`). Un clic, aucune recherche. */}
      {dernierEncaissement && (
        <div
          role="status"
          data-testid="encaissement-suite"
          className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
        >
          <span>
            Paiement enregistré sur {dernierEncaissement.reference}
            {dernierEncaissement.client_nom ? ` — ${dernierEncaissement.client_nom}` : ''}.
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild size="sm" variant="outline" data-testid="voir-encaissement">
              <Link to={dernierEncaissement.client
                ? `/ventes/paiements?client=${dernierEncaissement.client}`
                : '/ventes/paiements'}
              >
                Voir l’encaissement
              </Link>
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setDernierEncaissement(null)}>
              Fermer
            </Button>
          </div>
        </div>
      )}

      {showForm && (
        <FactureForm facture={editFacture} onClose={closeForm} onSaved={onSaved} />
      )}

      {/* ── Modale d'enregistrement de paiement (VX230 — composant partagé) ── */}
      <PaiementDialog
        facture={payTarget}
        onOpenChange={(o) => { if (!o) setPayTarget(null) }}
        onSaved={() => { dispatch(fetchFactures()); setDernierEncaissement(payTarget) }}
      />

      {/* APX14 — aperçu du PDF de la facture, INLINE. Source = le PDF LEGACY
          propre aux factures ; le moteur `/proposal` reste réservé au PDF de
          DEVIS (règle #4), et aucun chemin nouveau n'est créé. */}
      <PdfPreviewSheet
        open={!!previewFacture}
        onOpenChange={(o) => { if (!o) setPreviewFacture(null) }}
        title={`Aperçu — ${previewFacture?.reference ?? ''}`}
        description="Facture. Téléchargeable ou ouvrable dans un onglet."
        filename={previewFacture ? `${previewFacture.reference}.pdf` : undefined}
        fetchBlob={fetchFacturePreviewBlob}
      />

      {/* ── WIR103/ZFAC4 — Modale « Note de débit » (création + PDF) ── */}
      <NoteDebitDialog
        facture={noteDebitTarget
          ? (factures.find(x => x.id === noteDebitTarget.id) ?? noteDebitTarget)
          : null}
        onChanged={() => dispatch(fetchFactures())}
        open={!!noteDebitTarget}
        onOpenChange={(o) => { if (!o) setNoteDebitTarget(null) }}
      />

      {/* ── PACT121 — Modale « Payer en ligne » (core.PaymentTransaction) ── */}
      <PaiementEnLigneDialog
        facture={paiementEnLigneTarget}
        open={!!paiementEnLigneTarget}
        onOpenChange={(o) => { if (!o) setPaiementEnLigneTarget(null) }}
      />

      <DialoguesFacture gestes={gestes} lot={lot} docs={docs} factures={factures} />

      {/* VX21 — cockpit trésorerie : 4 cartes KPI max, détail sous le pli
          (Stripe) — un directeur voit la santé de trésorerie d'un coup d'œil.
          Anatomie complète : valeur + delta (vs mois précédent où pertinent)
          + période. Dérivées des factures déjà chargées, aucun appel réseau. */}
      {/* APX12 — UN seul langage de KPI d'argent : les 4 cartes passent par
          `<Stat>` (chiffres `.num` tabulaires, delta en icône lucide). Le
          glyphe de tendance en TEXTE posé ici régressait VX129 — c'était le
          dernier site du dossier ventes à ne pas parler ce langage. */}
      {factures.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat
            className="p-3 sm:p-3"
            label="Encaissé ce mois"
            value={formatMAD(encaisseMois)}
            delta={encaisseMoisPrecedent > 0 ? {
              direction: encaisseMois >= encaisseMoisPrecedent ? 'up' : 'down',
              value: `${formatMAD(Math.abs(encaisseMois - encaisseMoisPrecedent))} vs mois dernier`,
            } : undefined}
            hint={encaisseMoisPrecedent > 0 ? undefined : 'Mois en cours'}
          />
          <Stat
            className="p-3 sm:p-3"
            label="Total dû"
            value={formatMAD(totalDu)}
            hint="Toutes factures non soldées"
          />
          <Stat
            className="p-3 sm:p-3"
            label="En retard"
            value={(
              <span className={countEnRetard > 0 ? 'text-destructive' : undefined}>
                {formatMAD(totalEnRetard)}
              </span>
            )}
            hint={`${countEnRetard} facture${countEnRetard > 1 ? 's' : ''} échue${countEnRetard > 1 ? 's' : ''}`}
          />
          <Stat
            className="p-3 sm:p-3"
            label="À échoir ≤ 7 j"
            value={formatMAD(totalAEcheoirSoon)}
            hint={`${nbAEcheoirSoon} facture${nbAEcheoirSoon > 1 ? 's' : ''} · 7 prochains jours`}
          />
        </div>
      )}

      {/* ── Tabs + vues enregistrées (FG11) ── */}
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="flex-wrap">
            {TABS.map(t => (
              <OngletCompteur key={t.key} value={t.key} label={t.label} count={counts[t.key]}
                className={t.key === 'overdue' && counts.overdue > 0 ? 'text-destructive data-[state=active]:text-destructive' : undefined} />
            ))}
          </TabsList>
        </Tabs>
        {/* VX230 — « Reste à encaisser » de l'onglet/filtre courant (dérivé de
            `filtered`). Visible dès qu'un reste dû existe dans la sélection —
            surtout utile sur « Partiellement payées ». */}
        {resteAEncaisserOnglet > 0 && (
          <span
            className="rounded-md border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground tabular-nums"
            title="Somme des montants encore dus sur les factures affichées (onglet + filtres courants)"
          >
            Reste à encaisser (onglet) :{' '}
            <strong className="text-foreground">{formatMAD(resteAEncaisserOnglet)}</strong>
          </span>
        )}
        <div className="flex items-center gap-1.5">
          <Button type="button" variant="link" size="sm" onClick={saveCurrentFactView}>
            ⭐ Enregistrer cette vue
          </Button>
          <ViewsManagerPopover ecran={FL_ECRAN} onApply={applyFactView} />
        </div>
        {/* ZFAC9 — bascule Liste/Kanban : réutilise `filtered` déjà chargé,
            aucune donnée/refonte nouvelle. */}
        <BasculeAffichage viewMode={viewMode} setViewMode={setViewMode}
          autreMode="kanban" autreLabel="Kanban" />
      </div>

      {viewMode === 'kanban' ? (
        <FactureKanbanBoard factures={filtered} today={today} onOpenFacture={openEdit} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={ReceiptText}
          title={
            search ? `Aucun résultat pour « ${search} »`
              : activeTab !== 'toutes' ? 'Aucune facture dans cet onglet'
                : 'Aucune facture'
          }
          description={search || activeTab !== 'toutes' ? undefined : 'Créez votre première facture.'}
          action={!search && activeTab === 'toutes'
            ? <Button onClick={openNew}><Plus /> Nouvelle facture</Button> : undefined}
          className="mt-4"
        />
      ) : (
        <>
          {/* ── FG43/WR2b — barre d'actions en masse (visible dès une sélection) ── */}
          {selectedIds.length > 0 && (
            <div
              role="region"
              aria-label="Actions factures en masse"
              className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-nuit px-4 py-2.5 text-white shadow-ui-md"
            >
              <div className="text-sm">
                <strong className="tabular-nums">{selectedIds.length}</strong> facture{selectedIds.length > 1 ? 's' : ''} sélectionnée{selectedIds.length > 1 ? 's' : ''}
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {Object.entries(BULK_LABELS).map(([action, label]) => (
                  <button
                    key={action}
                    type="button" disabled={bulkBusy}
                    onClick={() => handleBulkAction(action)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-white/10 disabled:opacity-50"
                  >
                    {label}
                  </button>
                ))}
                {/* WIR183/ZFAC6 — un seul règlement réparti sur PLUSIEURS
                    factures. Le serveur exige un client UNIQUE : le bouton
                    reste visible mais désactivé, et DIT pourquoi. */}
                {canManage && (
                  <button
                    type="button"
                    disabled={bulkBusy || wir183Busy || !clientSelectionUnique}
                    title={clientSelectionUnique
                      ? undefined
                      : (facturesEncaissables.length === 0
                        ? 'Aucune facture sélectionnée n’est encaissable'
                        : 'Sélectionnez des factures d’un SEUL client')}
                    onClick={openEncaissementGroupe}
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-white/10 disabled:opacity-50"
                  >
                    Encaissement groupé
                  </button>
                )}
                <button
                  type="button" disabled={bulkBusy} onClick={clearSelection}
                  className="inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium text-white/70 transition-colors hover:text-white disabled:opacity-50"
                >
                  <X className="size-3.5" /> Désélectionner
                </button>
              </div>
            </div>
          )}
        <Card className="mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            {/* ── ARC53 — Tableau sur le frame `ui/datatable` (mode ligne custom).
                L'écran garde 100 % de son DOM : `table.data-table` avec
                `role="table"` (contrat `getByRole('table')`), son en-tête 8
                colonnes + case « tout sélectionner », `<FactureRow>` verbatim
                (boutons à état, menu « Actions », édition inline d'échéance,
                badges DGI), sa sélection propre (`selectedIds`) et sa barre de
                masse `role="region"` (rendue plus haut, hors table). Le PDF
                facture LEGACY est INTOUCHÉ (règle #4). Le moteur ne fait que
                dérouler le pipeline de lignes (seams manuels → ordre serveur,
                aucun tri/pagination/carte/outil intégré). `filtered.length > 0`
                est déjà garanti par la branche parente. ── */}
            <DataTable
              data={filtered}
              columns={FACTURE_DT_COLUMNS}
              getRowId={f => f.id}
              manualSorting
              manualFiltering
              manualPagination
              rowCount={filtered.length}
              pageSize={filtered.length}
              pageSizeOptions={[filtered.length]}
              searchable={false}
              hideToolbar
              hidePagination
              tableClassName="data-table calm-list"
              tableRole="table"
              aria-label="Factures"
              renderHeaderRow={() => (
                <>
                  <th className="w-10">
                    <Checkbox
                      checked={filtered.length > 0 && selectedIds.length === filtered.length}
                      onCheckedChange={(v) => setSelectedIds(v ? filtered.map(f => f.id) : [])}
                      aria-label="Tout sélectionner"
                    />
                  </th>
                  <th>Référence</th>
                  <th>Client</th>
                  <th>Émission</th>
                  <th>Échéance</th>
                  <th className="ta-right">Total TTC</th>
                  <th>Statut</th>
                  <th>Actions</th>
                </>
              )}
              renderRow={f => <FactureRow key={f.id} f={f} ctx={rowCtx} />}
            />
          </div>
        </Card>
        </>
      )}
    </div>
  )
}
