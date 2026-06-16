import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { updateInstallation } from '../../features/installations/store/installationsSlice'
import { fetchProduits } from '../../features/stock/store/stockSlice'
import installationsApi from '../../api/installationsApi'
import savApi from '../../api/savApi'
import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  INTERVENTION_TYPES,
} from '../../features/installations/statuses'
import { garantieLabel, garantieColor } from '../../features/sav/equipement'
import {
  TICKET_TYPES,
  TICKET_STATUS_LABELS,
  SOUS_GARANTIE_LABELS,
  statusColor as ticketStatusColor,
} from '../../features/sav/ticketStatuses'
import ChecklistPanel from './ChecklistPanel'
import PhaseGallery from './PhaseGallery'
import ChantierTimeline from './ChantierTimeline'
import './chantier-detail.css'

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "à l'instant"
  if (mins < 60) return `il y a ${mins} min`
  const h = Math.round(mins / 60)
  if (h < 24) return `il y a ${h} h`
  return new Date(iso).toLocaleDateString('fr-FR')
}

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

export default function InstallationDetail({ installation, onClose, onSaved }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const id = installation.id

  // État local éditable + version courante (rafraîchie après interventions).
  const [current, setCurrent] = useState(installation)
  const F = (k, d = '') => current?.[k] ?? d
  const [fields, setFields] = useState({
    statut: F('statut', 'a_planifier'),
    site_adresse: F('site_adresse'),
    site_ville: F('site_ville'),
    date_pose_prevue: F('date_pose_prevue'),
    date_pose_reelle: F('date_pose_reelle'),
    puissance_installee_kwc: F('puissance_installee_kwc'),
    notes: F('notes'),
  })
  const set = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  // Historique (chatter)
  const [historique, setHistorique] = useState([])
  const [noteBody, setNoteBody] = useState('')

  // Intervention en cours d'ajout
  const [interv, setInterv] = useState({ type_intervention: '', date_prevue: '', compte_rendu: '' })
  const [intervBusy, setIntervBusy] = useState(false)

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
  const [equip, setEquip] = useState({ produit: '', numero_serie: '', date_pose: '' })
  const [equipBusy, setEquipBusy] = useState(false)
  const [tickets, setTickets] = useState([])
  const [newTicket, setNewTicket] = useState({ type: 'correctif', description: '', equipement: '' })
  const [ticketBusy, setTicketBusy] = useState(false)

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

  useEffect(() => {
    loadHistorique()
    loadEquipements()
    loadTickets()
    if (produits.length === 0) dispatch(fetchProduits())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

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
      setEquip({ produit: '', numero_serie: '', date_pose: '' })
      loadEquipements()
    } catch { /* erreur silencieuse */ } finally { setEquipBusy(false) }
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
      loadTickets()
    } catch { /* erreur silencieuse */ } finally { setTicketBusy(false) }
  }

  const refreshInstallation = async () => {
    try {
      const r = await installationsApi.getInstallation(id)
      setCurrent(r.data)
    } catch { /* erreur silencieuse */ }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      const data = Object.fromEntries(
        Object.entries(fields).map(([k, v]) => [k, nullable(v)]))
      await dispatch(updateInstallation({ id, data })).unwrap()
      onSaved?.()
    } catch (err) {
      setSaveError(typeof err === 'object' ? JSON.stringify(err) : String(err))
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
      await refreshInstallation()
      loadHistorique()
    } catch { /* erreur silencieuse */ } finally { setIntervBusy(false) }
  }

  const saveMes = async () => {
    setMesBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined) ? null : v
      const data = Object.fromEntries(
        Object.entries(mes).map(([k, v]) => [k, nullable(v)]))
      await installationsApi.miseEnService(id, data)
      onSaved?.()
    } catch { /* erreur silencieuse */ } finally { setMesBusy(false) }
  }

  const annuler = async () => {
    const motif = window.prompt('Motif d\'annulation du chantier ?')
    if (motif === null) return
    try {
      await installationsApi.annuler(id, motif)
      onSaved?.()
    } catch { /* erreur silencieuse */ }
  }

  const reactiver = async () => {
    try {
      await installationsApi.reactiver(id)
      onSaved?.()
    } catch { /* erreur silencieuse */ }
  }

  const interventions = current.interventions ?? []

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-xl" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            Chantier — {current.reference ?? ''}
            {current.annule && <span className="lead-archived-badge">Annulé</span>}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {current.annule && (
            <div className="form-error-box" role="alert">
              <strong>Chantier annulé.</strong>
              {current.motif_annulation ? ` Motif : ${current.motif_annulation}` : ''}
              {' '}
              <button type="button" className="btn btn-sm btn-outline" onClick={reactiver}>
                Réactiver
              </button>
            </div>
          )}

          {/* ── Liens ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🔗 Liens</span>
            </div>
            <div className="actions-cell">
              {current.devis && (
                <button type="button" className="btn btn-sm btn-outline"
                        onClick={() => navigate('/ventes/devis')}>
                  Voir le devis{current.devis_reference ? ` (${current.devis_reference})` : ''}
                </button>
              )}
              {current.client && (
                <button type="button" className="btn btn-sm btn-outline"
                        onClick={() => navigate('/crm')}>
                  Voir le client
                </button>
              )}
              {current.lead && (
                <button type="button" className="btn btn-sm btn-outline"
                        onClick={() => navigate('/crm/leads')}>
                  Voir le lead
                </button>
              )}
            </div>
          </div>

          {/* ── Infos & édition ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🏗️ Chantier</span>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Référence</label>
                <input className="form-control" value={current.reference ?? '—'} readOnly />
              </div>
              <div className="form-group">
                <label className="form-label">Raccordement</label>
                <input className="form-control" value={current.raccordement_display ?? '—'} readOnly />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <input className="form-control" value={current.type_installation_display ?? '—'} readOnly />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Client</label>
                <input className="form-control" value={current.client_nom ?? '—'} readOnly />
              </div>
              <div className="form-group">
                <label className="form-label">Devis</label>
                <input className="form-control" value={current.devis_reference ?? '—'} readOnly />
              </div>
              <div className="form-group">
                <label className="form-label">Technicien</label>
                <input className="form-control" value={current.technicien_nom ?? '—'} readOnly />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Statut</label>
                <select className="form-select" value={fields.statut ?? ''}
                        onChange={e => set('statut', e.target.value)}>
                  {INSTALLATION_STATUSES.map(k => (
                    <option key={k} value={k}>{STATUS_LABELS[k]}</option>
                  ))}
                </select>
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Adresse du site</label>
                <input className="form-control" value={fields.site_adresse ?? ''}
                       onChange={e => set('site_adresse', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Ville</label>
                <input className="form-control" value={fields.site_ville ?? ''}
                       onChange={e => set('site_ville', e.target.value)} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Pose prévue le</label>
                <input type="date" className="form-control" value={fields.date_pose_prevue ?? ''}
                       onChange={e => set('date_pose_prevue', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Pose réelle le</label>
                <input type="date" className="form-control" value={fields.date_pose_reelle ?? ''}
                       onChange={e => set('date_pose_reelle', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Puissance installée (kWc)</label>
                <input type="number" step="any" className="form-control"
                       value={fields.puissance_installee_kwc ?? ''}
                       onChange={e => set('puissance_installee_kwc', e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea className="form-control" rows={2} value={fields.notes ?? ''}
                        onChange={e => set('notes', e.target.value)} />
            </div>
            {saveError && <div className="form-error-box" role="alert">{saveError}</div>}
          </div>

          {/* ── Timeline (N5) ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">📆 Chronologie</span>
            </div>
            <ChantierTimeline installation={current} />
          </div>

          {/* ── Checklist d'exécution (N3) ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">✅ Checklist d'exécution</span>
            </div>
            <ChecklistPanel installationId={id} onChange={refreshInstallation} />
          </div>

          {/* ── Photos par phase (N4) ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🖼️ Photos (Avant / Pendant / Après)</span>
            </div>
            <PhaseGallery installationId={id} />
          </div>

          {/* ── Interventions ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🛠️ Interventions</span>
            </div>
            {interventions.length === 0 ? (
              <p className="gen-hint">Aucune intervention.</p>
            ) : (
              <table className="lines-table">
                <thead>
                  <tr>
                    <th>Type</th><th>Prévue</th><th>Réalisée</th><th>Technicien</th><th>Compte rendu</th>
                  </tr>
                </thead>
                <tbody>
                  {interventions.map(iv => (
                    <tr key={iv.id}>
                      <td>{iv.type_intervention_display ?? iv.type_intervention}</td>
                      <td>{formatDateFR(iv.date_prevue)}</td>
                      <td>{formatDateFR(iv.date_realisee)}</td>
                      <td>{iv.technicien_nom ?? '—'}</td>
                      <td>{iv.compte_rendu ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="form-row" style={{ marginTop: 10 }}>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-select" value={interv.type_intervention}
                        onChange={e => setInterv(s => ({ ...s, type_intervention: e.target.value }))}>
                  <option value="">—</option>
                  {INTERVENTION_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Date prévue</label>
                <input type="date" className="form-control" value={interv.date_prevue}
                       onChange={e => setInterv(s => ({ ...s, date_prevue: e.target.value }))} />
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Compte rendu</label>
                <input className="form-control" value={interv.compte_rendu}
                       onChange={e => setInterv(s => ({ ...s, compte_rendu: e.target.value }))} />
              </div>
              <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                <button type="button" className="btn btn-outline"
                        disabled={intervBusy || !interv.type_intervention}
                        onClick={addIntervention}>
                  Ajouter une intervention
                </button>
              </div>
            </div>
          </div>

          {/* ── Équipements (parc) ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">📦 Équipements</span>
            </div>
            {equipements.length === 0 ? (
              <p className="gen-hint">Aucun équipement enregistré sur ce chantier.</p>
            ) : (
              <table className="lines-table">
                <thead>
                  <tr><th>Produit</th><th>N° série</th><th>Posé le</th><th>Garantie</th></tr>
                </thead>
                <tbody>
                  {equipements.map(eq => (
                    <tr key={eq.id}>
                      <td>{eq.produit_nom ?? '—'}{eq.produit_marque ? ` (${eq.produit_marque})` : ''}</td>
                      <td>{eq.numero_serie ?? '—'}</td>
                      <td>{formatDateFR(eq.date_pose)}</td>
                      <td><span style={{ color: garantieColor(eq), fontSize: 12, fontWeight: 600 }}>
                        {garantieLabel(eq)}
                      </span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="form-row" style={{ marginTop: 10 }}>
              <div className="form-group fg-grow">
                <label className="form-label">Produit</label>
                <select className="form-select" value={equip.produit}
                        onChange={e => setEquip(s => ({ ...s, produit: e.target.value }))}>
                  <option value="">— Choisir un produit —</option>
                  {produits.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.nom}{p.marque ? ` (${p.marque})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">N° de série</label>
                <input className="form-control" value={equip.numero_serie}
                       onChange={e => setEquip(s => ({ ...s, numero_serie: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Date de pose</label>
                <input type="date" className="form-control" value={equip.date_pose}
                       onChange={e => setEquip(s => ({ ...s, date_pose: e.target.value }))} />
              </div>
              <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                <button type="button" className="btn btn-outline"
                        disabled={equipBusy || !equip.produit} onClick={addEquipement}>
                  Ajouter l'équipement
                </button>
              </div>
            </div>
          </div>

          {/* ── Tickets SAV ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🎫 Tickets SAV</span>
            </div>
            {tickets.length === 0 ? (
              <p className="gen-hint">Aucun ticket SAV sur ce chantier.</p>
            ) : (
              <table className="lines-table">
                <thead>
                  <tr><th>Référence</th><th>Statut</th><th>Type</th><th>Garantie</th></tr>
                </thead>
                <tbody>
                  {tickets.map(t => (
                    <tr key={t.id}>
                      <td>{t.reference}{t.annule ? ' (annulé)' : ''}</td>
                      <td><span style={{ color: ticketStatusColor(t.statut), fontWeight: 600 }}>
                        {TICKET_STATUS_LABELS[t.statut] ?? t.statut}
                      </span></td>
                      <td>{t.type_display ?? t.type}</td>
                      <td>{SOUS_GARANTIE_LABELS[t.sous_garantie_effectif] ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="gen-hint" style={{ marginTop: 6 }}>
              Le suivi détaillé (interventions, historique) se fait dans l'écran « Tickets SAV ».
            </p>
            <div className="form-row" style={{ marginTop: 10 }}>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-select" value={newTicket.type}
                        onChange={e => setNewTicket(s => ({ ...s, type: e.target.value }))}>
                  {TICKET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Équipement concerné</label>
                <select className="form-select" value={newTicket.equipement}
                        onChange={e => setNewTicket(s => ({ ...s, equipement: e.target.value }))}>
                  <option value="">— Aucun —</option>
                  {equipements.map(eq => (
                    <option key={eq.id} value={eq.id}>
                      {(eq.produit_nom ?? 'Produit')} — {eq.numero_serie ?? 'sans n° série'}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Description</label>
                <input className="form-control" value={newTicket.description}
                       onChange={e => setNewTicket(s => ({ ...s, description: e.target.value }))}
                       placeholder="Symptôme / demande" />
              </div>
              <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                <button type="button" className="btn btn-outline"
                        disabled={ticketBusy} onClick={openTicket}>
                  Ouvrir un ticket
                </button>
              </div>
            </div>
          </div>

          {/* ── Mise en service ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">⚡ Mise en service</span>
            </div>
            {current.date_mise_en_service && (
              <p className="gen-hint">
                Mise en service enregistrée le {formatDateFR(current.date_mise_en_service)}.
              </p>
            )}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Date de mise en service</label>
                <input type="date" className="form-control" value={mes.date_mise_en_service ?? ''}
                       onChange={e => setMes(s => ({ ...s, date_mise_en_service: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Production test</label>
                <input type="number" step="any" className="form-control"
                       value={mes.mes_production_test ?? ''}
                       onChange={e => setMes(s => ({ ...s, mes_production_test: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Tension</label>
                <input type="number" step="any" className="form-control"
                       value={mes.mes_tension ?? ''}
                       onChange={e => setMes(s => ({ ...s, mes_tension: e.target.value }))} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Notes / PV</label>
              <textarea className="form-control" rows={2} value={mes.mes_pv_notes ?? ''}
                        onChange={e => setMes(s => ({ ...s, mes_pv_notes: e.target.value }))} />
            </div>
            <button type="button" className="btn btn-success" disabled={mesBusy} onClick={saveMes}>
              Enregistrer la mise en service
            </button>
          </div>

          {/* ── Historique (chatter) ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🕐 Historique</span>
            </div>
            <div className="chatter-note-box">
              <input className="form-control" placeholder="Écrire une note…"
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
          </div>
        </div>

        <div className="modal-footer">
          {!current.annule && (
            <button type="button" className="btn btn-danger" onClick={annuler}>
              Annuler le chantier
            </button>
          )}
          <button type="button" className="btn btn-outline" onClick={onClose}>
            Fermer
          </button>
          <button type="button" className="btn btn-primary" disabled={saving} onClick={handleSave}>
            {saving ? 'Enregistrement...' : 'Mettre à jour'}
          </button>
        </div>
      </div>
    </div>
  )
}
