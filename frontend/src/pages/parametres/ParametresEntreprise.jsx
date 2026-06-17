import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchProfile, saveProfile,
  uploadLogo, deleteLogo,
  uploadSignature, deleteSignature,
  clearSaveSuccess,
} from '../../features/parametres/store/parametresSlice'
import {
  fetchCategories, createCategorie, updateCategorie, deleteCategorie,
  fetchFournisseurs, createFournisseur, updateFournisseur, deleteFournisseur,
} from '../../features/stock/store/stockSlice'
import { originFrom } from '../../api/origin'
import crmApi from '../../api/crmApi'
import ventesApi from '../../api/ventesApi'
import parametresApi from '../../api/parametresApi'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import customFieldsApi from '../../api/customFieldsApi'
import './parametres.css'

// Défauts métier — miroir des valeurs codées en dur côté serveur. Affichés
// quand le profil n'a encore rien d'enregistré ; sauver = valeurs identiques.
const DEFAULT_PAYMENT_TERMS = {
  residentiel: { acompte: 30, materiel: 60, solde: 10 },
  agricole: { acompte: 30, materiel: 60, solde: 10 },
  industriel: { acompte: 50, materiel: 40, solde: 10 },
}
const DEFAULT_PREFIXES = { devis: 'DEV', facture: 'FAC', avoir: 'AVO', bon_commande: 'BC' }
const MODE_LABELS = { residentiel: 'Résidentiel', agricole: 'Agricole', industriel: 'Industriel / Commercial' }

const ACCEPTED   = ['image/png', 'image/jpeg', 'image/webp']
const MAX_MB     = 2
// Var d'env VIDE = même origine (prod derrière nginx) — surtout ne jamais
// construire new URL('') : c'est ce qui tuait toute la page en production.
const MEDIA_BASE = originFrom(import.meta.env.VITE_API_URL)
const mediaUrl   = (url) => {
  if (!url) return null
  if (MEDIA_BASE) {
    // Dev local : les URLs présignées MinIO utilisent l'hôte Docker interne
    return url
      .replace(/^https?:\/\/minio(:\d+)?/, `${MEDIA_BASE.replace(/:\d+$/, '')}:9000`)
      .replace(/^\//, `${MEDIA_BASE}/`)
  }
  // Prod (même origine) : on garde les chemins relatifs tels quels ; les URLs
  // minio internes ne sont pas joignables du navigateur — pas de réécriture
  // hasardeuse, l'aperçu dégrade proprement (la page, elle, vit).
  return url
}

// ── SVG helper ────────────────────────────────────────────────────────────────
function Ic({ size = 16, color = 'currentColor', sw = 1.8, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, display: 'block' }}>
      {children}
    </svg>
  )
}

// ── Section header ────────────────────────────────────────────────────────────
function SectionTitle({ icon, label, color = '#1d4ed8' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: '1.1rem' }}>
      <div style={{
        width: 30, height: 30, borderRadius: 8,
        background: color + '18',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Ic size={15} color={color} sw={1.8}>{icon}</Ic>
      </div>
      <span style={{ fontSize: 13.5, fontWeight: 700, color: '#1e293b', letterSpacing: '0.01em' }}>
        {label}
      </span>
    </div>
  )
}

// ── Field ─────────────────────────────────────────────────────────────────────
function Field({ label, required, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>
        {label}{required && <span style={{ color: '#ef4444', marginLeft: 2 }}>*</span>}
      </label>
      {children}
    </div>
  )
}

const inputBase = {
  width: '100%', padding: '9px 12px', borderRadius: 9,
  border: '1.5px solid #e2e8f0', fontSize: 13.5, color: '#111827',
  outline: 'none', boxSizing: 'border-box', background: '#f8fafc',
  transition: 'border-color 0.18s, box-shadow 0.18s, background 0.18s',
  fontFamily: 'inherit',
}
const onFocus = e => {
  e.target.style.borderColor = '#1d4ed8'
  e.target.style.boxShadow   = '0 0 0 3px rgba(29,78,216,0.1)'
  e.target.style.background  = '#fff'
}
const onBlur  = e => {
  e.target.style.borderColor = '#e2e8f0'
  e.target.style.boxShadow   = 'none'
  e.target.style.background  = '#f8fafc'
}

