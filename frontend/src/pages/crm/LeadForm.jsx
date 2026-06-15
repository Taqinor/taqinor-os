import { useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { createLead, updateLead, archiveLead, restoreLead } from '../../features/crm/store/crmSlice'
import api from '../../api/axios'
import crmApi from '../../api/crmApi'
import Avatar from '../../components/Avatar'
import AssigneePicker from '../../components/AssigneePicker'
import '../../components/assigneepicker.css'
import ActivitiesPanel from '../../components/ActivitiesPanel'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import '../../components/records-panels.css'
import LeadDevisPanel from './leads/LeadDevisPanel'
import './leads/leaddevispanel.css'
import './leadform-extra.css'

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

const CANAUX = {
  meta_ads: 'Publicité Meta', whatsapp_ctwa: 'WhatsApp/CTWA',
  site_web: 'Site web', reference: 'Référence', telephone: 'Téléphone',
  walk_in: 'Visite/Walk-in', autre: 'Autre',
}
const PRIORITES = { basse: 'Basse', normale: 'Normale', haute: 'Haute' }
const TYPES_INSTALLATION = {
  residentiel: 'Résidentiel', commercial: 'Commercial',
  industriel: 'Industriel', agricole: 'Agricole',
}
const RACCORDEMENTS = { monophase: 'Monophasé', triphase: 'Triphasé' }
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
const buildNavSections = ({ agricole, isEdit }) => {
  const secs = [
    ['contact', 'Contact'],
    ['pipeline', 'Suivi commercial'],
    ['energie', 'Profil énergétique'],
  ]
  if (agricole) secs.push(['pompage', 'Pompage'])
  secs.push(['toiture', 'Toiture & site'], ['visite', 'Visite'])
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

export default function LeadForm({ lead = null, onClose, onSaved, initialDevis = null }) {
  const dispatch = useDispatch()
  const isEdit = !!lead

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

  const toggleWaSelect = (id) => setWaSelected(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })

  const leadPhone = (liveLead?.whatsapp || liveLead?.telephone || '').trim()

  const envoyerWhatsApp = async () => {
    if (!leadPhone) return
    if (waSelected.size === 0) {
      alert('Sélectionnez au moins un devis.')
      return
    }
    setWaBusy(true)
    try {
      const res = await crmApi.whatsappDevis(lead.id, {
        devis_ids: Array.from(waSelected),
      })
      if (res.data?.wa_url) window.open(res.data.wa_url, '_blank', 'noopener')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    } finally {
      setWaBusy(false)
    }
  }

  // Doublons probables (fusion sans perte).
  const [dups, setDups] = useState([])
  // Listes gérées (suggestions ; le texte libre reste possible).
  const [tagOptions, setTagOptions] = useState([])
  const [motifOptions, setMotifOptions] = useState([])

  // Édition inline de la facture (enregistre CE champ seul, sans le formulaire).
  const [billEditing, setBillEditing] = useState(false)
  const [billSaving, setBillSaving] = useState(false)
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
    canal: F('canal', '') ?? '', priorite: F('priorite', 'normale'),
    tags: F('tags'), motif_perte: F('motif_perte'),
    perdu: lead?.perdu ?? false,
    relance_date: F('relance_date'), type_installation: F('type_installation', '') ?? '',
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
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [activeSec, setActiveSec] = useState('contact')
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
    } catch { /* silencieux */ }
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

  // Après création/édition d'un devis dans le panneau : on recharge le lead
  // (liste des devis à jour) et on prévient le parent (liste/kanban).
  const refreshLead = () => {
    if (!isEdit) return
    crmApi.getLead(lead.id)
      .then(r => setLiveLead(r.data)).catch(() => {})
    onSaved?.()
  }

  // ── Édition inline de la facture (enregistre CE seul champ) ──
  const startBillEdit = () => {
    setBillHiver(liveLead?.facture_hiver != null ? String(liveLead.facture_hiver) : '')
    setBillEte(liveLead?.facture_ete != null ? String(liveLead.facture_ete) : '')
    setBillEditing(true)
  }
  const saveBill = async () => {
    setBillSaving(true)
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
    } catch {
      /* erreur silencieuse — la valeur reste éditable */
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
    try {
      const r = await api.post(`/crm/leads/${lead.id}/noter/`, { body })
      setHistorique(h => [r.data, ...h])
      setNoteBody('')
    } catch { /* erreur silencieuse, la note reste saisie */ }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!fields.nom.trim()) { setErrors({ nom: 'Nom requis' }); return }
    setSaving(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      const payload = Object.fromEntries(
        Object.entries(fields).map(([k, v]) => [k, typeof v === 'boolean' ? v : nullable(v)]))
      // bascule OFF → la valeur unique vaut hiver ET été
      if (!fields.ete_differente) payload.facture_ete = null
      if (isEdit) {
        await dispatch(updateLead({ id: lead.id, data: payload })).unwrap()
      } else {
        await dispatch(createLead(payload)).unwrap()
      }
      onSaved?.()
      onClose()
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
              <button
                type="button"
                className="btn btn-sm btn-outline"
                disabled={archiveBusy}
                onClick={toggleArchive}
              >
                {lead.is_archived ? 'Restaurer' : 'Archiver'}
              </button>
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
                  <input type="number" step="any" className="form-control form-control-sm lead-bill-input"
                         placeholder={liveLead?.ete_differente ? 'Hiver' : 'MAD/mois'}
                         value={billHiver} autoFocus
                         onChange={e => setBillHiver(e.target.value)} />
                  {liveLead?.ete_differente && (
                    <input type="number" step="any" className="form-control form-control-sm lead-bill-input"
                           placeholder="Été" value={billEte}
                           onChange={e => setBillEte(e.target.value)} />
                  )}
                  <button type="button" className="btn btn-sm btn-primary"
                          disabled={billSaving} onClick={saveBill}>
                    {billSaving ? '…' : 'Enregistrer'}
                  </button>
                  <button type="button" className="btn btn-sm btn-outline"
                          onClick={() => setBillEditing(false)}>Annuler</button>
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
            </div>

            <div className="lead-subbar-devis">
              <button type="button" className="btn btn-sm gen-btn-orange"
                      disabled={!devisReady}
                      title={devisReady ? 'Créer le devis automatique (affiché ici)' : devisNotReadyMsg}
                      onClick={() => openDevisPanel('auto')}>
                ⚡ Devis automatique
              </button>
              <div className="lead-devis-menu-wrap" ref={devisMenuRef}>
                <button type="button" className="btn btn-sm btn-primary"
                        onClick={() => setDevisMenuOpen(o => !o)}>
                  📝 Devis modifiable ▾
                </button>
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
              {buildNavSections({ agricole, isEdit }).map(([id, label]) => (
                <button key={id} type="button"
                        className={activeSec === id ? 'active' : ''}
                        onClick={() => jumpTo(id)}>
                  {label}
                </button>
              ))}
            </nav>
          <div className="modal-body" ref={bodyRef} onScroll={onBodyScroll}>
            <Sec id="contact" title="👤 Contact">
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
                <Txt fields={fields} set={set} k="email" label="Email" type="email" />
              </div>
              <div className="form-row">
                <Txt fields={fields} set={set} k="societe" label="Société" />
                <div className="form-group fg-grow"><Txt fields={fields} set={set} k="adresse" label="Adresse" /></div>
                <Txt fields={fields} set={set} k="gps_lat" label="GPS lat." type="number" />
                <Txt fields={fields} set={set} k="gps_lng" label="GPS long." type="number" />
              </div>
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
                <Sel fields={fields} set={set} k="priorite" label="Priorité" labels={PRIORITES} />
                <Sel fields={fields} set={set} k="canal" label="Canal" labels={CANAUX} />
                <div className="form-group fg-grow">
                  <Txt fields={fields} set={set} k="tags" label="Tags (séparés par des virgules)"
                       placeholder="ex: Régularisation 82-21, VIP" list="ld-tags" />
                  <datalist id="ld-tags">
                    {tagOptions.map(t => <option key={t.id} value={t.nom} />)}
                  </datalist>
                </div>
              </div>
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
                    <Txt fields={fields} set={set} k="motif_perte" label="Motif de perte" list="ld-motifs" />
                    <datalist id="ld-motifs">
                      {motifOptions.map(m => <option key={m.id} value={m.nom} />)}
                    </datalist>
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
            </Sec>

            <div className="form-group">
              <label className="form-label">Note générale</label>
              <textarea className="form-control" rows={2} value={fields.note ?? ''}
                        onChange={e => set('note', e.target.value)} />
            </div>

            {/* ── Devis empilés ── */}
            {isEdit && (
              <Sec id="devis" title={`📄 Devis de ce lead${liveLead?.client_nom ? ` — client : ${liveLead.client_nom}` : ''}`}>
                {(liveLead?.devis ?? []).length === 0 ? (
                  <p className="gen-hint">Aucun devis pour ce lead.</p>
                ) : (
                  <>
                    <div style={{ margin: '8px 0', display: 'flex', alignItems: 'center' }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={!leadPhone || waBusy || waSelected.size === 0}
                        title={leadPhone
                          ? 'Ouvrir WhatsApp avec le(s) devis sélectionné(s)'
                          : 'Aucun numéro de téléphone'}
                        onClick={envoyerWhatsApp}>
                        🟢 Envoyer par WhatsApp{waSelected.size > 0 ? ` (${waSelected.size})` : ''}
                      </button>
                      {!leadPhone && (
                        <span className="gen-hint" style={{ marginLeft: 8 }}>
                          Aucun numéro de téléphone
                        </span>
                      )}
                    </div>
                    <table className="lines-table">
                      <thead>
                        <tr><th></th><th>Référence</th><th>Statut</th><th className="col-num">Total TTC</th><th>Créé le</th><th></th></tr>
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
                              {Math.round(parseFloat(d.total_ttc)).toLocaleString('fr-MA')} DH
                            </td>
                            <td>{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                            <td className="ta-right">📄 PDF</td>
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
                            <button type="button" className="btn btn-sm btn-primary"
                                    onClick={() => doMerge(d.id)}>
                              Fusionner ici
                            </button>
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
                  <button type="button" className="btn btn-outline" onClick={postNote}>
                    Noter
                  </button>
                </div>
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
                      <span className="chatter-meta">
                        — par {a.user_nom ?? '?'} · {timeAgo(a.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </Sec>
            )}

            {errors.submit && <div className="form-error-box">{errors.submit}</div>}
          </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Enregistrement...' : (isEdit ? 'Mettre à jour' : 'Créer le lead')}
            </button>
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
    </div>
  )
}
