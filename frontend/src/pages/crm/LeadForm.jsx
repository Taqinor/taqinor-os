import { useEffect, useState } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { createLead, updateLead } from '../../features/crm/store/crmSlice'
import api from '../../api/axios'

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
const Sec = ({ title, children }) => (
  <div className="form-section">
    <div className="form-section-header">
      <span className="form-section-title">{title}</span>
    </div>
    {children}
  </div>
)

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

export default function LeadForm({ lead = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const isEdit = !!lead

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
    relance_date: F('relance_date'), type_installation: F('type_installation', '') ?? '',
    // Énergie
    facture_hiver: F('facture_hiver'), facture_ete: F('facture_ete'),
    ete_differente: lead?.ete_differente ?? false,
    conso_mensuelle_kwh: F('conso_mensuelle_kwh'), tranche_onee: F('tranche_onee'),
    raccordement: F('raccordement', '') ?? '',
    regularisation_8221: lead?.regularisation_8221 ?? false,
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

  useEffect(() => {
    api.get('/users/').then(r => setUsers(r.data.results ?? r.data)).catch(() => {})
    if (isEdit) {
      api.get(`/crm/leads/${lead.id}/historique/`)
        .then(r => setHistorique(r.data)).catch(() => {})
    }
  }, [isEdit, lead?.id])

  const set = (k, v) => setFields(f => ({ ...f, [k]: v }))

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
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-body">
            <Sec title="👤 Contact">
              <div className="form-row">
                <div className="form-group fg-grow">
                  <label className="form-label">Nom <span className="req">*</span></label>
                  <input className={`form-control${errors.nom ? ' is-invalid' : ''}`}
                         value={fields.nom} onChange={e => set('nom', e.target.value)} />
                  {errors.nom && <div className="form-feedback">{errors.nom}</div>}
                </div>
                <Txt fields={fields} set={set} k="prenom" label="Prénom" />
                <Txt fields={fields} set={set} k="societe" label="Société" />
              </div>
              <div className="form-row">
                <Txt fields={fields} set={set} k="telephone" label="Téléphone" />
                <Txt fields={fields} set={set} k="whatsapp" label="WhatsApp" />
                <Txt fields={fields} set={set} k="email" label="Email" type="email" />
              </div>
              <div className="form-row">
                <div className="form-group fg-grow"><Txt fields={fields} set={set} k="adresse" label="Adresse" /></div>
                <Txt fields={fields} set={set} k="ville" label="Ville / quartier" />
                <Txt fields={fields} set={set} k="gps_lat" label="GPS lat." type="number" />
                <Txt fields={fields} set={set} k="gps_lng" label="GPS long." type="number" />
              </div>
            </Sec>

            <Sec title="📈 Pipeline">
              <div className="form-row">
                <Sel fields={fields} set={set} k="stage" label="Étape" labels={STAGE_LABELS} />
                <div className="form-group">
                  <label className="form-label">Responsable</label>
                  <select className="form-select" value={fields.owner ?? ''}
                          onChange={e => set('owner', e.target.value)}>
                    <option value="">—</option>
                    {users.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
                  </select>
                </div>
                <Sel fields={fields} set={set} k="canal" label="Canal" labels={CANAUX} />
                <Sel fields={fields} set={set} k="priorite" label="Priorité" labels={PRIORITES} />
              </div>
              <div className="form-row">
                <Sel fields={fields} set={set} k="type_installation" label="Type d'installation" labels={TYPES_INSTALLATION} />
                <Txt fields={fields} set={set} k="relance_date" label="Relance le" type="date" />
                <div className="form-group fg-grow">
                  <Txt fields={fields} set={set} k="tags" label="Tags (séparés par des virgules)"
                       placeholder="ex: Régularisation 82-21, VIP" />
                </div>
                <Txt fields={fields} set={set} k="motif_perte" label="Motif de perte" />
              </div>
            </Sec>

            <Sec title="💡 Énergie">
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

            <Sec title="🏠 Toiture & site">
              <div className="form-row">
                <Sel fields={fields} set={set} k="type_toiture" label="Type de toiture" labels={TYPES_TOITURE} />
                <Txt fields={fields} set={set} k="surface_toiture_m2" label="Surface (m²)" type="number" />
                <Sel fields={fields} set={set} k="orientation" label="Orientation" labels={ORIENTATIONS} />
                <Txt fields={fields} set={set} k="inclinaison_deg" label="Inclinaison (°)" type="number" />
              </div>
              <div className="form-row">
                <Sel fields={fields} set={set} k="ombrage" label="Ombrage" labels={OMBRAGES} />
                <div className="form-group fg-grow">
                  <Txt fields={fields} set={set} k="ombrage_notes" label="Notes ombrage" />
                </div>
                <Txt fields={fields} set={set} k="nb_etages" label="Étages / hauteur" type="number" />
              </div>
              <div className="form-row">
                <Sel fields={fields} set={set} k="structure_pref" label="Structure" labels={STRUCTURES} />
                <Txt fields={fields} set={set} k="taille_souhaitee_kwc" label="Taille souhaitée (kWc)" type="number" />
                <Sel fields={fields} set={set} k="batterie_souhaitee" label="Batterie" labels={BATTERIES} />
              </div>
            </Sec>

            <Sec title="📋 Visite technique">
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
              <Sec title={`📄 Devis de ce lead${lead.client_nom ? ` — client : ${lead.client_nom}` : ''}`}>
                {(lead.devis ?? []).length === 0 ? (
                  <p className="gen-hint">Aucun devis pour ce lead.</p>
                ) : (
                  <table className="lines-table">
                    <thead>
                      <tr><th>Référence</th><th>Statut</th><th className="col-num">Total TTC</th><th>Créé le</th></tr>
                    </thead>
                    <tbody>
                      {lead.devis.map(d => (
                        <tr key={d.id} style={{ cursor: 'pointer' }}
                            onClick={() => navigate('/ventes/devis')}>
                          <td><strong>{d.reference}</strong></td>
                          <td>{STATUT_DEVIS[d.statut] ?? d.statut}</td>
                          <td className="ta-right">
                            {Math.round(parseFloat(d.total_ttc)).toLocaleString('fr-MA')} DH
                          </td>
                          <td>{new Date(d.date_creation).toLocaleDateString('fr-FR')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Sec>
            )}

            {/* ── Historique (chatter) ── */}
            {isEdit && (
              <Sec title="🕐 Historique">
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
    </div>
  )
}
