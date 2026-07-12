import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'
import { isDirty } from '../../ui/form-utils'
import {
  fetchProfile, saveProfile,
  clearSaveSuccess,
} from '../../features/parametres/store/parametresSlice'
import {
  fetchCategories,
  fetchFournisseurs,
} from '../../features/stock/store/stockSlice'
import crmApi from '../../api/crmApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import customFieldsApi from '../../api/customFieldsApi'
import { CheckCircle2, AlertCircle, Save, Search, X, Info } from 'lucide-react'
import {
  Button, Spinner, TooltipProvider, Input,
} from '../../ui'
import { toast } from '../../ui/confirm'
import {
  TABS, DEFAULT_PAYMENT_TERMS, DEFAULT_PREFIXES, DEFAULT_NUMBERING,
  searchSettings, groupTabs, saveModelForTab, SAVE_MODEL_HINTS,
} from './peConstants'
import SettingsSidebar from './SettingsSidebar'
import OnboardingSection from './OnboardingSection'
import SocieteSection from './SocieteSection'
import LeadsSection from './LeadsSection'
import ClientsSection from './ClientsSection'
import DevisSection from './DevisSection'
import DocumentsSection from './DocumentsSection'
import TarificationSection from './TarificationSection'
import StockSection from './StockSection'
import DonneesSection from './DonneesSection'
import StatutsSection from './StatutsSection'
import MonitoringSection from './MonitoringSection'
import ChecklistSection from './ChecklistSection'
import EtapesChantierSection from './EtapesChantierSection'
import KitsSection from './KitsSection'
import ShotListSection from './ShotListSection'
import AutomatisationsSection from './AutomatisationsSection'
import SecuriteTerrainSection from './SecuriteTerrainSection'
import EquipeSection from './EquipeSection'
import MessagesSection from './MessagesSection'
import EmailSection from './EmailSection'
import ApiWebhooksSection from './ApiWebhooksSection'
import AvanceSection from './AvanceSection'
import SecuriteCompteSection from './SecuriteCompteSection'
import TraductionsSection from './TraductionsSection'
import ConfidentialiteSection from './ConfidentialiteSection'

// N96 — onglet « Sécurité du compte » (double authentification 2FA, opt-in).
// Ajouté localement (sans modifier la liste partagée peConstants.TABS) pour
// rester dans le périmètre de ce fichier.
const SECURITE_COMPTE_TAB = { key: 'securite_compte', label: 'Sécurité du compte', group: 'equipe' }
// N94 — onglet « Traductions » (surcharges d'interface par langue, sans code).
// Ajouté localement, même logique que l'onglet N96 (hors peConstants.TABS).
const TRADUCTIONS_TAB = { key: 'traductions', label: 'Traductions', group: 'avance' }
// XPLT23 — onglet « Confidentialité » (registre CNDP + demandes de personnes
// concernées). Ajouté localement, même logique que N96/N94.
const CONFIDENTIALITE_TAB = { key: 'confidentialite', label: 'Confidentialité', group: 'equipe' }

