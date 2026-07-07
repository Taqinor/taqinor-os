import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch } from 'react-redux'
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
import AppointmentBooker from './leads/AppointmentBooker'
import LeadDevisPanel from './leads/LeadDevisPanel'
import SigneDialog from './leads/SigneDialog'
import { CONVERSION_STAGE } from '../../features/crm/stages'
import useCanaux from '../../features/crm/useCanaux'
import {
  Button, Input,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../ui'
import { normalizeMaPhone } from '../../lib/format'

// Canal posé par défaut sur un lead créé à la main (jamais null) : une visite/
// un appel direct au showroom. Le webhook du site impose 'site_web' de son côté.
const DEFAULT_CANAL = 'walk_in'
// Validation e-mail minimale (le formulaire est noValidate) : « un@deux.trois ».
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const STAGE_LABELS = {
  NEW: 'Nouveau',
  CONTACTED: 'Contacté',
  QUOTE_SENT: 'Devis envoyé',
  FOLLOW_UP: 'Relance',
  SIGNED: 'Signé',
  COLD: 'Froid',
}

const STATUT_DEVIS = {
  brouillon: 'Brouillon', envoye: 'Envoyé', accepte: 'Accepté',
  refuse: 'Refusé', expire: 'Expiré',
}

const PRIORITES = { basse: 'Basse', normale: 'Normale', haute: 'Haute' }
// Langue préférée du contact — pré-sélectionne la langue du message WhatsApp.
const LANGUES_PREFEREES = { fr: 'Français', darija: 'Darija' }
const TYPES_INSTALLATION = {
  residentiel: 'Résidentiel', commercial: 'Commercial',
  industriel: 'Industriel', agricole: 'Agricole',
}
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

// Helpers hors composant : identité stable entre rendus (sinon les champs
// seraient démontés à chaque frappe et perdraient le focus).
const Sec = ({ title, children, id }) => (
  <div className="form-section" data-nav-id={id}>
    <div className="form-section-header">
      <span className="form-section-title">{title}</span>
    </div>
    {children}
  </div>
)

// Navigateur de sections (rail gauche) : libellé court → section du formulaire.
// La liste est calculée dans le composant car Pompage n'apparaît qu'en agricole.
const buildNavSections = ({ agricole, isEdit, hasWebOrigin }) => {
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
    ['pieces', 'Pièces jointes'], ['doublons', 'Doublons'],
    ['historique', 'Historique'])
  return secs
}

const Txt = ({ fields, set, k, label, type = 'text', ...rest }) => (
  <div className="form-group">
    <label className="form-label">{label}</label>
    <input type={type} step={type === 'number' ? 'any' : undefined}
           className="form-control" value={fields[k] ?? ''}
           onChange={e => set(k, e.target.value)} {...rest} />
  </div>
)

const Sel = ({ fields, set, k, label, labels }) => (
  <div className="form-group">
    <label className="form-label">{label}</label>
    <select className="form-select" value={fields[k] ?? ''}
            onChange={e => set(k, e.target.value)}>
      {enumOptions(labels)}
    </select>
  </div>
)

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "à l'instant"
  if (mins < 60) return `il y a ${mins} min`
  const h = Math.round(mins / 60)
  if (h < 24) return `il y a ${h} h`
  return new Date(iso).toLocaleDateString('fr-FR')
}

