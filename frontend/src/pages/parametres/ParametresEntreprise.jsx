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
import './parametres.css'
import { Ic } from './peComponents'
import {
  TABS, DEFAULT_PAYMENT_TERMS, DEFAULT_PREFIXES, DEFAULT_NUMBERING,
} from './peConstants'
import SocieteSection from './SocieteSection'
import LeadsSection from './LeadsSection'
import ClientsSection from './ClientsSection'
import DevisSection from './DevisSection'
import StockSection from './StockSection'
import EquipeSection from './EquipeSection'
import MessagesSection from './MessagesSection'
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
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 12, color: '#64748b' }}>
      <div style={{ width: 22, height: 22, border: '2.5px solid #e2e8f0', borderTopColor: '#1d4ed8', borderRadius: '50%', animation: 'paramSpin 0.7s linear infinite' }}/>
      Chargement…
    </div>
  )

  const saveButton = (
    <button
      type="submit"
      disabled={saving}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        padding: '11px 28px', borderRadius: 10, border: 'none',
        background: saved
          ? 'linear-gradient(135deg,#059669,#10b981)'
          : saving
            ? '#93c5fd'
            : `linear-gradient(135deg, ${accent}, ${accent}cc)`,
        color: '#fff', fontWeight: 700, fontSize: 14,
        cursor: saving ? 'not-allowed' : 'pointer',
        boxShadow: saving || saved ? 'none' : `0 4px 16px ${accent}40`,
        transition: 'background 0.3s, box-shadow 0.3s',
        alignSelf: 'flex-start',
      }}
    >
      {saving ? (
        <><div style={{ width: 15, height: 15, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', animation: 'paramSpin 0.7s linear infinite' }}/> Enregistrement…</>
      ) : saved ? (
        <><Ic size={16} color="#fff" sw={2.5}><polyline points="20 6 9 17 4 12"/></Ic> Enregistré !</>
      ) : (
        <><Ic size={16} color="#fff"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></Ic> Enregistrer</>
      )}
    </button>
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
    <div style={{ padding: '1.5rem', maxWidth: 1100, margin: '0 auto' }}>

      {/* ── Page title ── */}
      <div style={{ marginBottom: '1.1rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>
          Paramètres de l'entreprise
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
          Ces informations apparaissent dans l'en-tête de vos devis et factures PDF.
        </p>
      </div>

      {/* ── Onglets ── */}
      <div className="pe-tabs" role="tablist">
        {TABS.map(t => (
          <button key={t.key} type="button" role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`pe-tab${tab === t.key ? ' pe-tab--active' : ''}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Toast messages ── */}
      {saved && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '11px 16px', borderRadius: 10, marginBottom: '1rem',
          background: '#f0fdf4', border: '1px solid #bbf7d0',
          animation: 'paramSlideDown 0.3s ease',
        }}>
          <Ic size={16} color="#16a34a" sw={2.5}><polyline points="20 6 9 17 4 12"/></Ic>
          <span style={{ fontSize: 13.5, fontWeight: 500, color: '#166534' }}>Profil enregistré avec succès.</span>
        </div>
      )}
      {error && !saved && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '11px 16px', borderRadius: 10, marginBottom: '1rem',
          background: '#fef2f2', border: '1px solid #fecaca',
        }}>
          <Ic size={16} color="#dc2626" sw={2}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></Ic>
          <span style={{ fontSize: 13.5, color: '#b91c1c' }}>{typeof error === 'string' ? error : JSON.stringify(error)}</span>
        </div>
      )}

      {/* ── Formulaire (un seul <form> couvre tous les onglets ; les champs
            masqués restent dans l'état React, donc Enregistrer sauve tout) ── */}
      <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

        {tab === 'societe'  && <SocieteSection {...ctx} />}
        {tab === 'leads'    && <LeadsSection {...ctx} />}
        {tab === 'clients'  && <ClientsSection {...ctx} />}
        {tab === 'devis'    && <DevisSection {...ctx} />}
        {tab === 'stock'    && <StockSection {...ctx} />}
        {tab === 'equipe'   && <EquipeSection {...ctx} />}
        {tab === 'messages' && <MessagesSection {...ctx} />}
        {tab === 'avance'   && <AvanceSection {...ctx} />}

        {/* Bouton d'enregistrement du profil (onglets porteurs de champs) */}
        {showSave && saveButton}
      </form>

      <style>{`
        @keyframes paramSpin     { to { transform: rotate(360deg); } }
        @keyframes paramSlideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @media (max-width: 768px) {
          .param-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}
