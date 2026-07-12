import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  User, TrendingUp, Zap, Droplet, Home, ClipboardList, Globe,
  FileText, Clock, Paperclip, GitMerge, History, Lightbulb,
} from 'lucide-react'
import { createLead, updateLead, archiveLead, restoreLead } from '../../features/crm/store/crmSlice'
import api from '../../api/axios'
import crmApi from '../../api/crmApi'
import ventesApi from '../../api/ventesApi'
import installationsApi from '../../api/installationsApi'
import Avatar from '../../components/Avatar'
import AssigneePicker from '../../components/AssigneePicker'
import ActivitiesPanel from '../../components/ActivitiesPanel'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import CustomFieldsInput from '../../components/CustomFieldsInput'
// VX23 — chatter réutilisable (regroupement par jour, avatars, notes/logs).
import ChatterTimeline from '../../components/ChatterTimeline'
import AppointmentBooker from './leads/AppointmentBooker'
import LeadDevisPanel from './leads/LeadDevisPanel'
import SigneDialog from './leads/SigneDialog'
import PlanActiviteDialog from './leads/PlanActiviteDialog'
import ConvertirClientDialog from './leads/ConvertirClientDialog'
import {
  CONVERSION_STAGE, STAGE_LABELS, PRIORITE_LABELS, TYPE_INSTALLATION_LABELS,
} from '../../features/crm/stages'
import useCanaux from '../../features/crm/useCanaux'
// VX24 — bandeau de faits clés (LeadSummaryBar) réutilise le même ScoreBadge.
import ScoreBadge from '../../features/crm/ScoreBadge'
// VX87 — journal d'appel en un geste (issue + note + prochaine relance).
import CallLogPopover from '../../features/crm/CallLogPopover'
import useKeyboardAwareScroll from '../../hooks/useKeyboardAwareScroll'
import {
  Button, IconButton, Input, FormSection, FormField,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../ui'
// VX89 — shell externe Escape + focus-trap + bottom-sheet mobile (comme ClientForm).
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatMAD, normalizeMaPhone } from '../../lib/format'

// Canal posé par défaut sur un lead créé à la main (jamais null) : une visite/
// un appel direct au showroom. Le webhook du site impose 'site_web' de son côté.
const DEFAULT_CANAL = 'walk_in'
// Validation e-mail minimale (le formulaire est noValidate) : « un@deux.trois ».
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// VX93 — défauts intelligents : mémoire de la dernière ville saisie (par
// localStorage, toujours modifiable, jamais bloquant ; le pattern owner=moi
// utilise l'utilisateur courant côté composant). Silencieux si absent.
const LAST_VILLE_KEY = 'vx93.lead.ville'
const readLastVille = () => {
  try { return localStorage.getItem(LAST_VILLE_KEY) || '' } catch { return '' }
}
const rememberVille = (v) => {
  try { if (v && v.trim()) localStorage.setItem(LAST_VILLE_KEY, v.trim()) } catch { /* best-effort */ }
}

// VX143 — STAGE_LABELS/PRIORITE_LABELS/TYPE_INSTALLATION_LABELS viennent
// désormais de features/crm/stages.js (miroir strict de STAGES.py) au lieu
// d'une copie locale : une seule source, jamais de divergence (#2).

const STATUT_DEVIS = {
  brouillon: 'Brouillon', envoye: 'Envoyé', accepte: 'Accepté',
  refuse: 'Refusé', expire: 'Expiré',
}

// VX23 — OUTCOME_LABELS (résultat d'appel/e-mail journalisé) déménagé dans
// ChatterTimeline.jsx, seule source de rendu du chatter désormais.
// Langue préférée du contact — pré-sélectionne la langue du message WhatsApp.
const LANGUES_PREFEREES = { fr: 'Français', darija: 'Darija' }
const RACCORDEMENTS = { monophase: 'Monophasé', triphase: 'Triphasé', inconnu: 'Je ne sais pas' }
const TYPES_TOITURE = {
  terrasse_beton: 'Terrasse béton', tole_metal: 'Tôle/Métal', tuiles: 'Tuiles',
  bac_acier: 'Bac acier', fibrociment: 'Fibrociment', autre: 'Autre',
}
const ORIENTATIONS = {
  sud: 'Sud', sud_est: 'Sud-Est', sud_ouest: 'Sud-Ouest',
  est: 'Est', ouest: 'Ouest', autre: 'Autre',
}
const OMBRAGES = { aucun: 'Aucun', partiel: 'Partiel', important: 'Important' }
const STRUCTURES = { acier: 'Acier', aluminium: 'Aluminium' }
const BATTERIES = { sans: 'Sans batterie', avec: 'Avec batterie', les_deux: 'Les deux options' }

const enumOptions = (labels) => [
  <option key="" value="">—</option>,
  ...Object.entries(labels).map(([k, v]) => <option key={k} value={k}>{v}</option>),
]

// VX143 — un seul langage de formulaire dans le module CRM : les anciens
// helpers locaux `Sec`/`Txt`/`Sel` (classes hex-brutes) sont remplacés par les
// primitifs composables démontrés par ClientForm.jsx (`FormSection`/`FormField`),
// présentation pure — le scroll-spy `data-nav-id` et les verrouillages métier
// (perdu/motif, agricole, devis auto…) restent inchangés.

// Icône par section — même icône que le rail de navigation (VX143), à la
// place des emoji bruts. `contentBadge` (optionnel) affiche un compte dans le
// rail (ex. « Doublons (3) ») là où une simple emoji n'affichait jamais rien.
const NAV_ICONS = {
  contact: User,
  pipeline: TrendingUp,
  energie: Zap,
  pompage: Droplet,
  toiture: Home,
  visite: ClipboardList,
  origine: Globe,
  devis: FileText,
  activites: Clock,
  pieces: Paperclip,
  doublons: GitMerge,
  historique: History,
}

// Carte de section titrée, avec bordure/séparation visible (VX143 : les
// sections n'étaient distinguées que par une emoji, sans frontière). Identité
// stable hors composant (les champs enfants ne doivent pas être démontés à
// chaque frappe et perdre le focus).
const Sec = ({ title, children, id }) => {
  const Icon = NAV_ICONS[id]
  return (
    <div className="form-section" data-nav-id={id}>
      <FormSection
        title={(
          <span className="form-section-title-inner">
            {Icon && <Icon className="form-section-icon" aria-hidden="true" size={16} />}
            {title}
          </span>
        )}
      >
        {children}
      </FormSection>
    </div>
  )
}

// Navigateur de sections (rail gauche) : id → libellé court + compte de
// contenu optionnel (ex. nombre de doublons). La liste est calculée dans le
// composant car Pompage n'apparaît qu'en agricole et les comptes varient.
const buildNavSections = ({ agricole, isEdit, hasWebOrigin, dupCount = 0 }) => {
  const secs = [
    ['contact', 'Contact'],
    ['pipeline', 'Suivi commercial'],
    ['energie', 'Profil énergétique'],
  ]
  if (agricole) secs.push(['pompage', 'Pompage'])
  secs.push(['toiture', 'Toiture & site'], ['visite', 'Visite'])
  if (hasWebOrigin) secs.push(['origine', 'Origine web'])
  if (isEdit) secs.push(
    ['devis', 'Devis'], ['activites', 'Activités'],
    ['pieces', 'Pièces jointes'], ['doublons', 'Doublons', dupCount || null],
    ['historique', 'Historique'])
  return secs
}

// VX23 — timeAgo() déménagé dans ChatterTimeline.jsx (seul consommateur).

// VX24 — nombre de jours entiers depuis une date ISO (ou null si absente).
function joursDepuis(iso) {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const jours = Math.floor((Date.now() - d.getTime()) / 86400000)
  return jours >= 0 ? jours : null
}

// VX24 — LeadSummaryBar : le bandeau de faits clés façon Attio, en tête de
// fiche. Score, montant estimé, prochaine activité, jours depuis dernière
// modification — les 4 faits qui comptent pour préparer un appel, visibles
// sans avoir à scroller dans les sections détaillées.
function LeadSummaryBar({ lead }) {
  if (!lead) return null
  const jours = joursDepuis(lead.date_modification)
  const montant = lead.montant_estime != null && lead.montant_estime !== ''
    ? formatMAD(parseFloat(lead.montant_estime)) : null
  return (
    <div className="lead-summary-bar" data-testid="lead-summary-bar">
      <span className="lead-summary-item" title="Score de qualité du lead">
        <ScoreBadge lead={lead} />
      </span>
      <span className="lead-summary-item" title="Montant estimé (avant devis)">
        {montant ?? '—'}
      </span>
      <span className="lead-summary-item" title="Prochaine activité planifiée">
        {lead.next_activity
          ? `⏰ ${lead.next_activity.summary} — ${lead.next_activity.due_date}`
          : 'Aucune activité planifiée'}
      </span>
      <span className="lead-summary-item" title="Jours depuis la dernière modification">
        {jours != null ? `Modifié il y a ${jours} j` : '—'}
      </span>
    </div>
  )
}