export default function LeadForm({ lead = null, onClose, onSaved, initialDevis = null, onOpenDuplicate = null }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const isEdit = !!lead
  // Canaux depuis le référentiel géré (Paramètres → CRM) + libellés statiques :
  // un canal ajouté en Paramètres apparaît dans le sélecteur sans redéploiement.
  const { labels: canalLabels } = useCanaux()

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
    adresse: F('adresse'), ville: F('ville'),
    gps_lat: F('gps_lat'), gps_lng: F('gps_lng'),
    // Pipeline
    stage: F('stage', 'NEW'), owner: F('owner', '') ?? '',
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
      api.get(`/crm/leads/${lead.id}/historique/`)
        .then(r => setHistorique(r.data)).catch(() => {})
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

  const postNote = async () => {
    const body = noteBody.trim()
    if (!body) return
    setNoteError(null)
    try {
      const r = await api.post(`/crm/leads/${lead.id}/noter/`, { body })
      setHistorique(h => [r.data, ...h])
      setNoteBody('')
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
        onSaved?.()
        onClose()
      }
    } catch (err) {
      setErrors(typeof err === 'object' ? err : { submit: String(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-xl" onClick={e => e.stopPropagation()}>
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

        {/* ── Barre d'actions devis (style Odoo) — tout reste dans la fiche ── */}
        {isEdit && (
          <div className="lead-subbar">
            <div className="lead-subbar-bills">
              <span className="lead-subbar-label">💡 Facture :</span>
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
                        {Math.round(parseFloat(liveLead.facture_hiver)).toLocaleString('fr-MA')} MAD
                        {liveLead?.ete_differente && liveLead?.facture_ete != null && liveLead.facture_ete !== ''
                          ? ` (hiver) · ${Math.round(parseFloat(liveLead.facture_ete)).toLocaleString('fr-MA')} MAD (été)` : ''}
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
                        title="Ouvrir l'outil de conception 3D du site avec ce lead déjà chargé"
                        onClick={ouvrirConceptionToiture}>
                  🏠 Concevoir la toiture (3D)
                </Button>
              )}
              <Button type="button" size="sm" className="gen-btn-orange"
                      disabled={!devisReady}
                      title={devisReady ? 'Créer le devis automatique (affiché ici)' : devisNotReadyMsg}
                      onClick={() => openDevisPanel('auto')}>
                ⚡ Devis automatique
              </Button>
              <div className="lead-devis-menu-wrap" ref={devisMenuRef}>
                <Button type="button" size="sm"
                        onClick={() => setDevisMenuOpen(o => !o)}>
                  📝 Devis modifiable ▾
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
              {buildNavSections({ agricole, isEdit, hasWebOrigin }).map(([id, label]) => (
                <button key={id} type="button"
                        className={activeSec === id ? 'active' : ''}
                        onClick={() => jumpTo(id)}>
                  {label}
                </button>
              ))}
            </nav>
          <div className="modal-body" ref={bodyRef} onScroll={onBodyScroll}>
            <Sec id="contact" title="👤 Contact">
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
                  <label className="form-label">Nom <span className="req">*</span></label>
                  <input className={`form-control${errors.nom ? ' is-invalid' : ''}`}
                         value={fields.nom} onChange={e => set('nom', e.target.value)} />
                  {errors.nom && <div className="form-feedback">{errors.nom}</div>}
                </div>
                <Txt fields={fields} set={set} k="prenom" label="Prénom" />
                <Txt fields={fields} set={set} k="telephone" label="Téléphone" />
              </div>
              <div className="form-row">
                <Txt fields={fields} set={set} k="whatsapp" label="WhatsApp" />
                <Txt fields={fields} set={set} k="ville" label="Ville / quartier" />
                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input type="email"
                         className={`form-control${errors.email ? ' is-invalid' : ''}`}
                         value={fields.email ?? ''}
                         onChange={e => set('email', e.target.value)} />
                  {errors.email && <div className="form-feedback">{errors.email}</div>}
                </div>
              </div>
              <div className="form-row">
                <Txt fields={fields} set={set} k="societe" label="Société" />
                <div className="form-group fg-grow"><Txt fields={fields} set={set} k="adresse" label="Adresse" /></div>
                <Txt fields={fields} set={set} k="gps_lat" label="GPS lat." type="number" />
                <Txt fields={fields} set={set} k="gps_lng" label="GPS long." type="number" />
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

            <Sec id="pipeline" title="📈 Suivi commercial">
              <div className="form-row">
                <Sel fields={fields} set={set} k="type_installation" label="Type d'installation" labels={TYPES_INSTALLATION} />
                <Sel fields={fields} set={set} k="stage" label="Étape" labels={STAGE_LABELS} />
                <div className="form-group">
                  <label className="form-label">Responsable</label>
                  <AssigneePicker
                    users={users}
                    value={fields.owner ?? ''}
                    onChange={(id) => set('owner', id ?? '')}
                  />
                </div>
                <Txt fields={fields} set={set} k="relance_date" label="Relance le" type="date" />
              </div>
              <div className="form-row">
                {/* XSAL7 — pipeline pondéré pré-devis : un lead chaud sans
                    devis pèse zéro dans la prévision sans ces deux champs. */}
                <Txt fields={fields} set={set} k="montant_estime" label="Montant estimé (MAD)" type="number" />
                <Txt fields={fields} set={set} k="date_cloture_prevue" label="Clôture prévue le" type="date" />
              </div>
              <div className="form-row">
                <Sel fields={fields} set={set} k="priorite" label="Priorité" labels={PRIORITES} />
                <Sel fields={fields} set={set} k="canal" label="Canal" labels={canalLabels} />
                <Sel fields={fields} set={set} k="langue_preferee" label="Langue préférée" labels={LANGUES_PREFEREES} />
                <div className="form-group fg-grow">
                  <Txt fields={fields} set={set} k="tags" label="Tags (séparés par des virgules)"
                       placeholder="ex: Régularisation 82-21, VIP" list="ld-tags" />
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
                    <label className="form-label">
                      Motif de perte <span className="req">*</span>
                    </label>
                    <input className={`form-control${errors.motif_perte ? ' is-invalid' : ''}`}
                           value={fields.motif_perte ?? ''}
                           onChange={e => set('motif_perte', e.target.value)}
                           list="ld-motifs" />
                    <datalist id="ld-motifs">
                      {motifOptions.map(m => <option key={m.id} value={m.nom} />)}
                    </datalist>
                    {errors.motif_perte && (
                      <div className="form-feedback">{errors.motif_perte}</div>
                    )}
                  </div>
                )}
              </div>
            </Sec>

            <Sec id="energie" title="💡 Profil énergétique">
              <div className="form-row">
                <Txt fields={fields} set={set} k="facture_hiver"
                     label={fields.ete_differente ? 'Facture Hiver (MAD/mois)' : 'Facture mensuelle (MAD/mois)'}
                     type="number" placeholder="ex: 650" />
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.ete_differente}
                           onChange={e => set('ete_differente', e.target.checked)} />
                    <span>L'été est différent de l'hiver ?</span>
                  </label>
                </div>
                {fields.ete_differente && (
                  <Txt fields={fields} set={set} k="facture_ete" label="Facture Été (MAD/mois)" type="number" placeholder="ex: 420" />
                )}
              </div>
              <div className="form-row">
                <Txt fields={fields} set={set} k="conso_mensuelle_kwh" label="Conso mensuelle (kWh)" type="number" />
                <Txt fields={fields} set={set} k="tranche_onee" label="Tarif / tranche ONEE" />
                <Sel fields={fields} set={set} k="raccordement" label="Raccordement" labels={RACCORDEMENTS} />
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
              <Sec id="pompage" title="💧 Pompage">
                <div className="form-row">
                  <Txt fields={fields} set={set} k="pompe_cv" type="number"
                       label={<>Pompe (CV)<span className="req-auto"> *</span></>}
                       placeholder="ex: 10" />
                  <Txt fields={fields} set={set} k="pompe_hmt_m" type="number"
                       label={<>HMT (m)<span className="req-auto"> *</span></>}
                       placeholder="ex: 80" />
                  <Txt fields={fields} set={set} k="pompe_debit_m3h" type="number"
                       label={<>Débit souhaité (m³/h)<span className="req-auto"> *</span></>}
                       placeholder="ex: 12" />
                </div>
                <p className="gen-hint">
                  <span className="req-auto">*</span> Requis pour le devis automatique en mode agricole.
                </p>
              </Sec>
            )}

            <Sec id="toiture" title="🏠 Toiture & site">
              <div className="form-row">
                <Sel fields={fields} set={set} k="type_toiture" label="Type de toiture" labels={TYPES_TOITURE} />
                <Txt fields={fields} set={set} k="surface_toiture_m2" label="Surface (m²)" type="number" />
                <Txt fields={fields} set={set} k="taille_souhaitee_kwc" label="Taille souhaitée (kWc)" type="number" />
                <Sel fields={fields} set={set} k="batterie_souhaitee" label="Batterie" labels={BATTERIES} />
              </div>
              <div className="form-row">
                <Sel fields={fields} set={set} k="orientation" label="Orientation" labels={ORIENTATIONS} />
                <Txt fields={fields} set={set} k="inclinaison_deg" label="Inclinaison / pente (°)" type="number" />
                <Sel fields={fields} set={set} k="ombrage" label="Ombrage" labels={OMBRAGES} />
                <div className="form-group fg-grow">
                  <Txt fields={fields} set={set} k="ombrage_notes" label="Notes ombrage" />
                </div>
              </div>
              <div className="form-row">
                <Sel fields={fields} set={set} k="structure_pref" label="Structure" labels={STRUCTURES} />
                <Txt fields={fields} set={set} k="nb_etages" label="Étages / hauteur" type="number" />
              </div>
            </Sec>

            <Sec id="visite" title="📋 Visite technique">
              <div className="form-row">
                <Txt fields={fields} set={set} k="visite_prevue_le" label="Visite prévue le" type="date" />
                <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                  <label className="pdf-toggle">
                    <input type="checkbox" checked={fields.visite_effectuee}
                           onChange={e => set('visite_effectuee', e.target.checked)} />
                    <span>Visite effectuée</span>
                  </label>
                </div>
                <div className="form-group fg-grow">
                  <Txt fields={fields} set={set} k="visite_notes" label="Notes de visite" />
                </div>
              </div>
              {/* QJ20 — Planifier une visite (inline, edit mode seulement) */}
              {isEdit && <AppointmentBooker leadId={lead.id} />}
            </Sec>

            {/* ── Origine web (taqinor.ma) — lecture seule ; masquée si tout vide.
                Ces champs sont capturés par le site et ne s'éditent pas ici. ── */}
            {hasWebOrigin && (
              <Sec id="origine" title="🌐 Origine (site web)">
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
            {isEdit && (
              <Sec id="devis" title={`📄 Devis de ce lead${liveLead?.client_nom ? ` — client : ${liveLead.client_nom}` : ''}`}>
                {lead?.id && (
                  <div style={{ margin: '0 0 8px' }}>
                    <Button type="button" size="sm" className="gen-btn-orange"
                            title="Ouvrir l'outil de conception 3D du site avec ce lead déjà chargé"
                            onClick={ouvrirConceptionToiture}>
                      🏠 Concevoir la toiture (3D)
                    </Button>
                  </div>
                )}
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
                              {Math.round(parseFloat(d.total_ttc)).toLocaleString('fr-MA')} MAD
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
              <Sec id="activites" title="⏰ Activités">
                <ActivitiesPanel
                  model="crm.lead" id={lead.id} users={users}
                  onChange={() => onSaved?.()}
                />
              </Sec>
            )}

            {/* ── Pièces jointes ── */}
            {isEdit && (
              <Sec id="pieces" title="📎 Pièces jointes">
                <AttachmentsPanel model="crm.lead" id={lead.id} />
              </Sec>
            )}

            {/* ── Doublons / Fusion ── */}
            {isEdit && (
              <Sec id="doublons" title={`🔀 Doublons${dups.length ? ` (${dups.length})` : ''}`}>
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
              <Sec id="historique" title="🕐 Historique">
                <div className="chatter-note-box">
                  <input className="form-control" placeholder="Écrire une note (appel, commentaire…)"
                         value={noteBody} onChange={e => setNoteBody(e.target.value)}
                         onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); postNote() } }} />
                  <Button type="button" variant="outline" onClick={postNote}>
                    Noter
                  </Button>
                </div>
                {noteError && (
                  <p className="form-error" role="alert">{noteError}</p>
                )}
                <div className="chatter-timeline">
                  {historique.length === 0 && (
                    <p className="gen-hint">Aucune activité pour le moment.</p>
                  )}
                  {historique.map(a => (
                    <div key={a.id} className={`chatter-item chatter-${a.kind}`}>
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
                      {a.bulk && <span className="chatter-bulk">en masse</span>}
                      <span className="chatter-meta">
                        — par {a.user_nom ?? '?'} · {timeAgo(a.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
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
      </div>

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
    </div>
  )
}
