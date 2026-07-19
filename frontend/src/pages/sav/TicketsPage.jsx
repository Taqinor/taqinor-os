import { useEffect, useMemo, useState, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Download, Ticket as TicketIcon, AlertTriangle, RotateCcw, Save, FileText,
  Plus, Trash2, StickyNote, Sparkles, Pencil, Wrench, History, Clock,
  ShieldCheck, ExternalLink, Zap, ChevronRight, ChevronLeft, Link2,
} from 'lucide-react'
import {
  DndContext, PointerSensor, TouchSensor, useDraggable, useDroppable,
  useSensor, useSensors,
} from '@dnd-kit/core'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchTickets, updateTicket } from '../../features/sav/store/ticketsSlice'
import savApi from '../../api/savApi'
import api from '../../api/axios'
import { downloadBlob } from '../../utils/downloadBlob'
import { timeAgo } from '../../lib/format'
import importApi from '../../api/importApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import installationsApi from '../../api/installationsApi'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import TicketSuiviClientPanel from './TicketSuiviClientPanel'
import TicketChecklistPanel from './TicketChecklistPanel'
import TicketAdvancedPanel from './TicketAdvancedPanel'
import { groupTicketsByDate } from './ticketCalendarUtils'
import { buildCopyTSVAction } from '../../ui/datatable/BulkActionBar'
import { telHref } from '../../lib/contactLinks'
import { useIsMobile } from '../../ui/ResponsiveDialog'
import { INTERVENTION_TYPES } from '../../features/installations/statuses'
import {
  EMPTY_TICKET_FILTERS,
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TICKET_STATUS_COLORS,
  TICKET_TYPES,
  TICKET_PRIORITES,
  TICKET_PRIORITE_LABELS,
  SOUS_GARANTIE_OPTIONS,
  SOUS_GARANTIE_LABELS,
  filterTickets,
  sortTickets,
  statusLabel,
  isStatusTransitionAllowed,
  ticketAgeDays,
  ticketSlaLevel,
  statusCounts,
} from '../../features/sav/ticketStatuses'
import {
  TooltipProvider,
  Button,
  Badge,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Spinner,
  Input,
  Textarea,
  Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Segmented,
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  Form, FormSection, FormField, FormActions, useDirtyGuard, confirmLeaveIfDirty,
  DataTable,
  toast,
} from '../../ui'
import { useSavedViews } from '../../hooks/useSavedViews'
import useDocumentTitle from '../../hooks/useDocumentTitle'

const TP_SAVED_VIEWS_KEY = 'taqinor.sav.tickets.savedViews'

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}
const todayISO = () => new Date().toISOString().slice(0, 10)

// L302/L11 — libellés FR des champs pour transformer une erreur DRF brute
// ({champ: [raison]}) en message lisible « Échec : {champ} — {raison} », au lieu
// d'un JSON.stringify illisible.
const FIELD_LABELS_FR = {
  statut: 'Statut', type: 'Type', priorite: 'Priorité',
  description: 'Description', sous_garantie: 'Sous garantie',
  equipement: 'Équipement', technicien_responsable: 'Technicien responsable',
  date_resolution: 'Date de résolution', cout: 'Coût',
  detail: 'Erreur', non_field_errors: 'Erreur', body: 'Note', motif: 'Motif',
  produit: 'Produit', quantite: 'Quantité',
}
function frError(err, fallback = 'Action impossible.') {
  if (!err) return fallback
  const data = err?.response?.data ?? err
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const parts = []
    for (const [field, raison] of Object.entries(data)) {
      const label = FIELD_LABELS_FR[field] ?? field
      const txt = Array.isArray(raison) ? raison.join(' ') : String(raison)
      parts.push(field === 'detail' || field === 'non_field_errors'
        ? txt : `Échec : ${label} — ${txt}`)
    }
    if (parts.length) return parts.join(' · ')
  }
  return fallback
}

// L298 — niveau SLA → présentation (badge ton + libellé « ouvert depuis X j »).
const SLA_TONES = { ok: 'neutral', warn: 'warning', late: 'danger' }

// VX31 — boîte de réception SAV : sur grand viewport (≥1280px, xl Tailwind),
// le détail du ticket vit dans un panneau latéral PERSISTANT à côté de la liste
// (pattern inbox Linear/Plain) au lieu du tiroir `Sheet` plein-tiroir. Sous ce
// seuil (tablette/mobile), le `Sheet` reste le fallback inchangé. On réutilise
// le hook media-query de `ResponsiveDialog` (M158) avec une requête inversée —
// « pas mobile » devient ici « assez large pour le split-view ».
const DESKTOP_SPLIT_QUERY = '(min-width: 1280px)'
function useIsDesktopSplit() {
  return useIsMobile(DESKTOP_SPLIT_QUERY)
}

// L313 — section repliable (usage terrain/mobile). Utilise <details> natif :
// ouverte par défaut, le résumé fait office d'en-tête d'accordéon cliquable.
function CollapsibleSection({ icon: Icon, title, children }) {
  return (
    <details open className="group flex flex-col gap-3 [&[open]>summary>svg.chevron]:rotate-90">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-display text-base font-semibold text-foreground">
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
        <span className="flex-1">{title}</span>
        <ChevronRight className="chevron size-4 rotate-0 text-muted-foreground transition-transform" aria-hidden="true" />
      </summary>
      <div className="flex flex-col gap-3 pt-2">{children}</div>
    </details>
  )
}

// Statut de ticket → ton StatusPill (cycle de vie ticketStatuses.js : couche
// indépendante du funnel lead et des statuts de document). La couleur n'est
// jamais le seul signal — le libellé reste explicite.
const TICKET_STATUS_TONES = {
  nouveau: 'neutral',
  planifie: 'info',
  en_cours: 'warning',
  resolu: 'success',
  cloture: 'success',
}
export function StatutPill({ statut }) {
  return <StatusPill tone={TICKET_STATUS_TONES[statut] ?? 'neutral'} label={statusLabel(statut)} />
}

const GARANTIE_TONES = { oui: 'success', non: 'danger', a_determiner: 'neutral' }
function GarantieIndicator({ value }) {
  return (
    <Badge tone={GARANTIE_TONES[value] ?? 'neutral'}>
      Sous garantie : {SOUS_GARANTIE_LABELS[value] ?? value}
    </Badge>
  )
}

const PRIORITE_TONES = { basse: 'neutral', normale: 'info', haute: 'warning', urgente: 'danger' }
export function PrioriteBadge({ value }) {
  return <Badge tone={PRIORITE_TONES[value] ?? 'neutral'}>{TICKET_PRIORITE_LABELS[value] ?? value}</Badge>
}

// L298/L6 — badge SLA/âge des tickets ouverts (calculé à la lecture, sans
// scheduler). Couleur escaladée pour les ouverts en retard. Rien sur les autres.
export function TicketSlaBadge({ ticket }) {
  const age = ticketAgeDays(ticket)
  const level = ticketSlaLevel(ticket)
  if (age == null
      || !['nouveau', 'planifie', 'en_cours'].includes(ticket?.statut)
      || ticket?.annule) return null
  return (
    <Badge tone={SLA_TONES[level]}>
      <Clock className="size-3" aria-hidden="true" /> ouvert depuis {age} j
    </Badge>
  )
}