// ── Conteneur de la page Paramètres (D1) ───────────────────────────────────────
// Toute la logique (état du formulaire, chargements, handlers) vit ici, dans un
// seul <form> qui couvre tous les onglets — donc « Enregistrer » sauve TOUT,
// même les champs des onglets masqués (comportement inchangé). Chaque onglet est
// rendu par son propre composant de section ; les briques de présentation et les
// constantes sont partagées via ./peComponents et ./peConstants.
export default function ParametresEntreprise() {
  const dispatch = useDispatch()
  const { profile, loading, saving, uploading, error, saveSuccess } = useSelector(s => s.parametres)
  const { categories, fournisseurs } = useSelector(s => s.stock)
  // WR12 — rôle courant : les réglages sensibles (commission, DGI) ne sont
  // éditables que par un directeur/admin. Le backend gate déjà l'écriture
  // (IsAdminOrResponsableTier) ; ce contrôle UI empêche un rôle non autorisé
  // de voir/modifier les champs sensibles.
  const canManageSensitive = useIsAdmin()

  // Onglet actif (D1). Société & identité par défaut.
  const [tab, setTab] = useState('societe')
  // L790 — recherche de réglage : saute à l'onglet contenant un libellé.
  const [search, setSearch] = useState('')
  const searchResults = searchSettings(search)
  // Liste d'onglets affichée = onglets partagés + N96 (2FA) + N94 (traductions)
  // + XPLT23 (confidentialité).
  const allTabs = [...TABS, SECURITE_COMPTE_TAB, TRADUCTIONS_TAB, CONFIDENTIALITE_TAB]
  // VX35 — onglets rangés en familles pour la sidebar verticale (ordre =
  // SETTINGS_GROUPS). groupTabs garantit qu'aucun onglet ne disparaît.
  const tabGroups = groupTabs(allTabs)
  const tabLabel = (key) => (allTabs.find(t => t.key === key)?.label ?? key)
  const jumpToTab = (key) => { setTab(key); setSearch('') }

  const [form, setForm] = useState({
    nom: '', adresse: '', email: '', telephone: '',
    siret: '', tva_intra: '', rib: '', banque: '',
    instructions_paiement: '', conditions_generales: '',
    ice: '', identifiant_fiscal: '', rc: '', patente: '', cnss: '',
    couleur_principale: '#1d4ed8',
    responsable_defaut_leads: '',
    default_installer: '',
    payment_terms: DEFAULT_PAYMENT_TERMS,
    quote_validity_days: 30,
    agricole_pump_hours: 7,
    doc_prefixes: DEFAULT_PREFIXES,
    doc_numbering: DEFAULT_NUMBERING,
    tva_standard: 20,
    tva_panneaux: 10,
    onee_tarif_kwh: 1.75,
    productible_kwh_kwc: 1600,
    discount_approval_threshold: '',
    seuil_regime_declaration_kwc: 11,
    seuil_regime_anre_kwc: 1000,
    rendement_global: 0.8,
    panneaux_par_900mad: 8,
    prix_cible_kwc_defaut: '',
    remise_max_pct: '',
    commission_mode: 'off',
    commission_valeur: '',
    referral_enabled: false,
    referral_reward: '',
    // WR12 — flags jusqu'ici backend-only désormais éditables en Paramètres.
    lead_sla_hours: 24,       // FG28
    dgi_export_actif: false,  // N105 (interrupteur maître DGI, sensible/admin)
    // XSAL11 — round-robin équilibré des leads entrants (OFF par défaut).
    round_robin_leads_actif: false,
    round_robin_plafond_leads_ouverts: 20,
    // ZSTK13 — capacités stock (True = comportement actuel inchangé).
    stock_lots_series_actif: true,
    stock_colisage_actif: true,
    stock_scan_actif: true,
  })
  const [saved, setSaved] = useState(false)
  const [assignables, setAssignables] = useState([])
  const [niveaux, setNiveaux] = useState([])
  const [niveauxSaved, setNiveauxSaved] = useState(false)
  // ERR63 — message d'erreur par-ligne de l'enregistrement des niveaux.
  const [niveauxError, setNiveauxError] = useState('')
  const [tags, setTags] = useState([])
  const [motifs, setMotifs] = useState([])
  const [newTag, setNewTag] = useState('')
  const [newMotif, setNewMotif] = useState('')
  const [messages, setMessages] = useState([])
  const [msgSavedCle, setMsgSavedCle] = useState(null)
  // Listes gérées additives (T6) : canaux, types d'intervention, marques.
  const [canaux, setCanaux] = useState([])
  const [typesItv, setTypesItv] = useState([])
  const [checklistEtapes, setChecklistEtapes] = useState([])
  const [marques, setMarques] = useState([])
  const [newCanal, setNewCanal] = useState('')
  const [newType, setNewType] = useState('')
  const [newEtape, setNewEtape] = useState('')
  const [newMarque, setNewMarque] = useState('')
  // L777 — états de chargement par liste de référentiel (spinner pendant fetch).
  const [refLoading, setRefLoading] = useState({
    tags: true, motifs: true, canaux: true, typesItv: true,
  })
  const setRefDone = (key) =>
    setRefLoading(p => (p[key] ? { ...p, [key]: false } : p))
  // L770/L786 — aperçu du prochain numéro RÉEL par type de pièce (serveur).
  const [numberingNext, setNumberingNext] = useState(null)
  const loadNumberingPreview = () => ventesApi.numerotationPreview()
    .then(r => setNumberingNext(r.data)).catch(() => setNumberingNext(null))
  const loadCanaux = () => crmApi.getCanaux()
    .then(r => setCanaux(r.data.results ?? r.data)).catch(() => {})
    .finally(() => setRefDone('canaux'))
  const loadTypesItv = () => installationsApi.getTypesIntervention()
    .then(r => setTypesItv(r.data.results ?? r.data)).catch(() => {})
    .finally(() => setRefDone('typesItv'))
  const loadChecklistEtapes = () => installationsApi.getChecklistEtapes()
    .then(r => setChecklistEtapes(r.data.results ?? r.data)).catch(() => {})
  const loadMarques = () => stockApi.getMarques()
    .then(r => setMarques(r.data.results ?? r.data)).catch(() => {})
  // Champs personnalisés (T11) — module choisi (lead/client/produit).
  const [cfModule, setCfModule] = useState('lead')
  const [cfDefs, setCfDefs] = useState([])
  const [newCf, setNewCf] = useState({
    libelle: '', type: 'text', options: '', obligatoire: false,
    visible_liste: false,
  })
  // L809 — édition inline d'un champ existant : id en cours + brouillon.
  const [cfEditId, setCfEditId] = useState(null)
  const [cfEdit, setCfEdit] = useState(null)
  const loadCfDefs = (mod) => customFieldsApi.getDefs(mod)
    .then(r => setCfDefs(r.data.results ?? r.data)).catch(() => {})
  const slugifyCode = (s) => s.trim().toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50)
  // Message d'erreur serveur lisible (detail, ou première erreur de champ FR).
  const cfErr = (e, fallback) => {
    const d = e?.response?.data
    if (!d) return fallback
    if (typeof d === 'string') return d
    if (d.detail) return d.detail
    const first = Object.values(d)[0]
    return Array.isArray(first) ? first[0] : (first || fallback)
  }
  const addCf = async () => {
    const libelle = newCf.libelle.trim()
    if (!libelle) return
    try {
      await customFieldsApi.saveDef(null, {
        module: cfModule, code: slugifyCode(libelle), libelle, type: newCf.type,
        obligatoire: newCf.obligatoire, visible_liste: newCf.visible_liste,
        options: newCf.type === 'choice'
          ? newCf.options.split(',').map(o => o.trim()).filter(Boolean) : null,
      })
      setNewCf({
        libelle: '', type: 'text', options: '', obligatoire: false,
        visible_liste: false,
      })
      loadCfDefs(cfModule)
    } catch (e) { toast.error(cfErr(e, 'Ajout impossible.')) }
  }
  // L809/L811/L812 — ouvre/ferme l'éditeur inline d'un champ existant.
  const openCfEdit = (d) => {
    setCfEditId(d.id)
    setCfEdit({
      libelle: d.libelle, type: d.type, obligatoire: !!d.obligatoire,
      visible_liste: !!d.visible_liste,
      options: Array.isArray(d.options) ? d.options.join(', ') : '',
    })
  }
  const cancelCfEdit = () => { setCfEditId(null); setCfEdit(null) }
  const saveCfEdit = async (d) => {
    const libelle = (cfEdit?.libelle || '').trim()
    if (!libelle) return
    try {
      // Le code (clé JSON) n'est jamais renvoyé : protégé serveur (L814).
      await customFieldsApi.saveDef(d.id, {
        libelle, type: cfEdit.type, obligatoire: cfEdit.obligatoire,
        visible_liste: cfEdit.visible_liste,
        options: cfEdit.type === 'choice'
          ? cfEdit.options.split(',').map(o => o.trim()).filter(Boolean) : null,
      })
      cancelCfEdit()
      loadCfDefs(cfModule)
    } catch (e) { toast.error(cfErr(e, 'Modification impossible.')) }
  }
  // L810 — bascule actif/inactif sans perdre custom_data.
  const toggleCfActif = async (d) => {
    try {
      await customFieldsApi.saveDef(d.id, { actif: !d.actif })
      loadCfDefs(cfModule)
    } catch (e) { toast.error(cfErr(e, 'Modification impossible.')) }
  }
  // L813 — réordonne le champ d'un cran (haut/bas) et persiste l'ordre.
  const moveCf = async (d, dir) => {
    const ordered = [...cfDefs]
    const i = ordered.findIndex(x => x.id === d.id)
    const j = i + dir
    if (i < 0 || j < 0 || j >= ordered.length) return
    ;[ordered[i], ordered[j]] = [ordered[j], ordered[i]]
    setCfDefs(ordered)
    try {
      await customFieldsApi.reorder(ordered.map(x => x.id))
      loadCfDefs(cfModule)
    } catch (e) { toast.error(cfErr(e, 'Réordonnancement impossible.')) }
  }
  const delCf = async (d) => {
    if (!window.confirm(`Supprimer le champ « ${d.libelle} » ?`)) return
    try { await customFieldsApi.deleteDef(d.id); loadCfDefs(cfModule) }
    catch { /* */ }
  }
  const slugify = (s) => s.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

  const loadNiveaux = () => {
    ventesApi.getNiveauxRelance()
      .then(r => setNiveaux(r.data.results ?? r.data)).catch(() => {})
  }
  const loadTags = () => crmApi.getTags()
    .then(r => setTags(r.data.results ?? r.data)).catch(() => {})
    .finally(() => setRefDone('tags'))
  const loadMotifs = () => crmApi.getMotifsPerte()
    .then(r => setMotifs(r.data.results ?? r.data)).catch(() => {})
    .finally(() => setRefDone('motifs'))
  const loadMessages = () => parametresApi.getMessages()
    .then(r => setMessages(r.data)).catch(() => {})

  useEffect(() => {
    dispatch(fetchProfile())
    dispatch(fetchCategories())
    dispatch(fetchFournisseurs())
    crmApi.getAssignableUsers()
      .then(r => setAssignables(r.data.results ?? r.data)).catch(() => {})
    loadNiveaux()
    loadTags()
    loadMotifs()
    loadMessages()
    loadCanaux()
    loadTypesItv()
    loadChecklistEtapes()
    loadMarques()
    loadCfDefs('lead')
    loadNumberingPreview()
    // mount-only: one-time load of every reference list; the `load*` helpers
    // are recreated each render and read via closure, so listing them would
    // re-run every fetch on every render instead of once at mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch])

  const addEtape = async () => {
    const libelle = newEtape.trim()
    if (!libelle) return
    try {
      await installationsApi.saveChecklistEtape(null, {
        cle: slugify(libelle), libelle, ordre: checklistEtapes.length })
      setNewEtape(''); loadChecklistEtapes()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameEtape = async (et, libelle) => {
    // ERR102 — recharger pour refléter une normalisation serveur du libellé.
    try { await installationsApi.saveChecklistEtape(et.id, { libelle }); loadChecklistEtapes() } catch { /* */ }
  }
  const toggleEtapeActif = async (et) => {
    try { await installationsApi.saveChecklistEtape(et.id, { actif: !et.actif }); loadChecklistEtapes() }
    catch { /* */ }
  }
  // L785 — bascule capture_serie (saisie de n° de série) sur une étape.
  const toggleEtapeCapture = async (et) => {
    try {
      await installationsApi.saveChecklistEtape(et.id, { capture_serie: !et.capture_serie })
      loadChecklistEtapes()
    } catch { /* */ }
  }
  // L784 — réordonne une étape d'un cran (haut/bas) en échangeant les ordres.
  const moveEtape = async (et, dir) => {
    const i = checklistEtapes.findIndex(x => x.id === et.id)
    const j = i + dir
    if (i < 0 || j < 0 || j >= checklistEtapes.length) return
    const a = checklistEtapes[i]; const b = checklistEtapes[j]
    try {
      await Promise.all([
        installationsApi.saveChecklistEtape(a.id, { ordre: b.ordre }),
        installationsApi.saveChecklistEtape(b.id, { ordre: a.ordre }),
      ])
      loadChecklistEtapes()
    } catch { /* */ }
  }
  const delEtape = async (et) => {
    if (!window.confirm(`Supprimer l'étape « ${et.libelle} » ?`)) return
    try { await installationsApi.deleteChecklistEtape(et.id); loadChecklistEtapes() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible (étape protégée ?).') }
  }

  const addCanal = async () => {
    const libelle = newCanal.trim()
    if (!libelle) return
    try {
      await crmApi.saveCanal(null, { cle: slugify(libelle), libelle })
      setNewCanal(''); loadCanaux()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameCanal = async (c, libelle) => {
    // ERR102 — recharger pour refléter une normalisation serveur du libellé.
    try { await crmApi.saveCanal(c.id, { libelle }); loadCanaux() } catch { /* */ }
  }
  const delCanal = async (c) => {
    if (!window.confirm(`Supprimer le canal « ${c.libelle} » ?`)) return
    try { await crmApi.deleteCanal(c.id); loadCanaux() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  // L778 — archiver/réactiver un canal (préserve l'historique des leads).
  const archiveCanal = async (c) => {
    try { await crmApi.saveCanal(c.id, { archived: !c.archived }); loadCanaux() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Action impossible.') }
  }
  const addType = async () => {
    const libelle = newType.trim()
    if (!libelle) return
    try {
      await installationsApi.saveTypeIntervention(null, { cle: slugify(libelle), libelle })
      setNewType(''); loadTypesItv()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameType = async (t, libelle) => {
    // ERR102 — recharger pour refléter une normalisation serveur du libellé.
    try { await installationsApi.saveTypeIntervention(t.id, { libelle }); loadTypesItv() } catch { /* */ }
  }
  const delType = async (t) => {
    if (!window.confirm(`Supprimer le type « ${t.libelle} » ?`)) return
    try { await installationsApi.deleteTypeIntervention(t.id); loadTypesItv() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  const addMarque = async () => {
    const nom = newMarque.trim()
    if (!nom) return
    try { await stockApi.saveMarque(null, { nom }); setNewMarque(''); loadMarques() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const delMarque = async (m) => {
    if (!window.confirm(`Supprimer la marque « ${m.nom} » ?`)) return
    try { await stockApi.deleteMarque(m.id); loadMarques() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  const setMsgField = (cle, key, val) =>
    setMessages(ms => ms.map(m => (m.cle === cle ? { ...m, [key]: val } : m)))
  const saveMessage = async (m) => {
    try {
      await parametresApi.saveMessage({
        cle: m.cle, corps_fr: m.corps_fr, corps_darija: m.corps_darija,
      })
      setMsgSavedCle(m.cle)
      setTimeout(() => setMsgSavedCle(null), 2500)
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.')
    }
  }
  // L776 — réinitialiser un modèle WhatsApp au texte par défaut (endpoint reset).
  const resetMessage = async (m) => {
    if (!window.confirm(`Réinitialiser le message « ${m.label} » au modèle par défaut ?`)) return
    try {
      const r = await parametresApi.saveMessage({ cle: m.cle, reset: true })
      setMessages(ms => ms.map(x => (x.cle === m.cle
        ? { ...x, corps_fr: r.data.corps_fr, corps_darija: r.data.corps_darija } : x)))
      setMsgSavedCle(m.cle)
      setTimeout(() => setMsgSavedCle(null), 2500)
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Réinitialisation impossible.')
    }
  }

  const addTag = async () => {
    const nom = newTag.trim()
    if (!nom) return
    try { await crmApi.saveTag(null, { nom }); setNewTag(''); loadTags() } catch { /* */ }
  }
  const renameTag = async (t, nom) => {
    // ERR102 — recharger pour refléter une normalisation serveur du nom.
    try { await crmApi.saveTag(t.id, { nom }); loadTags() } catch { /* */ }
  }
  // L781 — couleur d'une étiquette (color-picker), persistée immédiatement.
  const setTagColor = async (t, couleur) => {
    setTags(ts => ts.map(x => (x.id === t.id ? { ...x, couleur } : x)))
    try { await crmApi.saveTag(t.id, { couleur }) } catch { /* */ }
  }
  const delTag = async (t) => {
    if (!window.confirm(`Supprimer l'étiquette « ${t.nom} » ?`)) return
    // L780 — la suppression est bloquée (409) si l'étiquette est utilisée :
    // on remonte le message serveur (qui propose l'archivage).
    try { await crmApi.deleteTag(t.id); loadTags() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  // L778 — archiver/réactiver une étiquette.
  const archiveTag = async (t) => {
    try { await crmApi.saveTag(t.id, { archived: !t.archived }); loadTags() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Action impossible.') }
  }
  const addMotif = async () => {
    const nom = newMotif.trim()
    if (!nom) return
    try { await crmApi.saveMotifPerte(null, { nom }); setNewMotif(''); loadMotifs() } catch { /* */ }
  }
  const renameMotif = async (m, nom) => {
    // ERR102 — recharger pour refléter une normalisation serveur du nom.
    try { await crmApi.saveMotifPerte(m.id, { nom }); loadMotifs() } catch { /* */ }
  }
  const delMotif = async (m) => {
    if (!window.confirm(`Supprimer le motif « ${m.nom} » ?`)) return
    // L779 — bloqué (409) si le motif est utilisé : on remonte le message
    // serveur (qui propose l'archivage).
    try { await crmApi.deleteMotifPerte(m.id); loadMotifs() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  // L778 — archiver/réactiver un motif de perte.
  const archiveMotif = async (m) => {
    try {
      await crmApi.saveMotifPerte(m.id, { archived: !m.archived }); loadMotifs()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Action impossible.') }
  }

  const setNiveau = (id, key, val) =>
    setNiveaux(ns => ns.map(n => (n.id === id ? { ...n, [key]: val } : n)))

  const saveNiveaux = async () => {
    // ERR63 — on ne « swallow » plus les échecs : chaque ligne est tentée
    // (allSettled, donc une ligne en échec ne rejette pas les autres déjà
    // enregistrées) et toute défaillance est remontée en français.
    setNiveauxError('')
    const results = await Promise.allSettled(
      niveaux.map(n => ventesApi.saveNiveauRelance(n.id, {
        nom: n.nom, delai_jours: Number(n.delai_jours) || 0,
        ordre: n.ordre, message: n.message || '',
      })))
    const failed = niveaux.filter((n, i) => results[i].status === 'rejected')
    loadNiveaux()
    if (failed.length > 0) {
      const noms = failed.map(n => `« ${n.nom} »`).join(', ')
      setNiveauxError(
        failed.length === niveaux.length
          ? 'Échec de l’enregistrement des niveaux. Réessayez.'
          : `Niveau(x) non enregistré(s) : ${noms}. Les autres ont bien été sauvegardés.`)
      return
    }
    setNiveauxSaved(true)
    setTimeout(() => setNiveauxSaved(false), 3000)
  }
  // L767 — ajout/suppression d'un niveau de relance depuis la carte.
  const addNiveau = async () => {
    const ordre = niveaux.length
    try {
      await ventesApi.saveNiveauRelance(null, {
        nom: `Niveau ${ordre + 1}`, delai_jours: 7, ordre, message: '',
      })
      loadNiveaux()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const delNiveau = async (n) => {
    if (!window.confirm(`Supprimer le niveau « ${n.nom} » ?`)) return
    try { await ventesApi.deleteNiveauRelance(n.id); loadNiveaux() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  // L768 — crée les niveaux par défaut (J+7 / J+15 / J+30) quand il n'y en a pas.
  const seedNiveaux = async () => {
    try { await ventesApi.seedNiveauxRelance(); loadNiveaux() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Création impossible.') }
  }

  // VX169 — garde de navigation IN-APP : snapshot pris à chaque resynchro
  // depuis `profile` (montage ET après un enregistrement réussi qui refetch
  // le profil — la garde s'éteint alors naturellement, saisie sauvegardée).
  const [initialSnapshot, setInitialSnapshot] = useState(null)
  const dirty = initialSnapshot != null
    && isDirty(initialSnapshot, form)
  useNavigationGuard(dirty)

  useEffect(() => {
    // Synchronisation du formulaire avec le profil chargé depuis le store
    if (!profile) return
    const next = {
      nom:               profile.nom               ?? '',
      adresse:           profile.adresse           ?? '',
      email:             profile.email             ?? '',
      telephone:         profile.telephone         ?? '',
      siret:             profile.siret             ?? '',
      tva_intra:         profile.tva_intra         ?? '',
      rib:               profile.rib               ?? '',
      banque:            profile.banque            ?? '',
      instructions_paiement: profile.instructions_paiement ?? '',
      conditions_generales:  profile.conditions_generales  ?? '',
      ice:               profile.ice               ?? '',
      identifiant_fiscal: profile.identifiant_fiscal ?? '',
      rc:                profile.rc                ?? '',
      patente:           profile.patente           ?? '',
      cnss:              profile.cnss              ?? '',
      couleur_principale: profile.couleur_principale ?? '#1d4ed8',
      responsable_defaut_leads: profile.responsable_defaut_leads ?? '',
      default_installer: profile.default_installer ?? '',
      payment_terms: { ...DEFAULT_PAYMENT_TERMS, ...(profile.payment_terms || {}) },
      quote_validity_days: profile.quote_validity_days ?? 30,
      agricole_pump_hours: profile.agricole_pump_hours ?? 7,
      doc_prefixes: { ...DEFAULT_PREFIXES, ...(profile.doc_prefixes || {}) },
      doc_numbering: Object.fromEntries(Object.keys(DEFAULT_NUMBERING).map(k => [
        k, { ...DEFAULT_NUMBERING[k], ...((profile.doc_numbering || {})[k] || {}) },
      ])),
      tva_standard: profile.tva_standard ?? 20,
      tva_panneaux: profile.tva_panneaux ?? 10,
      onee_tarif_kwh: profile.onee_tarif_kwh ?? 1.75,
      productible_kwh_kwc: profile.productible_kwh_kwc ?? 1600,
      discount_approval_threshold: profile.discount_approval_threshold ?? '',
      seuil_regime_declaration_kwc: profile.seuil_regime_declaration_kwc ?? 11,
      seuil_regime_anre_kwc: profile.seuil_regime_anre_kwc ?? 1000,
      rendement_global: profile.rendement_global ?? 0.8,
      panneaux_par_900mad: profile.panneaux_par_900mad ?? 8,
      prix_cible_kwc_defaut: profile.prix_cible_kwc_defaut ?? '',
      remise_max_pct: profile.remise_max_pct ?? '',
      commission_mode: profile.commission_mode ?? 'off',
      commission_valeur: profile.commission_valeur ?? '',
      referral_enabled: profile.referral_enabled ?? false,
      referral_reward: profile.referral_reward ?? '',
      // WR12 — FG28 (SLA) + N105 (DGI) exposés en Paramètres.
      lead_sla_hours: profile.lead_sla_hours ?? 24,
      dgi_export_actif: profile.dgi_export_actif ?? false,
      // XSAL11 — round-robin équilibré des leads entrants (OFF par défaut).
      round_robin_leads_actif: profile.round_robin_leads_actif ?? false,
      round_robin_plafond_leads_ouverts:
        profile.round_robin_plafond_leads_ouverts ?? 20,
      // FG22 — politique de sécurité (défauts inertes).
      password_min_length: profile.password_min_length ?? 8,
      password_require_complexity: profile.password_require_complexity ?? false,
      lockout_max_attempts: profile.lockout_max_attempts ?? 0,
      lockout_duration_minutes: profile.lockout_duration_minutes ?? 15,
      password_expiry_days: profile.password_expiry_days ?? 0,
      // FG26 — rétention RGPD du journal d'audit.
      audit_retention_days: profile.audit_retention_days ?? 0,
      // ZSTK13 — capacités stock (True = comportement actuel inchangé).
      stock_lots_series_actif: profile.stock_lots_series_actif ?? true,
      stock_colisage_actif: profile.stock_colisage_actif ?? true,
      stock_scan_actif: profile.stock_scan_actif ?? true,
    }
    /* eslint-disable react-hooks/set-state-in-effect -- resynchro depuis `profile` */
    setInitialSnapshot(next)
    setForm(next)
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [profile])

  useEffect(() => {
    if (saveSuccess) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSaved(true)
      const t = setTimeout(() => { dispatch(clearSaveSuccess()); setSaved(false) }, 3000)
      return () => clearTimeout(t)
    }
  }, [saveSuccess, dispatch])

  const set = (e) => setForm(p => ({
    ...p,
    // FG22 — gère aussi les cases à cocher (booléens) sans changer le reste.
    [e.target.name]: e.target.type === 'checkbox'
      ? e.target.checked : e.target.value,
  }))
  const setPT = (mode, key, val) => setForm(p => ({
    ...p, payment_terms: { ...p.payment_terms,
      [mode]: { ...p.payment_terms[mode], [key]: val } } }))
  const setPrefix = (key, val) => setForm(p => ({
    ...p, doc_prefixes: { ...p.doc_prefixes, [key]: val } }))
  const setNumbering = (key, field, val) => setForm(p => ({
    ...p, doc_numbering: {
      ...p.doc_numbering,
      [key]: { ...(p.doc_numbering?.[key] || DEFAULT_NUMBERING[key]), [field]: val },
    } }))
  // Aperçu du prochain numéro (L770/L786). Quand le serveur a renvoyé le vrai
  // prochain numéro (séquence réelle la plus haute + 1) ET que les réglages de
  // numérotation N'ONT PAS été modifiés localement (mêmes préfixe/largeur/
  // période que le profil enregistré), on l'affiche tel quel. Dès que l'utilisateur
  // édite un de ces réglages, on retombe sur l'aperçu calculé (au n°1) car le
  // « seau » de numérotation change avec le préfixe/période.
  const numberingUnchanged = (key) => {
    const sp = profile?.doc_prefixes?.[key] ?? DEFAULT_PREFIXES[key]
    const sn = { ...DEFAULT_NUMBERING[key], ...((profile?.doc_numbering || {})[key] || {}) }
    const fp = form.doc_prefixes?.[key] ?? DEFAULT_PREFIXES[key]
    const fn = form.doc_numbering?.[key] || DEFAULT_NUMBERING[key]
    return String(sp) === String(fp)
      && Number(sn.padding) === Number(fn.padding)
      && (sn.reset || 'monthly') === (fn.reset || 'monthly')
  }
  const numberingPreview = (key) => {
    if (numberingNext?.[key] && numberingUnchanged(key)) return numberingNext[key]
    const px = String(form.doc_prefixes?.[key] || DEFAULT_PREFIXES[key] || key)
    const pad = Math.max(1, Number(form.doc_numbering?.[key]?.padding) || 4)
    const reset = form.doc_numbering?.[key]?.reset || 'monthly'
    const now = new Date()
    const yyyy = String(now.getFullYear())
    const mm = String(now.getMonth() + 1).padStart(2, '0')
    const seg = reset === 'yearly' ? yyyy : reset === 'none' ? '' : `${yyyy}${mm}`
    const num = '1'.padStart(pad, '0')
    return seg ? `${px}-${seg}-${num}` : `${px}-${num}`
  }

  const handleSave = (e) => {
    e.preventDefault()
    // L769 — taux de TVA : on PRÉSERVE la valeur tapée (y compris un 0
    // délibéré) et on transmet le vide tel quel (le serveur le rejette avec
    // une erreur claire au lieu d'un re-snap silencieux à 20/10).
    const keepNum = (v) => (v === '' || v == null ? v : Number(v))
    // Coercition douce : pourcentages en nombres ; FK '' → null.
    const pt = {}
    for (const mode of Object.keys(form.payment_terms || {})) {
      const t = form.payment_terms[mode]
      pt[mode] = {
        acompte: Number(t.acompte) || 0,
        materiel: Number(t.materiel) || 0,
        solde: Number(t.solde) || 0,
      }
    }
    // Coercition de la numérotation (D3) : largeur en nombre, période valide.
    const dn = {}
    for (const k of Object.keys(form.doc_numbering || {})) {
      const e = form.doc_numbering[k] || {}
      dn[k] = {
        padding: Math.max(1, Number(e.padding) || 4),
        reset: ['monthly', 'yearly', 'none'].includes(e.reset) ? e.reset : 'monthly',
      }
    }
    const payload = {
      ...form,
      responsable_defaut_leads: form.responsable_defaut_leads === ''
        ? null : form.responsable_defaut_leads,
      default_installer: form.default_installer === ''
        ? null : form.default_installer,
      payment_terms: pt,
      doc_numbering: dn,
      quote_validity_days: Number(form.quote_validity_days) || 30,
      agricole_pump_hours: Number(form.agricole_pump_hours) || 7,
      tva_standard: keepNum(form.tva_standard),
      tva_panneaux: keepNum(form.tva_panneaux),
      onee_tarif_kwh: Number(form.onee_tarif_kwh) || 1.75,
      productible_kwh_kwc: Number(form.productible_kwh_kwc) || 1600,
      discount_approval_threshold: form.discount_approval_threshold === '' ? null : Number(form.discount_approval_threshold),
      seuil_regime_declaration_kwc: Number(form.seuil_regime_declaration_kwc) || 11,
      seuil_regime_anre_kwc: Number(form.seuil_regime_anre_kwc) || 1000,
      rendement_global: Number(form.rendement_global) || 0.8,
      panneaux_par_900mad: Number(form.panneaux_par_900mad) || 8,
      prix_cible_kwc_defaut: form.prix_cible_kwc_defaut === '' ? null : Number(form.prix_cible_kwc_defaut),
      remise_max_pct: form.remise_max_pct === '' ? null : Number(form.remise_max_pct),
      commission_mode: ['off', 'pct_devis', 'par_kwc'].includes(form.commission_mode) ? form.commission_mode : 'off',
      commission_valeur: form.commission_valeur === '' ? null : Number(form.commission_valeur),
      referral_enabled: !!form.referral_enabled,
      referral_reward: form.referral_reward === '' ? null : Number(form.referral_reward),
      // WR12/FG28 — SLA premier contact (heures) : entier ≥ 0, 0 = désactivé.
      lead_sla_hours: Math.max(0, Math.trunc(Number(form.lead_sla_hours) || 0)),
      // XSAL11 — round-robin équilibré des leads entrants.
      round_robin_leads_actif: !!form.round_robin_leads_actif,
      round_robin_plafond_leads_ouverts: Math.max(
        1, Math.trunc(Number(form.round_robin_plafond_leads_ouverts) || 20)),
      // ZSTK13 — capacités stock (booléens simples, jamais désactivées
      // silencieusement).
      stock_lots_series_actif: form.stock_lots_series_actif !== false,
      stock_colisage_actif: form.stock_colisage_actif !== false,
      stock_scan_actif: form.stock_scan_actif !== false,
    }
    // WR12 — réglages SENSIBLES : ne les transmettre que si l'utilisateur est
    // autorisé (admin). Un rôle non autorisé ne les voit pas et ne peut donc
    // pas les modifier ; on les retire du payload par sécurité (défense en
    // profondeur — le backend reste l'autorité).
    if (canManageSensitive) {
      payload.commission_mode = ['off', 'pct_devis', 'par_kwc']
        .includes(form.commission_mode) ? form.commission_mode : 'off'
      payload.commission_valeur = form.commission_valeur === ''
        ? null : Number(form.commission_valeur)
      payload.dgi_export_actif = !!form.dgi_export_actif
    } else {
      delete payload.commission_mode
      delete payload.commission_valeur
      delete payload.dgi_export_actif
    }
    dispatch(saveProfile(payload))
  }

  const accent = form.couleur_principale || '#1d4ed8'
  // Le bouton d'enregistrement du profil n'apparaît que sur les onglets qui
  // portent des champs du profil (les autres réglages s'enregistrent seuls).
  const showSave = ['societe', 'leads', 'devis', 'avance'].includes(tab)

  if (loading) return (
    <div className="flex min-h-[200px] items-center justify-center gap-3 text-sm text-muted-foreground">
      <Spinner className="size-5 text-primary" />
      Chargement…
    </div>
  )

  // Bouton d'enregistrement du profil. Le NOM ACCESSIBLE reste exactement
  // « Enregistrer » (contrat e2e) : pendant l'envoi le bouton est désactivé et
  // affiche un spinner, l'état « Enregistré ! » n'apparaît qu'après succès.
  const saveButton = (
    <Button type="submit" loading={saving} disabled={saving}
      variant={saved ? 'success' : 'default'} className="self-start">
      {saving ? 'Enregistrement…' : saved ? (
        <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
      ) : (
        <><Save className="size-4" aria-hidden="true" /> Enregistrer</>
      )}
    </Button>
  )

  // Tout l'état + tous les handlers passés tels quels aux sections. Chaque
  // section ne destructure que ce dont elle a besoin ; comme le sac contient
  // tout, aucune prop ne peut être oubliée silencieusement.
  const ctx = {
    profile, form, set, setForm, accent, uploading, dispatch,
    canManageSensitive,
    categories, fournisseurs,
    assignables,
    niveaux, setNiveau, saveNiveaux, niveauxSaved, niveauxError, addNiveau, delNiveau, seedNiveaux,
    tags, newTag, setNewTag, addTag, renameTag, delTag, archiveTag, setTagColor,
    motifs, newMotif, setNewMotif, addMotif, renameMotif, delMotif, archiveMotif,
    messages, setMsgField, saveMessage, resetMessage, msgSavedCle,
    canaux, newCanal, setNewCanal, addCanal, renameCanal, delCanal, archiveCanal,
    refLoading,
    typesItv, newType, setNewType, addType, renameType, delType,
    checklistEtapes, newEtape, setNewEtape, addEtape, renameEtape, toggleEtapeActif, delEtape,
    toggleEtapeCapture, moveEtape,
    marques, newMarque, setNewMarque, addMarque, delMarque,
    cfModule, setCfModule, cfDefs, newCf, setNewCf, addCf, delCf, loadCfDefs,
    cfEditId, cfEdit, setCfEdit, openCfEdit, cancelCfEdit, saveCfEdit,
    toggleCfActif, moveCf,
    setPT, setPrefix, setNumbering, numberingPreview,
  }

  // ── L790 — recherche de réglage (saute à l'onglet correspondant). Rendue en
  //    tête de la sidebar (VX35) ; sa logique — searchSettings, jumpToTab — est
  //    inchangée. ──
  const searchBlock = (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input
        type="search" value={search} onChange={e => setSearch(e.target.value)}
        placeholder="Rechercher un réglage (ex. « TVA », « ICE », « relance »)…"
        aria-label="Rechercher un réglage"
        className="pl-9 pr-9"
      />
      {search && (
        <button type="button" onClick={() => setSearch('')}
                aria-label="Effacer la recherche"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
          <X className="size-4" aria-hidden="true" />
        </button>
      )}
      {search.trim().length >= 2 && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-border bg-popover shadow-ui-md">
          {searchResults.length === 0 ? (
            <p className="px-3 py-2.5 text-xs text-muted-foreground">Aucun réglage correspondant.</p>
          ) : (
            searchResults.slice(0, 8).map(({ tab: rt, hits }) => (
              <button key={rt} type="button" onClick={() => jumpToTab(rt)}
                      className="flex w-full flex-col items-start gap-0.5 border-b border-border px-3 py-2 text-left last:border-0 hover:bg-accent">
                <span className="text-sm font-medium text-foreground">{tabLabel(rt)}</span>
                <span className="text-[11px] text-muted-foreground">{hits.slice(0, 4).join(' · ')}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )

  return (
    <TooltipProvider delayDuration={200}>
      <div className="mx-auto max-w-[1100px] p-6">

        {/* ── Titre de page ── */}
        <div className="mb-4">
          <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
            Paramètres de l'entreprise
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Ces informations apparaissent dans l'en-tête de vos devis et factures PDF.
          </p>
        </div>

        {/* ── VX35 — sidebar verticale groupée + colonne de contenu ── */}
        <div className="flex flex-col gap-6 md:flex-row md:items-start">

          <SettingsSidebar
            groups={tabGroups}
            activeTab={tab}
            onSelect={setTab}
            searchSlot={searchBlock}
          />

          <div className="min-w-0 flex-1">

        {/* ── Bandeaux de feedback ── */}
        {saved && (
          <div className="mb-4 flex animate-pop-in items-center gap-2.5 rounded-lg border border-success/30 bg-success/12 px-4 py-2.5">
            <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden="true" />
            <span className="text-sm font-medium text-success">Profil enregistré avec succès.</span>
          </div>
        )}
        {error && !saved && (
          <div className="mb-4 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5">
            <AlertCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
            <span className="text-sm text-destructive">{typeof error === 'string' ? error : JSON.stringify(error)}</span>
          </div>
        )}

        {/* ── VX151 — modèle de sauvegarde annoncé AVANT édition : chaque onglet
              dit s'il s'enregistre via le bouton partagé du bas, via ses
              propres boutons de section, ou s'il n'a rien à enregistrer. ── */}
        <p
          className="mb-4 flex items-center gap-2 text-[13px] text-muted-foreground"
          data-testid="settings-save-hint"
          data-save-model={saveModelForTab(tab)}
        >
          <Info className="size-3.5 shrink-0" aria-hidden="true" />
          {SAVE_MODEL_HINTS[saveModelForTab(tab)]}
        </p>

        {/* ── Formulaire (un seul <form> couvre tous les onglets ; les champs
              masqués restent dans l'état React, donc Enregistrer sauve tout).
              noValidate (ERR28) : la validation HTML5 native (min/max/step) ne
              doit JAMAIS bloquer/snapper une valeur tapée — la coercition douce
              se fait en JS dans handleSave. ── */}
        <form noValidate onSubmit={handleSave} className="flex flex-col gap-[1.1rem]">

          {/* FG16 — onglet « Prise en main » (checklist + rejeu du guide). */}
          {tab === 'onboarding' && <OnboardingSection />}
          {tab === 'societe'  && <SocieteSection {...ctx} />}
          {tab === 'leads'    && <LeadsSection {...ctx} />}
          {tab === 'clients'  && <ClientsSection {...ctx} />}
          {tab === 'devis'    && <DevisSection {...ctx} />}
          {/* D2/N60/N67/N26/N59 — section autonome (textes éditables du devis). */}
          {tab === 'documents' && <DocumentsSection />}
          {/* N64/N65 — section autonome (barème ONEE + ROI/productible). */}
          {tab === 'tarification' && <TarificationSection />}
          {tab === 'stock'    && <StockSection {...ctx} />}
          {/* WR5 — opérations stock avancées + export/sauvegarde (admin). */}
          {tab === 'donnees'  && <DonneesSection />}
          {/* N58 — section autonome (charge & enregistre sa propre config). */}
          {tab === 'statuts'    && <StatutsSection />}
          {/* N52 — section autonome (seuil de sous-performance + auto-ticket SAV). */}
          {tab === 'monitoring' && <MonitoringSection />}
          {/* N74 — éditeur de modèles de checklist par type d'installation. */}
          {tab === 'checklists' && <ChecklistSection />}
          {tab === 'etapes_chantier' && <EtapesChantierSection />}
          {/* F2 — éditeur de kits d'outillage (liste ordonnée d'outils). */}
          {tab === 'kits'       && <KitsSection />}
          {/* F7/F8 — éditeur de la shot list (créneaux photo avant/pendant/après). */}
          {tab === 'shotlist'   && <ShotListSection />}
          {/* N72 / N73 — moteur d'automatisations + approbations. */}
          {tab === 'automatisations' && <AutomatisationsSection />}
          {/* F18/F12/F14/F20 — consignes de sécurité + seuil dépassement + services swappables. */}
          {tab === 'securite'   && <SecuriteTerrainSection />}
          {tab === 'equipe'   && <EquipeSection {...ctx} />}
          {tab === 'messages' && <MessagesSection {...ctx} />}
          {/* N87/N88 — état du compte d'envoi email & capture entrante (autonome). */}
          {tab === 'email'    && <EmailSection />}
          {/* N89 — clés d'API publiques & webhooks signés (section autonome). */}
          {tab === 'api'      && <ApiWebhooksSection />}
          {tab === 'avance'   && <AvanceSection {...ctx} />}
          {/* N96 — double authentification (2FA, opt-in). Section autonome. */}
          {tab === 'securite_compte' && <SecuriteCompteSection />}
          {/* N94 — traductions d'interface éditables par langue (autonome). */}
          {tab === 'traductions' && <TraductionsSection />}
          {/* XPLT23 — registre CNDP + demandes de personnes concernées (autonome). */}
          {tab === 'confidentialite' && <ConfidentialiteSection />}

          {/* Bouton d'enregistrement du profil (onglets porteurs de champs) */}
          {showSave && saveButton}
        </form>

          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}
