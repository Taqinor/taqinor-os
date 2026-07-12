import { lazy, Suspense, useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Link2, FileText, Package, Hammer, ClipboardList, Camera, Wrench, Zap,
  History, Send, ScrollText, Download, ExternalLink, WifiOff, TriangleAlert,
  RotateCw, Milestone, Printer,
} from 'lucide-react'
import { updateInstallation } from '../../features/installations/store/installationsSlice'
import { fetchProduits } from '../../features/stock/store/stockSlice'
import installationsApi from '../../api/installationsApi'
import savApi from '../../api/savApi'
import crmApi from '../../api/crmApi'
import documentsApi from '../../api/documentsApi'
import ventesApi from '../../api/ventesApi'
import { downloadBlob } from '../../utils/downloadBlob'
import { openPdfInGesture } from '../../utils/pdfBlob'
import { errorMessageFrom } from '../../lib/toast'
import { telHref } from '../../lib/contactLinks'
import {
  pdfBlob, previewView, classifyFetchError, PREVIEW_VIEW,
} from '../../features/ventes/previewPdf'
import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  INTERVENTION_TYPES,
  adjacentStatuses,
  canMoveStatus,
  nextBestAction,
} from '../../features/installations/statuses'
import ProduitPicker from '../../components/ProduitPicker'
import OwnerChain from '../../components/OwnerChain'
import ChantierChecklist from './ChantierChecklist'
import ChantierTimeline from './ChantierTimeline'
import ChantierGateTimeline from './ChantierGateTimeline'
import ChantierPhotos from './ChantierPhotos'
// FG386 — même bandeau d'état de synchro terrain que la page Interventions
// (N91/F21) : la checklist chantier file déjà ses cochages hors-ligne via
// `withOfflineFallback`, il ne restait qu'à rendre l'état visible ici aussi.
import OfflineSyncIndicator from '../../features/installations/offline/OfflineSyncIndicator'
import { garantieLabel, garantieColor } from '../../features/sav/equipement'
import {
  TICKET_TYPES,
  TICKET_STATUS_LABELS,
  SOUS_GARANTIE_LABELS,
} from '../../features/sav/ticketStatuses'
import { formatDate } from '../../lib/format'
import useDocumentTitle from '../../hooks/useDocumentTitle'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Card, CardHeader, CardTitle, CardContent,
  Button, Input, Textarea, Checkbox, Label, StatusPill,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  FormField, FormActions, useDirtyGuard, confirmLeaveIfDirty,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Spinner, EmptyState,
} from '../../ui'

// L4 — l'aperçu PDF (canvas PDF.js) est chargé à la demande (gros module) : il
// ne pèse sur le bundle que quand on ouvre réellement un aperçu après-vente.
// On RÉUTILISE le composant exact de l'aperçu devis (fiche lead) — aucun rendu
// PDF dupliqué, et le PDF affiché provient des MÊMES octets que le
// téléchargement (donc aperçu et fichier téléchargé concordent à l'octet près).
const PdfCanvas = lazy(() => import('../../features/ventes/PdfCanvas'))

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "à l'instant"
  if (mins < 60) return `il y a ${mins} min`
  const h = Math.round(mins / 60)
  if (h < 24) return `il y a ${h} h`
  return new Date(iso).toLocaleDateString('fr-FR')
}

// Sous-titre de section (mêmes intitulés/émojis qu'avant, mais en composant
// du système de design — surface Card + titre cohérent).
function Section({ icon: Icon, title, action, children }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">
          {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
          {title}
        </CardTitle>
        {action}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">{children}</CardContent>
    </Card>
  )
}