export function TicketDetail({ ticket, onClose, onSaved }) {
  const dispatch = useDispatch()
  const allTickets = useSelector((s) => s.tickets.items)
  const id = ticket.id
  const [current, setCurrent] = useState(ticket)
  const F = (k, d = '') => current?.[k] ?? d

  // VX216(b) — l'intervention qui a RÉSOLU ce ticket : la plus récemment
  // réalisée parmi `current.interventions` (TicketInterventionSerializer,
  // déjà exposé par l'API — aucun champ backend manquant). N'affiche rien
  // pour un ticket jamais résolu par une intervention (résolution à distance,
  // manuelle...).
  const resolvingIntervention = useMemo(() => {
    const list = (current.interventions ?? []).filter((iv) => iv.date_realisee)
    if (list.length === 0) return null
    return list.reduce((latest, iv) =>
      (!latest || iv.date_realisee > latest.date_realisee ? iv : latest), null)
  }, [current.interventions])

  const initialFields = useMemo(() => ({
    statut: current.statut ?? 'nouveau',
    type: current.type ?? 'correctif',
    priorite: current.priorite ?? 'normale',
    description: current.description ?? '',
    sous_garantie: current.sous_garantie ?? 'a_determiner',
    equipement: current.equipement ?? '',
    technicien_responsable: current.technicien_responsable ?? '',
    date_resolution: current.date_resolution ?? '',
    cout: current.cout ?? '',
  }), [current])

  const [fields, setFields] = useState(initialFields)
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  const dirty = useMemo(
    () => Object.keys(initialFields).some((k) => String(fields[k] ?? '') !== String(initialFields[k] ?? '')),
    [fields, initialFields],
  )
  useDirtyGuard(dirty)

  const [equipements, setEquipements] = useState([])
  const [users, setUsers] = useState([])
  const [interventions, setInterventions] = useState([])
  // L316 — date prévue pré-remplie à aujourd'hui (éditable).
  const [interv, setInterv] = useState(
    { type_intervention: 'depannage', date_prevue: todayISO(), compte_rendu: '' })
  const [intervBusy, setIntervBusy] = useState(false)
  // L303/L11 — surface les échecs autrefois silencieux (note/intervention/pièce).
  const [actionError, setActionError] = useState(null)

  const [historique, setHistorique] = useState([])
  const [noteBody, setNoteBody] = useState('')

  // N46 — pièces consommées (le stock peut être décrémenté).
  const [pieces, setPieces] = useState([])
  const [produits, setProduits] = useState([])
  const [pieceForm, setPieceForm] = useState(
    { produit: '', quantite: '1', decrement: false })
  const [pieceBusy, setPieceBusy] = useState(false)
  const [annulerOpen, setAnnulerOpen] = useState(false)
  const [motif, setMotif] = useState('')
  const [confirmVide, setConfirmVide] = useState(false) // L300 — confirmation motif vide

  const loadPieces = () => {
    savApi.getTicketPieces(id).then((r) => setPieces(r.data)).catch(() => {})
  }

  const reloadAll = async () => {
    try {
      const r = await savApi.getTicket(id)
      setCurrent(r.data)
    } catch { /* silencieux */ }
  }
  const loadHistorique = () => {
    savApi.getTicketHistorique(id).then((r) => setHistorique(r.data)).catch(() => {})
  }
  const loadInterventions = () => {
    installationsApi.getInterventions({ ticket: id })
      .then((r) => setInterventions(r.data?.results ?? r.data ?? [])).catch(() => {})
  }

  useEffect(() => {
    loadHistorique()
    loadInterventions()
    loadPieces()
    api.get('/stock/produits/')
      .then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
    // Équipements du chantier concerné (pour lier l'équipement précis).
    if (current.installation) {
      savApi.getEquipements({ installation: current.installation })
        .then((r) => setEquipements(r.data?.results ?? r.data ?? [])).catch(() => {})
    }
    // Liste des techniciens — best effort (réservé admin) ; sinon dropdown vide.
    api.get('/users/').then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // L296 — saut de statut hors ordre détecté (pour avertir avant submit).
  const statutSautHorsOrdre = !isStatusTransitionAllowed(current.statut, fields.statut)

  // YDOCF1 — `statut` par action guardée dédiée (POST) : plus de PATCH
  // direct. On mappe le statut cible choisi dans le formulaire vers l'action
  // serveur correspondante ; une transition hors machine d'états renvoie 400
  // (message clair remonté par `frError`).
  const STATUT_ACTION = {
    // XSAV11 — « nouveau » est une RÉOUVERTURE gardée (pas un PATCH direct),
    // sinon le choix « Nouveau » était un no-op silencieux qui laissait l'UI
    // afficher un statut périmé. Le backend refuse (400) une transition
    // illégale (ex. en_cours → nouveau), remontée dans setSaveError.
    nouveau: savApi.reouvrirTicket,
    planifie: savApi.planifierTicket,
    en_cours: savApi.demarrerTicket,
    resolu: savApi.resoudreTicket,
    cloture: savApi.cloturerTicket,
  }

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      const data = {
        type: fields.type,
        priorite: fields.priorite,
        description: nullable(fields.description),
        sous_garantie: fields.sous_garantie,
        equipement: fields.equipement === '' ? null : fields.equipement,
        technicien_responsable: fields.technicien_responsable === '' ? null : fields.technicien_responsable,
        cout: nullable(fields.cout),
      }
      // date_resolution reste PATCHable directement (pas de action dédiée) ;
      // auto-tamponnée si le statut cible est resolu/cloture et qu'elle est
      // encore vide (comportement inchangé).
      let dateResolution = fields.date_resolution
      if (!dateResolution && ['resolu', 'cloture'].includes(fields.statut)) {
        dateResolution = todayISO()
      }
      data.date_resolution = nullable(dateResolution)

      let updated = await dispatch(updateTicket({ id, data })).unwrap()
      if (fields.statut && fields.statut !== current.statut) {
        const action = STATUT_ACTION[fields.statut]
        if (action) {
          const r = await action(id)
          updated = r.data
        }
      }
      setCurrent(updated)
      loadHistorique()
      toast.success('Ticket mis à jour')
      onSaved?.()
    } catch (err) {
      setSaveError(frError(err, 'Échec de la mise à jour.'))
    } finally {
      setSaving(false)
    }
  }

  const postNote = async () => {
    const body = noteBody.trim()
    if (!body) return
    setActionError(null)
    try {
      const r = await savApi.noterTicket(id, body)
      setHistorique((h) => [r.data, ...h])
      setNoteBody('')
    } catch (err) { setActionError(frError(err, "Échec de l'ajout de la note.")) }
  }

  // XSAV23 — insertion d'une réponse type (macro) depuis TicketAdvancedPanel.
  const insererMacro = async (reponseTypeId) => {
    setActionError(null)
    try {
      const r = await savApi.noterTicketAvecMacro(id, reponseTypeId)
      setHistorique((h) => [r.data, ...h])
      toast.success('Réponse type insérée')
      await reloadAll()
    } catch (err) { setActionError(frError(err, "Échec de l'insertion de la réponse type.")) }
  }

  // XSAV5 — pause/reprise SLA « en attente client ».
  const [attenteBusy, setAttenteBusy] = useState(false)
  const mettreEnAttenteClient = async () => {
    setAttenteBusy(true)
    try {
      const r = await savApi.attenteClientTicket(id)
      setCurrent(r.data)
      toast.success('Mis en attente client')
    } catch (err) { setActionError(frError(err, 'Impossible de mettre en attente.')) }
    finally { setAttenteBusy(false) }
  }
  const reprendreApresAttente = async () => {
    setAttenteBusy(true)
    try {
      const r = await savApi.reprendreTicket(id)
      setCurrent(r.data)
      toast.success('Reprise après attente client')
    } catch (err) { setActionError(frError(err, 'Impossible de reprendre.')) }
    finally { setAttenteBusy(false) }
  }

  const addIntervention = async () => {
    if (!interv.type_intervention) return
    setIntervBusy(true)
    setActionError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      await installationsApi.createIntervention({
        installation: current.installation,
        ticket: id,
        type_intervention: interv.type_intervention,
        date_prevue: nullable(interv.date_prevue),
        compte_rendu: nullable(interv.compte_rendu),
      })
      setInterv({ type_intervention: 'depannage', date_prevue: todayISO(), compte_rendu: '' })
      loadInterventions()
      loadHistorique()
    } catch (err) {
      setActionError(frError(err, "Échec de l'ajout de l'intervention."))
    } finally { setIntervBusy(false) }
  }

  // WIR29 — bouton « Planifier en un clic » : crée l'intervention pré-remplie
  // via `POST tickets/{id}/planifier-intervention/` (apps.installations.services,
  // frontière cross-app déjà respectée côté backend) et passe le ticket en
  // PLANIFIE si besoin. Le formulaire manuel ci-dessous reste disponible en option.
  const [planBusy, setPlanBusy] = useState(false)
  const planifierUnClic = async () => {
    setPlanBusy(true)
    setActionError(null)
    try {
      const r = await api.post(`/sav/tickets/${id}/planifier-intervention/`)
      loadInterventions()
      loadHistorique()
      await reloadAll()
      toast.success(`Intervention #${r.data?.intervention_id} planifiée`)
      onSaved?.()
    } catch (err) {
      setActionError(frError(err, 'Échec de la planification en un clic.'))
    } finally { setPlanBusy(false) }
  }

  const addPiece = async () => {
    if (!pieceForm.produit) return
    // L309/L7 — garde anti-survente : si on décrémente le stock et que la qté
    // demandée dépasse le stock disponible, avertir avant le POST.
    if (pieceForm.decrement) {
      const pr = produits.find((p) => String(p.id) === String(pieceForm.produit))
      const dispo = Number(pr?.quantite_stock ?? 0)
      const demande = Number(pieceForm.quantite || '1')
      if (Number.isFinite(demande) && demande > dispo) {
        setActionError(
          `Stock insuffisant : ${dispo} en stock pour ${demande} demandé(s).`)
        return
      }
    }
    setPieceBusy(true)
    setActionError(null)
    try {
      await savApi.addTicketPiece(id, {
        produit: pieceForm.produit,
        quantite: pieceForm.quantite || '1',
        decrement: pieceForm.decrement,
      })
      setPieceForm({ produit: '', quantite: '1', decrement: false })
      loadPieces()
      loadHistorique()
    } catch (err) {
      setActionError(frError(err, "Échec de l'ajout de la pièce."))
    } finally { setPieceBusy(false) }
  }
  const removePiece = async (pieceId) => {
    setActionError(null)
    try {
      await savApi.removeTicketPiece(id, pieceId)
      loadPieces()
      loadHistorique()
    } catch (err) { setActionError(frError(err, 'Échec du retrait de la pièce.')) }
  }

  const annuler = async () => {
    setActionError(null)
    try {
      await savApi.annulerTicket(id, motif)
      setAnnulerOpen(false)
      setMotif('')
      await reloadAll()
      loadHistorique()
      onSaved?.()
    } catch (err) { setActionError(frError(err, "Échec de l'annulation.")) }
  }
  const reactiver = async () => {
    setActionError(null)
    try {
      await savApi.reactiverTicket(id)
      await reloadAll()
      loadHistorique()
      onSaved?.()
    } catch (err) { setActionError(frError(err, 'Échec de la réactivation.')) }
  }
  const telechargerRapport = async () => {
    // L314/L11 — échec PDF affiché via le bloc d'erreur in-modal standard.
    setActionError(null)
    try {
      const r = await savApi.rapportPdf(id)
      downloadBlob(r.data, `rapport-intervention-${current.reference || id}.pdf`)
    } catch (err) {
      setActionError(frError(err, 'Rapport indisponible.'))
    }
  }

  // ── XSAV3/XFSM1/XCTR4 — devis de réparation / facturation depuis le ticket ──
  const [devisBusy, setDevisBusy] = useState(false)
  const [factureBusy, setFactureBusy] = useState(false)
  const creerDevis = async () => {
    setActionError(null)
    setDevisBusy(true)
    try {
      const r = await savApi.creerDevisTicket(id)
      toast.success(`Devis ${r.data?.devis_reference ?? ''} créé (brouillon)`)
      setCurrent((c) => ({ ...c, devis_id_ext: r.data?.devis_id }))
      loadHistorique()
      onSaved?.()
    } catch (err) {
      setActionError(frError(err, 'Impossible de créer le devis.'))
    } finally { setDevisBusy(false) }
  }
  const genererFacture = async () => {
    setActionError(null)
    setFactureBusy(true)
    try {
      const r = await savApi.genererFactureTicket(id)
      toast.success(`Facture ${r.data?.facture_reference ?? ''} générée`)
      setCurrent((c) => ({ ...c, facture_id_ext: r.data?.facture_id }))
      loadHistorique()
      onSaved?.()
    } catch (err) {
      setActionError(frError(err, 'Impossible de générer la facture.'))
    } finally { setFactureBusy(false) }
  }
  const facturer = async () => {
    setActionError(null)
    setFactureBusy(true)
    try {
      const r = await savApi.facturerTicket(id)
      toast.success(`Facture ${r.data?.facture_reference ?? ''} générée (${r.data?.couverture ?? ''})`)
      setCurrent((c) => ({ ...c, facture_id_ext: r.data?.facture_id }))
      loadHistorique()
      onSaved?.()
    } catch (err) {
      setActionError(frError(err, 'Impossible de facturer ce ticket.'))
    } finally { setFactureBusy(false) }
  }

  // L308 — options de technicien. Si /users/ renvoie vide (endpoint admin),
  // on alimente le dropdown depuis les techniciens déjà assignés sur les
  // tickets (id + nom) afin que les non-admins puissent quand même assigner.
  const technicienOptions = useMemo(() => {
    if (users.length) return users.map((u) => ({ id: u.id, label: u.username }))
    const seen = new Map()
    for (const t of allTickets ?? []) {
      if (t.technicien_responsable && t.technicien_nom
          && !seen.has(String(t.technicien_responsable))) {
        seen.set(String(t.technicien_responsable),
          { id: t.technicien_responsable, label: t.technicien_nom })
      }
    }
    // Garder l'assigné courant même s'il n'apparaît pas ailleurs.
    if (current.technicien_responsable && current.technicien_nom
        && !seen.has(String(current.technicien_responsable))) {
      seen.set(String(current.technicien_responsable),
        { id: current.technicien_responsable, label: current.technicien_nom })
    }
    return [...seen.values()]
  }, [users, allTickets, current.technicien_responsable, current.technicien_nom])

  const linkedEquip = equipements.find((e) => String(e.id) === String(fields.equipement))
  // L307/L1 — quand un équipement est lié et porte une date de fin de garantie,
  // la garantie effective est CALCULÉE. On la calcule à partir de l'équipement
  // sélectionné pour griser et remplir le champ manuel à la bonne valeur.
  const garantieCalculee = useMemo(() => {
    if (!fields.equipement || !linkedEquip) return null
    if (!linkedEquip.date_fin_garantie) return null
    const fin = new Date(`${linkedEquip.date_fin_garantie}T00:00:00`)
    return new Date() < fin ? 'oui' : 'non'
  }, [fields.equipement, linkedEquip])

  // VX31 — sur grand viewport, le panneau est un aside PERSISTANT à côté de la
  // liste (jamais un tiroir plein-tiroir qui masque la DataTable) ; sous le
  // seuil desktop, le `Sheet` plein-tiroir reste le fallback mobile/tablette
  // inchangé (mêmes CollapsibleSection, même contenu — seule l'enveloppe change).
  const isDesktopSplit = useIsDesktopSplit()

  const titleContent = (
    <>
      Ticket SAV — {current.reference ?? ''}
      <StatutPill statut={current.statut} />
      {current.annule && <Badge tone="danger">Annulé</Badge>}
      <TicketSlaBadge ticket={current} />
    </>
  )

  // L299/L1 — compte-à-rebours de garantie de l'équipement lié.
  const headerContent = current.equipement_fin_garantie ? (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <ShieldCheck className="size-3.5" aria-hidden="true" />
      {(() => {
        const fin = new Date(`${current.equipement_fin_garantie}T00:00:00`)
        const jours = Math.round((fin - new Date()) / 86400000)
        return jours >= 0
          ? `Garantie jusqu'au ${formatDateFR(current.equipement_fin_garantie)} (${jours} j restant${jours > 1 ? 's' : ''})`
          : `Garantie expirée le ${formatDateFR(current.equipement_fin_garantie)} (${-jours} j)`
      })()}
    </span>
  ) : null

  const bodyContent = (
    <>
        {current.annule && (
          <div role="alert"
               className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <span>
              <strong>Ticket annulé.</strong>
              {current.motif_annulation ? ` Motif : ${current.motif_annulation}` : ''}
            </span>
            <Button size="sm" variant="outline" onClick={reactiver}>Réactiver</Button>
          </div>
        )}

        <Form onSubmit={(e) => { e.preventDefault(); save() }} className="gap-6">
          {/* ── Infos ── */}
          <FormSection title="Ticket">
            <FormField label="Client">
              <div className="flex items-center gap-2">
                <Input value={current.client_nom ?? '—'} readOnly />
                {telHref(current.client_telephone) && (
                  <a href={telHref(current.client_telephone)} title="Appeler"
                     className="link-blue whitespace-nowrap">☎ {current.client_telephone}</a>
                )}
              </div>
            </FormField>
            <FormField label="Chantier">
              <div className="flex items-center gap-2">
                <Input value={current.installation_reference ?? '—'} readOnly />
                {current.installation && (
                  // VX216(b) — L312 pointait vers la page générique des
                  // chantiers ; deep-link réel vers CE chantier (même patron
                  // `?id=` que VX79/InstallationsPage.jsx).
                  <Button asChild variant="ghost" size="sm" title="Ouvrir ce chantier">
                    <Link to={`/chantiers?id=${current.installation}`}><ExternalLink /></Link>
                  </Button>
                )}
              </div>
            </FormField>
            {/* VX216(b) — YSERV2 avance automatiquement un ticket vers RESOLU
                quand son intervention liée se termine, mais jusqu'ici le
                ticket ne montrait jamais QUELLE intervention l'a résolu.
                `current.interventions` (TicketInterventionSerializer) porte
                déjà date_realisee/technicien_nom — la plus récente réalisée
                est la résolvante. */}
            {resolvingIntervention && (
              <FormField label="Résolu par">
                <div className="flex items-center gap-2">
                  <Input
                    value={
                      `Intervention #${resolvingIntervention.id} du `
                      + `${formatDateFR(resolvingIntervention.date_realisee)} par `
                      + `${resolvingIntervention.technicien_nom ?? '—'}`
                    }
                    readOnly
                  />
                  {current.installation && (
                    <Button asChild variant="ghost" size="sm" title="Ouvrir le chantier de cette intervention">
                      <Link to={`/chantiers?id=${current.installation}`}><ExternalLink /></Link>
                    </Button>
                  )}
                </div>
              </FormField>
            )}
            <FormField label="Ouvert le">
              <Input value={formatDateFR(current.date_ouverture)} readOnly />
            </FormField>
            <FormField label="Statut">
              <Select value={fields.statut} onValueChange={(v) => set('statut', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TICKET_STATUSES.map((k) => {
                    // L296 — signaler les sauts hors ordre depuis le statut actuel.
                    const horsOrdre = !isStatusTransitionAllowed(current.statut, k)
                    return (
                      <SelectItem key={k} value={k}>
                        {TICKET_STATUS_LABELS[k]}{horsOrdre ? ' (saut d’étape)' : ''}
                      </SelectItem>
                    )
                  })}
                </SelectContent>
              </Select>
              {statutSautHorsOrdre && (
                <p className="mt-1 flex items-center gap-1 text-xs text-warning">
                  <AlertTriangle className="size-3" aria-hidden="true" />
                  Saut d&apos;étape : passez par les statuts intermédiaires (ex. En cours).
                </p>
              )}
            </FormField>
            <FormField label="Type">
              <Select value={fields.type} onValueChange={(v) => set('type', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Priorité">
              <Select value={fields.priorite} onValueChange={(v) => set('priorite', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TICKET_PRIORITES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Description" fullWidth>
              <Textarea rows={2} value={fields.description ?? ''}
                        onChange={(e) => set('description', e.target.value)} />
            </FormField>
          </FormSection>

          {/* ── Équipement & garantie ── */}
          <FormSection title="Équipement concerné"
                       description="La garantie effective est calculée automatiquement à partir de l'équipement lié.">
            <FormField label="Équipement (du chantier)" fullWidth>
              <Select value={fields.equipement ? String(fields.equipement) : '__none'}
                      onValueChange={(v) => set('equipement', v === '__none' ? '' : v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Aucun (garantie manuelle) —</SelectItem>
                  {equipements.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {(e.produit_nom ?? 'Produit')} — {e.numero_serie ?? 'sans n° série'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField
              label={fields.equipement
                ? 'Sous garantie (calculée — verrouillée)'
                : 'Sous garantie (si aucun équipement)'}
              fullWidth
            >
              <Select
                value={fields.equipement ? (garantieCalculee || fields.sous_garantie) : fields.sous_garantie}
                onValueChange={(v) => set('sous_garantie', v)}
                disabled={!!fields.equipement}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SOUS_GARANTIE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
              <GarantieIndicator value={current.sous_garantie_effectif} />
              {linkedEquip && (
                <span className="text-xs text-muted-foreground">
                  {linkedEquip.date_fin_garantie
                    ? `Fin de garantie de l'équipement : ${formatDateFR(linkedEquip.date_fin_garantie)} — calculée automatiquement.`
                    : "Garantie de l'équipement non renseignée."}
                </span>
              )}
              {current.equipement && (
                // L312 — lien vers la page des équipements (parc).
                <Button asChild variant="ghost" size="sm" title="Ouvrir le parc d'équipements">
                  <Link to="/equipements"><ExternalLink /> Équipement</Link>
                </Button>
              )}
            </div>
          </FormSection>

          {/* ── Suivi ── */}
          <FormSection title="Suivi">
            <FormField label="Technicien responsable">
              <Select value={fields.technicien_responsable ? String(fields.technicien_responsable) : '__none'}
                      onValueChange={(v) => set('technicien_responsable', v === '__none' ? '' : v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Non assigné —</SelectItem>
                  {technicienOptions.map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>{u.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Date de résolution">
              <Input type="date" value={fields.date_resolution ?? ''}
                     onChange={(e) => set('date_resolution', e.target.value)} />
            </FormField>
            <FormField label="Coût (interne)">
              <Input type="number" step="any" value={fields.cout ?? ''}
                     onChange={(e) => set('cout', e.target.value)} />
            </FormField>
            {saveError && (
              <div role="alert" className="sm:col-span-2 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
                <span className="break-all">{saveError}</span>
              </div>
            )}
          </FormSection>
        </Form>

        {/* ── Pièces jointes ── */}
        <section className="flex flex-col gap-3">
          <AttachmentsPanel model="sav.ticket" id={id} />
        </section>

        {/* ── WR11/FG81+FG86 — SLA première réponse + lien de suivi client ── */}
        <CollapsibleSection icon={Clock} title="Suivi client & SLA">
          <TicketSuiviClientPanel
            ticket={current}
            onUpdated={(t) => { setCurrent(t); loadHistorique(); onSaved?.() }}
          />
          {/* XSAV5 — pause/reprise SLA « en attente client ». */}
          <div className="flex items-center gap-2">
            {current.en_attente_client ? (
              <Button type="button" size="sm" variant="outline" loading={attenteBusy} onClick={reprendreApresAttente}>
                Reprendre après attente client
              </Button>
            ) : (
              <Button type="button" size="sm" variant="outline" loading={attenteBusy} onClick={mettreEnAttenteClient}>
                Mettre en attente client
              </Button>
            )}
          </div>
        </CollapsibleSection>

        {/* ── WR11/FG82 — checklist de visite de maintenance ── */}
        <CollapsibleSection icon={ShieldCheck} title="Checklist de maintenance">
          <TicketChecklistPanel ticketId={id} />
        </CollapsibleSection>

        {/* ── XSAV12/21/27/28, ZSAV8/9 — actions avancées (fusion, similaires,
             triage IA, macros, prêts équipement, conversion lead, suivre). ── */}
        <CollapsibleSection icon={Sparkles} title="Actions avancées">
          <TicketAdvancedPanel ticket={current} onNoteInsert={insererMacro} />
        </CollapsibleSection>

        {/* ── Interventions (L313 — repliable) ── */}
        <CollapsibleSection icon={Wrench} title="Interventions">
          {/* WIR29 — création one-click depuis le ticket ; formulaire manuel conservé en option ci-dessous. */}
          <div>
            <Button type="button" variant="outline" size="sm"
                    loading={planBusy} onClick={planifierUnClic}>
              <Zap /> Planifier une intervention en un clic
            </Button>
          </div>
          {interventions.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune intervention rattachée.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {interventions.map((iv) => (
                <li key={iv.id} className="rounded-lg border border-border bg-card p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">{iv.type_intervention_display ?? iv.type_intervention}</span>
                    <span className="text-xs text-muted-foreground">
                      Prévue {formatDateFR(iv.date_prevue)} · Réalisée {formatDateFR(iv.date_realisee)}
                    </span>
                  </div>
                  <p className="mt-1 text-muted-foreground">
                    {iv.technicien_nom ?? '—'}{iv.compte_rendu ? ` — ${iv.compte_rendu}` : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Type">
              <Select value={interv.type_intervention}
                      onValueChange={(v) => setInterv((s) => ({ ...s, type_intervention: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {INTERVENTION_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Date prévue">
              <Input type="date" value={interv.date_prevue}
                     onChange={(e) => setInterv((s) => ({ ...s, date_prevue: e.target.value }))} />
            </FormField>
            <FormField label="Compte rendu" fullWidth>
              <Input value={interv.compte_rendu}
                     onChange={(e) => setInterv((s) => ({ ...s, compte_rendu: e.target.value }))} />
            </FormField>
          </div>
          <div>
            <Button type="button" variant="outline" size="sm"
                    loading={intervBusy} disabled={!interv.type_intervention} onClick={addIntervention}>
              <Plus /> Ajouter une intervention
            </Button>
          </div>
        </CollapsibleSection>

        {/* ── Pièces consommées (N46) — L313 repliable ── */}
        <CollapsibleSection icon={Wrench} title="Pièces consommées">
          {pieces.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune pièce enregistrée.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
              {pieces.map((p) => (
                <li key={p.id} className="flex items-center gap-2 p-2.5 text-sm">
                  <span className="flex-1">
                    {p.produit_nom}{p.produit_marque ? ` — ${p.produit_marque}` : ''} × {p.quantite}
                    {p.stock_decremente && <Badge tone="info" className="ml-2">stock −</Badge>}
                  </span>
                  <Button type="button" variant="ghost" size="sm" onClick={() => removePiece(p.id)}>
                    <Trash2 /> Retirer
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <div className="grid items-end gap-3 sm:grid-cols-[2fr_auto_auto]">
            <FormField label="Produit">
              <Select value={pieceForm.produit ? String(pieceForm.produit) : '__none'}
                      onValueChange={(v) => setPieceForm((s) => ({ ...s, produit: v === '__none' ? '' : v }))}>
                <SelectTrigger><SelectValue placeholder="— Produit —" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">— Produit —</SelectItem>
                  {produits.map((pr) => (
                    <SelectItem key={pr.id} value={String(pr.id)}>
                      {pr.nom}{pr.sku ? ` (${pr.sku})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Qté" className="w-24">
              <Input type="number" min="0" step="any" value={pieceForm.quantite}
                     onChange={(e) => setPieceForm((s) => ({ ...s, quantite: e.target.value }))} />
            </FormField>
            <label className="flex h-[var(--control-h)] items-center gap-2 text-sm">
              <Checkbox checked={pieceForm.decrement}
                        onCheckedChange={(v) => setPieceForm((s) => ({ ...s, decrement: !!v }))} />
              Décrémenter le stock
            </label>
          </div>
          <div>
            <Button type="button" variant="outline" size="sm"
                    loading={pieceBusy} disabled={!pieceForm.produit} onClick={addPiece}>
              <Plus /> Ajouter la pièce
            </Button>
          </div>
        </CollapsibleSection>

        {/* ── Historique (chatter) — L313 repliable ── */}
        <CollapsibleSection icon={History} title="Historique">
          <div className="flex gap-2">
            <Input placeholder="Écrire une note…" value={noteBody}
                   onChange={(e) => setNoteBody(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); postNote() } }} />
            <Button type="button" variant="outline" onClick={postNote}>Noter</Button>
          </div>
          <div className="flex flex-col gap-2">
            {historique.length === 0 && <p className="text-sm text-muted-foreground">Aucune activité pour le moment.</p>}
            {historique.map((a) => (
              <div key={a.id} className="rounded-lg border border-border bg-card p-2.5 text-sm">
                {a.kind === 'note' && (
                  <span className="flex items-start gap-1.5">
                    <StickyNote className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                    <span><strong>Note :</strong> {a.body}</span>
                  </span>
                )}
                {a.kind === 'creation' && (
                  <span className="flex items-start gap-1.5">
                    <Sparkles className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" /> {a.body}
                  </span>
                )}
                {a.kind === 'modification' && (
                  <span className="flex items-start gap-1.5">
                    <Pencil className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                    <span><strong>{a.field_label} :</strong> {a.old_value} → <strong>{a.new_value}</strong></span>
                  </span>
                )}
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  — par {a.user_nom ?? '?'} · {timeAgo(a.created_at)}
                </span>
              </div>
            ))}
          </div>
        </CollapsibleSection>

        {/* L303/L311/L314/L11 — échecs d'action (note/intervention/pièce/PDF)
            surfacés ici plutôt qu'avalés silencieusement. */}
        {actionError && (
          <div role="alert"
               className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            <span>{actionError}</span>
          </div>
        )}

        <FormActions sticky={false}>
          {!current.annule && (
            <Button type="button" variant="destructive" className="mr-auto" onClick={() => setAnnulerOpen(true)}>
              <Trash2 /> Annuler le ticket
            </Button>
          )}
          {/* XSAV3 — devis de réparation hors garantie (refusé côté serveur
              si le ticket est sous garantie calculée). */}
          {current.sous_garantie_effectif !== 'oui' && (
            current.devis_id_ext ? (
              <Badge tone="success">Devis créé</Badge>
            ) : (
              <Button type="button" variant="outline" loading={devisBusy} onClick={creerDevis}>
                <FileText /> Créer un devis
              </Button>
            )
          )}
          {/* XCTR4 — facturation routée par couverture (garantie/contrat/
              facturable) une fois posée ou calculable ; XFSM1 en repli
              générique sinon. Idempotent (facture_id_ext déjà posé). */}
          {current.facture_id_ext ? (
            <Badge tone="success">Facture générée</Badge>
          ) : current.couverture && current.couverture !== 'a_determiner' ? (
            <Button type="button" variant="outline" loading={factureBusy} onClick={facturer}>
              <FileText /> Facturer
            </Button>
          ) : (
            <Button type="button" variant="outline" loading={factureBusy} onClick={genererFacture}>
              <FileText /> Générer facture
            </Button>
          )}
          <Button type="button" variant="outline" onClick={telechargerRapport}>
            <FileText /> Rapport d'intervention (PDF)
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          <Button type="button" loading={saving} onClick={save}><Save /> Mettre à jour</Button>
        </FormActions>

        <AlertDialog open={annulerOpen} onOpenChange={setAnnulerOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Annuler ce ticket ?</AlertDialogTitle>
              <AlertDialogDescription>
                Le ticket sera marqué annulé (avec motif). Vous pourrez le réactiver ensuite.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="grid gap-1.5">
              <label htmlFor="motif-annulation" className="text-sm font-medium">Motif d'annulation</label>
              <Textarea id="motif-annulation" rows={2} value={motif}
                        onChange={(e) => { setMotif(e.target.value); setConfirmVide(false) }}
                        placeholder="Motif (recommandé)…" />
              {/* L300 — motif vide : demander confirmation au lieu d'accepter en silence. */}
              {confirmVide && (
                <p className="flex items-center gap-1 text-xs text-warning">
                  <AlertTriangle className="size-3" aria-hidden="true" />
                  Aucun motif saisi. Cliquez de nouveau pour annuler sans motif.
                </p>
              )}
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setConfirmVide(false)}>Revenir</AlertDialogCancel>
              <AlertDialogAction onClick={(e) => {
                if (!motif.trim() && !confirmVide) { e.preventDefault(); setConfirmVide(true); return }
                annuler()
              }}>Annuler le ticket</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
    </>
  )

  // ── Desktop (≥1280px) : panneau latéral persistant à côté de la liste. ──
  if (isDesktopSplit) {
    return (
      <aside
        aria-label={`Détail du ticket ${current.reference ?? ''}`}
        className="flex w-[26rem] shrink-0 flex-col gap-4 overflow-y-auto rounded-xl border border-border bg-card p-4 xl:sticky xl:top-1"
      >
        <div className="flex flex-col gap-1.5 border-b border-border pb-3">
          <div className="flex flex-wrap items-center gap-2 font-display text-lg font-semibold">
            {titleContent}
          </div>
          <p className="text-sm text-muted-foreground">
            Suivi, équipement, interventions, pièces et historique du ticket.
          </p>
          {headerContent}
        </div>
        {bodyContent}
      </aside>
    )
  }

  // ── Mobile/tablette (<1280px) : tiroir Sheet plein-tiroir (fallback inchangé). ──
  return (
    <Sheet open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}>
      <SheetContent side="right" className="w-[min(46rem,calc(100%-1.5rem))] sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle className="flex flex-wrap items-center gap-2">
            {titleContent}
          </SheetTitle>
          <SheetDescription>
            Suivi, équipement, interventions, pièces et historique du ticket.
          </SheetDescription>
          {headerContent}
        </SheetHeader>
        {bodyContent}
      </SheetContent>
    </Sheet>
  )
}

// L295 — colonne Kanban (un statut) : cartes ticket cliquables, couleur de
// statut (TICKET_STATUS_COLORS) en bandeau de tête. Ordre funnel garanti par
// l'appelant (TICKET_STATUSES). Couleur jamais le seul signal — le libellé reste.
export function KanbanColumn({ statut, tickets, onSelect }) {
  return (
    <div className="flex w-64 shrink-0 flex-col gap-2">
      <div className="flex items-center justify-between rounded-lg px-2.5 py-1.5 text-sm font-semibold"
           style={{ background: `${TICKET_STATUS_COLORS[statut]}1a`, color: TICKET_STATUS_COLORS[statut] }}>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ background: TICKET_STATUS_COLORS[statut] }} />
          {statusLabel(statut)}
        </span>
        <span className="rounded-full bg-card px-1.5 text-xs text-muted-foreground">{tickets.length}</span>
      </div>
      <div className="flex flex-col gap-2">
        {tickets.length === 0 && <p className="px-1 text-xs text-muted-foreground">—</p>}
        {tickets.map((t) => (
          <button key={t.id} type="button" onClick={() => onSelect(t)}
                  className="flex flex-col gap-1.5 rounded-lg border border-border bg-card p-2.5 text-left text-sm hover:border-primary/40">
            <span className="flex items-center gap-1.5 font-medium">
              {t.reference}
              {t.annule && <Badge tone="danger">Annulé</Badge>}
            </span>
            <span className="text-xs text-muted-foreground">{t.client_nom ?? '—'}</span>
            <span className="flex flex-wrap items-center gap-1">
              <PrioriteBadge value={t.priorite} />
              <TicketSlaBadge ticket={t} />
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

const CAL_WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const CAL_MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

const calYmd = (d) => {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

// Grille du mois : commence le lundi de la semaine du 1er, finit le dimanche
// de la semaine du dernier jour (toujours des lignes complètes de 7 colonnes).
function calMonthGrid(year, month) {
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7 // 0 = lundi
  const start = new Date(year, month, 1 - startOffset)
  const cells = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    cells.push(d)
  }
  if (cells[35].getMonth() !== month && cells[28].getMonth() !== month) {
    return cells.slice(0, 35)
  }
  return cells
}

function CalendarTicketCard({ ticket }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-card p-1.5 text-left text-xs shadow-sm hover:border-primary/40">
      <span className="flex items-center gap-1 font-medium">
        <span className="size-1.5 shrink-0 rounded-full"
              style={{ background: TICKET_STATUS_COLORS[ticket.statut] }} />
        {ticket.reference}
      </span>
      <span className="truncate text-muted-foreground">{ticket.client_nom ?? '—'}</span>
    </div>
  )
}

function DraggableCalendarCard({ ticket, onSelect }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `ticket-cal-${ticket.id}`, data: { ticket },
  })
  return (
    <div ref={setNodeRef} {...listeners} {...attributes}
         onClick={() => onSelect(ticket)}
         className={isDragging ? 'cursor-grabbing opacity-50' : 'cursor-grab'}>
      <CalendarTicketCard ticket={ticket} />
    </div>
  )
}

function CalendarDayCell({ date: cellDate, inMonth, isToday, tickets, onSelect, onQuickCreate }) {
  const key = calYmd(cellDate)
  const { setNodeRef, isOver } = useDroppable({ id: `day-${key}`, data: { date: key } })
  return (
    <div ref={setNodeRef}
         className={`group flex min-h-[6rem] flex-col gap-1 p-1 ${inMonth ? 'bg-card' : 'bg-muted/30'} ${isOver ? 'ring-2 ring-inset ring-primary' : ''}`}>
      <div className="flex items-center justify-between px-0.5">
        <span className={`text-xs ${inMonth ? 'text-foreground' : 'text-muted-foreground'} ${isToday ? 'font-bold' : ''}`}>
          {isToday
            ? <span className="rounded-full bg-primary px-1.5 py-0.5 text-primary-foreground">{cellDate.getDate()}</span>
            : cellDate.getDate()}
        </span>
        {/* Création rapide d'un ticket depuis ce créneau. */}
        <button type="button" title="Créer un ticket ce jour"
                onClick={() => onQuickCreate(key)}
                className="hidden size-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground group-hover:flex">
          <Plus className="size-3" aria-hidden="true" />
        </button>
      </div>
      <div className="flex flex-col gap-1">
        {tickets.map((t) => (
          <DraggableCalendarCard key={t.id} ticket={t} onSelect={onSelect} />
        ))}
      </div>
    </div>
  )
}

// Formulaire minimal de création rapide (référence auto côté serveur) : type,
// client texte libre non requis ici — on réutilise le flux normal via
// createTicket avec juste la date_tournee proposée en info (posée ensuite par
// le glisser-déposer si l'utilisateur veut affiner) — garde le composant
// simple : ouvre la fiche standard n'est pas nécessaire, un POST minimal suffit.
// VX240(d) — dernier type de ticket utilisé (localStorage, modifiable),
// même patron que VX93 (lireLastTva/lireDernierMode) : le type ne reset plus
// silencieusement à « correctif » à chaque ouverture.
const TICKET_QC_TYPE_KEY = 'taqinor.tickets.quickCreate.lastType'
const lireLastTicketType = () => {
  try { return window.localStorage.getItem(TICKET_QC_TYPE_KEY) || 'correctif' }
  catch { return 'correctif' }
}
const ecrireLastTicketType = (v) => {
  try { if (v) window.localStorage.setItem(TICKET_QC_TYPE_KEY, v) }
  catch { /* localStorage indisponible (navigation privée, quota) : no-op */ }
}

function CalendarQuickCreateDialog({ date: openDate, onClose, onCreated }) {
  const [description, setDescription] = useState('')
  const [type, setType] = useState(lireLastTicketType)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async () => {
    setBusy(true)
    setErr(null)
    try {
      const r = await savApi.createTicket({ type, description: description || undefined })
      // Pose la date planifiée sur le ticket fraîchement créé.
      await savApi.replanifierTicket(r.data.id, openDate)
      ecrireLastTicketType(type)  // VX240(d) — mémorise le type pour la prochaine création
      onCreated?.()
      onClose()
    } catch (e) {
      setErr(frError(e, 'Échec de la création.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AlertDialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Nouveau ticket — {formatDateFR(openDate)}</AlertDialogTitle>
          <AlertDialogDescription>
            Créer un ticket planifié à cette date.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="grid gap-3">
          <FormField label="Type">
            {/* VX240(d) — la modale s'ouvrait sans aucun autofocus. */}
            <Select value={type} onValueChange={setType}>
              <SelectTrigger autoFocus><SelectValue /></SelectTrigger>
              <SelectContent>
                {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Description">
            <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </FormField>
          {err && (
            <div role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" /> <span>{err}</span>
            </div>
          )}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction disabled={busy} onClick={(e) => { e.preventDefault(); submit() }}>
            Créer
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function TicketCalendarView({ tickets, onSelect, onReload }) {
  const today = useMemo(() => new Date(), [])
  const [cursor, setCursor] = useState(
    () => ({ year: today.getFullYear(), month: today.getMonth() }))
  const [quickCreateDate, setQuickCreateDate] = useState(null)
  const [dragTicket, setDragTicket] = useState(null)
  const [err, setErr] = useState('')

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )

  const cells = useMemo(() => calMonthGrid(cursor.year, cursor.month), [cursor])
  const byDay = useMemo(() => groupTicketsByDate(tickets), [tickets])

  const go = (delta) => setCursor((c) => {
    const d = new Date(c.year, c.month + delta, 1)
    return { year: d.getFullYear(), month: d.getMonth() }
  })
  const goToday = () => setCursor({ year: today.getFullYear(), month: today.getMonth() })

  const handleDragEnd = useCallback(async ({ active, over }) => {
    setDragTicket(null)
    const ticket = active?.data?.current?.ticket
    const targetDate = over?.data?.current?.date
    if (!ticket || !targetDate || targetDate === ticket.date_tournee) return
    setErr('')
    try {
      await savApi.replanifierTicket(ticket.id, targetDate)
      onReload?.()
    } catch {
      setErr('Replanification impossible.')
    }
  }, [onReload])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => go(-1)}><ChevronLeft /></Button>
        <Button variant="outline" size="sm" onClick={goToday}>Aujourd'hui</Button>
        <Button variant="outline" size="sm" onClick={() => go(1)}><ChevronRight /></Button>
        <strong className="min-w-[140px] text-center text-sm">
          {CAL_MONTHS[cursor.month]} {cursor.year}
        </strong>
      </div>

      {err && (
        <p role="alert" className="text-sm text-destructive">{err}</p>
      )}

      <DndContext sensors={sensors}
                  onDragStart={({ active }) => setDragTicket(active?.data?.current?.ticket ?? null)}
                  onDragEnd={handleDragEnd}
                  onDragCancel={() => setDragTicket(null)}>
        <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-border bg-border">
          {CAL_WEEKDAYS.map((d) => (
            <div key={d} className="bg-muted px-2 py-1.5 text-center text-xs font-semibold text-muted-foreground">
              {d}
            </div>
          ))}
          {cells.map((d) => {
            const key = calYmd(d)
            return (
              <CalendarDayCell
                key={key}
                date={d}
                inMonth={d.getMonth() === cursor.month}
                isToday={key === calYmd(today)}
                tickets={byDay[key] || []}
                onSelect={onSelect}
                onQuickCreate={setQuickCreateDate}
              />
            )
          })}
        </div>
      </DndContext>

      {!dragTicket && Object.keys(byDay).length === 0 && (
        <p className="text-center text-sm text-muted-foreground">
          Aucun ticket planifié (date de tournée) ce mois-ci.
        </p>
      )}

      {quickCreateDate && (
        <CalendarQuickCreateDialog
          date={quickCreateDate}
          onClose={() => setQuickCreateDate(null)}
          onCreated={() => onReload?.()}
        />
      )}
    </div>
  )
}

export default function TicketsPage() {
  // VX82 — titre d'onglet dédié (chrome navigateur vivant).
  useDocumentTitle('Tickets SAV')
  const dispatch = useDispatch()
  const { items, loading, error } = useSelector((s) => s.tickets)
  const [filters, setFilters] = useState(EMPTY_TICKET_FILTERS)
  const [selected, setSelected] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [view, setView] = useState('table') // L295/ZMFG3 — 'table' | 'kanban' | 'calendrier'
  // VX172 — pending visible sur « Exporter Excel » (VX49 pose déjà le toast
  // d'erreur ; ceci ajoute juste l'état chargement manquant).
  const [xlsxBusy, setXlsxBusy] = useState(false)
  // Vues enregistrées (FG11).
  const { savedViews: ticketSavedViews, saveView: saveTicketView, deleteView: deleteTicketView } = useSavedViews(TP_SAVED_VIEWS_KEY)
  const saveCurrentTicketView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    saveTicketView(name, { filters })
  }
  const applyTicketView = (v) => {
    if (v.state?.filters) setFilters({ ...EMPTY_TICKET_FILTERS, ...v.state.filters })
  }

  const reload = () => dispatch(fetchTickets())
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // VX79 — lien interne partageable : /sav?id=<pk> ouvre la fiche du ticket
  // ciblé (patron ?lead= de LeadsPage — état DÉRIVÉ, aucun effet). Fermer retire
  // le paramètre pour ne pas ré-ouvrir la fiche. Un id absent des tickets
  // chargés est signalé par un EmptyState inline (jamais une page blanche).
  const wantedId = searchParams.get('id')
  const deepTicket = useMemo(() => {
    if (!wantedId) return null
    return (items ?? []).find((t) => String(t.id) === String(wantedId)) ?? null
  }, [wantedId, items])
  const deepMissing = !!wantedId && !loading && !error && !deepTicket

  const clearDeepLink = () => {
    if (searchParams.has('id')) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.delete('id')
        return next
      }, { replace: true })
    }
  }
  // Panneau ouvert : sélection manuelle OU ticket ciblé par le lien profond.
  const detailTicket = selected ?? deepTicket
  const closeDetail = () => { setSelected(null); clearDeepLink() }

  // VX79 — « Copier le lien » : URL INTERNE de l'ERP (jamais un lien public) que
  // l'on peut envoyer à un collègue — /sav?id=<pk> rouvre le même ticket.
  const copierLien = async (t) => {
    const url = `${window.location.origin}/sav?id=${t.id}`
    try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
    toast.success('Lien du ticket copié.')
  }

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const technicienOptions = useMemo(
    () => [...new Set(items.map((it) => it.technicien_nom).filter(Boolean))].sort(),
    [items])
  // L317 — pour l'assignation en lot : techniciens (id+nom) disponibles.
  const technicienById = useMemo(() => {
    const m = new Map()
    for (const it of items) {
      if (it.technicien_responsable && it.technicien_nom) {
        m.set(String(it.technicien_responsable), it.technicien_nom)
      }
    }
    return m
  }, [items])

  const rows = useMemo(
    () => sortTickets(filterTickets(items, filters), 'statut', 'asc'),
    [items, filters])

  // L306/L314 — comptes par statut (ordre funnel) sur le jeu filtré.
  const counts = useMemo(() => statusCounts(rows), [rows])

  const hasFilters = filters.q || filters.statut || filters.type || filters.priorite
    || filters.technicien || filters.sous_garantie || filters.ouvert !== 'ouverts'
    || filters.annule || filters.urgent_garantie

  // ZSAV10 — action groupée atomique (une seule requête serveur), remplace le
  // fan-out de PATCH par ligne (ERR64). `operation` ∈ statut/technicien/
  // priorite/annuler ; `extra` porte la valeur (ex. {statut: 'planifie'}).
  const bulkAction = async (selectedKeys, operation, extra, clear) => {
    try {
      const { data } = await savApi.actionsGroupeesTickets(selectedKeys, operation, extra)
      if (data.nb_echecs === 0) {
        toast.success('Tickets mis à jour')
        clear?.()
      } else if (data.nb_traites === 0) {
        toast.error('Mise à jour groupée impossible.')
      } else {
        toast.error(`${data.nb_echecs} ticket(s) sur ${selectedKeys.length} n'ont pas pu être mis à jour.`)
      }
    } catch {
      toast.error('Mise à jour groupée impossible.')
    }
    // Toujours recharger : certains tickets ont pu changer côté serveur.
    reload()
  }

  const columns = useMemo(() => [
    {
      id: 'reference',
      header: 'Référence',
      width: 150,
      cell: (_v, row) => (
        <span className="flex items-center gap-1.5 font-medium">
          {row.reference}
          {row.annule && <Badge tone="danger">Annulé</Badge>}
        </span>
      ),
      accessor: (r) => r.reference,
    },
    { id: 'client_nom', header: 'Client', width: 160, accessor: (r) => r.client_nom ?? '—' },
    { id: 'installation_reference', header: 'Chantier', width: 140, accessor: (r) => r.installation_reference ?? '—' },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      searchable: false,
      cell: (_v, row) => <StatutPill statut={row.statut} />,
      exportValue: (row) => statusLabel(row.statut),
    },
    {
      // L298 — colonne SLA/âge (badge escaladé pour les ouverts en retard).
      id: 'sla',
      header: 'Âge',
      width: 130,
      searchable: false,
      sortable: false,
      cell: (_v, row) => <TicketSlaBadge ticket={row} />,
      exportValue: (row) => {
        const age = ticketAgeDays(row)
        return age != null && ['nouveau', 'planifie', 'en_cours'].includes(row.statut) && !row.annule
          ? `${age} j` : '—'
      },
    },
    { id: 'type', header: 'Type', width: 110, accessor: (r) => r.type_display ?? r.type },
    {
      id: 'priorite',
      header: 'Priorité',
      width: 110,
      searchable: false,
      cell: (_v, row) => <PrioriteBadge value={row.priorite} />,
      exportValue: (row) => TICKET_PRIORITE_LABELS[row.priorite] ?? row.priorite,
    },
    {
      id: 'garantie',
      header: 'Garantie',
      width: 120,
      searchable: false,
      accessor: (r) => SOUS_GARANTIE_LABELS[r.sous_garantie_effectif] ?? '—',
    },
    { id: 'technicien_nom', header: 'Technicien', width: 140, accessor: (r) => r.technicien_nom ?? '—' },
  ], [])

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root flex flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Tickets SAV</h1>
            <p className="text-sm text-muted-foreground">
              {rows.length} ticket{rows.length > 1 ? 's' : ''}
            </p>
          </div>
          {/* MB5 — segmenté + bouton export : passe sur deux lignes sous 375px
              au lieu de déborder horizontalement. */}
          <div className="flex flex-wrap items-center gap-2">
            {/* L295 — bascule Table / Kanban. */}
            <Segmented
              size="sm"
              value={view}
              onChange={setView}
              options={[
                { value: 'table', label: 'Table' },
                { value: 'kanban', label: 'Kanban' },
                { value: 'calendrier', label: 'Calendrier' },
              ]}
            />
            {/* VX79 — « Copier le lien » du ticket ouvert : URL INTERNE
                partageable (/sav?id=<pk>), pour l'envoyer à un collègue. */}
            {detailTicket && (
              <Button variant="ghost" size="sm"
                      onClick={() => copierLien(detailTicket)}
                      title="Copier le lien interne de ce ticket (à envoyer à un collègue)">
                <Link2 /> Copier le lien
              </Button>
            )}
            <Button variant="outline" size="sm" disabled={xlsxBusy}
                    onClick={() => {
                      const pending = downloadBlobInGesture()
                      setXlsxBusy(true)
                      importApi.exportList('tickets', rows.map((r) => r.id))
                        .then((r) => pending.deliver(r.data, 'tickets.xlsx'))
                        .catch(() => {})
                        .finally(() => setXlsxBusy(false))
                    }}>
              {xlsxBusy ? <Spinner /> : <Download />} Exporter Excel
            </Button>
          </div>
        </header>

        {/* L306/L314 — rangée de comptes par statut (ordre funnel). */}
        {!loading && !error && (
          <div className="flex flex-wrap gap-2">
            {counts.map((c) => (
              <button key={c.key} type="button"
                      onClick={() => setF('statut', filters.statut === c.key ? '' : c.key)}
                      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                        filters.statut === c.key ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}>
                <span className="size-2 rounded-full" style={{ background: TICKET_STATUS_COLORS[c.key] }} />
                {c.label}
                <span className="font-semibold">{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {/* VX79 — lien profond ?id=<pk> pointant vers un ticket introuvable :
            EmptyState inline (jamais une page blanche). */}
        {deepMissing && (
          <EmptyState
            icon={AlertTriangle}
            title="Ticket introuvable"
            description="Le ticket de ce lien n'existe plus ou n'est pas accessible."
            action={<Button size="sm" variant="outline" onClick={clearDeepLink}>Fermer</Button>}
          />
        )}

        {/* ── Filtres ── */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[220px] flex-1">
            <Input placeholder="Rechercher (référence, client, chantier, description)…"
                   value={filters.q} onChange={(e) => setF('q', e.target.value)} />
          </div>
          {/* L305 — puce rapide « urgent & sous garantie ». */}
          <Button variant={filters.urgent_garantie ? 'default' : 'outline'} size="sm"
                  onClick={() => setF('urgent_garantie', !filters.urgent_garantie)}>
            <Zap /> Urgent & sous garantie
          </Button>
          <Select value={filters.statut || '__all'}
                  onValueChange={(v) => setF('statut', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[130px]"><SelectValue placeholder="Tous statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous statuts</SelectItem>
              {TICKET_STATUSES.map((k) => <SelectItem key={k} value={k}>{TICKET_STATUS_LABELS[k]}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.type || '__all'}
                  onValueChange={(v) => setF('type', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[120px]"><SelectValue placeholder="Tous types" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous types</SelectItem>
              {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.priorite || '__all'}
                  onValueChange={(v) => setF('priorite', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[130px]"><SelectValue placeholder="Toutes priorités" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Toutes priorités</SelectItem>
              {TICKET_PRIORITES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.technicien || '__all'}
                  onValueChange={(v) => setF('technicien', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[140px]"><SelectValue placeholder="Tous techniciens" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous techniciens</SelectItem>
              {technicienOptions.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.sous_garantie || '__all'}
                  onValueChange={(v) => setF('sous_garantie', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[150px]"><SelectValue placeholder="Garantie (tous)" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Garantie (tous)</SelectItem>
              {SOUS_GARANTIE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>Sous garantie : {o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filters.ouvert} onValueChange={(v) => setF('ouvert', v)}>
            <SelectTrigger className="w-auto min-w-[170px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ouverts">Ouverts seulement</SelectItem>
              <SelectItem value="tous">Tous (incl. clôturés/annulés)</SelectItem>
            </SelectContent>
          </Select>
          {/* L304 — filtre d'annulation (le backend supporte ?annule=only|sans). */}
          <Select value={filters.annule || '__all'}
                  onValueChange={(v) => setF('annule', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[150px]"><SelectValue placeholder="Annulés (tous)" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Annulés (tous)</SelectItem>
              <SelectItem value="only">Annulés seulement</SelectItem>
              <SelectItem value="sans">Sans annulés</SelectItem>
            </SelectContent>
          </Select>
          <div className="lp-saved-views">
            <Button type="button" variant="link" size="sm" onClick={saveCurrentTicketView}>
              ⭐ Enregistrer cette vue
            </Button>
            {ticketSavedViews.map((v) => (
              <span key={v.name} className="lp-saved-view-chip">
                <button type="button" className="lp-saved-view-apply"
                        onClick={() => applyTicketView(v)} title="Appliquer cette vue">
                  {v.name}
                </button>
                <button type="button" className="lp-saved-view-del"
                        onClick={() => deleteTicketView(v.name)}
                        aria-label={`Supprimer la vue ${v.name}`}>
                  ✕
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* VX31 — boîte de réception SAV : à partir de 1280px (xl), la liste et
            le panneau de détail vivent CÔTE À CÔTE (pattern inbox Linear/Plain) —
            la liste ne disparaît jamais derrière un tiroir. Sous ce seuil,
            `TicketDetail` retombe seul sur son `Sheet` plein-tiroir (fallback
            mobile/tablette inchangé), donc pas de wrapper flex nécessaire ici. */}
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start">
          <div className="min-w-0 flex-1">
            {loading ? (
              <Card className="space-y-2 p-4">
                {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
              </Card>
            ) : error ? (
              <EmptyState
                icon={AlertTriangle}
                title="Chargement impossible"
                description="Les tickets n'ont pas pu être chargés. Réessayez."
                action={<Button size="sm" variant="outline" onClick={reload}><RotateCcw /> Réessayer</Button>}
              />
            ) : rows.length === 0 ? (
              // L315 — distinguer « aucun ticket ouvert » de « aucun match ».
              <EmptyState
                icon={TicketIcon}
                title={hasFilters ? 'Aucun résultat' : 'Aucun ticket ouvert'}
                description={hasFilters
                  ? 'Aucun ticket ne correspond aux filtres.'
                  : "Aucun ticket ouvert pour le moment. Ouvrez-en un depuis la fiche d'un chantier."}
                action={hasFilters
                  ? <Button size="sm" variant="outline" onClick={() => setFilters(EMPTY_TICKET_FILTERS)}><RotateCcw /> Réinitialiser</Button>
                  : undefined}
              />
            ) : view === 'kanban' ? (
              // L295 — vue Kanban : colonnes Nouveau → Clôturé via TICKET_STATUSES.
              <div className="flex gap-3 overflow-x-auto pb-2">
                {TICKET_STATUSES.map((k) => (
                  <KanbanColumn key={k} statut={k}
                                tickets={rows.filter((r) => r.statut === k)}
                                onSelect={setSelected} />
                ))}
              </div>
            ) : view === 'calendrier' ? (
              // ZMFG3 — vue calendrier : tickets datés (date_tournee) par jour,
              // glisser-déposer pour replanifier, création rapide depuis un créneau.
              <TicketCalendarView tickets={rows} onSelect={setSelected} onReload={reload} />
            ) : (
              <DataTable
                data={rows}
                columns={columns}
                getRowId={(row) => row.id}
                searchable={false}
                selectable
                onRowClick={(row) => setSelected(row)}
                exportName="tickets"
                emptyTitle="Aucun ticket"
                emptyDescription="Aucun ticket ne correspond à votre recherche."
                bulkActions={(selRows, selKeys, clear) => [
                  // VX246(c) — « Copier » la sélection en TSV (colle en colonnes dans Excel).
                  buildCopyTSVAction({ rows: selRows, filteredRows: selRows, columns }),
                  // L317 — assignation technicien en lot.
                  ...[...technicienById.entries()].map(([tid, nom]) => ({
                    id: `tech-${tid}`,
                    label: `Assigner à ${nom}`,
                    icon: Wrench,
                    onClick: () => bulkAction(selKeys, 'technicien', { technicien: tid }, clear),
                  })),
                  // YDOCF1/ZSAV10 — changement de statut en lot, désormais via
                  // l'action groupée gardée (respecte la machine d'états).
                  ...TICKET_STATUSES.map((k) => ({
                    id: `statut-${k}`,
                    label: `Statut → ${TICKET_STATUS_LABELS[k]}`,
                    onClick: () => bulkAction(selKeys, 'statut', { statut: k }, clear),
                  })),
                  // ZSAV10 — priorité en lot (nouveau, n'existait pas avant).
                  ...TICKET_PRIORITES.map((p) => ({
                    id: `priorite-${p}`,
                    label: `Priorité → ${TICKET_PRIORITE_LABELS[p]}`,
                    onClick: () => bulkAction(selKeys, 'priorite', { priorite: p }, clear),
                  })),
                  // ZSAV10 — annulation en lot (nouveau, n'existait pas avant).
                  {
                    id: 'annuler',
                    label: 'Annuler',
                    onClick: () => bulkAction(selKeys, 'annuler', {}, clear),
                  },
                ]}
              />
            )}
          </div>

          {detailTicket && (
            <TicketDetail ticket={detailTicket} onClose={closeDetail} onSaved={reload} />
          )}
        </div>
      </div>
    </TooltipProvider>
  )
}