// ── Image upload zone ─────────────────────────────────────────────────────────
function UploadZone({ label, hint, currentUrl, onUpload, onDelete, uploading }) {
  const inputRef      = useRef(null)
  const [drag, setDrag] = useState(false)
  const [err,  setErr]  = useState(null)
  const [imgErr, setImgErr] = useState(false)

  const fullUrl = mediaUrl(currentUrl)

  const validate = (file) => {
    if (!ACCEPTED.includes(file.type)) { setErr('Format non supporté (PNG, JPEG, WebP).'); return false }
    if (file.size > MAX_MB * 1024 * 1024) { setErr(`Taille max : ${MAX_MB} Mo.`); return false }
    setErr(null); return true
  }
  const handleFile = (file) => { if (file && validate(file)) { setImgErr(false); onUpload(file) } }
  const handleDrop = (e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: '#374151' }}>{label}</p>

      {/* ── Current image preview ── */}
      {fullUrl && (
        <div style={{ position: 'relative' }}>
          <div style={{
            width: '100%', minHeight: 110, borderRadius: 10,
            border: '1.5px solid #e2e8f0',
            background: 'repeating-linear-gradient(45deg,#f8fafc 0,#f8fafc 8px,#f1f5f9 8px,#f1f5f9 16px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden', padding: 10,
          }}>
            {imgErr ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, color: '#94a3b8' }}>
                <Ic size={28} color="#cbd5e1" sw={1.4}>
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </Ic>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>Aperçu indisponible</span>
              </div>
            ) : (
              <img
                src={fullUrl}
                alt={label}
                onError={() => setImgErr(true)}
                style={{
                  maxHeight: 90, maxWidth: '100%',
                  objectFit: 'contain',
                  borderRadius: 6,
                  filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.12))',
                }}
              />
            )}
          </div>
          {/* Delete button */}
          <button
            type="button" onClick={() => { setImgErr(false); onDelete() }} disabled={uploading}
            style={{
              position: 'absolute', top: -7, right: -7,
              width: 24, height: 24, borderRadius: '50%',
              background: '#ef4444', border: '2px solid #fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', boxShadow: '0 2px 6px rgba(239,68,68,0.4)',
            }}
            title="Supprimer"
          >
            <Ic size={11} color="#fff" sw={2.5}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Ic>
          </button>
        </div>
      )}

      {/* ── Drop zone ── */}
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
        style={{
          border: `1.5px dashed ${drag ? '#1d4ed8' : '#cbd5e1'}`,
          borderRadius: 10, padding: '0.85rem',
          textAlign: 'center', cursor: uploading ? 'default' : 'pointer',
          background: drag ? '#eff6ff' : '#fafafa',
          transition: 'border-color 0.18s, background 0.18s',
        }}
      >
        {uploading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: '#64748b', fontSize: 12.5 }}>
            <div style={{ width: 16, height: 16, border: '2px solid #e2e8f0', borderTopColor: '#1d4ed8', borderRadius: '50%', animation: 'paramSpin 0.7s linear infinite' }}/>
            Téléversement…
          </div>
        ) : (
          <div>
            <Ic size={20} color={drag ? '#1d4ed8' : '#94a3b8'} sw={1.5}>
              <polyline points="16 16 12 12 8 16"/>
              <line x1="12" y1="12" x2="12" y2="21"/>
              <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
            </Ic>
            <p style={{ margin: '5px 0 1px', color: drag ? '#1d4ed8' : '#64748b', fontWeight: 500, fontSize: 12 }}>
              {fullUrl ? 'Remplacer —' : 'Glissez ou'}{' '}
              <span style={{ color: '#1d4ed8', textDecoration: 'underline' }}>parcourez</span>
            </p>
            <span style={{ fontSize: 10.5, color: '#94a3b8' }}>{hint}</span>
          </div>
        )}
      </div>

      <input ref={inputRef} type="file" accept={ACCEPTED.join(',')} style={{ display: 'none' }}
        onChange={e => handleFile(e.target.files[0])}/>
      {err && <p style={{ margin: '2px 0 0', fontSize: 11.5, color: '#ef4444' }}>{err}</p>}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
// ── Référentiel block (Catégories / Fournisseurs) ─────────────────────────────
function ReferentielBlock({ title, color, icon, items, onCreate, onUpdate, onDelete }) {
  const [newName, setNewName]       = useState('')
  const [creating, setCreating]     = useState(false)
  const [editId, setEditId]         = useState(null)
  const [editName, setEditName]     = useState('')
  const [busy, setBusy]             = useState(false)
  const inputRef = useRef(null)
  const editRef  = useRef(null)

  useEffect(() => { if (creating) inputRef.current?.focus() }, [creating])
  useEffect(() => { if (editId !== null) editRef.current?.focus() }, [editId])

  const doCreate = async () => {
    const nom = newName.trim(); if (!nom) return
    setBusy(true)
    try { await onCreate(nom); setNewName(''); setCreating(false) } catch { /* erreur affichée ailleurs */ } finally { setBusy(false) }
  }

  const doUpdate = async () => {
    const nom = editName.trim(); if (!nom) return
    setBusy(true)
    try { await onUpdate(editId, nom); setEditId(null) } catch { /* erreur affichée ailleurs */ } finally { setBusy(false) }
  }

  const doDelete = async (id) => {
    if (!window.confirm('Supprimer ?')) return
    await onDelete(id)
  }

  return (
    <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
      <SectionTitle color={color} label={title} icon={icon}/>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
        {items.length === 0 && (
          <p style={{ margin: 0, fontSize: 12.5, color: '#94a3b8', fontStyle: 'italic' }}>Aucun élément</p>
        )}
        {items.map(item => (
          <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {editId === item.id ? (
              <>
                <input
                  ref={editRef}
                  style={{ ...inputBase, flex: 1, padding: '6px 10px', fontSize: 13 }}
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') doUpdate(); if (e.key === 'Escape') setEditId(null) }}
                />
                <button type="button" className="btn btn-primary" disabled={busy || !editName.trim()}
                  onClick={doUpdate} style={{ padding: '5px 10px', fontSize: 12 }}>
                  {busy ? '…' : 'OK'}
                </button>
                <button type="button" className="btn btn-outline"
                  onClick={() => setEditId(null)} style={{ padding: '5px 8px', fontSize: 12 }}>
                  ✕
                </button>
              </>
            ) : (
              <>
                <span style={{ flex: 1, fontSize: 13, color: '#1e293b', padding: '6px 0' }}>{item.nom}</span>
                <button type="button" onClick={() => { setEditId(item.id); setEditName(item.nom) }}
                  title="Renommer" style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px',
                    color: '#64748b', borderRadius: 6, lineHeight: 1,
                  }}>
                  <Ic size={13} color="#64748b" sw={2}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></Ic>
                </button>
                <button type="button" onClick={() => doDelete(item.id)}
                  title="Supprimer" style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px',
                    color: '#ef4444', borderRadius: 6, lineHeight: 1,
                  }}>
                  <Ic size={13} color="#ef4444" sw={2}><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></Ic>
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      {creating ? (
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            ref={inputRef}
            style={{ ...inputBase, flex: 1, padding: '7px 10px', fontSize: 13 }}
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') doCreate(); if (e.key === 'Escape') { setCreating(false); setNewName('') } }}
            placeholder="Nouveau nom…"
          />
          <button type="button" className="btn btn-primary" disabled={busy || !newName.trim()}
            onClick={doCreate} style={{ padding: '6px 12px', fontSize: 13 }}>
            {busy ? '…' : 'Ajouter'}
          </button>
          <button type="button" className="btn btn-outline"
            onClick={() => { setCreating(false); setNewName('') }} style={{ padding: '6px 10px', fontSize: 13 }}>
            ✕
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setCreating(true)} style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '6px 12px', borderRadius: 8, border: `1.5px dashed ${color}60`,
          background: color + '08', color, fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
        }}>
          <Ic size={13} color={color} sw={2.5}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></Ic>
          Ajouter
        </button>
      )}
    </div>
  )
}