// Petite table tokenisée réutilisée par les sous-listes (interventions, etc.).
function MiniTable({ head, children }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-muted/60">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

const Hint = ({ children }) => <p className="text-sm text-muted-foreground">{children}</p>

const ALL_NONE = '__none__'

// N5 — statuts d'un équipement du parc (miroir de sav.Equipement.Statut).
const EQUIP_STATUTS = [
  { value: 'en_service', label: 'En service' },
  { value: 'remplace', label: 'Remplacé' },
  { value: 'hors_service', label: 'Hors service' },
]
const equipStatutLabel = (v) =>
  EQUIP_STATUTS.find((s) => s.value === v)?.label ?? '—'

export default function InstallationDetail({ installation, onClose, onSaved }) {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant) : la fiche
  // installation est un panneau/hub ouvert par actif, donc dynamique (client)
  // plutôt qu'une route dédiée — repli sur « Installation » si le client
  // n'est pas encore chargé.
  useDocumentTitle(installation?.client_nom ? `Installation · ${installation.client_nom}` : 'Installation')
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const id = installation.id

  // État local éditable + version courante (rafraîchie après interventions).
  const [current, setCurrent] = useState(installation)
  const F = (k, d = '') => current?.[k] ?? d
  const initialFields = {
    statut: F('statut', 'a_planifier'),
    site_adresse: F('site_adresse'),
    site_ville: F('site_ville'),
    // XFSM8 — notes d'accès, saisies une fois et réutilisées sur chaque visite.
    contact_site_nom: F('contact_site_nom'),
    contact_site_telephone: F('contact_site_telephone'),
    acces_instructions: F('acces_instructions'),
    horaires_acces: F('horaires_acces'),
    date_pose_prevue: F('date_pose_prevue'),
    date_pose_reelle: F('date_pose_reelle'),
    puissance_installee_kwc: F('puissance_installee_kwc'),
    labour_jours_estimes: F('labour_jours_estimes'),
    labour_jours_reels: F('labour_jours_reels'),
    regime_8221: F('regime_8221', 'non_concerne'),
    dossier_statut: F('dossier_statut', 'non_concerne'),
    dossier_reference: F('dossier_reference'),
    dossier_operateur: F('dossier_operateur'),
    dossier_date_depot: F('dossier_date_depot'),
    dossier_date_approbation: F('dossier_date_approbation'),
    art33_regularisation: current?.art33_regularisation ?? false,
    notes: F('notes'),
  }
  const [fields, setFields] = useState(initialFields)
  const set = (k, v) => setFields(f => ({ ...f, [k]: v }))
  const dirty = JSON.stringify(fields) !== JSON.stringify(initialFields)
  useDirtyGuard(dirty)

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  // Retour FR explicite pour les actions secondaires (équipement / intervention
  // / ticket / besoin) dont les échecs étaient avalés (catch vides).
  const [actionError, setActionError] = useState(null)
  const actionMsg = (err, fallback) =>
    err?.response?.data?.detail || (typeof fallback === 'string' ? fallback : 'Action impossible.')

  // Historique (chatter)
  const [historique, setHistorique] = useState([])
  const [noteBody, setNoteBody] = useState('')

  // Intervention en cours d'ajout
  const [interv, setInterv] = useState({ type_intervention: '', date_prevue: '', compte_rendu: '' })
  const [intervBusy, setIntervBusy] = useState(false)
  // N5 — édition en place d'une intervention existante (ligne du tableau).
  const [editInterv, setEditInterv] = useState(null) // { id, date_realisee, compte_rendu, technicien }
  const [editIntervBusy, setEditIntervBusy] = useState(false)
  const [users, setUsers] = useState([])
  const startEditInterv = (iv) => setEditInterv({
    id: iv.id,
    date_realisee: iv.date_realisee ?? '',
    compte_rendu: iv.compte_rendu ?? '',
    technicien: iv.technicien ? String(iv.technicien) : '',
  })
  const saveEditInterv = async () => {
    if (!editInterv) return
    setEditIntervBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      await installationsApi.updateIntervention(editInterv.id, {
        date_realisee: nullable(editInterv.date_realisee),
        compte_rendu: nullable(editInterv.compte_rendu),
        technicien: nullable(editInterv.technicien),
      })
      setEditInterv(null)
      setActionError(null)
      await refreshInstallation()
      loadHistorique()
    } catch (err) {
      setActionError(actionMsg(err, "Édition de l'intervention impossible."))
    } finally { setEditIntervBusy(false) }
  }

  // N2 — types d'intervention gérés de la société (Paramètres → Chantiers) ;
  // repli sur la liste en dur tant qu'aucun type géré n'est chargé.
  const [typesInterv, setTypesInterv] = useState([])
  const typeOptions = typesInterv.length
    ? typesInterv.map((t) => ({ value: t.cle, label: t.libelle }))
    : INTERVENTION_TYPES

  // N3 — choisir le type « pose » pré-remplit la date prévue depuis la date de
  // pose prévue du chantier (si le champ date est encore vide).
  const onChangeIntervType = (value) => {
    setInterv((s) => {
      const next = { ...s, type_intervention: value }
      if (value === 'pose' && !s.date_prevue && current?.date_pose_prevue) {
        next.date_prevue = current.date_pose_prevue
      }
      return next
    })
  }

  // Mise en service
  const [mes, setMes] = useState({
    date_mise_en_service: F('date_mise_en_service'),
    mes_pv_notes: F('mes_pv_notes'),
    mes_production_test: F('mes_production_test'),
    mes_tension: F('mes_tension'),
  })
  const [mesBusy, setMesBusy] = useState(false)

  // Parc d'équipements & tickets SAV du chantier
  const produits = useSelector(s => s.stock.produits) ?? []
  const [equipements, setEquipements] = useState([])
  // N3 — la date de pose de l'équipement est pré-remplie depuis la date de pose
  // réelle du chantier (miroir du fallback serveur de cocher_checklist).
  const equipBlank = () => ({ produit: '', numero_serie: '', date_pose: F('date_pose_reelle') })
  const [equip, setEquip] = useState(equipBlank)
  const [equipBusy, setEquipBusy] = useState(false)
  // L578 — slot d'équipement sélectionné (type de catégorie) qui filtre le
  // picker par TYPE ; '' = tous les produits du BOM (comportement historique).
  const [equipSlot, setEquipSlot] = useState('')
  const [tickets, setTickets] = useState([])
  // VX216(c) — le ticket SAV le plus récent de ce chantier, pour le maillon
  // « SAV » de l'OwnerChain (lecture seule, aucun état nouveau à charger —
  // `tickets` est déjà chargé pour la section Tickets plus bas).
  const latestTicket = tickets.length > 0
    ? [...tickets].sort((a, b) => (b.date_ouverture || '').localeCompare(a.date_ouverture || ''))[0]
    : null
  const [newTicket, setNewTicket] = useState({ type: 'correctif', description: '', equipement: '' })
  const [ticketBusy, setTicketBusy] = useState(false)
  const [contrats, setContrats] = useState([])

  // Confirmations
  const [annulerOpen, setAnnulerOpen] = useState(false)
  const [annulerMotif, setAnnulerMotif] = useState('')
  // N7 — confirmation supplémentaire si le système est actif au parc.
  const [annulerParcConfirm, setAnnulerParcConfirm] = useState(false)

  // N15 — détecte si le devis lié a divergé depuis la création du chantier
  // (nomenclature gelée `bom` vs lignes actuelles du devis).
  const [devisDivergent, setDevisDivergent] = useState(false)
  const checkDevisDivergence = () => {
    if (!installation.devis) {
      // Reset hors du corps synchrone de l'effet (évite un setState en cascade).
      Promise.resolve().then(() => setDevisDivergent(false))
      return
    }
    ventesApi.getDevisById(installation.devis).then((r) => {
      const lignes = (r.data?.lignes ?? []).filter((l) => l.produit)
      const bom = Array.isArray(current.bom) ? current.bom : []
      const norm = (arr) => arr
        .map((x) => `${x.produit ?? x.produit_id}:${Number(x.quantite) || 0}`)
        .sort()
        .join('|')
      const devisKey = norm(lignes)
      const bomKey = norm(bom)
      // Un BOM vide (chantier sans devis d'origine) n'est pas une divergence.
      setDevisDivergent(bom.length > 0 && devisKey !== bomKey)
    }).catch(() => {})
  }

  const loadHistorique = () => {
    installationsApi.getHistorique(id)
      .then(r => setHistorique(r.data)).catch(() => {})
  }
  const loadEquipements = () => {
    savApi.getEquipements({ installation: id })
      .then(r => setEquipements(r.data?.results ?? r.data ?? [])).catch(() => {})
  }
  const loadTickets = () => {
    savApi.getTickets({ installation: id, ouvert: 'tous' })
      .then(r => setTickets(r.data?.results ?? r.data ?? [])).catch(() => {})
  }
  const loadContrats = () => {
    if (!installation.client) return
    savApi.getContrats({ client: installation.client })
      .then(r => setContrats(r.data?.results ?? r.data ?? [])).catch(() => {})
  }

  useEffect(() => {
    loadHistorique()
    loadEquipements()
    loadTickets()
    loadContrats()
    if (produits.length === 0) dispatch(fetchProduits())
    installationsApi.getTypesIntervention()
      .then((r) => setTypesInterv(
        (r.data?.results ?? r.data ?? []).filter((t) => !t.archived)))
      .catch(() => {})
    checkDevisDivergence()
    crmApi.getAssignableUsers()
      .then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // N5 — édition/suppression en place d'un équipement capturé.
  const [editEquip, setEditEquip] = useState(null) // { id, numero_serie, statut }
  const [editEquipBusy, setEditEquipBusy] = useState(false)
  const startEditEquip = (eq) => setEditEquip({
    id: eq.id,
    numero_serie: eq.numero_serie ?? '',
    statut: eq.statut ?? 'en_service',
  })
  const saveEditEquip = async () => {
    if (!editEquip) return
    setEditEquipBusy(true)
    try {
      await savApi.updateEquipement(editEquip.id, {
        numero_serie: editEquip.numero_serie === '' ? null : editEquip.numero_serie,
        statut: editEquip.statut,
      })
      setEditEquip(null)
      setActionError(null)
      loadEquipements()
    } catch (err) {
      setActionError(actionMsg(err, "Édition de l'équipement impossible."))
    } finally { setEditEquipBusy(false) }
  }
  const deleteEquip = async (eq) => {
    if (!window.confirm('Supprimer cet équipement du parc ?')) return
    try {
      await savApi.deleteEquipement(eq.id)
      setActionError(null)
      loadEquipements()
    } catch (err) {
      setActionError(actionMsg(err, "Suppression de l'équipement impossible."))
    }
  }

  const addEquipement = async () => {
    if (!equip.produit) return
    setEquipBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      await savApi.createEquipement({
        produit: equip.produit,
        installation: id,
        numero_serie: nullable(equip.numero_serie),
        date_pose: nullable(equip.date_pose),
      })
      setEquip(equipBlank())
      setActionError(null)
      loadEquipements()
    } catch (err) {
      setActionError(actionMsg(err, "Ajout de l'équipement impossible."))
    } finally { setEquipBusy(false) }
  }

  const openTicket = async () => {
    setTicketBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      await savApi.createTicket({
        client: current.client,
        installation: id,
        type: newTicket.type,
        description: nullable(newTicket.description),
        equipement: newTicket.equipement === '' ? null : newTicket.equipement,
      })
      setNewTicket({ type: 'correctif', description: '', equipement: '' })
      setActionError(null)
      loadTickets()
    } catch (err) {
      setActionError(actionMsg(err, "Ouverture du ticket impossible."))
    } finally { setTicketBusy(false) }
  }

  const refreshInstallation = async () => {
    try {
      const r = await installationsApi.getInstallation(id)
      setCurrent(r.data)
    } catch { /* erreur silencieuse */ }
  }

  const handleSave = async (e) => {
    e?.preventDefault?.()
    setSaving(true)
    setSaveError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      const data = Object.fromEntries(
        Object.entries(fields).map(([k, v]) => [k, nullable(v)]))
      await dispatch(updateInstallation({ id, data })).unwrap()
      onSaved?.()
    } catch (err) {
      // ERR61 — message FR lisible plutôt qu'un objet d'erreur brut sérialisé.
      // Le thunk rejette avec `err.response.data ?? err.message` ; on reconstruit
      // la forme attendue par `errorMessageFrom` (qui lit `error.response.data`).
      setSaveError(errorMessageFrom({ response: { data: err } }, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  const postNote = async () => {
    const body = noteBody.trim()
    if (!body) return
    try {
      const r = await installationsApi.noter(id, body)
      setHistorique(h => [r.data, ...h])
      setNoteBody('')
    } catch { /* erreur silencieuse */ }
  }

  const addIntervention = async () => {
    if (!interv.type_intervention) return
    setIntervBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      await installationsApi.createIntervention({
        installation: id,
        type_intervention: interv.type_intervention,
        date_prevue: nullable(interv.date_prevue),
        compte_rendu: nullable(interv.compte_rendu),
      })
      setInterv({ type_intervention: '', date_prevue: '', compte_rendu: '' })
      setActionError(null)
      await refreshInstallation()
      loadHistorique()
    } catch (err) {
      setActionError(actionMsg(err, "Ajout de l'intervention impossible."))
    } finally { setIntervBusy(false) }
  }

  const saveMes = async () => {
    // N7 — la mise en service exige une date ; on avertit (sans bloquer) si le
    // test de production ou la tension mesurée sont vides.
    if (!mes.date_mise_en_service) {
      setActionError('Indiquez une date de mise en service avant d’enregistrer.')
      return
    }
    const manques = []
    if (mes.mes_production_test === '' || mes.mes_production_test == null) {
      manques.push('test de production')
    }
    if (mes.mes_tension === '' || mes.mes_tension == null) manques.push('tension')
    if (manques.length
        && !window.confirm(
          `Champs non renseignés : ${manques.join(' et ')}. `
          + 'Enregistrer quand même la mise en service ?')) {
      return
    }
    setMesBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      const data = Object.fromEntries(
        Object.entries(mes).map(([k, v]) => [k, nullable(v)]))
      await installationsApi.miseEnService(id, data)
      setActionError(null)
      onSaved?.()
    } catch (err) {
      setActionError(actionMsg(err, 'Enregistrement de la mise en service impossible.'))
    } finally { setMesBusy(false) }
  }

  const confirmAnnuler = async () => {
    // Comportement préservé : motif optionnel, même appel API qu'avant.
    try {
      await installationsApi.annuler(id, annulerMotif)
      onSaved?.()
    } catch { /* erreur silencieuse */ }
    setAnnulerOpen(false)
  }

  const reactiver = async () => {
    try {
      await installationsApi.reactiver(id)
      onSaved?.()
    } catch { /* erreur silencieuse */ }
  }

  // N7 — action rapide « Marquer réceptionné » : pose le statut Réceptionné
  // (le serveur tamponne date_reception et journalise l'ajout au parc).
  const [receptBusy, setReceptBusy] = useState(false)
  const marquerReceptionne = async () => {
    // Avertissement (non bloquant) si la checklist n'est pas à 100 %.
    const comp = current.checklist_completion
    if (Number.isInteger(comp) && comp < 100
        && !window.confirm(
          `La checklist n'est complétée qu'à ${comp} %. `
          + 'Passer quand même le chantier à « Réceptionné » ?')) {
      return
    }
    setReceptBusy(true)
    try {
      await dispatch(updateInstallation({
        id, data: { statut: 'receptionne' },
      })).unwrap()
      setActionError(null)
      onSaved?.()
    } catch (err) {
      setActionError(actionMsg(err, 'Passage à « Réceptionné » impossible.'))
    } finally { setReceptBusy(false) }
  }

  // ── Aperçu in-app des documents après-vente (L4) ───────────────────────────
  // Chaque bouton « Documents après-vente » ouvre d'abord un APERÇU inline (le
  // PDF dessiné par PDF.js sur canvas, comme l'aperçu devis) AVANT de proposer
  // le téléchargement. Le contenu/endpoint du PDF généré est INCHANGÉ : on ne
  // fait qu'ajouter une étape d'aperçu devant le téléchargement existant.
  // `fetcher` renvoie la réponse axios (responseType:'blob') du MÊME appel API
  // qu'avant, donc l'octet affiché et l'octet téléchargé sont identiques.
  const [previewDoc, setPreviewDoc] = useState(null) // { title, filename, fetcher }
  const [previewBlob, setPreviewBlob] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewServerError, setPreviewServerError] = useState(false)
  const [previewNetworkFailed, setPreviewNetworkFailed] = useState(false)
  const [previewRenderFailed, setPreviewRenderFailed] = useState(false)
  const [previewReloadKey, setPreviewReloadKey] = useState(0)
  const [previewDownloading, setPreviewDownloading] = useState(false)

  // Ouvre le panneau d'aperçu pour un document donné (sans télécharger).
  const openPreview = (title, filename, fetcher) => {
    setPreviewDoc({ title, filename, fetcher })
    setPreviewBlob(null)
    setPreviewServerError(false)
    setPreviewNetworkFailed(false)
    setPreviewRenderFailed(false)
    setPreviewReloadKey((k) => k + 1)
  }
  const closePreview = () => {
    setPreviewDoc(null)
    setPreviewBlob(null)
    setPreviewServerError(false)
    setPreviewNetworkFailed(false)
    setPreviewRenderFailed(false)
  }
  const reloadPreview = () => {
    setPreviewBlob(null)
    setPreviewServerError(false)
    setPreviewNetworkFailed(false)
    setPreviewRenderFailed(false)
    setPreviewReloadKey((k) => k + 1)
  }

  // Récupère les octets du document à apercevoir. Distingue un VRAI échec
  // serveur (4xx/5xx, message clair) d'un échec réseau (repli téléchargeable).
  useEffect(() => {
    if (!previewDoc) return undefined
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewLoading(true)
    setPreviewServerError(false)
    setPreviewNetworkFailed(false)
    setPreviewRenderFailed(false)
    setPreviewBlob(null)
    previewDoc.fetcher()
      .then((res) => {
        if (cancelled) return
        setPreviewBlob(pdfBlob(res.data))
      })
      .catch((err) => {
        if (cancelled) return
        if (classifyFetchError(err) === 'server') setPreviewServerError(true)
        else setPreviewNetworkFailed(true)
      })
      .finally(() => { if (!cancelled) setPreviewLoading(false) })
    return () => { cancelled = true }
  }, [previewDoc, previewReloadKey])

  // Téléchargement depuis l'aperçu : MÊME chemin/octets qu'avant. On réutilise
  // le blob déjà récupéré ; sinon on relance l'appel d'origine.
  const downloadPreview = async () => {
    if (!previewDoc) return
    setPreviewDownloading(true)
    try {
      if (previewBlob) {
        downloadBlob(previewBlob, previewDoc.filename)
      } else {
        const res = await previewDoc.fetcher()
        downloadBlob(res.data, previewDoc.filename)
      }
    } catch {
      alert('Téléchargement indisponible. Réessayez.')
    } finally {
      setPreviewDownloading(false)
    }
  }

  // « Ouvrir dans un nouvel onglet » : MÊME PDF authentifié via une URL blob,
  // révoquée ensuite (aucune fuite).
  // VX48 — onglet pré-ouvert SYNCHRONE avant l'await (Safari iOS bloque
  // silencieusement un window.open() post-await).
  const openPreviewNewTab = async () => {
    if (!previewDoc) return
    const pending = openPdfInGesture()
    try {
      let blob = previewBlob
      if (!blob) {
        const res = await previewDoc.fetcher()
        blob = pdfBlob(res.data)
      }
      if (!pending.deliver(blob, previewDoc.filename)) {
        alert('Ouverture bloquée par le navigateur. Téléchargez le document.')
      }
    } catch {
      alert('Ouverture impossible. Réessayez ou téléchargez le document.')
    }
  }

  const previewState = previewView({
    loading: previewLoading,
    serverError: previewServerError,
    blocked: previewNetworkFailed || previewRenderFailed,
    hasUrl: !!previewBlob,
  })

  // Ouvre l'aperçu d'un document après-vente standard (PV, bon de livraison…).
  const openDocument = (kind, filename, title) =>
    openPreview(title, filename, () => documentsApi[kind](current.id))

  // Fiche de remise / garantie après-vente PREMIUM (langage visuel du devis).
  const openFicheRemise = () =>
    openPreview(
      'Fiche de remise / garantie',
      `Fiche_remise_${current.reference}.pdf`,
      () => ventesApi.getFicheRemisePremiumPdf(current.id),
    )

  const [besoin, setBesoin] = useState(null)
  const [besoinLoading, setBesoinLoading] = useState(false)
  const chargerBesoin = async () => {
    setBesoinLoading(true)
    try {
      const r = await installationsApi.besoinMateriel(current.id)
      setBesoin(r.data)
    } catch {
      setBesoin({ items: [], nb_manques: 0, error: true })
    }
    setBesoinLoading(false)
  }
  const commanderBesoin = async () => {
    try {
      const r = await installationsApi.commanderBesoin(current.id)
      alert(`Bon de commande fournisseur créé : ${r.data.reference} (${r.data.nb_lignes} ligne(s)).`)
      chargerBesoin()
    } catch (e) {
      alert(e?.response?.data?.detail || 'Création impossible.')
    }
  }

  const interventions = current.interventions ?? []

  // N1/N2 — produits du picker scopés à la nomenclature gelée du devis (BOM) ;
  // repli sur tout le catalogue si le chantier n'a pas de BOM.
  const bom = Array.isArray(current.bom) ? current.bom : []
  const bomProduitIds = new Set(bom.map((l) => String(l.produit_id)).filter(Boolean))
  const bomProduits = bomProduitIds.size
    ? produits.filter((p) => bomProduitIds.has(String(p.id)))
    : produits

  // L578 — filtre de SLOT par TYPE d'équipement : chaque type est dérivé des
  // catégories TYPÉES (Categorie.type_equipement) présentes dans le BOM. Quand
  // la société n'a typé aucune de ses catégories, aucune option n'apparaît et
  // le picker reste sur la liste BOM complète (comportement historique). Choisir
  // « Onduleur » ne montre que les produits typés onduleur, « Panneau » que les
  // panneaux, etc. « Tous » revient à la liste BOM complète.
  // Type d'un produit : le champ plat `categorie_type` (L578) avec repli sur la
  // catégorie imbriquée pour rester robuste si l'API n'a pas encore le champ.
  const typeOf = (p) => p?.categorie_type ?? p?.categorie?.type_equipement ?? null
  const equipTypes = (() => {
    const seen = new Map()
    for (const p of bomProduits) {
      const t = typeOf(p)
      if (t && !seen.has(t)) {
        seen.set(t, p.categorie_type_display ?? t)
      }
    }
    return [...seen.entries()].map(([value, label]) => ({ value, label }))
  })()
  const equipProduits = equipSlot
    ? bomProduits.filter((p) => typeOf(p) === equipSlot)
    : bomProduits

  // N8 — réconciliation : pour chaque ligne BOM, nb de séries capturées.
  const bomReconciliation = bom.map((l) => {
    const captured = equipements.filter(
      (eq) => String(eq.produit) === String(l.produit_id)).length
    return {
      produit_id: l.produit_id,
      designation: l.designation,
      attendu: l.quantite ?? null,
      captured,
    }
  })

  // N7 — équipement : produit choisi, garantie manquante, n° série en doublon.
  const equipProduit = produits.find((p) => String(p.id) === String(equip.produit))
  const garantieManquante = equipProduit
    && !equipProduit.garantie_mois && !equipProduit.garantie_production_mois
  const serieSaisie = (equip.numero_serie || '').trim().toLowerCase()
  const serieDoublon = !!serieSaisie && equipements.some(
    (eq) => (eq.numero_serie || '').trim().toLowerCase() === serieSaisie)

  // N6 — les documents après-vente (PV / handover) ne sont pertinents qu'une
  // fois le jalon atteint : statut canonique ≥ « Installé » ET checklist
  // quasi-complète (≥ 80 %). Sinon les boutons sont désactivés avec un tooltip.
  const installeRank = INSTALLATION_STATUSES.indexOf('installe')
  const statutOk = (() => {
    const r = INSTALLATION_STATUSES.indexOf(current.statut)
    // Statut hérité (hors liste) : pose/installe/mise_en_service/raccordement
    // couvrent déjà le jalon « Installé ».
    if (r === -1) {
      return ['pose', 'mise_en_service', 'raccordement_onee'].includes(current.statut)
    }
    return r >= installeRank
  })()
  const pvComp = current.checklist_completion
  const checklistOk = !Number.isInteger(pvComp) || pvComp >= 80
  const pvReady = statutOk && checklistOk
  const pvTooltip = pvReady ? undefined
    : 'Disponible une fois le chantier installé et la checklist quasi-complète.'

  return (
    <Sheet open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose?.() }}>
      <SheetContent side="right" className="w-[min(64rem,calc(100%-1.5rem))] sm:max-w-none">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            Chantier — {current.reference ?? ''}
            {current.annule && <StatusPill tone="danger" label="Annulé" />}
          </SheetTitle>
        </SheetHeader>

        <div className="flex flex-col gap-4">
          {current.annule && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm" role="alert">
              <strong className="text-destructive">Chantier annulé.</strong>
              {current.motif_annulation ? <span>Motif : {current.motif_annulation}</span> : null}
              <Button size="sm" variant="outline" className="ml-auto" onClick={reactiver}>
                Réactiver
              </Button>
            </div>
          )}

          {/* ── Prochaine action recommandée (N1) — bannière sous l'en-tête ── */}
          {!current.annule && nextBestAction(current) && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-info/30 bg-info/10 p-3 text-sm" role="status">
              <strong className="text-info">Prochaine action&nbsp;:</strong>
              <span>{nextBestAction(current)}</span>
            </div>
          )}

          {/* N15 — le devis lié a changé depuis la création du chantier. */}
          {!current.annule && devisDivergent && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm" role="status">
              <strong className="text-warning-foreground">Devis modifié&nbsp;:</strong>
              <span>
                le devis a changé depuis la création du chantier (la nomenclature
                gelée diffère des lignes actuelles).
              </span>
            </div>
          )}

          {/* N15 — chantier sans nomenclature gelée (créé sans devis). */}
          {!current.annule && Array.isArray(current.bom) && current.bom.length === 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm" role="status">
              <strong className="text-warning-foreground">Nomenclature absente&nbsp;:</strong>
              <span>ce chantier n&apos;a pas de nomenclature gelée (créé sans devis).</span>
            </div>
          )}

          {/* Retour FR des actions secondaires (échecs auparavant silencieux). */}
          {actionError && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive" role="alert">
              <span>{actionError}</span>
              <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setActionError(null)}>
                Fermer
              </Button>
            </div>
          )}

          {/* ── Liens ── */}
          <Section icon={Link2} title="Liens">
            {/* VX216(c) — chaîne de responsabilité cliquable : personne ne
                voyait « Lead : A · Devis : B · Chantier : C · SAV : D » d'un
                coup d'œil quand le client rappelle. Maillons = deep-links
                RÉELS existants (VX79 ?id=/?lead=/?devis=) ; un maillon sans
                id connu est simplement absent. */}
            <OwnerChain
              className="mb-2"
              lead={current.lead ? { id: current.lead, nom: current.lead_nom } : null}
              devis={current.devis ? { id: current.devis, nom: current.devis_reference } : null}
              chantier={{ id: current.id, nom: current.reference }}
              sav={latestTicket ? { id: latestTicket.id, nom: latestTicket.reference } : null}
            />
            <div className="flex flex-wrap gap-2">
              {current.devis && (
                <Button size="sm" variant="outline"
                        onClick={() => navigate(`/ventes/devis?devis=${current.devis}`)}>
                  Voir le devis{current.devis_reference ? ` (${current.devis_reference})` : ''}
                </Button>
              )}
              {current.client && (
                <Button size="sm" variant="outline" onClick={() => navigate('/crm')}>
                  Voir le client
                </Button>
              )}
              {current.lead && (
                <Button size="sm" variant="outline"
                        onClick={() => navigate(`/crm/leads?lead=${current.lead}`)}>
                  Voir le lead
                </Button>
              )}
            </div>
          </Section>

          {/* ── Timeline du chantier (N6) ── */}
          <Section icon={History} title="Timeline">
            <ChantierTimeline installation={current} />
          </Section>

          {/* ── CH6 — parcours d'étapes/gates guidé (remplace le simple statut) :
              chaque étape du cycle de vie configurable (CH1), l'état de son
              gate (CH2, raisons de blocage en français), la prochaine action
              explicite, et la recette de mise en service (CH3) + le pack de
              remise client (CH4) mis en avant. Dégrade proprement (message
              informatif) si la société n'a configuré aucune étape. ── */}
          <Section icon={Milestone} title="Parcours du chantier">
            <ChantierGateTimeline installationId={id} onAdvanced={refreshInstallation} />
          </Section>

          {/* ── Documents après-vente (PDF régénérés à la demande) ── */}
          <Section icon={FileText} title="Documents après-vente">
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" disabled={!pvReady} title={pvTooltip}
                      onClick={() => openDocument('pvReception', `pv-reception-${current.reference}.pdf`, 'PV de réception')}>
                PV de réception
              </Button>
              <Button size="sm" variant="outline" disabled={!pvReady} title={pvTooltip}
                      onClick={() => openDocument('bonLivraison', `bon-livraison-${current.reference}.pdf`, 'Bon de livraison')}>
                Bon de livraison
              </Button>
              <Button size="sm" variant="outline" disabled={!pvReady} title={pvTooltip}
                      onClick={() => openDocument('dossierRemise', `dossier-remise-${current.reference}.pdf`, 'Dossier de remise')}>
                Dossier de remise
              </Button>
              <Button size="sm" variant="outline" disabled={!pvReady} title={pvTooltip}
                      onClick={openFicheRemise}>
                Fiche de remise / garantie
              </Button>
              {!pvReady && (
                <span className="w-full text-xs text-muted-foreground">{pvTooltip}</span>
              )}
              <Button size="sm" variant="outline"
                      onClick={() => openDocument('attestation', `attestation-${current.reference}.pdf`, 'Attestation')}>
                Attestation
              </Button>
              <Button size="sm" variant="outline"
                      onClick={() => navigate(`/reporting/archive/chantier/${current.id}`)}>
                Archive documentaire
              </Button>
            </div>
          </Section>

          {/* ── Besoin matériel vs stock (N13) ── */}
          <Section
            icon={Package}
            title="Besoin matériel"
            action={(
              <Button size="sm" variant="outline" onClick={chargerBesoin} loading={besoinLoading}>
                {besoinLoading ? 'Calcul…' : 'Calculer le besoin'}
              </Button>
            )}
          >
            {besoin && (
              besoin.error ? (
                <Hint>Besoin indisponible (ce chantier a-t-il un devis ?).</Hint>
              ) : besoin.items.length === 0 ? (
                <Hint>Aucune ligne produit sur le devis source.</Hint>
              ) : (
                <>
                  <MiniTable head={['Article', 'Requis', 'Réservé', 'Dispo', 'Manque', 'Fournisseur']}>
                    {besoin.items.map((it) => (
                      <tr key={it.produit_id} className={`border-t border-border ${it.manque > 0 ? 'bg-destructive/5' : ''}`}>
                        <td className="px-3 py-2">{it.designation}</td>
                        <td className="px-3 py-2">{it.requis}</td>
                        <td className="px-3 py-2">{it.reserve > 0 ? it.reserve : '—'}</td>
                        <td className="px-3 py-2">{it.disponible}</td>
                        <td className="px-3 py-2">{it.manque > 0 ? <strong className="text-destructive">{it.manque}</strong> : '—'}</td>
                        <td className="px-3 py-2">{it.fournisseur_nom || '—'}</td>
                      </tr>
                    ))}
                  </MiniTable>
                  {besoin.nb_manques > 0 && (
                    <Button size="sm" onClick={commanderBesoin} className="self-start">
                      Créer un bon de commande fournisseur ({besoin.nb_manques})
                    </Button>
                  )}
                </>
              )
            )}
          </Section>

          {/* ── Infos & édition ── */}
          <Section icon={Hammer} title="Chantier">
            <div className="grid gap-3 sm:grid-cols-3">
              <FormField label="Référence" htmlFor="ch-ref">
                <Input id="ch-ref" value={current.reference ?? '—'} readOnly />
              </FormField>
              <FormField label="Raccordement" htmlFor="ch-rac">
                <Input id="ch-rac" value={current.raccordement_display ?? '—'} readOnly />
              </FormField>
              <FormField label="Type" htmlFor="ch-type">
                <Input id="ch-type" value={current.type_installation_display ?? '—'} readOnly />
              </FormField>
              <FormField label="Client" htmlFor="ch-cli">
                <Input id="ch-cli" value={current.client_nom ?? '—'} readOnly />
              </FormField>
              <FormField label="Devis" htmlFor="ch-dev">
                <Input id="ch-dev" value={current.devis_reference ?? '—'} readOnly />
              </FormField>
              <FormField label="Technicien" htmlFor="ch-tec">
                <Input id="ch-tec" value={current.technicien_nom ?? '—'} readOnly />
              </FormField>
              <FormField label="Statut" htmlFor="ch-statut">
                <Select
                  value={fields.statut ?? ''}
                  onValueChange={(v) => {
                    // Garde de transition côté client : on n'accepte qu'un pas
                    // (avant/arrière) depuis le statut STOCKÉ du chantier, ou la
                    // valeur déjà sélectionnée. Un saut non-adjacent est empêché.
                    if (v === fields.statut
                        || canMoveStatus(current.statut, v)
                        || v === current.statut) {
                      set('statut', v)
                    }
                  }}
                >
                  <SelectTrigger id="ch-statut"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {/* Statut hérité éventuel conservé en tête pour ne pas le perdre. */}
                    {fields.statut && !INSTALLATION_STATUSES.includes(fields.statut) && (
                      <SelectItem value={fields.statut}>
                        {STATUS_LABELS[fields.statut] ?? fields.statut} (ancien)
                      </SelectItem>
                    )}
                    {/* Seuls le statut courant et ses voisins (±1) sont offerts. */}
                    {adjacentStatuses(current.statut).map((k) => (
                      <SelectItem key={k} value={k}>{STATUS_LABELS[k]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="mt-1 text-xs text-muted-foreground">
                  Le statut n&apos;avance ou ne recule que d&apos;une étape à la fois.
                </p>
              </FormField>
              <FormField label="Adresse du site" htmlFor="ch-adr" className="sm:col-span-2">
                <Input id="ch-adr" value={fields.site_adresse ?? ''}
                       onChange={(e) => set('site_adresse', e.target.value)} />
              </FormField>
              <FormField label="Ville" htmlFor="ch-ville">
                <Input id="ch-ville" value={fields.site_ville ?? ''}
                       onChange={(e) => set('site_ville', e.target.value)} />
              </FormField>
              <FormField label="Pose prévue le" htmlFor="ch-pp">
                <Input id="ch-pp" type="date" value={fields.date_pose_prevue ?? ''}
                       onChange={(e) => set('date_pose_prevue', e.target.value)} />
              </FormField>
              <FormField label="Pose réelle le" htmlFor="ch-pr">
                <Input id="ch-pr" type="date" value={fields.date_pose_reelle ?? ''}
                       onChange={(e) => set('date_pose_reelle', e.target.value)} />
              </FormField>
              <FormField label="Puissance installée (kWc)" htmlFor="ch-kwc">
                <Input id="ch-kwc" type="number" step="any" value={fields.puissance_installee_kwc ?? ''}
                       onChange={(e) => set('puissance_installee_kwc', e.target.value)} />
              </FormField>
              <FormField label="Jours-homme estimés" htmlFor="ch-je">
                <Input id="ch-je" type="number" step="any" value={fields.labour_jours_estimes ?? ''}
                       onChange={(e) => set('labour_jours_estimes', e.target.value)} />
              </FormField>
              <FormField label="Jours-homme réels" htmlFor="ch-jr">
                <Input id="ch-jr" type="number" step="any" value={fields.labour_jours_reels ?? ''}
                       onChange={(e) => set('labour_jours_reels', e.target.value)} />
              </FormField>
              <FormField label="Contact sur site" htmlFor="ch-contact-nom">
                <Input id="ch-contact-nom" value={fields.contact_site_nom ?? ''}
                       onChange={(e) => set('contact_site_nom', e.target.value)} />
              </FormField>
              <FormField label="Téléphone du contact" htmlFor="ch-contact-tel">
                <div className="flex items-center gap-2">
                  <Input id="ch-contact-tel" value={fields.contact_site_telephone ?? ''}
                         onChange={(e) => set('contact_site_telephone', e.target.value)} />
                  {telHref(fields.contact_site_telephone) && (
                    <a href={telHref(fields.contact_site_telephone)} title="Appeler"
                       className="link-blue whitespace-nowrap">☎</a>
                  )}
                </div>
              </FormField>
              <FormField label="Horaires d'accès" htmlFor="ch-horaires" className="sm:col-span-2">
                <Input id="ch-horaires" value={fields.horaires_acces ?? ''}
                       onChange={(e) => set('horaires_acces', e.target.value)} />
              </FormField>
            </div>
            <FormField label="Consignes d'accès (clé/badge/gardien, animal, etc.)" htmlFor="ch-acces">
              <Textarea id="ch-acces" rows={2} value={fields.acces_instructions ?? ''}
                        onChange={(e) => set('acces_instructions', e.target.value)} />
            </FormField>
            <FormField label="Notes" htmlFor="ch-notes">
              <Textarea id="ch-notes" rows={2} value={fields.notes ?? ''}
                        onChange={(e) => set('notes', e.target.value)} />
            </FormField>
            {saveError && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive" role="alert">
                {saveError}
              </div>
            )}
          </Section>

          {/* ── Dossier réglementaire loi 82-21 / Article 33 (N40/N42) ── */}
          <Section icon={ScrollText} title="Dossier réglementaire (loi 82-21)">
            <div className="grid gap-3 sm:grid-cols-3">
              <FormField label="Régime" htmlFor="ch-regime">
                <Select value={fields.regime_8221 ?? 'non_concerne'} onValueChange={(v) => set('regime_8221', v)}>
                  <SelectTrigger id="ch-regime"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="non_concerne">Non concerné</SelectItem>
                    <SelectItem value="declaration_bt">Déclaration (&lt; 11 kW, BT)</SelectItem>
                    <SelectItem value="accord_raccordement">Accord de raccordement</SelectItem>
                    <SelectItem value="autorisation_anre">Autorisation ANRE (&gt; 1 MW)</SelectItem>
                  </SelectContent>
                </Select>
                {current?.regime_suggere?.code
                  && current.regime_suggere.code !== 'non_concerne'
                  && current.regime_suggere.code !== fields.regime_8221 && (
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                    Suggéré : <strong>{current.regime_suggere.label}</strong>
                    <Button size="sm" variant="outline" className="h-6 px-2 text-xs"
                            onClick={() => set('regime_8221', current.regime_suggere.code)}>
                      Appliquer
                    </Button>
                  </div>
                )}
              </FormField>
              <FormField label="Statut du dossier" htmlFor="ch-dstatut">
                <Select value={fields.dossier_statut ?? 'non_concerne'} onValueChange={(v) => set('dossier_statut', v)}>
                  <SelectTrigger id="ch-dstatut"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="non_concerne">Non concerné</SelectItem>
                    <SelectItem value="a_deposer">À déposer</SelectItem>
                    <SelectItem value="depose">Déposé</SelectItem>
                    <SelectItem value="approuve">Approuvé</SelectItem>
                    <SelectItem value="compteur_pose">Compteur posé</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <div className="flex items-end">
                <label className="flex items-center gap-2 pb-2 text-sm">
                  <Checkbox checked={!!fields.art33_regularisation}
                            onCheckedChange={(c) => set('art33_regularisation', c === true)} />
                  Régularisation Article 33
                </label>
              </div>
              <FormField label="Référence / N° de dossier" htmlFor="ch-dref">
                <Input id="ch-dref" value={fields.dossier_reference ?? ''}
                       onChange={(e) => set('dossier_reference', e.target.value)} />
              </FormField>
              <FormField label="Opérateur / interlocuteur" htmlFor="ch-dop">
                <Input id="ch-dop" value={fields.dossier_operateur ?? ''}
                       onChange={(e) => set('dossier_operateur', e.target.value)} />
              </FormField>
              <FormField label="Date de dépôt" htmlFor="ch-ddep">
                <Input id="ch-ddep" type="date" value={fields.dossier_date_depot ?? ''}
                       onChange={(e) => set('dossier_date_depot', e.target.value)} />
              </FormField>
              <FormField label="Date d'approbation" htmlFor="ch-dapp">
                <Input id="ch-dapp" type="date" value={fields.dossier_date_approbation ?? ''}
                       onChange={(e) => set('dossier_date_approbation', e.target.value)} />
              </FormField>
            </div>
            <Hint>Joignez les pièces du dossier dans « Photos &amp; fichiers » ci-dessous.</Hint>
          </Section>

          {/* ── Checklist d'exécution (N4/N9) ── */}
          <Section icon={ClipboardList} title="Checklist d'exécution">
            {/* VX80 — impression de la checklist chantier (feuille print.css :
                chrome masqué, noir-sur-blanc, contenu complet). Distinct des PDF
                WeasyPrint. */}
            <div className="mb-3">
              <Button size="sm" variant="outline" onClick={() => window.print()}>
                <Printer /> Imprimer la checklist
              </Button>
            </div>
            {/* FG386/N91/F21 — état de la synchro terrain hors-ligne (silencieux
                si en ligne et file vide). */}
            <OfflineSyncIndicator />
            <ChantierChecklist installationId={id} produits={produits}
                               series={equipements.map((eq) => eq.numero_serie).filter(Boolean)}
                               onChanged={() => { refreshInstallation(); loadEquipements() }} />
          </Section>

          {/* ── Photos & fichiers avant/pendant/après (N5) ── */}
          <Section icon={Camera} title="Photos & fichiers">
            <ChantierPhotos installationId={id} />
          </Section>

          {/* ── Interventions ── */}
          <Section icon={Wrench} title="Interventions">
            {interventions.length === 0 ? (
              <Hint>Aucune intervention.</Hint>
            ) : (
              <MiniTable head={['Type', 'Prévue', 'Réalisée', 'Technicien', 'Compte rendu', '']}>
                {interventions.map((iv) => {
                  const editing = editInterv?.id === iv.id
                  return (
                    <tr key={iv.id} className="border-t border-border">
                      <td className="px-3 py-2">{iv.type_intervention_display ?? iv.type_intervention}</td>
                      <td className="px-3 py-2">{formatDate(iv.date_prevue)}</td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Input type="date" value={editInterv.date_realisee}
                                 onChange={(e) => setEditInterv(s => ({ ...s, date_realisee: e.target.value }))} />
                        ) : formatDate(iv.date_realisee)}
                      </td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Select value={editInterv.technicien || ALL_NONE}
                                  onValueChange={(v) => setEditInterv(s => ({ ...s, technicien: v === ALL_NONE ? '' : v }))}>
                            <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value={ALL_NONE}>—</SelectItem>
                              {users.map((u) => (
                                <SelectItem key={u.id} value={String(u.id)}>
                                  {u.username ?? u.nom ?? `#${u.id}`}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (iv.technicien_nom ?? '—')}
                      </td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Input value={editInterv.compte_rendu}
                                 onChange={(e) => setEditInterv(s => ({ ...s, compte_rendu: e.target.value }))} />
                        ) : (iv.compte_rendu ?? '—')}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        {editing ? (
                          <span className="flex gap-1">
                            <Button size="sm" loading={editIntervBusy} onClick={saveEditInterv}>
                              Enregistrer
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditInterv(null)}>
                              Annuler
                            </Button>
                          </span>
                        ) : (
                          <Button size="sm" variant="outline" onClick={() => startEditInterv(iv)}>
                            Éditer
                          </Button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </MiniTable>
            )}
            <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_2fr_auto]">
              <FormField label="Type" htmlFor="iv-type">
                <Select value={interv.type_intervention || ALL_NONE}
                        onValueChange={(v) => onChangeIntervType(v === ALL_NONE ? '' : v)}>
                  <SelectTrigger id="iv-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_NONE}>—</SelectItem>
                    {typeOptions.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField label="Date prévue" htmlFor="iv-date">
                <Input id="iv-date" type="date" value={interv.date_prevue}
                       onChange={(e) => setInterv(s => ({ ...s, date_prevue: e.target.value }))} />
              </FormField>
              <FormField label="Compte rendu" htmlFor="iv-cr">
                <Input id="iv-cr" value={interv.compte_rendu}
                       onChange={(e) => setInterv(s => ({ ...s, compte_rendu: e.target.value }))} />
              </FormField>
              <Button variant="outline" loading={intervBusy} disabled={!interv.type_intervention}
                      onClick={addIntervention}>
                Ajouter
              </Button>
            </div>
          </Section>

          {/* ── Équipements (parc) ── */}
          <Section icon={Package} title="Équipements">
            {/* N8 — réconciliation nomenclature gelée vs séries capturées. */}
            {bomReconciliation.length > 0 && (
              <div className="rounded-lg border border-border p-2">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Nomenclature vs séries capturées
                </p>
                <MiniTable head={['Composant', 'Attendu', 'Capturés']}>
                  {bomReconciliation.map((b) => {
                    const manque = b.captured === 0
                    return (
                      <tr key={b.produit_id ?? b.designation}
                          className={`border-t border-border ${manque ? 'bg-warning/10' : ''}`}>
                        <td className="px-3 py-2">{b.designation}</td>
                        <td className="px-3 py-2">{b.attendu ?? '—'}</td>
                        <td className="px-3 py-2">
                          {manque
                            ? <strong className="text-warning-foreground">0</strong>
                            : b.captured}
                        </td>
                      </tr>
                    )
                  })}
                </MiniTable>
              </div>
            )}
            {equipements.length === 0 ? (
              <Hint>Aucun équipement enregistré sur ce chantier.</Hint>
            ) : (
              <MiniTable head={['Produit', 'N° série', 'Posé le', 'Statut', 'Garantie', '']}>
                {equipements.map((eq) => {
                  const editing = editEquip?.id === eq.id
                  return (
                    <tr key={eq.id} className="border-t border-border">
                      <td className="px-3 py-2">{eq.produit_nom ?? '—'}{eq.produit_marque ? ` (${eq.produit_marque})` : ''}</td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Input value={editEquip.numero_serie}
                                 onChange={(e) => setEditEquip(s => ({ ...s, numero_serie: e.target.value }))} />
                        ) : (eq.numero_serie ?? '—')}
                      </td>
                      <td className="px-3 py-2">{formatDate(eq.date_pose)}</td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Select value={editEquip.statut}
                                  onValueChange={(v) => setEditEquip(s => ({ ...s, statut: v }))}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {EQUIP_STATUTS.map((s) => (
                                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (eq.statut_display ?? equipStatutLabel(eq.statut))}
                      </td>
                      <td className="px-3 py-2">
                        <span className="text-xs font-semibold" style={{ color: garantieColor(eq) }}>
                          {garantieLabel(eq)}
                        </span>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        {editing ? (
                          <span className="flex gap-1">
                            <Button size="sm" loading={editEquipBusy} onClick={saveEditEquip}>
                              Enregistrer
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditEquip(null)}>
                              Annuler
                            </Button>
                          </span>
                        ) : (
                          <span className="flex gap-1">
                            <Button size="sm" variant="outline" onClick={() => startEditEquip(eq)}>
                              Éditer
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => deleteEquip(eq)}>
                              Supprimer
                            </Button>
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </MiniTable>
            )}
            {/* L578 — filtre de slot par TYPE (n'apparaît que si des catégories
                du BOM sont typées). Choisir un type restreint le picker. */}
            {equipTypes.length > 0 && (
              <FormField label="Type d'équipement" htmlFor="eq-slot">
                <Select value={equipSlot || ALL_NONE}
                        onValueChange={(v) => {
                          const next = v === ALL_NONE ? '' : v
                          setEquipSlot(next)
                          // Vide le produit choisi s'il ne correspond plus au slot.
                          if (next && equip.produit) {
                            const sel = produits.find((p) => String(p.id) === String(equip.produit))
                            if (typeOf(sel) !== next) setEquip(s => ({ ...s, produit: '' }))
                          }
                        }}>
                  <SelectTrigger id="eq-slot"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_NONE}>Tous</SelectItem>
                    {equipTypes.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
            )}
            <div className="grid items-end gap-3 sm:grid-cols-[2fr_1fr_1fr_auto]">
              <FormField label="Produit" htmlFor="eq-prod">
                <ProduitPicker produits={equipProduits}
                               value={equip.produit ?? ''}
                               onChange={(v) => setEquip(s => ({ ...s, produit: v ?? '' }))} />
              </FormField>
              <FormField label="N° de série" htmlFor="eq-ns">
                <Input id="eq-ns" value={equip.numero_serie}
                       onChange={(e) => setEquip(s => ({ ...s, numero_serie: e.target.value }))} />
              </FormField>
              <FormField label="Date de pose" htmlFor="eq-dp">
                <Input id="eq-dp" type="date" value={equip.date_pose}
                       onChange={(e) => setEquip(s => ({ ...s, date_pose: e.target.value }))} />
              </FormField>
              <Button variant="outline" loading={equipBusy} disabled={!equip.produit} onClick={addEquipement}>
                Ajouter
              </Button>
            </div>
            {garantieManquante && (
              <p className="text-xs text-warning-foreground">
                Garantie non renseignée pour ce produit — l&apos;horloge de garantie
                restera vide.
              </p>
            )}
            {serieDoublon && (
              <p className="text-xs text-destructive">
                Ce numéro de série existe déjà sur un équipement de ce chantier.
              </p>
            )}
          </Section>

          {/* ── Tickets SAV ── */}
          <Section icon={Wrench} title="Tickets SAV">
            {tickets.length === 0 ? (
              <Hint>Aucun ticket SAV sur ce chantier.</Hint>
            ) : (
              <MiniTable head={['Référence', 'Statut', 'Type', 'Garantie']}>
                {tickets.map((t) => (
                  <tr key={t.id} className="border-t border-border">
                    <td className="px-3 py-2">{t.reference}{t.annule ? ' (annulé)' : ''}</td>
                    <td className="px-3 py-2">
                      <StatusPill status={t.statut} label={TICKET_STATUS_LABELS[t.statut] ?? t.statut} />
                    </td>
                    <td className="px-3 py-2">{t.type_display ?? t.type}</td>
                    <td className="px-3 py-2">{SOUS_GARANTIE_LABELS[t.sous_garantie_effectif] ?? '—'}</td>
                  </tr>
                ))}
              </MiniTable>
            )}
            <Hint>Le suivi détaillé (interventions, historique) se fait dans l&apos;écran « Tickets SAV ».</Hint>
            <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_2fr_auto]">
              <FormField label="Type" htmlFor="tk-type">
                <Select value={newTicket.type} onValueChange={(v) => setNewTicket(s => ({ ...s, type: v }))}>
                  <SelectTrigger id="tk-type"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField label="Équipement concerné" htmlFor="tk-eq">
                <Select value={newTicket.equipement || ALL_NONE}
                        onValueChange={(v) => setNewTicket(s => ({ ...s, equipement: v === ALL_NONE ? '' : v }))}>
                  <SelectTrigger id="tk-eq"><SelectValue placeholder="Aucun" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_NONE}>— Aucun —</SelectItem>
                    {equipements.map((eq) => (
                      <SelectItem key={eq.id} value={String(eq.id)}>
                        {(eq.produit_nom ?? 'Produit')} — {eq.numero_serie ?? 'sans n° série'}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <FormField label="Description" htmlFor="tk-desc">
                <Input id="tk-desc" value={newTicket.description}
                       onChange={(e) => setNewTicket(s => ({ ...s, description: e.target.value }))}
                       placeholder="Symptôme / demande" />
              </FormField>
              <Button variant="outline" loading={ticketBusy} onClick={openTicket}>
                Ouvrir un ticket
              </Button>
            </div>
          </Section>

          {/* ── Suivi & maintenance (N10 — hub système installé) ── */}
          <Section
            icon={Wrench}
            title="Suivi & maintenance"
            action={(
              <Button size="sm" variant="outline" onClick={() => navigate('/sav/contrats')}>
                Contrats
              </Button>
            )}
          >
            {contrats.length === 0 ? (
              <Hint>Aucun contrat de maintenance pour ce client.</Hint>
            ) : (
              <MiniTable head={['Périodicité', 'Début', 'Prochaine visite', 'Statut']}>
                {contrats.map((c) => (
                  <tr key={c.id} className="border-t border-border">
                    <td className="px-3 py-2">{c.periodicite_display ?? c.periodicite}</td>
                    <td className="px-3 py-2">{formatDate(c.date_debut)}</td>
                    <td className="px-3 py-2">{formatDate(c.prochaine_visite)}</td>
                    <td className="px-3 py-2">{c.actif ? (c.due ? 'Visite due' : 'Actif') : 'Inactif'}</td>
                  </tr>
                ))}
              </MiniTable>
            )}
            <Hint>Supervision : non configurée (connecteur de monitoring à venir).</Hint>
          </Section>

          {/* ── Mise en service ── */}
          <Section icon={Zap} title="Mise en service">
            {current.date_mise_en_service && (
              <Hint>Mise en service enregistrée le {formatDate(current.date_mise_en_service)}.</Hint>
            )}
            <div className="grid gap-3 sm:grid-cols-3">
              <FormField label="Date de mise en service" htmlFor="mes-date">
                <Input id="mes-date" type="date" value={mes.date_mise_en_service ?? ''}
                       onChange={(e) => setMes(s => ({ ...s, date_mise_en_service: e.target.value }))} />
              </FormField>
              <FormField label="Production test" htmlFor="mes-prod">
                <Input id="mes-prod" type="number" step="any" value={mes.mes_production_test ?? ''}
                       onChange={(e) => setMes(s => ({ ...s, mes_production_test: e.target.value }))} />
              </FormField>
              <FormField label="Tension" htmlFor="mes-tension">
                <Input id="mes-tension" type="number" step="any" value={mes.mes_tension ?? ''}
                       onChange={(e) => setMes(s => ({ ...s, mes_tension: e.target.value }))} />
              </FormField>
            </div>
            <FormField label="Notes / PV" htmlFor="mes-notes">
              <Textarea id="mes-notes" rows={2} value={mes.mes_pv_notes ?? ''}
                        onChange={(e) => setMes(s => ({ ...s, mes_pv_notes: e.target.value }))} />
            </FormField>
            <Button variant="success" loading={mesBusy} onClick={saveMes} className="self-start">
              Enregistrer la mise en service
            </Button>
          </Section>

          {/* ── Historique (chatter) ── */}
          <Section icon={History} title="Historique">
            <div className="flex gap-2">
              <Input placeholder="Écrire une note…"
                     value={noteBody} onChange={(e) => setNoteBody(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); postNote() } }} />
              <Button variant="outline" onClick={postNote}><Send /> Noter</Button>
            </div>
            <div className="flex flex-col gap-2">
              {historique.length === 0 && <Hint>Aucune activité pour le moment.</Hint>}
              {historique.map((a) => (
                <div key={a.id} className="border-b border-border pb-2 text-sm last:border-0">
                  {a.kind === 'note' && (
                    <span>📝 <strong>Note&nbsp;:</strong> {a.body}</span>
                  )}
                  {a.kind === 'creation' && <span>✨ {a.body}</span>}
                  {a.kind === 'modification' && (
                    <span>
                      ✏️ <strong>{a.field_label}&nbsp;:</strong>{' '}
                      {a.old_value} → <strong>{a.new_value}</strong>
                    </span>
                  )}
                  <span className="ml-1 text-xs text-muted-foreground">
                    — par {a.user_nom ?? '?'} · {timeAgo(a.created_at)}
                  </span>
                </div>
              ))}
            </div>
          </Section>
        </div>

        <FormActions>
          {!current.annule && (
            <Button variant="destructive" className="sm:mr-auto"
                    onClick={() => { setAnnulerMotif(''); setAnnulerParcConfirm(false); setAnnulerOpen(true) }}>
              Annuler le chantier
            </Button>
          )}
          {!current.annule && canMoveStatus(current.statut, 'receptionne') && (
            <Button variant="success" loading={receptBusy} onClick={marquerReceptionne}>
              Marquer réceptionné
            </Button>
          )}
          <Button variant="outline" onClick={onClose}>Fermer</Button>
          <Button loading={saving} onClick={handleSave}>
            {saving ? 'Enregistrement…' : 'Mettre à jour'}
          </Button>
        </FormActions>
      </SheetContent>

      {/* Confirmation d'annulation — remplace window.prompt, même appel API. */}
      <AlertDialog open={annulerOpen} onOpenChange={setAnnulerOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Annuler ce chantier ?</AlertDialogTitle>
            <AlertDialogDescription>
              Indiquez éventuellement un motif. Le chantier pourra être réactivé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="annuler-motif">Motif d&apos;annulation (optionnel)</Label>
            <Input id="annuler-motif" value={annulerMotif}
                   onChange={(e) => setAnnulerMotif(e.target.value)}
                   placeholder="Ex. report client" />
          </div>
          {current.est_parc && (
            <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
              <p className="font-semibold text-warning-foreground">
                Ce système est installé et actif au parc.
              </p>
              <p className="text-muted-foreground">
                L&apos;annuler le masquera du parc installé.
              </p>
              <label className="mt-2 flex items-center gap-2">
                <Checkbox checked={annulerParcConfirm}
                          onCheckedChange={(c) => setAnnulerParcConfirm(c === true)} />
                Je confirme retirer ce système du parc.
              </label>
            </div>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>Retour</AlertDialogCancel>
            <AlertDialogAction
              disabled={current.est_parc && !annulerParcConfirm}
              onClick={confirmAnnuler}>
              Annuler le chantier
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── Aperçu in-app d'un document après-vente AVANT téléchargement (L4) ──
          Panneau plein écran réutilisant l'aperçu PDF.js (canvas) du devis :
          même rendu inblocable, même source d'octets que le téléchargement. */}
      {previewDoc && (
        <div className="ldp-overlay" onClick={closePreview}>
          <div className="ldp-panel" onClick={(e) => e.stopPropagation()}>
            <div className="ldp-header">
              <h3 className="ldp-title">
                {previewDoc.title}
                {current.reference && <span className="ldp-ref">{current.reference}</span>}
              </h3>
              <button type="button" className="modal-close" onClick={closePreview} aria-label="Fermer">✕</button>
            </div>
            <div className="ldp-body">
              <div className="ldp-preview">
                <div className="ldp-toolbar">
                  <div className="ldp-format" />
                  <div className="ldp-toolbar-actions">
                    <Button type="button" variant="outline" size="sm" onClick={openPreviewNewTab}>
                      <ExternalLink /> Nouvel onglet
                    </Button>
                    <Button type="button" size="sm"
                            onClick={downloadPreview} loading={previewDownloading} disabled={previewDownloading}>
                      {!previewDownloading && <Download />}
                      {previewDownloading ? '…' : 'Télécharger'}
                    </Button>
                  </div>
                </div>
                <div className="ldp-pdf-area">
                  {previewState === PREVIEW_VIEW.LOADING && (
                    <p className="ldp-pdf-loading">
                      <Spinner /> Chargement de l'aperçu…
                    </p>
                  )}

                  {/* Vrai échec serveur (4xx/5xx) : le PDF n'a pas pu être généré. */}
                  {previewState === PREVIEW_VIEW.ERROR && (
                    <EmptyState
                      role="alert"
                      className="ldp-fallback"
                      icon={TriangleAlert}
                      title="Aperçu indisponible"
                      description="Le serveur n'a pas pu générer ce document. Réessayez."
                      action={(
                        <Button type="button" variant="outline" size="sm" onClick={reloadPreview}>
                          <RotateCw /> Réessayer
                        </Button>
                      )}
                    />
                  )}

                  {/* Repli réseau/timeout : le document reste téléchargeable. */}
                  {previewState === PREVIEW_VIEW.FALLBACK && (
                    <EmptyState
                      className="ldp-fallback"
                      icon={WifiOff}
                      title="Aperçu indisponible"
                      description="Vérifiez votre connexion. Vous pouvez réessayer ou télécharger le document directement."
                      action={(
                        <div className="ldp-fallback-actions">
                          <Button type="button" size="sm"
                                  onClick={downloadPreview} loading={previewDownloading} disabled={previewDownloading}>
                            {!previewDownloading && <Download />}
                            {previewDownloading ? '…' : 'Télécharger'}
                          </Button>
                          <Button type="button" variant="outline" size="sm" onClick={reloadPreview}>
                            <RotateCw /> Réessayer
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
                        onError={() => setPreviewRenderFailed(true)}
                      />
                    </Suspense>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Sheet>
  )
}