export default function LeadForm({
  lead = null, onClose, onSaved, initialDevis = null, onOpenDuplicate = null,
  // QX25 — « Planifier une relance » (kanban) ouvre directement la fiche sur
  // la section « Suivi commercial » (relance_date) au lieu d'un texte inerte.
  focusSection = null,
}) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const isEdit = !!lead
  // VX93 — défaut « propriétaire = moi » à la création (le créateur est presque
  // toujours le propriétaire) ; toujours modifiable ensuite.
  const currentUserId = useSelector((s) => s.auth?.user?.id)
  // Canaux depuis le référentiel géré (Paramètres → CRM) + libellés statiques :
  // un canal ajouté en Paramètres apparaît dans le sélecteur sans redéploiement.
  const { labels: canalLabels } = useCanaux()
  // VX51 — un champ bas de page ne doit plus rester caché sous le clavier iOS.
  useKeyboardAwareScroll()

  // Copie « vivante » du lead : reflète les enregistrements ponctuels faits
  // SANS soumettre tout le formulaire (facture inline, devis créés). Sert au
  // verrouillage des boutons devis (devis_auto.pret) et à la liste des devis.
  const [liveLead, setLiveLead] = useState(lead)
  // On ne resynchronise la copie « vivante » que quand on change DE lead
  // (id différent). Sinon un simple re-rendu du parent (déclenché par onSaved
  // après création d'un devis) repasse un objet `lead` issu de la LISTE — dont
  // la liste `devis` est périmée/absente — et écrasait le devis fraîchement
  // ajouté tant qu'on ne rechargeait pas la page (FEATURE 0, symptôme 2).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLiveLead(lead)
  }, [lead?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Panneau devis inline (mode : auto | remise | onepage | premium | edit | view).
  const [devisPanel, setDevisPanel] = useState(null)
  const [panelDevisId, setPanelDevisId] = useState(null)
  const [devisMenuOpen, setDevisMenuOpen] = useState(false)
  const devisMenuRef = useRef(null)
  // Envoyer par WhatsApp : sélection multiple de devis du lead.
  const [waSelected, setWaSelected] = useState(() => new Set())
  const [waBusy, setWaBusy] = useState(false)
  // L851 — langue du message ('fr' par défaut, 'darija' au choix).
  // L17 — pré-sélectionne la langue préférée du lead quand elle est renseignée.
  const [waLangue, setWaLangue] = useState(() => lead?.langue_preferee || 'fr')
  // L852 — aperçu du message avant ouverture de wa.me.
  const [waPreview, setWaPreview] = useState(null) // { message, links, wa_url }
  // VX87 — ouverture contrôlée du popover « Journaliser un appel » (section
  // Historique), pour pouvoir la déclencher aussi depuis un futur nudge.
  const [callLogOpen, setCallLogOpen] = useState(false)

  const toggleWaSelect = (id) => setWaSelected(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })

  const leadPhone = (liveLead?.whatsapp || liveLead?.telephone || '').trim()
  // L853 — téléphone normalisable côté front (miroir de normalize_ma_phone) :
  // un numéro inexploitable désactive le bouton, sans aller-retour 400.
  const leadPhoneOk = !!normalizeMaPhone(leadPhone)

  // L852 — construit le message côté serveur puis affiche l'aperçu (FR/Darija)
  // + le(s) lien(s) public(s) avant d'ouvrir wa.me. Le POST consigne aussi
  // l'action au chatter du lead (côté serveur, L856).
  const envoyerWhatsApp = async () => {
    if (!leadPhoneOk) return
    if (waSelected.size === 0) {
      alert('Sélectionnez au moins un devis.')
      return
    }
    setWaBusy(true)
    try {
      const res = await crmApi.whatsappDevis(lead.id, {
        devis_ids: Array.from(waSelected),
        langue: waLangue,
      })
      setWaPreview({
        message: res.data?.message ?? '',
        links: res.data?.links ?? [],
        wa_url: res.data?.wa_url ?? '',
      })
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusy(false)
    }
  }

  // Ouvre wa.me avec le message pré-rempli après confirmation de l'aperçu.
  const ouvrirWhatsApp = () => {
    if (waPreview?.wa_url) window.open(waPreview.wa_url, '_blank', 'noopener')
    setWaPreview(null)
  }

  // Doublons probables (fusion sans perte).
  const [dups, setDups] = useState([])
  // Listes gérées (suggestions ; le texte libre reste possible).
  const [tagOptions, setTagOptions] = useState([])
  const [motifOptions, setMotifOptions] = useState([])

  // Édition inline de la facture (enregistre CE champ seul, sans le formulaire).
  const [billEditing, setBillEditing] = useState(false)
  const [billSaving, setBillSaving] = useState(false)
  const [billError, setBillError] = useState(null)
  const [billHiver, setBillHiver] = useState('')
  const [billEte, setBillEte] = useState('')

  const F = (k, d = '') => lead?.[k] ?? d
  const [fields, setFields] = useState({
    // Contact
    nom: F('nom'), prenom: F('prenom'), societe: F('societe'),
    email: F('email'), telephone: F('telephone'), whatsapp: F('whatsapp'),
    adresse: F('adresse'),
    // VX93 — ville pré-remplie avec la dernière saisie (création seulement).
    ville: lead ? F('ville') : (F('ville') || readLastVille()),
    gps_lat: F('gps_lat'), gps_lng: F('gps_lng'),
    // Pipeline
    stage: F('stage', 'NEW'),
    // VX93 — owner = utilisateur courant à la création (jamais en édition).
    owner: lead ? (F('owner', '') ?? '') : (F('owner', '') || (currentUserId ? String(currentUserId) : '')),
    // Canal prérempli à la création (jamais null) ; en édition on respecte la
    // valeur du lead (y compris vide pour un ancien lead).
    canal: lead ? (F('canal', '') ?? '') : DEFAULT_CANAL,
    // QW3 — préférence de contact explicite (posée par le site/webhook),
    // lecture seule ici : distincte du canal marketing et de whatsapp_opt_in.
    contact_preference: F('contact_preference', '') ?? '',
    priorite: F('priorite', 'normale'),
    langue_preferee: F('langue_preferee', '') ?? '',
    tags: F('tags'), motif_perte: F('motif_perte'),
    perdu: lead?.perdu ?? false,
    relance_date: F('relance_date'), type_installation: F('type_installation', '') ?? '',
    // XSAL7 — pipeline pondéré pré-devis (saisie libre, jamais snap/reject).
    montant_estime: F('montant_estime'), date_cloture_prevue: F('date_cloture_prevue'),
    // Énergie
    facture_hiver: F('facture_hiver'), facture_ete: F('facture_ete'),
    ete_differente: lead?.ete_differente ?? false,
    conso_mensuelle_kwh: F('conso_mensuelle_kwh'), tranche_onee: F('tranche_onee'),
    raccordement: F('raccordement', '') ?? '',
    regularisation_8221: lead?.regularisation_8221 ?? false,
    // Pompage (requis pour le devis auto en mode agricole)
    pompe_cv: F('pompe_cv'), pompe_hmt_m: F('pompe_hmt_m'),
    pompe_debit_m3h: F('pompe_debit_m3h'),
    // Toiture & site
    type_toiture: F('type_toiture', '') ?? '', surface_toiture_m2: F('surface_toiture_m2'),
    orientation: F('orientation', '') ?? '', inclinaison_deg: F('inclinaison_deg'),
    ombrage: F('ombrage', '') ?? '', ombrage_notes: F('ombrage_notes'),
    nb_etages: F('nb_etages'), structure_pref: F('structure_pref', '') ?? '',
    taille_souhaitee_kwc: F('taille_souhaitee_kwc'),
    batterie_souhaitee: F('batterie_souhaitee', '') ?? '',
    // Visite
    visite_prevue_le: F('visite_prevue_le'),
    visite_effectuee: lead?.visite_effectuee ?? false,
    visite_notes: F('visite_notes'),
    note: F('note'),
  })
  const [users, setUsers] = useState([])
  const [historique, setHistorique] = useState([])
  const [noteBody, setNoteBody] = useState('')
  const [noteError, setNoteError] = useState(null)
  // VX111 — pièce jointe optionnelle sur la note en cours de rédaction (ex.
  // photo prise depuis mobile). Réutilise records.Attachment côté serveur
  // (jamais un second magasin) — voir crmApi via postNote().
  const [noteFile, setNoteFile] = useState(null)
  const noteFileInputRef = useRef(null)
  const [saving, setSaving] = useState(false)
  const [savedConfirm, setSavedConfirm] = useState(false)
  const savedConfirmTimer = useRef(null)
  const [errors, setErrors] = useState({})
  const [activeSec, setActiveSec] = useState('contact')
  // Doublons probables détectés EN DIRECT depuis le téléphone/email saisi
  // (avertissement NON bloquant, à la création comme à l'édition).
  const [dupMatches, setDupMatches] = useState([])
  // Dialogue « Signé » : passer l'étape à Signé via le select ouvre le
  // dialogue d'acceptation (devis + option) au lieu d'enregistrer SIGNED.
  const [signeOpen, setSigneOpen] = useState(false)
  // ZSAL2 — dialogue « Appliquer un plan d'activité ».
  const [planOpen, setPlanOpen] = useState(false)
  // ZSAL4 — dialogue « Convertir en client » (nouveau / lier / aucun).
  const [convertOpen, setConvertOpen] = useState(false)
  // Champs personnalisés (T11).
  const [customData, setCustomData] = useState(lead?.custom_data || {})
  const bodyRef = useRef(null)

  // Scroll-spy : la section dont le haut est le plus proche du haut du
  // panneau (avec une marge) devient active dans le rail de navigation.
  const onBodyScroll = () => {
    const box = bodyRef.current
    if (!box) return
    const top = box.getBoundingClientRect().top
    let current = 'contact'
    for (const sec of box.querySelectorAll('[data-nav-id]')) {
      if (sec.getBoundingClientRect().top - top <= 90) {
        current = sec.dataset.navId
      }
    }
    setActiveSec(current)
  }

  const jumpTo = (id) => {
    const sec = bodyRef.current?.querySelector(`[data-nav-id="${id}"]`)
    sec?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  useEffect(() => {
    // Liste assignable (ouverte à la Commerciale) : id, username, poste, avatar.
    crmApi.getAssignableUsers()
      .then(r => setUsers(r.data.results ?? r.data)).catch(() => {})
    crmApi.getTags()
      .then(r => setTagOptions((r.data.results ?? r.data).filter(t => !t.archived)))
      .catch(() => {})
    crmApi.getMotifsPerte()
      .then(r => setMotifOptions((r.data.results ?? r.data).filter(m => !m.archived)))
      .catch(() => {})
    if (isEdit) {
      api.get(`/crm/leads/${lead.id}/historique/`)
        .then(r => setHistorique(r.data)).catch(() => {})
      crmApi.getLeadDuplicates(lead.id)
        .then(r => setDups(r.data)).catch(() => {})
    }
  }, [isEdit, lead?.id])

  // Avertissement doublon EN DIRECT (non bloquant) : dès qu'un téléphone ou un
  // email est saisi, on interroge le serveur (société côté serveur). En édition
  // on exclut le lead courant de ses propres doublons. Debounce léger.
  const phoneKey = fields.telephone
  const emailKey = fields.email
  useEffect(() => {
    const phone = (phoneKey ?? '').trim()
    const email = (emailKey ?? '').trim()
    const t = setTimeout(() => {
      if (!phone && !email) { setDupMatches([]); return }
      const params = {}
      if (phone) params.telephone = phone
      if (email) params.email = email
      if (isEdit) params.exclude = lead.id
      crmApi.checkDuplicates(params)
        .then(r => setDupMatches(r.data || []))
        .catch(() => setDupMatches([]))
    }, 400)
    return () => clearTimeout(t)
  }, [phoneKey, emailKey, isEdit, lead?.id])

  const doMerge = async (otherId) => {
    if (!window.confirm('Fusionner ce doublon dans la fiche courante ? '
      + 'Le doublon sera archivé (jamais supprimé) et ses devis/activités '
      + 'rattachés à cette fiche.')) return
    try {
      await crmApi.mergeLeads(lead.id, [otherId])
      setDups(d => d.filter(x => x.id !== otherId))
      refreshLead()
      refreshHistorique()
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'La fusion a échoué — réessayez.')
    }
  }

  // Ouverture directe sur un mode devis (depuis le ⚡ d'une carte / liste).
  const devisIntentRan = useRef(false)
  useEffect(() => {
    if (isEdit && initialDevis && !devisIntentRan.current) {
      devisIntentRan.current = true
      setDevisPanel(initialDevis)
    }
  }, [isEdit, initialDevis])

  // QX25 — « Planifier une relance » : fait défiler jusqu'à la section « Suivi
  // commercial » (relance_date) à l'ouverture, une seule fois.
  // VX223 — même geste pour « → Renseigner la facture » (LeadCard.jsx), SANS
  // prop dédiée : la carte pose une clé sessionStorage ciblant ce lead avant
  // d'appeler `onOpen`, consommée ICI une seule fois puis retirée (jamais un
  // focus fantôme sur un futur lead sans rapport).
  const focusSectionRan = useRef(false)
  useEffect(() => {
    if (!isEdit || focusSectionRan.current) return
    let target = focusSection
    if (!target) {
      try {
        const raw = sessionStorage.getItem('taqinor.leadform.pendingFocus')
        if (raw) {
          const pending = JSON.parse(raw)
          sessionStorage.removeItem('taqinor.leadform.pendingFocus')
          if (pending && String(pending.leadId) === String(lead.id)) target = pending.section
        }
      } catch { /* best-effort */ }
    }
    if (!target) return
    focusSectionRan.current = true
    setTimeout(() => jumpTo(target), 0)
  }, [isEdit, focusSection, lead?.id])

  // Fermeture du petit menu « Devis modifiable » au clic extérieur.
  useEffect(() => {
    if (!devisMenuOpen) return undefined
    const onDoc = (e) => {
      if (devisMenuRef.current && !devisMenuRef.current.contains(e.target)) {
        setDevisMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [devisMenuOpen])

  const set = (k, v) => setFields(f => ({ ...f, [k]: v }))
  const agricole = fields.type_installation === 'agricole'

  // Champs d'origine web (taqinor.ma) en LECTURE SEULE : capturés par le site,
  // jamais édités ici. La section est masquée si tous sont vides.
  const WEB_ORIGIN_FIELDS = [
    'bill_range_bucket', 'roi_band', 'utm_source', 'utm_medium',
    'utm_campaign', 'fbclid',
  ]
  const webVal = (k) => {
    const v = liveLead?.[k] ?? lead?.[k]
    return v === undefined || v === null || v === '' ? '' : String(v)
  }
  const hasWebOrigin = WEB_ORIGIN_FIELDS.some(k => webVal(k) !== '')
  const webRO = (k, label) => webVal(k) === '' ? null : (
    <div className="form-group">
      <label className="form-label">{label}</label>
      <input className="form-control" value={webVal(k)} readOnly disabled />
    </div>
  )

  // Le devis se crée et s'affiche DANS la fiche (LeadDevisPanel) — on ne quitte
  // jamais le lead. Le verrouillage « prêt ? » suit la règle serveur exposée
  // sur le lead (devis_auto.pret), recalculée après une sauvegarde de facture.
  const devisReady = !!liveLead?.devis_auto?.pret
  const devisNotReadyMsg = liveLead?.devis_auto?.message
    ?? 'Renseignez la facture du lead pour activer le devis automatique.'
  // QX28 — mêmes chips de préparation que LeadCard.jsx (crm/leads/views/) :
  // ce que le site a déjà capturé, visible dès l'ouverture de la fiche.
  const roofReady = !!liveLead?.roof_point
  const factureReady = liveLead?.facture_hiver != null && liveLead.facture_hiver !== ''

  const openDevisPanel = (mode) => {
    setDevisMenuOpen(false)
    setDevisPanel(mode)
  }

  // Ouvre l'outil de conception 3D DANS l'ERP (même origine, session cookie de
  // Meriem) avec le lead déjà chargé — navigation interne, aucun ID à copier.
  const ouvrirConceptionToiture = () => {
    if (!lead?.id) return
    navigate(`/devis-design/${lead.id}`)
  }

  // Après création/édition d'un devis dans le panneau : on recharge le lead
  // (liste des devis à jour) et on prévient le parent (liste/kanban).
  const refreshLead = () => {
    if (!isEdit) return
    crmApi.getLead(lead.id)
      .then(r => setLiveLead(r.data)).catch(() => {})
    onSaved?.()
  }

  // ── A4 — actions en ligne après acceptation d'un devis ──
  // « Générer la facture » : échéancier acompte → matériel → solde sur clics
  // répétés (moteur inchangé, nourri de l'option acceptée — A3). « Créer le
  // chantier » : pré-rempli depuis l'option acceptée, jamais en double (le
  // backend renvoie le chantier existant). On rafraîchit la fiche après.
  const [devisActionBusy, setDevisActionBusy] = useState(null)
  const [devisActionMsg, setDevisActionMsg] = useState(null)

  const genererFactureDevis = async (d) => {
    setDevisActionBusy(`f-${d.id}`)
    setDevisActionMsg(null)
    try {
      const res = await ventesApi.genererFacture(d.id)
      const f = res.data
      setDevisActionMsg(`${f.type_facture_display ?? 'Facture'} ${f.reference} créée.`)
      refreshLead()
    } catch (err) {
      setDevisActionMsg(err?.response?.data?.detail ?? 'Génération de facture impossible.')
    } finally {
      setDevisActionBusy(null)
    }
  }

  const creerChantierDevis = async (d) => {
    setDevisActionBusy(`c-${d.id}`)
    setDevisActionMsg(null)
    try {
      const res = await installationsApi.createFromDevis(d.id)
      setDevisActionMsg(`Chantier ${res.data.reference} prêt.`)
      refreshLead()
    } catch (err) {
      setDevisActionMsg(err?.response?.data?.detail ?? 'Création du chantier impossible.')
    } finally {
      setDevisActionBusy(null)
    }
  }

  // ── Édition inline de la facture (enregistre CE seul champ) ──
  const startBillEdit = () => {
    setBillHiver(liveLead?.facture_hiver != null ? String(liveLead.facture_hiver) : '')
    setBillEte(liveLead?.facture_ete != null ? String(liveLead.facture_ete) : '')
    setBillEditing(true)
  }
  const saveBill = async () => {
    setBillSaving(true)
    setBillError(null)
    try {
      const payload = {
        facture_hiver: billHiver === '' ? null : billHiver,
        facture_ete: liveLead?.ete_differente
          ? (billEte === '' ? null : billEte) : null,
      }
      const r = await crmApi.updateLead(lead.id, payload)
      setLiveLead(r.data)                 // devis_auto.pret recalculé côté serveur
      // garde le formulaire complet cohérent avec l'enregistrement ponctuel
      set('facture_hiver', r.data.facture_hiver ?? '')
      set('facture_ete', r.data.facture_ete ?? '')
      setBillEditing(false)
      onSaved?.()
    } catch (err) {
      // La valeur reste éditable ; on explique l'échec au lieu de l'avaler.
      setBillError(err?.response?.data?.detail
        ?? "La facture n'a pas pu être enregistrée — réessayez.")
    } finally {
      setBillSaving(false)
    }
  }

  // Archiver / restaurer depuis la fiche : on rafraîchit puis on ferme.
  const [archiveBusy, setArchiveBusy] = useState(false)
  const toggleArchive = async () => {
    setArchiveBusy(true)
    try {
      if (lead.is_archived) {
        await dispatch(restoreLead(lead.id)).unwrap()
      } else {
        await dispatch(archiveLead(lead.id)).unwrap()
      }
      onSaved?.()
      onClose()
    } catch { /* erreur silencieuse */ } finally { setArchiveBusy(false) }
  }

  // VX87 — helper partagé : recharge l'Historique (chatter) sans tout
  // recharger le lead. Consommé par le merge de doublons (déjà existant) et
  // par CallLogPopover après une journalisation d'appel réussie.
  const refreshHistorique = () => {
    if (!lead?.id) return
    api.get(`/crm/leads/${lead.id}/historique/`)
      .then(r => setHistorique(r.data)).catch(() => {})
  }

  // VX111 — la note poste en multipart dès qu'une pièce jointe est attachée
  // (endpoint `noter` désormais bilingue JSON/multipart côté serveur) ; sans
  // fichier, comportement STRICTEMENT inchangé (JSON simple).
  const postNote = async () => {
    const body = noteBody.trim()
    if (!body && !noteFile) return
    setNoteError(null)
    try {
      let r
      if (noteFile) {
        const form = new FormData()
        form.append('body', body)
        form.append('file', noteFile)
        r = await api.post(`/crm/leads/${lead.id}/noter/`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        r = await api.post(`/crm/leads/${lead.id}/noter/`, { body })
      }
      setHistorique(h => [r.data, ...h])
      setNoteBody('')
      setNoteFile(null)
      if (noteFileInputRef.current) noteFileInputRef.current.value = ''
    } catch (err) {
      // La note reste saisie ; on explique l'échec au lieu de l'avaler.
      setNoteError(err?.response?.data?.detail
        ?? "La note n'a pas pu être enregistrée — réessayez.")
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    // Validation côté client (le formulaire est noValidate) : on rassemble les
    // erreurs bloquantes avant d'envoyer quoi que ce soit.
    const ve = {}
    if (!fields.nom.trim()) ve.nom = 'Nom requis'
    const email = (fields.email ?? '').trim()
    if (email && !EMAIL_RE.test(email)) ve.email = 'Email invalide'
    // « Perdu ? » coché → le motif de perte est requis.
    if (fields.perdu && !(fields.motif_perte ?? '').trim()) {
      ve.motif_perte = 'Indiquez le motif de perte'
    }
    if (Object.keys(ve).length) { setErrors(ve); return }
    // Passer manuellement en « Signé » via le select ne s'enregistre PAS : on
    // ouvre le dialogue d'acceptation (devis + option) — l'acceptation fait
    // avancer l'étape côté serveur (couches funnel/document séparées, #2/#4).
    // Uniquement à l'édition (un nouveau lead n'a pas encore de devis).
    if (isEdit && fields.stage === CONVERSION_STAGE
        && lead.stage !== CONVERSION_STAGE) {
      setSigneOpen(true)
      return
    }
    setSaving(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      const payload = Object.fromEntries(
        Object.entries(fields).map(([k, v]) => [k, typeof v === 'boolean' ? v : nullable(v)]))
      // bascule OFF → la valeur unique vaut hiver ET été
      if (!fields.ete_differente) payload.facture_ete = null
      payload.custom_data = customData  // champs personnalisés (T11)
      if (isEdit) {
        const updated = await dispatch(updateLead({ id: lead.id, data: payload })).unwrap()
        // En mode ÉDITION : on reste ouvert — on recharge les données en place.
        setLiveLead(updated)
        // Ré-hydrate les champs modifiés (par ex. valeurs normalisées côté serveur).
        setFields(prev => ({ ...prev, ...Object.fromEntries(
          Object.keys(prev).map(k => [k, updated[k] !== undefined ? (updated[k] ?? '') : prev[k]])
        )}))
        setCustomData(updated.custom_data || {})
        onSaved?.()  // rafraîchit la liste/kanban parent sans fermer la fiche
        // Confirmation visuelle transitoire (2 s).
        if (savedConfirmTimer.current) clearTimeout(savedConfirmTimer.current)
        setSavedConfirm(true)
        savedConfirmTimer.current = setTimeout(() => setSavedConfirm(false), 2000)
      } else {
        await dispatch(createLead(payload)).unwrap()
        rememberVille(fields.ville)  // VX93 — mémorise la ville pour le prochain lead
        onSaved?.()
        onClose()
      }
    } catch (err) {
      setErrors(typeof err === 'object' ? err : { submit: String(err) })
    } finally {
      setSaving(false)
    }
  }

  // VX89 — le modal n°1 de l'ERP (20-40 ouvertures/jour/commercial) était le
  // SEUL à ne pas répondre à Escape ni focuser son champ requis : shell brut
  // `div.modal-overlay` (MB4 prétendait la migration ResponsiveDialog faite —
  // fact-check : faux pour ce fichier, corrigé ici). Le shell EXTERNE
  // (overlay + conteneur) est désormais `ResponsiveDialog` (Escape + focus-
  // trap + bottom-sheet mobile gratuits, comme ClientForm) ; l'entête
  // personnalisée (avatar, badge devis, actions Convertir/Archiver, bouton
  // fermer) et tout le `lead-form-layout` interne restent EXACTEMENT ceux
  // d'avant — ResponsiveDialog est monté SANS `title` (donc sans rendre de
  // second header) et avec `showClose={false}` (le bouton ✕ existant reste
  // l'unique fermeture).
  return (
    <ResponsiveDialog
      open
      onOpenChange={(o) => { if (!o) onClose() }}
      // p-0 : .modal-header/.modal-body/.modal-footer portent déjà chacun
      // leur propre padding (comme avant ResponsiveDialog) — sans ce reset,
      // le p-5 par défaut de DialogContent doublerait la marge visuelle.
      className="sm:max-w-5xl p-0 overflow-hidden gap-0"
      showClose={false}
    >
      <div className="modal-header">
          <h3 className="modal-title">
            {isEdit ? `Lead — ${lead.nom} ${lead.prenom || ''}` : 'Nouveau lead'}
            {isEdit && lead.is_archived && (
              <span className="lead-archived-badge">Archivé</span>
            )}
          </h3>
          <div className="lead-head-actions">
            {isEdit && (
              <span className="lead-head-owner" title="Responsable du lead">
                <Avatar
                  name={users.find(u => String(u.id) === String(fields.owner))?.username || null}
                  src={users.find(u => String(u.id) === String(fields.owner))?.avatar_url}
                  size={26}
                />
              </span>
            )}
            {isEdit && (
              <button
                type="button"
                className={`lead-devis-badge${(liveLead?.devis ?? []).length ? '' : ' is-zero'}`}
                title="Voir les devis de ce lead"
                onClick={() => jumpTo('devis')}
              >
                {(liveLead?.devis ?? []).length} devis
              </button>
            )}
            {isEdit && !liveLead?.client && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setConvertOpen(true)}
                title="Convertir ce lead en client (nouveau, lier à un client existant, ou aucun)"
              >
                Convertir en client
              </Button>
            )}
            {isEdit && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={archiveBusy}
                onClick={toggleArchive}
              >
                {lead.is_archived ? 'Restaurer' : 'Archiver'}
              </Button>
            )}
            <button type="button" className="modal-close" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* QX28 — chips de préparation (même logique que LeadCard.jsx) : ce
            que le site a déjà capturé pour ce lead, visible dès l'ouverture
            de la fiche, jamais un chip « manquant » — juste l'absence. */}
        {isEdit && (roofReady || factureReady || devisReady) && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', padding: '0 1rem' }}>
            {roofReady && (
              <span style={{ fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-success-muted, rgba(22,163,74,.12))', color: 'var(--color-success, #16a34a)' }}
                    title="Un repère GPS de toiture a été capturé (site ou 3D)">
                📍 Toit épinglé (GPS)
              </span>
            )}
            {factureReady && (
              <span style={{ fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-info-muted, rgba(37,99,235,.12))', color: 'var(--color-info, #2563eb)' }}
                    title="Une facture d'électricité a été saisie">
                🧾 Facture saisie
              </span>
            )}
            {devisReady && (
              <span style={{ fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-primary-muted, rgba(37,99,235,.12))', color: 'var(--color-primary, #2563eb)' }}
                    title="Toutes les données nécessaires sont réunies pour générer un devis en un clic">
                ⚡ Prêt à deviser en 1 clic
              </span>
            )}
          </div>
        )}

        {/* VX24 — bandeau de faits clés (LeadSummaryBar) : score, montant
            estimé, prochaine activité, jours depuis dernière modification —
            les 4 faits qui comptent, visibles sans scroller. */}
        {isEdit && <LeadSummaryBar lead={liveLead} />}

        {/* ── Barre d'actions devis (style Odoo) — tout reste dans la fiche ── */}
        {isEdit && (
          <div className="lead-subbar">
            <div className="lead-subbar-bills">
              <span className="lead-subbar-label">
                <Lightbulb className="lead-subbar-icon" aria-hidden="true" size={14} /> Facture :
              </span>
              {billEditing ? (
                <>
                  <Input type="number" step="any" className="lead-bill-input"
                         placeholder={liveLead?.ete_differente ? 'Hiver' : 'MAD/mois'}
                         value={billHiver} autoFocus
                         onChange={e => setBillHiver(e.target.value)} />
                  {liveLead?.ete_differente && (
                    <Input type="number" step="any" className="lead-bill-input"
                           placeholder="Été" value={billEte}
                           onChange={e => setBillEte(e.target.value)} />
                  )}
                  <Button type="button" size="sm"
                          loading={billSaving} disabled={billSaving} onClick={saveBill}>
                    {billSaving ? '…' : 'Enregistrer'}
                  </Button>
                  <Button type="button" size="sm" variant="outline"
                          onClick={() => setBillEditing(false)}>Annuler</Button>
                </>
              ) : (
                <button type="button" className="lead-bill-view" onClick={startBillEdit}
                        title="Cliquer pour modifier la facture (enregistre ce champ seul)">
                  {liveLead?.facture_hiver != null && liveLead.facture_hiver !== ''
                    ? <>
                        {formatMAD(liveLead.facture_hiver, { decimals: 0 })}
                        {liveLead?.ete_differente && liveLead?.facture_ete != null && liveLead.facture_ete !== ''
                          ? ` (hiver) · ${formatMAD(liveLead.facture_ete, { decimals: 0 })} (été)` : ''}
                        <span className="lead-bill-edit-hint"> ✎</span>
                      </>
                    : <span className="lead-bill-empty">+ Renseigner la facture ✎</span>}
                </button>
              )}
              {billError && (
                <span className="lead-bill-error" role="alert">{billError}</span>
              )}
            </div>

            <div className="lead-subbar-devis">
              {lead?.id && (
                <Button type="button" size="sm" className="gen-btn-orange"
                        title={roofReady
                          ? 'Repère toit (GPS) disponible — ouvrir le plan déjà positionné'
                          : "Ouvrir l'outil de conception 3D du site avec ce lead déjà chargé"}
                        onClick={ouvrirConceptionToiture}>
                  <Home aria-hidden="true" size={14} /> Concevoir la toiture (3D){roofReady ? ' 📍' : ''}
                </Button>
              )}
              <Button type="button" size="sm" className="gen-btn-orange"
                      disabled={!devisReady}
                      title={devisReady ? 'Créer le devis automatique (affiché ici)' : devisNotReadyMsg}
                      onClick={() => openDevisPanel('auto')}>
                <Zap aria-hidden="true" size={14} /> Devis automatique
              </Button>
              <div className="lead-devis-menu-wrap" ref={devisMenuRef}>
                <Button type="button" size="sm"
                        onClick={() => setDevisMenuOpen(o => !o)}>
                  <FileText aria-hidden="true" size={14} /> Devis modifiable ▾
                </Button>
                {devisMenuOpen && (
                  <div className="lead-devis-menu">
                    <button type="button" className="lead-devis-menu-item"
                            disabled={!devisReady} title={devisReady ? undefined : devisNotReadyMsg}
                            onClick={() => openDevisPanel('remise')}>
                      Remise %…
                    </button>
                    <button type="button" className="lead-devis-menu-item"
                            disabled={!devisReady} title={devisReady ? undefined : devisNotReadyMsg}
                            onClick={() => openDevisPanel('onepage')}>
                      Devis 1 page
                    </button>
                    <button type="button" className="lead-devis-menu-item"
                            disabled={!devisReady} title={devisReady ? undefined : devisNotReadyMsg}
                            onClick={() => openDevisPanel('premium')}>
                      Devis premium
                    </button>
                    <button type="button" className="lead-devis-menu-item"
                            onClick={() => openDevisPanel('edit')}>
                      Édition complète…
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="lead-form-layout">
            <nav className="lead-nav" aria-label="Sections du lead">
              {buildNavSections({ agricole, isEdit, hasWebOrigin, dupCount: dups.length })
                .map(([id, label, badge]) => {
                  const Icon = NAV_ICONS[id]
                  return (
                    <button key={id} type="button"
                            className={activeSec === id ? 'active' : ''}
                            onClick={() => jumpTo(id)}>
                      {Icon && <Icon className="lead-nav-icon" aria-hidden="true" size={15} />}
                      <span>{label}</span>
                      {!!badge && <span className="lead-nav-badge">{badge}</span>}
                    </button>
                  )
                })}
            </nav>
          <div className="modal-body" ref={bodyRef} onScroll={onBodyScroll}>
            <Sec id="contact" title="Contact">
              {dupMatches.length > 0 && (
                <div className="lead-dup-warning" role="status">
                  ⚠️ Un lead avec ce numéro existe déjà
                  {dupMatches.length > 1 ? ` (${dupMatches.length})` : ''} :{' '}
                  {dupMatches.slice(0, 3).map((d, i) => (
                    <span key={d.id}>
                      {i > 0 && ', '}
                      <button type="button" className="lead-dup-link"
                              onClick={() => onOpenDuplicate?.(d.id)}>
                        {`${d.nom} ${d.prenom || ''}`.trim() || `#${d.id}`}
                        {d.is_archived ? ' (archivé)' : ''}
                      </button>
                    </span>
                  ))}
                  {dupMatches.length > 3 && '…'}
                </div>
              )}
              <div className="form-row">
                <div className="form-group fg-grow">
                  {/* VX193 — label/champ associés via FormField (htmlFor déjà
                      correct depuis VX143, mais aria-invalid/aria-describedby/
                      role="alert" manquaient sur ce champ resté en balisage
                      brut) ; VX89 — le modal n°1 de l'ERP (20-40 ouvertures/
                      jour/commercial) focusait jusqu'ici son champ requis
                      nulle part : autoFocus posé explicitement (indépendant du
                      focus-management par défaut de Radix Dialog/Sheet). */}
                  <FormField label="Nom" required htmlFor="lf-nom" error={errors.nom} errorKind="required">
                    <Input id="lf-nom" autoFocus invalid={!!errors.nom}
                           value={fields.nom} onChange={e => set('nom', e.target.value)} />
                  </FormField>
                </div>
                <FormField label="Prénom" htmlFor="lf-prenom">
                  <Input id="lf-prenom" value={fields.prenom ?? ''} onChange={e => set('prenom', e.target.value)} />
                </FormField>
                <FormField label="Téléphone" htmlFor="lf-telephone">
                  <Input id="lf-telephone" value={fields.telephone ?? ''} onChange={e => set('telephone', e.target.value)} />
                </FormField>
              </div>
              <div className="form-row">
                <FormField label="WhatsApp" htmlFor="lf-whatsapp">
                  <Input id="lf-whatsapp" value={fields.whatsapp ?? ''} onChange={e => set('whatsapp', e.target.value)} />
                </FormField>
                <FormField label="Ville / quartier" htmlFor="lf-ville">
                  <Input id="lf-ville" value={fields.ville ?? ''} onChange={e => set('ville', e.target.value)} />
                </FormField>
                <div className="form-group">
                  <FormField label="Email" htmlFor="lf-email" error={errors.email}>
                    <Input id="lf-email" type="email" invalid={!!errors.email}
                           value={fields.email ?? ''}
                           onChange={e => set('email', e.target.value)} />
                  </FormField>
                </div>
              </div>
              <div className="form-row">
                <FormField label="Société" htmlFor="lf-societe">
                  <Input id="lf-societe" value={fields.societe ?? ''} onChange={e => set('societe', e.target.value)} />
                </FormField>
                <div className="form-group fg-grow">
                  <FormField label="Adresse" htmlFor="lf-adresse">
                    <Input id="lf-adresse" value={fields.adresse ?? ''} onChange={e => set('adresse', e.target.value)} />
                  </FormField>
                </div>
                <FormField label="GPS lat." htmlFor="lf-gps-lat">
                  <Input id="lf-gps-lat" type="number" step="any" value={fields.gps_lat ?? ''} onChange={e => set('gps_lat', e.target.value)} />
                </FormField>
                <FormField label="GPS long." htmlFor="lf-gps-lng">
                  <Input id="lf-gps-lng" type="number" step="any" value={fields.gps_lng ?? ''} onChange={e => set('gps_lng', e.target.value)} />
                </FormField>
              </div>
              {fields.gps_lat && fields.gps_lng && (
                <div className="form-row">
                  <a className="lead-gps-link"
                     href={`https://maps.google.com/?q=${encodeURIComponent(fields.gps_lat)},${encodeURIComponent(fields.gps_lng)}`}
                     target="_blank" rel="noopener noreferrer">
                    📍 Voir sur la carte
                  </a>
                </div>
              )}
            </Sec>

            <Sec id="pipeline" title="Suivi commercial">
              <div className="form-row">
                <FormField label="Type d'installation" htmlFor="lf-type-installation">
                  <select id="lf-type-installation" className="form-select" value={fields.type_installation ?? ''}
                          onChange={e => set('type_installation', e.target.value)}>
                    {enumOptions(TYPE_INSTALLATION_LABELS)}
                  </select>
                </FormField>
                <FormField label="Étape" htmlFor="lf-stage">
                  <select id="lf-stage" className="form-select" value={fields.stage ?? ''}
                          onChange={e => set('stage', e.target.value)}>
                    {enumOptions(STAGE_LABELS)}
                  </select>
                </FormField>
                <div className="form-group">
                  <label className="form-label">Responsable</label>
                  <AssigneePicker
                    users={users}
                    value={fields.owner ?? ''}
                    onChange={(id) => set('owner', id ?? '')}
                  />
                </div>
                <FormField label="Relance le" htmlFor="lf-relance-date">
                  <Input id="lf-relance-date" type="date" value={fields.relance_date ?? ''} onChange={e => set('relance_date', e.target.value)} />
                </FormField>
              </div>
              <div className="form-row">
                {/* XSAL7 — pipeline pondéré pré-devis : un lead chaud sans
                    devis pèse zéro dans la prévision sans ces deux champs. */}
                <FormField label="Montant estimé (MAD)" htmlFor="lf-montant-estime">
                  <Input id="lf-montant-estime" type="number" step="any" value={fields.montant_estime ?? ''} onChange={e => set('montant_estime', e.target.value)} />
                </FormField>
                <FormField label="Clôture prévue le" htmlFor="lf-date-cloture">
                  <Input id="lf-date-cloture" type="date" value={fields.date_cloture_prevue ?? ''} onChange={e => set('date_cloture_prevue', e.target.value)} />
                </FormField>
              </div>
              <div className="form-row">
                <FormField label="Priorité" htmlFor="lf-priorite">
                  <select id="lf-priorite" className="form-select" value={fields.priorite ?? ''}
                          onChange={e => set('priorite', e.target.value)}>
                    {enumOptions(PRIORITE_LABELS)}
                  </select>
                </FormField>
                <FormField label="Canal" htmlFor="lf-canal">
                  <select id="lf-canal" className="form-select" value={fields.canal ?? ''}
                          onChange={e => set('canal', e.target.value)}>
                    {enumOptions(canalLabels)}
                  </select>
                </FormField>
                <FormField label="Langue préférée" htmlFor="lf-langue-preferee">
                  <select id="lf-langue-preferee" className="form-select" value={fields.langue_preferee ?? ''}
                          onChange={e => set('langue_preferee', e.target.value)}>
                    {enumOptions(LANGUES_PREFEREES)}
                  </select>
                </FormField>
                <div className="form-group fg-grow">
                  <FormField label="Tags (séparés par des virgules)" htmlFor="lf-tags">
                    <Input id="lf-tags" value={fields.tags ?? ''} onChange={e => set('tags', e.target.value)}
                           placeholder="ex: Régularisation 82-21, VIP" list="ld-tags" />
                  </FormField>
                  <datalist id="ld-tags">
                    {tagOptions.map(t => <option key={t.id} value={t.nom} />)}
                  </datalist>
                </div>
              </div>
              {/* QW3 — préférence de contact explicite du client, distincte du
                  canal marketing et du consentement WhatsApp : lecture seule
                  ici (posée par le site/webhook), visuellement distincte de
                  l'icône WhatsApp. */}
              {fields.contact_preference === 'phone_ok' && (
                <div className="form-row">
                  <span
                    className="kb-badge-rappel rounded-full bg-info/15 px-1.5 py-0.5 text-info"
                    title="Le client a demandé à être rappelé par téléphone"
                  >
                    ☎ Rappel demandé
                  </span>
                </div>
              )}
              <div className="form-row">
                {/* « Perdu ? » est un drapeau indépendant de l'étape : un lead
                    peut être perdu à n'importe quelle étape. */}
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.perdu}
                           onChange={e => set('perdu', e.target.checked)} />
                    <span>Perdu ?</span>
                  </label>
                </div>
                {/* Motif de perte : visible dès que le lead est marqué Perdu,
                    quelle que soit l'étape. */}
                {fields.perdu && (
                  <div className="form-group fg-grow">
                    <FormField label="Motif de perte" required htmlFor="lf-motif-perte"
                               error={errors.motif_perte} errorKind="required">
                      <Input id="lf-motif-perte" invalid={!!errors.motif_perte}
                             value={fields.motif_perte ?? ''}
                             onChange={e => set('motif_perte', e.target.value)}
                             list="ld-motifs" />
                      <datalist id="ld-motifs">
                        {motifOptions.map(m => <option key={m.id} value={m.nom} />)}
                      </datalist>
                    </FormField>
                  </div>
                )}
              </div>
            </Sec>

            <Sec id="energie" title="Profil énergétique">
              <div className="form-row">
                <FormField label={fields.ete_differente ? 'Facture Hiver (MAD/mois)' : 'Facture mensuelle (MAD/mois)'} htmlFor="lf-facture-hiver">
                  <Input id="lf-facture-hiver" type="number" step="any" placeholder="ex: 650"
                         value={fields.facture_hiver ?? ''} onChange={e => set('facture_hiver', e.target.value)} />
                </FormField>
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.ete_differente}
                           onChange={e => set('ete_differente', e.target.checked)} />
                    <span>L'été est différent de l'hiver ?</span>
                  </label>
                </div>
                {fields.ete_differente && (
                  <FormField label="Facture Été (MAD/mois)" htmlFor="lf-facture-ete">
                    <Input id="lf-facture-ete" type="number" step="any" placeholder="ex: 420"
                           value={fields.facture_ete ?? ''} onChange={e => set('facture_ete', e.target.value)} />
                  </FormField>
                )}
              </div>
              <div className="form-row">
                <FormField label="Conso mensuelle (kWh)" htmlFor="lf-conso-mensuelle">
                  <Input id="lf-conso-mensuelle" type="number" step="any" value={fields.conso_mensuelle_kwh ?? ''} onChange={e => set('conso_mensuelle_kwh', e.target.value)} />
                </FormField>
                <FormField label="Tarif / tranche ONEE" htmlFor="lf-tranche-onee">
                  <Input id="lf-tranche-onee" value={fields.tranche_onee ?? ''} onChange={e => set('tranche_onee', e.target.value)} />
                </FormField>
                <FormField label="Raccordement" htmlFor="lf-raccordement">
                  <select id="lf-raccordement" className="form-select" value={fields.raccordement ?? ''}
                          onChange={e => set('raccordement', e.target.value)}>
                    {enumOptions(RACCORDEMENTS)}
                  </select>
                </FormField>
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.regularisation_8221}
                           onChange={e => set('regularisation_8221', e.target.checked)} />
                    <span>Installation existante à régulariser ? (82-21)</span>
                  </label>
                </div>
              </div>
            </Sec>

            {/* Pompage — section dédiée, visible uniquement en mode agricole ;
                ces champs alimentent le devis automatique. */}
            {agricole && (
              <Sec id="pompage" title="Pompage">
                <div className="form-row">
                  <FormField label={<>Pompe (CV)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-cv">
                    <Input id="lf-pompe-cv" type="number" step="any" placeholder="ex: 10"
                           value={fields.pompe_cv ?? ''} onChange={e => set('pompe_cv', e.target.value)} />
                  </FormField>
                  <FormField label={<>HMT (m)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-hmt">
                    <Input id="lf-pompe-hmt" type="number" step="any" placeholder="ex: 80"
                           value={fields.pompe_hmt_m ?? ''} onChange={e => set('pompe_hmt_m', e.target.value)} />
                  </FormField>
                  <FormField label={<>Débit souhaité (m³/h)<span className="req-auto"> *</span></>} htmlFor="lf-pompe-debit">
                    <Input id="lf-pompe-debit" type="number" step="any" placeholder="ex: 12"
                           value={fields.pompe_debit_m3h ?? ''} onChange={e => set('pompe_debit_m3h', e.target.value)} />
                  </FormField>
                </div>
                <p className="gen-hint">
                  <span className="req-auto">*</span> Requis pour le devis automatique en mode agricole.
                </p>
              </Sec>
            )}

            <Sec id="toiture" title="Toiture & site">
              <div className="form-row">
                <FormField label="Type de toiture" htmlFor="lf-type-toiture">
                  <select id="lf-type-toiture" className="form-select" value={fields.type_toiture ?? ''}
                          onChange={e => set('type_toiture', e.target.value)}>
                    {enumOptions(TYPES_TOITURE)}
                  </select>
                </FormField>
                <FormField label="Surface (m²)" htmlFor="lf-surface-toiture">
                  <Input id="lf-surface-toiture" type="number" step="any" value={fields.surface_toiture_m2 ?? ''} onChange={e => set('surface_toiture_m2', e.target.value)} />
                </FormField>
                <FormField label="Taille souhaitée (kWc)" htmlFor="lf-taille-souhaitee">
                  <Input id="lf-taille-souhaitee" type="number" step="any" value={fields.taille_souhaitee_kwc ?? ''} onChange={e => set('taille_souhaitee_kwc', e.target.value)} />
                </FormField>
                <FormField label="Batterie" htmlFor="lf-batterie">
                  <select id="lf-batterie" className="form-select" value={fields.batterie_souhaitee ?? ''}
                          onChange={e => set('batterie_souhaitee', e.target.value)}>
                    {enumOptions(BATTERIES)}
                  </select>
                </FormField>
              </div>
              <div className="form-row">
                <FormField label="Orientation" htmlFor="lf-orientation">
                  <select id="lf-orientation" className="form-select" value={fields.orientation ?? ''}
                          onChange={e => set('orientation', e.target.value)}>
                    {enumOptions(ORIENTATIONS)}
                  </select>
                </FormField>
                <FormField label="Inclinaison / pente (°)" htmlFor="lf-inclinaison">
                  <Input id="lf-inclinaison" type="number" step="any" value={fields.inclinaison_deg ?? ''} onChange={e => set('inclinaison_deg', e.target.value)} />
                </FormField>
                <FormField label="Ombrage" htmlFor="lf-ombrage">
                  <select id="lf-ombrage" className="form-select" value={fields.ombrage ?? ''}
                          onChange={e => set('ombrage', e.target.value)}>
                    {enumOptions(OMBRAGES)}
                  </select>
                </FormField>
                <div className="form-group fg-grow">
                  <FormField label="Notes ombrage" htmlFor="lf-ombrage-notes">
                    <Input id="lf-ombrage-notes" value={fields.ombrage_notes ?? ''} onChange={e => set('ombrage_notes', e.target.value)} />
                  </FormField>
                </div>
              </div>
              <div className="form-row">
                <FormField label="Structure" htmlFor="lf-structure">
                  <select id="lf-structure" className="form-select" value={fields.structure_pref ?? ''}
                          onChange={e => set('structure_pref', e.target.value)}>
                    {enumOptions(STRUCTURES)}
                  </select>
                </FormField>
                <FormField label="Étages / hauteur" htmlFor="lf-nb-etages">
                  <Input id="lf-nb-etages" type="number" step="any" value={fields.nb_etages ?? ''} onChange={e => set('nb_etages', e.target.value)} />
                </FormField>
              </div>
            </Sec>

            <Sec id="visite" title="Visite technique">
              <div className="form-row">
                <FormField label="Visite prévue le" htmlFor="lf-visite-prevue">
                  <Input id="lf-visite-prevue" type="date" value={fields.visite_prevue_le ?? ''} onChange={e => set('visite_prevue_le', e.target.value)} />
                </FormField>
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.visite_effectuee}
                           onChange={e => set('visite_effectuee', e.target.checked)} />
                    <span>Visite effectuée</span>
                  </label>
                </div>
                <div className="form-group fg-grow">
                  <FormField label="Notes de visite" htmlFor="lf-visite-notes">
                    <Input id="lf-visite-notes" value={fields.visite_notes ?? ''} onChange={e => set('visite_notes', e.target.value)} />
                  </FormField>
                </div>
              </div>
              {/* QJ20 — Planifier une visite (inline, edit mode seulement) */}
              {isEdit && <AppointmentBooker leadId={lead.id} />}
            </Sec>

            {/* ── Origine web (taqinor.ma) — lecture seule ; masquée si tout vide.
                Ces champs sont capturés par le site et ne s'éditent pas ici. ── */}
            {hasWebOrigin && (
              <Sec id="origine" title="Origine (site web)">
                <div className="form-row">
                  {webRO('bill_range_bucket', 'Tranche de facture (site)')}
                  {webRO('roi_band', 'Estimation ROI (site)')}
                </div>
                <div className="form-row">
                  {webRO('utm_source', 'UTM source')}
                  {webRO('utm_medium', 'UTM medium')}
                  {webRO('utm_campaign', 'UTM campagne')}
                  {webRO('fbclid', 'fbclid')}
                </div>
              </Sec>
            )}

            <div className="form-group">
              <label className="form-label">Note générale</label>
              <textarea className="form-control" rows={2} value={fields.note ?? ''}
                        onChange={e => set('note', e.target.value)} />
            </div>

            {/* ── Devis empilés ── */}
            {/* VX143 — le bouton « Concevoir la toiture (3D) » vit désormais
                UNE SEULE FOIS, dans la barre d'actions devis (sticky, hors
                scroll) : plus de doublon verbatim ici. */}
            {isEdit && (
              <Sec id="devis" title={`Devis de ce lead${liveLead?.client_nom ? ` — client : ${liveLead.client_nom}` : ''}`}>
                {(liveLead?.devis ?? []).length === 0 ? (
                  <p className="gen-hint">Aucun devis pour ce lead.</p>
                ) : (
                  <>
                    <div style={{ margin: '8px 0', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <Button
                        type="button"
                        variant="success"
                        loading={waBusy}
                        disabled={!leadPhoneOk || waBusy || waSelected.size === 0}
                        title={!leadPhone
                          ? 'Aucun numéro de téléphone'
                          : !leadPhoneOk
                            ? 'Numéro invalide'
                            : 'Préparer le message WhatsApp pour le(s) devis sélectionné(s)'}
                        onClick={envoyerWhatsApp}>
                        {waBusy ? 'Préparation…' : '🟢'} Envoyer par WhatsApp{waSelected.size > 0 ? ` (${waSelected.size})` : ''}
                      </Button>
                      {/* L851 — choix de la langue du message (FR par défaut). */}
                      <div role="group" aria-label="Langue du message WhatsApp" style={{ display: 'inline-flex', gap: 4 }}>
                        {[['fr', 'FR'], ['darija', 'Darija']].map(([val, label]) => (
                          <Button key={val} type="button" size="sm"
                                  variant={waLangue === val ? 'default' : 'outline'}
                                  aria-pressed={waLangue === val}
                                  onClick={() => setWaLangue(val)}>
                            {label}
                          </Button>
                        ))}
                      </div>
                      {!leadPhone && (
                        <span className="gen-hint">Aucun numéro de téléphone</span>
                      )}
                      {leadPhone && !leadPhoneOk && (
                        <span className="gen-hint">Numéro invalide</span>
                      )}
                    </div>
                    {/* L852 — aperçu du message WhatsApp avant ouverture de wa.me. */}
                    <Dialog open={!!waPreview} onOpenChange={(o) => { if (!o) setWaPreview(null) }}>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Aperçu du message WhatsApp</DialogTitle>
                          <DialogDescription>
                            {waLangue === 'darija' ? 'Variante Darija' : 'Variante Français'}
                            {' '}— vérifiez le texte et le(s) lien(s), puis ouvrez WhatsApp.
                          </DialogDescription>
                        </DialogHeader>
                        <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                          background: 'var(--muted, #f4f4f5)', padding: 12, borderRadius: 8,
                          fontFamily: 'inherit', fontSize: 13, margin: 0 }}>
                          {waPreview?.message}
                        </pre>
                        {(waPreview?.links?.length ?? 0) > 0 && (
                          <ul className="gen-hint" style={{ margin: '8px 0 0', paddingLeft: 16 }}>
                            {waPreview.links.map(l => (
                              <li key={l.devis_id ?? l.url}>{l.reference} : {l.url}</li>
                            ))}
                          </ul>
                        )}
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
                          <Button type="button" variant="ghost" onClick={() => setWaPreview(null)}>
                            Annuler
                          </Button>
                          <Button type="button" variant="success" disabled={!waPreview?.wa_url}
                                  onClick={ouvrirWhatsApp}>
                            🟢 Ouvrir WhatsApp
                          </Button>
                        </div>
                      </DialogContent>
                    </Dialog>
                    {devisActionMsg && (
                      <p className="gen-hint" role="status" style={{ margin: '4px 0' }}>
                        {devisActionMsg}
                      </p>
                    )}
                    <table className="lines-table">
                      <thead>
                        <tr><th></th><th>Référence</th><th>Statut</th><th className="col-num">Total TTC</th><th>Créé le</th><th>Actions</th></tr>
                      </thead>
                      <tbody>
                        {liveLead.devis.map(d => (
                          <tr key={d.id} style={{ cursor: 'pointer' }}
                              title="Voir / télécharger le PDF dans la fiche"
                              onClick={() => { setPanelDevisId(d.id); setDevisPanel('view') }}>
                            <td onClick={e => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={waSelected.has(d.id)}
                                onChange={() => toggleWaSelect(d.id)}
                                aria-label={`Sélectionner ${d.reference} pour WhatsApp`} />
                            </td>
                            <td><strong>{d.reference}</strong></td>
                            <td>{STATUT_DEVIS[d.statut] ?? d.statut}</td>
                            <td className="ta-right">
                              {formatMAD(d.total_ttc, { decimals: 0 })}
                            </td>
                            <td>{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                            <td className="ta-right">
                              <div className="lead-devis-actions">
                                {d.statut === 'accepte' && (
                                  <>
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      disabled={devisActionBusy === `f-${d.id}`}
                                      onClick={e => { e.stopPropagation(); genererFactureDevis(d) }}>
                                      {devisActionBusy === `f-${d.id}` ? '…' : '🧾 Générer la facture'}
                                    </Button>
                                    {d.chantier ? (
                                      <span className="gen-hint" title="Chantier déjà créé">
                                        🏗 {d.chantier.reference}
                                      </span>
                                    ) : (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        disabled={devisActionBusy === `c-${d.id}`}
                                        onClick={e => { e.stopPropagation(); creerChantierDevis(d) }}>
                                        {devisActionBusy === `c-${d.id}` ? '…' : '🏗 Créer le chantier'}
                                      </Button>
                                    )}
                                  </>
                                )}
                                <span className="lead-devis-pdf-hint">📄 PDF</span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </Sec>
            )}

            {/* ── Activités planifiées ── */}
            {isEdit && (
              <Sec id="activites" title="Activités">
                <div style={{ margin: '0 0 8px' }}>
                  <Button type="button" size="sm" variant="outline"
                          onClick={() => setPlanOpen(true)}>
                    📋 Appliquer un plan
                  </Button>
                </div>
                <ActivitiesPanel
                  model="crm.lead" id={lead.id} users={users}
                  onChange={() => onSaved?.()}
                />
              </Sec>
            )}

            {/* ── Pièces jointes ── */}
            {isEdit && (
              <Sec id="pieces" title="Pièces jointes">
                <AttachmentsPanel model="crm.lead" id={lead.id} />
              </Sec>
            )}

            {/* ── Doublons / Fusion ── */}
            {isEdit && (
              <Sec id="doublons" title={`Doublons${dups.length ? ` (${dups.length})` : ''}`}>
                {dups.length === 0 ? (
                  <p className="gen-hint">Aucun doublon détecté (même téléphone ou email).</p>
                ) : (
                  <table className="lines-table">
                    <thead>
                      <tr><th>Lead</th><th>Téléphone</th><th>Email</th><th>Devis</th><th></th></tr>
                    </thead>
                    <tbody>
                      {dups.map(d => (
                        <tr key={d.id}>
                          <td><strong>{d.nom} {d.prenom || ''}</strong>{d.is_archived ? ' (archivé)' : ''}</td>
                          <td>{d.telephone || '—'}</td>
                          <td>{d.email || '—'}</td>
                          <td>{d.nb_devis}</td>
                          <td className="ta-right">
                            <Button type="button" size="sm"
                                    onClick={() => doMerge(d.id)}>
                              Fusionner ici
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Sec>
            )}

            {/* ── Historique (chatter) ── */}
            {isEdit && (
              <Sec id="historique" title="Historique">
                <div className="chatter-note-box">
                  <input className="form-control" placeholder="Écrire une note (appel, commentaire…)"
                         value={noteBody} onChange={e => setNoteBody(e.target.value)}
                         onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); postNote() } }} />
                  {/* VX111 — attacher une pièce jointe à CETTE note (ex. photo
                      prise depuis mobile pendant une visite) : réutilise le
                      magasin records.Attachment existant, jamais un second
                      magasin (décision tranchée dans cette tâche). */}
                  <input
                    ref={noteFileInputRef}
                    type="file"
                    accept="application/pdf,image/png,image/jpeg,image/webp"
                    className="chatter-note-file-input"
                    onChange={e => setNoteFile(e.target.files?.[0] ?? null)}
                  />
                  <IconButton
                    type="button"
                    variant="outline"
                    label="Attacher une pièce jointe à la note"
                    onClick={() => noteFileInputRef.current?.click()}
                  >
                    <Paperclip aria-hidden="true" size={16} />
                  </IconButton>
                  <Button type="button" variant="outline" onClick={postNote}>
                    Noter
                  </Button>
                  {/* VX87 — journal d'appel en un geste : issue + note +
                      prochaine relance, le tout en 1 requête (logInteraction
                      avait ZÉRO site d'appel avant cette tâche). */}
                  <CallLogPopover
                    leadId={lead.id}
                    open={callLogOpen}
                    onOpenChange={setCallLogOpen}
                    onLogged={refreshHistorique}
                  />
                </div>
                {noteFile && (
                  <p className="chatter-note-file-preview" data-testid="chatter-note-file-preview">
                    <Paperclip size={12} aria-hidden="true" /> {noteFile.name}
                    <button type="button" className="chatter-note-file-clear"
                            aria-label="Retirer la pièce jointe"
                            onClick={() => { setNoteFile(null); if (noteFileInputRef.current) noteFileInputRef.current.value = '' }}>
                      ✕
                    </button>
                  </p>
                )}
                {noteError && (
                  <p className="form-error" role="alert">{noteError}</p>
                )}
                {/* VX23 — ChatterTimeline : composant réutilisable (regroupement
                    par jour, avatars, distinction note/log). Remplace l'ancien
                    journal texte plat rendu inline ici. */}
                <ChatterTimeline entries={historique} />
              </Sec>
            )}

            <CustomFieldsInput module="lead" value={customData} onChange={setCustomData} />

            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>
          </div>

          <div className="modal-footer">
            {savedConfirm && (
              <span className="lead-saved-confirm" role="status" aria-live="polite">
                ✓ Enregistré
              </span>
            )}
            <Button type="button" variant="outline" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" loading={saving} disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le lead')}
            </Button>
          </div>
        </form>

      {/* Panneau devis inline : créer / voir / télécharger sans quitter la fiche. */}
      {isEdit && devisPanel && (
        <LeadDevisPanel
          lead={liveLead}
          mode={devisPanel}
          existingDevisId={devisPanel === 'view' ? panelDevisId : null}
          onDevisChanged={refreshLead}
          onClose={() => { setDevisPanel(null); setPanelDevisId(null); refreshLead() }}
        />
      )}

      {/* Dialogue « Signé » : ouvert quand on choisit Signé dans le select de
          l'étape. L'acceptation d'un devis fait avancer l'étape côté serveur ;
          on ne pose JAMAIS stage=SIGNED directement (couches funnel/document
          séparées, #2/#4). Annuler remet l'étape à sa valeur courante. */}
      {isEdit && signeOpen && (
        <SigneDialog
          lead={liveLead}
          onClose={() => { set('stage', lead.stage); setSigneOpen(false) }}
          onConfirmed={() => { setSigneOpen(false); onSaved?.(); onClose() }}
        />
      )}

      {/* ZSAL2 — Appliquer un plan d'activité au lead ouvert. */}
      {isEdit && planOpen && (
        <PlanActiviteDialog
          lead={liveLead}
          onClose={() => setPlanOpen(false)}
          onApplied={() => onSaved?.()}
        />
      )}

      {/* ZSAL4 — Convertir en client (nouveau / lier / aucun). */}
      {isEdit && convertOpen && (
        <ConvertirClientDialog
          lead={liveLead}
          onClose={() => setConvertOpen(false)}
          onConverted={refreshLead}
        />
      )}
    </ResponsiveDialog>
  )
}