export default function ParametresEntreprise() {
  const dispatch = useDispatch()
  const { profile, loading, saving, uploading, error, saveSuccess } = useSelector(s => s.parametres)
  const { categories, fournisseurs } = useSelector(s => s.stock)

  const [form, setForm] = useState({
    nom: '', adresse: '', email: '', telephone: '',
    siret: '', tva_intra: '', rib: '', banque: '',
    ice: '', identifiant_fiscal: '', rc: '', patente: '', cnss: '',
    couleur_principale: '#1d4ed8',
    responsable_defaut_leads: '',
    payment_terms: DEFAULT_PAYMENT_TERMS,
    quote_validity_days: 30,
    agricole_pump_hours: 7,
    doc_prefixes: DEFAULT_PREFIXES,
    tva_standard: 20,
    tva_panneaux: 10,
    onee_tarif_kwh: 1.75,
    productible_kwh_kwc: 1600,
    discount_approval_threshold: '',
    seuil_regime_declaration_kwc: 11,
    seuil_regime_anre_kwc: 1000,
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
      payment_terms: { ...DEFAULT_PAYMENT_TERMS, ...(profile.payment_terms || {}) },
      quote_validity_days: profile.quote_validity_days ?? 30,
      agricole_pump_hours: profile.agricole_pump_hours ?? 7,
      doc_prefixes: { ...DEFAULT_PREFIXES, ...(profile.doc_prefixes || {}) },
      tva_standard: profile.tva_standard ?? 20,
      tva_panneaux: profile.tva_panneaux ?? 10,
      onee_tarif_kwh: profile.onee_tarif_kwh ?? 1.75,
      productible_kwh_kwc: profile.productible_kwh_kwc ?? 1600,
      discount_approval_threshold: profile.discount_approval_threshold ?? '',
      seuil_regime_declaration_kwc: profile.seuil_regime_declaration_kwc ?? 11,
      seuil_regime_anre_kwc: profile.seuil_regime_anre_kwc ?? 1000,
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
    const payload = {
      ...form,
      responsable_defaut_leads: form.responsable_defaut_leads === ''
        ? null : form.responsable_defaut_leads,
      payment_terms: pt,
      quote_validity_days: Number(form.quote_validity_days) || 30,
      agricole_pump_hours: Number(form.agricole_pump_hours) || 7,
      tva_standard: Number(form.tva_standard) || 20,
      tva_panneaux: Number(form.tva_panneaux) || 10,
      onee_tarif_kwh: Number(form.onee_tarif_kwh) || 1.75,
      productible_kwh_kwc: Number(form.productible_kwh_kwc) || 1600,
      discount_approval_threshold: form.discount_approval_threshold === '' ? null : Number(form.discount_approval_threshold),
      seuil_regime_declaration_kwc: Number(form.seuil_regime_declaration_kwc) || 11,
      seuil_regime_anre_kwc: Number(form.seuil_regime_anre_kwc) || 1000,
    }
    dispatch(saveProfile(payload))
  }

  const accent = form.couleur_principale || '#1d4ed8'

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 12, color: '#64748b' }}>
      <div style={{ width: 22, height: 22, border: '2.5px solid #e2e8f0', borderTopColor: '#1d4ed8', borderRadius: '50%', animation: 'paramSpin 0.7s linear infinite' }}/>
      Chargement…
    </div>
  )

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1100, margin: '0 auto' }}>

      {/* ── Page title ── */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>
          Paramètres de l'entreprise
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
          Ces informations apparaissent dans l'en-tête de vos devis et factures PDF.
        </p>
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

      {/* ── Live preview card ── */}
      <div style={{
        borderRadius: 14, marginBottom: '1.5rem', overflow: 'hidden',
        border: `1px solid ${accent}30`,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}>
        <div style={{
          background: `linear-gradient(135deg, ${accent}12 0%, ${accent}06 100%)`,
          borderBottom: `1px solid ${accent}20`,
          padding: '1rem 1.5rem',
          display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        }}>
          {/* Logo or initials */}
          <div style={{
            width: 52, height: 52, borderRadius: 12, flexShrink: 0,
            background: profile?.logo_url ? 'transparent' : accent + '20',
            border: `1.5px solid ${accent}30`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden',
          }}>
            {mediaUrl(profile?.logo_url)
              ? <img src={mediaUrl(profile.logo_url)} alt="logo" style={{ width: '100%', height: '100%', objectFit: 'contain', padding: 4 }}/>
              : <span style={{ fontSize: 20, fontWeight: 800, color: accent }}>
                  {(form.nom || '?')[0].toUpperCase()}
                </span>
            }
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: accent, letterSpacing: '0.01em' }}>
              {form.nom || 'Nom de votre entreprise'}
            </h3>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>
              {[form.adresse, form.email, form.telephone].filter(Boolean).join(' · ') || 'Adresse · Email · Téléphone'}
            </p>
          </div>

          {/* Color preview */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: accent, boxShadow: `0 0 0 3px ${accent}30` }}/>
            <span style={{ fontSize: 11.5, color: '#64748b', fontFamily: 'monospace' }}>{accent}</span>
          </div>

          <div style={{ padding: '4px 10px', borderRadius: 20, background: accent + '20', border: `1px solid ${accent}30`, fontSize: 11, color: accent, fontWeight: 600 }}>
            Aperçu PDF
          </div>
        </div>
      </div>

      {/* ── Main grid ── */}
      <div className="pe-main">

        {/* ─── LEFT: Form ─── */}
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

          {/* Identité */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#1d4ed8" label="Identité" icon={<><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></>}/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <Field label="Nom de l'entreprise" required>
                <input style={inputBase} name="nom" value={form.nom} onChange={set} onFocus={onFocus} onBlur={onBlur} required placeholder="TAQINOR SARL"/>
              </Field>
              <Field label="Adresse">
                <textarea style={{ ...inputBase, resize: 'vertical', minHeight: 68 }} name="adresse" value={form.adresse} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="12 rue Mohammed V, Casablanca" rows={2}/>
              </Field>
            </div>
          </div>

          {/* Contact */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#059669" label="Coordonnées" icon={<><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.5 2 2 0 0 1 3.6 1.32h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9a16 16 0 0 0 6 6l1.27-.95a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></>}/>
            <div className="pe-grid-2">
              <Field label="Email">
                <input style={inputBase} name="email" type="email" value={form.email} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="contact@entreprise.ma"/>
              </Field>
              <Field label="Téléphone">
                <input style={inputBase} name="telephone" value={form.telephone} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="+212 6 XX XX XX XX"/>
              </Field>
            </div>
          </div>

          {/* Légal */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#7c3aed" label="Informations légales" icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>}/>
            <div className="pe-grid-2">
              <Field label="SIRET">
                <input style={inputBase} name="siret" value={form.siret} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="14 chiffres"/>
              </Field>
              <Field label="N° TVA intracommunautaire">
                <input style={inputBase} name="tva_intra" value={form.tva_intra} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="FR12345678901"/>
              </Field>
              <Field label="RIB / IBAN">
                <input style={inputBase} name="rib" value={form.rib} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="FR76 3000…"/>
              </Field>
              <Field label="Banque">
                <input style={inputBase} name="banque" value={form.banque} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="CIH, Attijariwafa…"/>
              </Field>
            </div>
          </div>

          {/* Identifiants légaux (Maroc) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#0d9488" label="Identifiants légaux (Maroc)" icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              L'ICE, l'IF et le RC apparaissent en pied de page de vos factures (l'ICE est obligatoire au Maroc).
            </p>
            <div className="pe-grid-2">
              <Field label="ICE">
                <input style={inputBase} name="ice" value={form.ice} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="000000000000000"/>
              </Field>
              <Field label="IF (Identifiant Fiscal)">
                <input style={inputBase} name="identifiant_fiscal" value={form.identifiant_fiscal} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="00000000"/>
              </Field>
              <Field label="RC (Registre de Commerce)">
                <input style={inputBase} name="rc" value={form.rc} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="N° RC"/>
              </Field>
              <Field label="Patente / Taxe professionnelle">
                <input style={inputBase} name="patente" value={form.patente} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="N° patente"/>
              </Field>
              <Field label="CNSS">
                <input style={inputBase} name="cnss" value={form.cnss} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="N° affiliation CNSS"/>
              </Field>
            </div>
          </div>

          {/* Leads — responsable par défaut */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#0369a1" label="Leads" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Responsable assigné automatiquement aux nouveaux leads (site web et
              création manuelle) quand aucun responsable n'est choisi.
            </p>
            <Field label="Responsable par défaut des nouveaux leads">
              <select style={inputBase} name="responsable_defaut_leads"
                      value={form.responsable_defaut_leads ?? ''} onChange={set}
                      onFocus={onFocus} onBlur={onBlur}>
                <option value="">— Aucun (laisser non assigné) —</option>
                {assignables.map(u => (
                  <option key={u.id} value={u.id}>
                    {u.username}{u.poste ? ` — ${u.poste}` : ''}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {/* Devis — échéancier, validité, pompage, numérotation */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#1d4ed8" label="Devis" icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Conditions de paiement par marché (acompte / matériel / solde, en %).
              Les factures d'acompte suivent ces valeurs.
            </p>
            {Object.keys(MODE_LABELS).map(mode => (
              <div key={mode} style={{ marginBottom: '0.6rem' }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>{MODE_LABELS[mode]}</div>
                <div className="pe-grid-3">
                  {['acompte', 'materiel', 'solde'].map(k => (
                    <div key={k}>
                      <label style={{ fontSize: 10.5, color: '#64748b', textTransform: 'capitalize' }}>{k} %</label>
                      <input style={inputBase} type="number" min="0" max="100"
                             value={form.payment_terms?.[mode]?.[k] ?? ''}
                             onChange={e => setPT(mode, k, e.target.value)} />
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div className="pe-grid-2" style={{ marginTop: '0.6rem' }}>
              <Field label="Validité du devis (jours)">
                <input style={inputBase} type="number" min="1" name="quote_validity_days"
                       value={form.quote_validity_days} onChange={set} />
              </Field>
              <Field label="Heures de pompage / jour (agricole, défaut)">
                <input style={inputBase} type="number" min="0" step="0.5" name="agricole_pump_hours"
                       value={form.agricole_pump_hours} onChange={set} />
              </Field>
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', margin: '0.8rem 0 0.4rem' }}>
              Préfixes de numérotation
            </div>
            <div className="pe-grid-4">
              {[['devis', 'Devis'], ['facture', 'Facture'], ['avoir', 'Avoir'], ['bon_commande', 'Bon cmd']].map(([k, lbl]) => (
                <div key={k}>
                  <label style={{ fontSize: 10.5, color: '#64748b' }}>{lbl}</label>
                  <input style={inputBase} value={form.doc_prefixes?.[k] ?? ''}
                         onChange={e => setPrefix(k, e.target.value)} />
                </div>
              ))}
            </div>
            <p style={{ margin: '0.6rem 0 0', fontSize: 11, color: '#94a3b8' }}>
              Les numéros déjà émis ne changent pas ; seuls les nouveaux suivent ces préfixes.
            </p>
          </div>

          {/* TVA / Taxes (réglage légal/comptable) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #fde68a', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#b45309" label="TVA / Taxes" icon={<><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#b45309' }}>
              ⚠ Réglage légal/comptable. Les valeurs par défaut (10 % panneaux,
              20 % standard) correspondent à la réforme marocaine. À vérifier
              avec votre comptable avant toute modification.
            </p>
            <div className="pe-grid-2">
              <Field label="Taux standard (%)">
                <input style={inputBase} type="number" min="0" max="100" step="0.01"
                       name="tva_standard" value={form.tva_standard} onChange={set} />
              </Field>
              <Field label="Taux panneaux PV (%)">
                <input style={inputBase} type="number" min="0" max="100" step="0.01"
                       name="tva_panneaux" value={form.tva_panneaux} onChange={set} />
              </Field>
            </div>
          </div>

          {/* ROI — hypothèses (tarif ONEE, productible) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#0e7490" label="Hypothèses ROI" icon={<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Constantes utilisées pour les estimations d'économies/rentabilité.
              Les valeurs par défaut reprennent l'historique du simulateur — rien
              ne change tant que vous ne les modifiez pas.
            </p>
            <div className="pe-grid-2">
              <Field label="Tarif ONEE moyen (MAD/kWh)">
                <input style={inputBase} type="number" min="0" step="0.001"
                       name="onee_tarif_kwh" value={form.onee_tarif_kwh} onChange={set} />
              </Field>
              <Field label="Productible (kWh/kWc/an)">
                <input style={inputBase} type="number" min="0" step="1"
                       name="productible_kwh_kwc" value={form.productible_kwh_kwc} onChange={set} />
              </Field>
              <Field label="Seuil d'approbation de remise (%)">
                <input style={inputBase} type="number" min="0" max="100" step="0.01"
                       name="discount_approval_threshold" placeholder="vide = désactivé"
                       value={form.discount_approval_threshold} onChange={set} />
              </Field>
              <Field label="Seuil régime « Déclaration » (kWc)">
                <input style={inputBase} type="number" min="0" step="0.01"
                       name="seuil_regime_declaration_kwc"
                       value={form.seuil_regime_declaration_kwc} onChange={set} />
              </Field>
              <Field label="Seuil régime « Autorisation ANRE » (kWc)">
                <input style={inputBase} type="number" min="0" step="0.01"
                       name="seuil_regime_anre_kwc"
                       value={form.seuil_regime_anre_kwc} onChange={set} />
              </Field>
            </div>
            <p style={{ margin: '0.5rem 0 0', fontSize: 11, color: '#94a3b8' }}>
              Seuils loi 82-21 proposés à la création d'un chantier (régime
              suggéré, modifiable) : sous le 1er seuil = Déclaration, entre les
              deux = Accord de raccordement, au-dessus du 2nd = Autorisation ANRE.
            </p>
            <p style={{ margin: '0.5rem 0 0', fontSize: 11, color: '#94a3b8' }}>
              Au-delà de ce seuil de remise, un devis exige l'approbation d'un
              administrateur avant l'envoi. Vide = désactivé (défaut).
            </p>
          </div>

          {/* CRM — Étiquettes & motifs de perte (listes gérées) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#7c3aed" label="CRM — Étiquettes & motifs" icon={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Étiquettes et motifs de perte proposés sur les leads. Le texte
              libre reste possible ; les leads existants ne changent pas.
            </p>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>Étiquettes</div>
            {tags.map(t => (
              <div key={t.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <input style={{ ...inputBase, flex: 1 }} defaultValue={t.nom}
                       onBlur={e => renameTag(t, e.target.value)} />
                <button type="button" onClick={() => delTag(t)}
                        style={{ border: '1px solid #fca5a5', color: '#ef4444', background: '#fff', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}>✕</button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
              <input style={{ ...inputBase, flex: 1 }} placeholder="Nouvelle étiquette" value={newTag}
                     onChange={e => setNewTag(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }} />
              <button type="button" onClick={addTag}
                      style={{ border: 'none', background: '#7c3aed', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>Motifs de perte</div>
            {motifs.map(m => (
              <div key={m.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <input style={{ ...inputBase, flex: 1 }} defaultValue={m.nom}
                       onBlur={e => renameMotif(m, e.target.value)} />
                <button type="button" onClick={() => delMotif(m)}
                        style={{ border: '1px solid #fca5a5', color: '#ef4444', background: '#fff', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}>✕</button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6 }}>
              <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau motif" value={newMotif}
                     onChange={e => setNewMotif(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMotif() } }} />
              <button type="button" onClick={addMotif}
                      style={{ border: 'none', background: '#7c3aed', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
          </div>

          {/* CRM — Canaux / sources de lead (liste gérée, site_web protégé) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#0891b2" label="CRM — Canaux / sources" icon={<><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Sources d'où viennent les leads. « Site web » est protégé (utilisé
              par le formulaire du site) et ne peut être ni renommé ni supprimé.
              Un canal déjà utilisé par des leads ne peut pas être supprimé.
            </p>
            {canaux.map(c => (
              <div key={c.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <input style={{ ...inputBase, flex: 1 }} defaultValue={c.libelle}
                       onBlur={e => renameCanal(c, e.target.value)} />
                {c.protege
                  ? <span style={{ fontSize: 10, color: '#0891b2', fontWeight: 600 }}>protégé</span>
                  : (
                    <button type="button" onClick={() => delCanal(c)}
                            disabled={c.en_usage > 0}
                            title={c.en_usage > 0 ? `${c.en_usage} lead(s) utilisent ce canal` : 'Supprimer'}
                            style={{ border: 'none', background: c.en_usage > 0 ? '#e2e8f0' : '#fee2e2', color: c.en_usage > 0 ? '#94a3b8' : '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: c.en_usage > 0 ? 'not-allowed' : 'pointer' }}>✕</button>
                  )}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6 }}>
              <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau canal" value={newCanal}
                     onChange={e => setNewCanal(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCanal() } }} />
              <button type="button" onClick={addCanal}
                      style={{ border: 'none', background: '#0891b2', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
          </div>

          {/* Chantiers — Types d'intervention (liste gérée) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#0d9488" label="Chantiers — Types d'intervention" icon={<><path d="M14.7 6.3a4 4 0 0 0-5.6 5.6l-6 6 2 2 6-6a4 4 0 0 0 5.6-5.6l-2.5 2.5-2-2 2.5-2.5z"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Types d'intervention proposés sur les chantiers. Les types système
              sont protégés ; un type déjà utilisé ne peut pas être supprimé.
            </p>
            {typesItv.map(t => (
              <div key={t.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <input style={{ ...inputBase, flex: 1 }} defaultValue={t.libelle}
                       onBlur={e => renameType(t, e.target.value)} />
                {t.protege
                  ? <span style={{ fontSize: 10, color: '#0d9488', fontWeight: 600 }}>système</span>
                  : (
                    <button type="button" onClick={() => delType(t)}
                            disabled={t.en_usage > 0}
                            style={{ border: 'none', background: t.en_usage > 0 ? '#e2e8f0' : '#fee2e2', color: t.en_usage > 0 ? '#94a3b8' : '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: t.en_usage > 0 ? 'not-allowed' : 'pointer' }}>✕</button>
                  )}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6 }}>
              <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau type" value={newType}
                     onChange={e => setNewType(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addType() } }} />
              <button type="button" onClick={addType}
                      style={{ border: 'none', background: '#0d9488', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
          </div>

          {/* Chantiers — Étapes de checklist d'exécution (N4) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#2563eb" label="Chantiers — Checklist d'exécution" icon={<><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Étapes proposées sur la checklist des chantiers. Désactivez une
              étape pour la retirer des nouveaux chantiers sans toucher aux
              chantiers existants ; les étapes système sont protégées.
            </p>
            {checklistEtapes.map(et => (
              <div key={et.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <input style={{ ...inputBase, flex: 1, opacity: et.actif ? 1 : 0.5 }} defaultValue={et.libelle}
                       onBlur={e => renameEtape(et, e.target.value)} />
                {et.capture_serie && <span style={{ fontSize: 10, color: '#2563eb' }} title="Saisie de n° de série">série</span>}
                <button type="button" onClick={() => toggleEtapeActif(et)}
                        title={et.actif ? 'Désactiver' : 'Activer'}
                        style={{ border: 'none', background: et.actif ? '#dcfce7' : '#e2e8f0', color: et.actif ? '#15803d' : '#64748b', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>
                  {et.actif ? 'Actif' : 'Inactif'}
                </button>
                {et.protege
                  ? <span style={{ fontSize: 10, color: '#2563eb', fontWeight: 600 }}>système</span>
                  : (
                    <button type="button" onClick={() => delEtape(et)}
                            style={{ border: 'none', background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>✕</button>
                  )}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6 }}>
              <input style={{ ...inputBase, flex: 1 }} placeholder="Nouvelle étape" value={newEtape}
                     onChange={e => setNewEtape(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEtape() } }} />
              <button type="button" onClick={addEtape}
                      style={{ border: 'none', background: '#2563eb', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
          </div>

          {/* Stock — Marques (liste gérée) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#b45309" label="Stock — Marques" icon={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Marques proposées sur les produits (ajout libre possible). Une
              marque utilisée par des produits ne peut pas être supprimée.
            </p>
            {marques.map(m => (
              <div key={m.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <input style={{ ...inputBase, flex: 1 }} defaultValue={m.nom} readOnly />
                <button type="button" onClick={() => delMarque(m)}
                        disabled={m.en_usage > 0}
                        title={m.en_usage > 0 ? `${m.en_usage} produit(s)` : 'Supprimer'}
                        style={{ border: 'none', background: m.en_usage > 0 ? '#e2e8f0' : '#fee2e2', color: m.en_usage > 0 ? '#94a3b8' : '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: m.en_usage > 0 ? 'not-allowed' : 'pointer' }}>✕</button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6 }}>
              <input style={{ ...inputBase, flex: 1 }} placeholder="Nouvelle marque" value={newMarque}
                     onChange={e => setNewMarque(e.target.value)}
                     onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMarque() } }} />
              <button type="button" onClick={addMarque}
                      style={{ border: 'none', background: '#b45309', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
          </div>

          {/* Champs personnalisés (T11) */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#9333ea" label="Champs personnalisés" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Ajoutez vos propres champs aux fiches (leads, clients, produits).
              Ils apparaissent dans le formulaire ; rien n'est perdu si vous en
              retirez un.
            </p>
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              <select className="form-control" style={{ maxWidth: 140 }} value={cfModule}
                      onChange={e => { setCfModule(e.target.value); loadCfDefs(e.target.value) }}>
                <option value="lead">Leads</option>
                <option value="client">Clients</option>
                <option value="produit">Produits</option>
              </select>
            </div>
            {cfDefs.map(d => (
              <div key={d.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
                <span style={{ flex: 1, fontSize: 13 }}>{d.libelle}</span>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>{d.type}</span>
                <button type="button" onClick={() => delCf(d)}
                        style={{ border: 'none', background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>✕</button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <input style={{ ...inputBase, flex: '1 1 140px' }} placeholder="Libellé du champ"
                     value={newCf.libelle} onChange={e => setNewCf(c => ({ ...c, libelle: e.target.value }))} />
              <select className="form-control" style={{ maxWidth: 120 }} value={newCf.type}
                      onChange={e => setNewCf(c => ({ ...c, type: e.target.value }))}>
                <option value="text">Texte</option>
                <option value="number">Nombre</option>
                <option value="date">Date</option>
                <option value="choice">Choix</option>
                <option value="boolean">Oui/Non</option>
              </select>
              {newCf.type === 'choice' && (
                <input style={{ ...inputBase, flex: '1 1 160px' }} placeholder="Options (a, b, c)"
                       value={newCf.options} onChange={e => setNewCf(c => ({ ...c, options: e.target.value }))} />
              )}
              <button type="button" onClick={addCf}
                      style={{ border: 'none', background: '#9333ea', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
            </div>
          </div>

          {/* Niveaux de relance */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#dc2626" label="Niveaux de relance" icon={<><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Seuils de retard (en jours) pour relancer les factures impayées.
              Vue / consigne / impression uniquement — aucun envoi automatique.
            </p>
            {niveaux.map(n => (
              <div key={n.id} className="pe-grid-relance" style={{ marginBottom: '0.6rem' }}>
                <Field label={`Niveau ${n.ordre}`}>
                  <input style={inputBase} value={n.nom}
                         onChange={e => setNiveau(n.id, 'nom', e.target.value)} />
                </Field>
                <Field label="Jours (J+)">
                  <input style={inputBase} type="number" min="0" value={n.delai_jours}
                         onChange={e => setNiveau(n.id, 'delai_jours', e.target.value)} />
                </Field>
              </div>
            ))}
            {niveaux.length === 0 && (
              <p style={{ fontSize: 12, color: '#94a3b8' }}>Aucun niveau configuré.</p>
            )}
            <button type="button" onClick={saveNiveaux}
                    style={{ marginTop: 4, padding: '8px 18px', borderRadius: 8, border: 'none', background: niveauxSaved ? '#10b981' : '#dc2626', color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
              {niveauxSaved ? 'Niveaux enregistrés ✓' : 'Enregistrer les niveaux'}
            </button>
          </div>

          {/* Messages WhatsApp */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#16a34a" label="Messages WhatsApp" icon={<><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.38 8.38 0 0 1-4-1L3 21l1-5.5a8.38 8.38 0 0 1-1-4A8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              Modèles du message « Envoyer par WhatsApp » (devis, facture,
              rappel). Variantes Français et Darija. Placeholders disponibles :
              {' '}<code>{'{civilite}'}</code> <code>{'{nom}'}</code>{' '}
              <code>{'{reference}'}</code> <code>{'{lien}'}</code>{' '}
              <code>{'{n}'}</code>. Le lien envoyé est public, en lecture seule,
              expire après 30 jours et ne montre que le PDF client.
            </p>
            {messages.map(m => (
              <div key={m.cle} style={{ borderTop: '1px solid #f1f5f9', paddingTop: 10, marginTop: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
                  {m.label}
                  {m.placeholders?.length > 0 && (
                    <span style={{ fontWeight: 400, color: '#94a3b8', marginLeft: 6 }}>
                      ({m.placeholders.join(' ')})
                    </span>
                  )}
                </div>
                <Field label="Français">
                  <textarea style={{ ...inputBase, minHeight: 54, resize: 'vertical' }}
                            value={m.corps_fr}
                            onChange={e => setMsgField(m.cle, 'corps_fr', e.target.value)} />
                </Field>
                <Field label="Darija (laisser vide = utiliser le Français)">
                  <textarea style={{ ...inputBase, minHeight: 54, resize: 'vertical' }}
                            value={m.corps_darija}
                            onChange={e => setMsgField(m.cle, 'corps_darija', e.target.value)} />
                </Field>
                <button type="button" onClick={() => saveMessage(m)}
                        style={{ marginTop: 2, padding: '6px 14px', borderRadius: 8, border: 'none', background: msgSavedCle === m.cle ? '#10b981' : '#16a34a', color: '#fff', fontWeight: 600, fontSize: 12.5, cursor: 'pointer' }}>
                  {msgSavedCle === m.cle ? 'Enregistré ✓' : 'Enregistrer'}
                </button>
              </div>
            ))}
            {messages.length === 0 && (
              <p style={{ fontSize: 12, color: '#94a3b8' }}>Chargement…</p>
            )}
          </div>

          {/* Couleur PDF */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#ea580c" label="Apparence PDF" icon={<><circle cx="12" cy="12" r="10"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></>}/>
            <Field label="Couleur principale">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ position: 'relative', flexShrink: 0 }}>
                  <input
                    type="color" name="couleur_principale" value={form.couleur_principale} onChange={set}
                    style={{ width: 46, height: 42, borderRadius: 9, border: '1.5px solid #e2e8f0', cursor: 'pointer', padding: 3, background: '#fff' }}
                  />
                </div>
                <input
                  style={{ ...inputBase, width: 130, fontFamily: 'monospace' }}
                  name="couleur_principale" value={form.couleur_principale} onChange={set}
                  onFocus={onFocus} onBlur={onBlur} placeholder="#1d4ed8"
                />
                <div style={{
                  flex: 1, height: 42, borderRadius: 9,
                  background: `linear-gradient(135deg, ${accent}, ${accent}99)`,
                  border: `1.5px solid ${accent}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <span style={{ fontSize: 11.5, color: '#fff', fontWeight: 600, textShadow: '0 1px 2px rgba(0,0,0,0.3)' }}>
                    Aperçu
                  </span>
                </div>
              </div>
            </Field>
          </div>

          {/* Save button */}
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
        </form>

        {/* ─── RIGHT: Media ─── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

          {/* Logo */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#1d4ed8" label="Logo de l'entreprise" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>}/>
            <UploadZone
              label="Affiché en en-tête du PDF"
              hint="PNG, JPEG, WebP — max 2 Mo"
              currentUrl={profile?.logo_url}
              onUpload={f => dispatch(uploadLogo(f))}
              onDelete={() => dispatch(deleteLogo())}
              uploading={uploading}
            />
          </div>

          {/* Signature */}
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
            <SectionTitle color="#7c3aed" label="Signature électronique" icon={<><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></>}/>
            <UploadZone
              label="Apposée en bas du PDF"
              hint="PNG, JPEG, WebP — max 2 Mo"
              currentUrl={profile?.signature_url}
              onUpload={f => dispatch(uploadSignature(f))}
              onDelete={() => dispatch(deleteSignature())}
              uploading={uploading}
            />
          </div>

          {/* PDF info */}
          <div style={{
            borderRadius: 12, padding: '0.9rem 1.1rem',
            background: `linear-gradient(135deg, ${accent}08, ${accent}14)`,
            border: `1px solid ${accent}25`,
            display: 'flex', gap: 10, alignItems: 'flex-start',
          }}>
            <Ic size={16} color={accent} sw={1.8}>
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </Ic>
            <p style={{ margin: 0, fontSize: 12.5, color: accent, lineHeight: 1.5 }}>
              <strong>Aperçu PDF :</strong> le logo, la signature et les informations ci-contre apparaissent automatiquement dans l'en-tête et le pied de page de tous vos devis et factures.
            </p>
          </div>
        </div>
      </div>

      {/* ── Référentiels Stock ── */}
      <div className="pe-grid-2" style={{ marginTop: '1.5rem' }}>
        <ReferentielBlock
          title="Catégories produit"
          color="#1d4ed8"
          icon={<><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></>}
          items={categories}
          onCreate={nom => dispatch(createCategorie({ nom })).unwrap()}
          onUpdate={(id, nom) => dispatch(updateCategorie({ id, data: { nom } })).unwrap()}
          onDelete={id => dispatch(deleteCategorie(id)).unwrap()}
        />
        <ReferentielBlock
          title="Fournisseurs"
          color="#059669"
          icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}
          items={fournisseurs}
          onCreate={nom => dispatch(createFournisseur({ nom })).unwrap()}
          onUpdate={(id, nom) => dispatch(updateFournisseur({ id, data: { nom } })).unwrap()}
          onDelete={id => dispatch(deleteFournisseur(id)).unwrap()}
        />
      </div>

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
