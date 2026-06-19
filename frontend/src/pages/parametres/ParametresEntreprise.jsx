import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
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
import { CheckCircle2, AlertCircle, Save } from 'lucide-react'
import {
  Button, Spinner, Tabs, TabsList, TabsTrigger, TooltipProvider,
} from '../../ui'
import {
  TABS, DEFAULT_PAYMENT_TERMS, DEFAULT_PREFIXES, DEFAULT_NUMBERING,
} from './peConstants'
import SocieteSection from './SocieteSection'
import LeadsSection from './LeadsSection'
import ClientsSection from './ClientsSection'
import DevisSection from './DevisSection'
import DocumentsSection from './DocumentsSection'
import TarificationSection from './TarificationSection'
import StockSection from './StockSection'
import StatutsSection from './StatutsSection'
import ChecklistSection from './ChecklistSection'
import KitsSection from './KitsSection'
import ShotListSection from './ShotListSection'
import AutomatisationsSection from './AutomatisationsSection'
import EquipeSection from './EquipeSection'
import MessagesSection from './MessagesSection'
import EmailSection from './EmailSection'
import AvanceSection from './AvanceSection'

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

  // Onglet actif (D1). Société & identité par défaut.
  const [tab, setTab] = useState('societe')

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
  })
  const [saved, setSaved] = useState(false)
  const [assignables, setAssignables] = useState([])
  const [niveaux, setNiveaux] = useState([])
  const [niveauxSaved, setNiveauxSaved] = useState(false)
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
  const loadCanaux = () => crmApi.getCanaux()
    .then(r => setCanaux(r.data.results ?? r.data)).catch(() => {})
  const loadTypesItv = () => installationsApi.getTypesIntervention()
    .then(r => setTypesItv(r.data.results ?? r.data)).catch(() => {})
  const loadChecklistEtapes = () => installationsApi.getChecklistEtapes()
    .then(r => setChecklistEtapes(r.data.results ?? r.data)).catch(() => {})
  const loadMarques = () => stockApi.getMarques()
    .then(r => setMarques(r.data.results ?? r.data)).catch(() => {})
  // Champs personnalisés (T11) — module choisi (lead/client/produit).
  const [cfModule, setCfModule] = useState('lead')
  const [cfDefs, setCfDefs] = useState([])
  const [newCf, setNewCf] = useState({ libelle: '', type: 'text', options: '' })
  const loadCfDefs = (mod) => customFieldsApi.getDefs(mod)
    .then(r => setCfDefs(r.data.results ?? r.data)).catch(() => {})
  const slugifyCode = (s) => s.trim().toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50)
  const addCf = async () => {
    const libelle = newCf.libelle.trim()
    if (!libelle) return
    try {
      await customFieldsApi.saveDef(null, {
        module: cfModule, code: slugifyCode(libelle), libelle, type: newCf.type,
        options: newCf.type === 'choice'
          ? newCf.options.split(',').map(o => o.trim()).filter(Boolean) : null,
      })
      setNewCf({ libelle: '', type: 'text', options: '' })
      loadCfDefs(cfModule)
    } catch (e) { alert(e?.response?.data?.detail ?? 'Ajout impossible.') }
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
  const loadMotifs = () => crmApi.getMotifsPerte()
    .then(r => setMotifs(r.data.results ?? r.data)).catch(() => {})
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
  }, [dispatch])

  const addEtape = async () => {
    const libelle = newEtape.trim()
    if (!libelle) return
    try {
      await installationsApi.saveChecklistEtape(null, {
        cle: slugify(libelle), libelle, ordre: checklistEtapes.length })
      setNewEtape(''); loadChecklistEtapes()
    } catch (e) { alert(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameEtape = async (et, libelle) => {
    try { await installationsApi.saveChecklistEtape(et.id, { libelle }) } catch { /* */ }
  }
  const toggleEtapeActif = async (et) => {
    try { await installationsApi.saveChecklistEtape(et.id, { actif: !et.actif }); loadChecklistEtapes() }
    catch { /* */ }
  }
  const delEtape = async (et) => {
    if (!window.confirm(`Supprimer l'étape « ${et.libelle} » ?`)) return
    try { await installationsApi.deleteChecklistEtape(et.id); loadChecklistEtapes() }
    catch (e) { alert(e?.response?.data?.detail ?? 'Suppression impossible (étape protégée ?).') }
  }

  const addCanal = async () => {
    const libelle = newCanal.trim()
    if (!libelle) return
    try {
      await crmApi.saveCanal(null, { cle: slugify(libelle), libelle })
      setNewCanal(''); loadCanaux()
    } catch (e) { alert(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameCanal = async (c, libelle) => {
    try { await crmApi.saveCanal(c.id, { libelle }) } catch { /* */ }
  }
  const delCanal = async (c) => {
    if (!window.confirm(`Supprimer le canal « ${c.libelle} » ?`)) return
    try { await crmApi.deleteCanal(c.id); loadCanaux() }
    catch (e) { alert(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  const addType = async () => {
    const libelle = newType.trim()
    if (!libelle) return
    try {
      await installationsApi.saveTypeIntervention(null, { cle: slugify(libelle), libelle })
      setNewType(''); loadTypesItv()
    } catch (e) { alert(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameType = async (t, libelle) => {
    try { await installationsApi.saveTypeIntervention(t.id, { libelle }) } catch { /* */ }
  }
  const delType = async (t) => {
    if (!window.confirm(`Supprimer le type « ${t.libelle} » ?`)) return
    try { await installationsApi.deleteTypeIntervention(t.id); loadTypesItv() }
    catch (e) { alert(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  const addMarque = async () => {
    const nom = newMarque.trim()
    if (!nom) return
    try { await stockApi.saveMarque(null, { nom }); setNewMarque(''); loadMarques() }
    catch (e) { alert(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const delMarque = async (m) => {
    if (!window.confirm(`Supprimer la marque « ${m.nom} » ?`)) return
    try { await stockApi.deleteMarque(m.id); loadMarques() }
    catch (e) { alert(e?.response?.data?.detail ?? 'Suppression impossible.') }
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
      alert(e?.response?.data?.detail ?? 'Enregistrement impossible.')
    }
  }

  const addTag = async () => {
    const nom = newTag.trim()
    if (!nom) return
    try { await crmApi.saveTag(null, { nom }); setNewTag(''); loadTags() } catch { /* */ }
  }
  const renameTag = async (t, nom) => {
    try { await crmApi.saveTag(t.id, { nom }) } catch { /* */ }
  }
  const delTag = async (t) => {
    if (!window.confirm(`Supprimer l'étiquette « ${t.nom} » ?`)) return
    try { await crmApi.deleteTag(t.id); loadTags() } catch { /* */ }
  }
  const addMotif = async () => {
    const nom = newMotif.trim()
    if (!nom) return
    try { await crmApi.saveMotifPerte(null, { nom }); setNewMotif(''); loadMotifs() } catch { /* */ }
  }
  const renameMotif = async (m, nom) => {
    try { await crmApi.saveMotifPerte(m.id, { nom }) } catch { /* */ }
  }
  const delMotif = async (m) => {
    if (!window.confirm(`Supprimer le motif « ${m.nom} » ?`)) return
    try { await crmApi.deleteMotifPerte(m.id); loadMotifs() } catch { /* */ }
  }

  const setNiveau = (id, key, val) =>
    setNiveaux(ns => ns.map(n => (n.id === id ? { ...n, [key]: val } : n)))

  const saveNiveaux = async () => {
    try {
      await Promise.all(niveaux.map(n => ventesApi.saveNiveauRelance(n.id, {
        nom: n.nom, delai_jours: Number(n.delai_jours) || 0,
        ordre: n.ordre, message: n.message || '',
      })))
      setNiveauxSaved(true)
      setTimeout(() => setNiveauxSaved(false), 3000)
      loadNiveaux()
    } catch { /* silencieux */ }
  }

  useEffect(() => {
    // Synchronisation du formulaire avec le profil chargé depuis le store
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (profile) setForm({
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
    })
  }, [profile])

  useEffect(() => {
    if (saveSuccess) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSaved(true)
      const t = setTimeout(() => { dispatch(clearSaveSuccess()); setSaved(false) }, 3000)
      return () => clearTimeout(t)
    }
  }, [saveSuccess, dispatch])

  const set = (e) => setForm(p => ({ ...p, [e.target.name]: e.target.value }))
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
  // Aperçu du prochain numéro (côté écran) selon le préfixe/largeur/période.
  const numberingPreview = (key) => {
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
      tva_standard: Number(form.tva_standard) || 20,
      tva_panneaux: Number(form.tva_panneaux) || 10,
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
    categories, fournisseurs,
    assignables,
    niveaux, setNiveau, saveNiveaux, niveauxSaved,
    tags, newTag, setNewTag, addTag, renameTag, delTag,
    motifs, newMotif, setNewMotif, addMotif, renameMotif, delMotif,
    messages, setMsgField, saveMessage, msgSavedCle,
    canaux, newCanal, setNewCanal, addCanal, renameCanal, delCanal,
    typesItv, newType, setNewType, addType, renameType, delType,
    checklistEtapes, newEtape, setNewEtape, addEtape, renameEtape, toggleEtapeActif, delEtape,
    marques, newMarque, setNewMarque, addMarque, delMarque,
    cfModule, setCfModule, cfDefs, newCf, setNewCf, addCf, delCf, loadCfDefs,
    setPT, setPrefix, setNumbering, numberingPreview,
  }

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

        {/* ── Onglets (primitif Tabs, défilable sur mobile) ── */}
        <Tabs value={tab} onValueChange={setTab} className="mb-5">
          <TabsList className="pe-tabs-scroll flex w-full justify-start overflow-x-auto">
            {TABS.map(t => (
              <TabsTrigger key={t.key} value={t.key} className="shrink-0">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

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

        {/* ── Formulaire (un seul <form> couvre tous les onglets ; les champs
              masqués restent dans l'état React, donc Enregistrer sauve tout) ── */}
        <form onSubmit={handleSave} className="flex flex-col gap-[1.1rem]">

          {tab === 'societe'  && <SocieteSection {...ctx} />}
          {tab === 'leads'    && <LeadsSection {...ctx} />}
          {tab === 'clients'  && <ClientsSection {...ctx} />}
          {tab === 'devis'    && <DevisSection {...ctx} />}
          {/* D2/N60/N67/N26/N59 — section autonome (textes éditables du devis). */}
          {tab === 'documents' && <DocumentsSection />}
          {/* N64/N65 — section autonome (barème ONEE + ROI/productible). */}
          {tab === 'tarification' && <TarificationSection />}
          {tab === 'stock'    && <StockSection {...ctx} />}
          {/* N58 — section autonome (charge & enregistre sa propre config). */}
          {tab === 'statuts'    && <StatutsSection />}
          {/* N74 — éditeur de modèles de checklist par type d'installation. */}
          {tab === 'checklists' && <ChecklistSection />}
          {/* F2 — éditeur de kits d'outillage (liste ordonnée d'outils). */}
          {tab === 'kits'       && <KitsSection />}
          {/* F7/F8 — éditeur de la shot list (créneaux photo avant/pendant/après). */}
          {tab === 'shotlist'   && <ShotListSection />}
          {/* N72 / N73 — moteur d'automatisations + approbations. */}
          {tab === 'automatisations' && <AutomatisationsSection />}
          {tab === 'equipe'   && <EquipeSection {...ctx} />}
          {tab === 'messages' && <MessagesSection {...ctx} />}
          {/* N87/N88 — état du compte d'envoi email & capture entrante (autonome). */}
          {tab === 'email'    && <EmailSection />}
          {tab === 'avance'   && <AvanceSection {...ctx} />}

          {/* Bouton d'enregistrement du profil (onglets porteurs de champs) */}
          {showSave && saveButton}
        </form>
      </div>
    </TooltipProvider>
  )
}
