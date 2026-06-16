import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchTickets, updateTicket } from '../../features/sav/store/ticketsSlice'
import savApi from '../../api/savApi'
import api from '../../api/axios'
import installationsApi from '../../api/installationsApi'
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
  statusColor,
} from '../../features/sav/ticketStatuses'
import ExportButton from '../../components/ExportButton'

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

function StatutBadge({ statut }) {
  const c = statusColor(statut)
  return (
    <span className="badge" style={{
      background: `${c}22`, color: c, padding: '2px 8px', borderRadius: 6,
      fontSize: 12, whiteSpace: 'nowrap',
    }}>{statusLabel(statut)}</span>
  )
}

function GarantieIndicator({ value }) {
  const color = value === 'oui' ? '#16a34a' : value === 'non' ? '#dc2626' : '#64748b'
  return (
    <span className="badge" style={{
      background: `${color}22`, color, padding: '2px 8px', borderRadius: 6, fontSize: 12,
    }}>Sous garantie : {SOUS_GARANTIE_LABELS[value] ?? value}</span>
  )
}

function TicketDetail({ ticket, onClose, onSaved }) {
  const dispatch = useDispatch()
  const id = ticket.id
  const [current, setCurrent] = useState(ticket)
  const F = (k, d = '') => current?.[k] ?? d

  const [fields, setFields] = useState({
    statut: F('statut', 'nouveau'),
    type: F('type', 'correctif'),
    priorite: F('priorite', 'normale'),
    description: F('description'),
    sous_garantie: F('sous_garantie', 'a_determiner'),
    equipement: current.equipement ?? '',
    technicien_responsable: current.technicien_responsable ?? '',
    date_resolution: F('date_resolution'),
    cout: F('cout'),
  })
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  const [equipements, setEquipements] = useState([])
  const [users, setUsers] = useState([])
  const [interventions, setInterventions] = useState([])
  const [interv, setInterv] = useState({ type_intervention: 'depannage', date_prevue: '', compte_rendu: '' })
  const [intervBusy, setIntervBusy] = useState(false)

  const [historique, setHistorique] = useState([])
  const [noteBody, setNoteBody] = useState('')

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
    // Équipements du chantier concerné (pour lier l'équipement précis).
    if (current.installation) {
      savApi.getEquipements({ installation: current.installation })
        .then((r) => setEquipements(r.data?.results ?? r.data ?? [])).catch(() => {})
    }
    // Liste des techniciens — best effort (réservé admin) ; sinon dropdown vide.
    api.get('/users/').then((r) => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const save = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      const data = {
        statut: fields.statut,
        type: fields.type,
        priorite: fields.priorite,
        description: nullable(fields.description),
        sous_garantie: fields.sous_garantie,
        equipement: fields.equipement === '' ? null : fields.equipement,
        technicien_responsable: fields.technicien_responsable === '' ? null : fields.technicien_responsable,
        date_resolution: nullable(fields.date_resolution),
        cout: nullable(fields.cout),
      }
      const updated = await dispatch(updateTicket({ id, data })).unwrap()
      setCurrent(updated)
      loadHistorique()
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
      const r = await savApi.noterTicket(id, body)
      setHistorique((h) => [r.data, ...h])
      setNoteBody('')
    } catch { /* silencieux */ }
  }

  const addIntervention = async () => {
    if (!interv.type_intervention) return
    setIntervBusy(true)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      await installationsApi.createIntervention({
        installation: current.installation,
        ticket: id,
        type_intervention: interv.type_intervention,
        date_prevue: nullable(interv.date_prevue),
        compte_rendu: nullable(interv.compte_rendu),
      })
      setInterv({ type_intervention: 'depannage', date_prevue: '', compte_rendu: '' })
      loadInterventions()
      loadHistorique()
    } catch { /* silencieux */ } finally { setIntervBusy(false) }
  }

  const annuler = async () => {
    const motif = window.prompt("Motif d'annulation du ticket ?")
    if (motif === null) return
    try {
      await savApi.annulerTicket(id, motif)
      await reloadAll()
      loadHistorique()
      onSaved?.()
    } catch { /* silencieux */ }
  }
  const reactiver = async () => {
    try {
      await savApi.reactiverTicket(id)
      await reloadAll()
      loadHistorique()
      onSaved?.()
    } catch { /* silencieux */ }
  }

  const linkedEquip = equipements.find((e) => String(e.id) === String(fields.equipement))

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">
            Ticket SAV — {current.reference ?? ''}
            {current.annule && <span className="lead-archived-badge">Annulé</span>}
          </h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {current.annule && (
            <div className="form-error-box" role="alert">
              <strong>Ticket annulé.</strong>
              {current.motif_annulation ? ` Motif : ${current.motif_annulation}` : ''}{' '}
              <button type="button" className="btn btn-sm btn-outline" onClick={reactiver}>Réactiver</button>
            </div>
          )}

          {/* ── Infos ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🎫 Ticket</span>
              <span><StatutBadge statut={current.statut} /></span>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Client</label>
                <input className="form-control" value={current.client_nom ?? '—'} readOnly />
              </div>
              <div className="form-group">
                <label className="form-label">Chantier</label>
                <input className="form-control" value={current.installation_reference ?? '—'} readOnly />
              </div>
              <div className="form-group">
                <label className="form-label">Ouvert le</label>
                <input className="form-control" value={formatDateFR(current.date_ouverture)} readOnly />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Statut</label>
                <select className="form-select" value={fields.statut}
                        onChange={(e) => set('statut', e.target.value)}>
                  {TICKET_STATUSES.map((k) => (
                    <option key={k} value={k}>{TICKET_STATUS_LABELS[k]}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-select" value={fields.type}
                        onChange={(e) => set('type', e.target.value)}>
                  {TICKET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Priorité</label>
                <select className="form-select" value={fields.priorite}
                        onChange={(e) => set('priorite', e.target.value)}>
                  {TICKET_PRIORITES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-control" rows={2} value={fields.description ?? ''}
                        onChange={(e) => set('description', e.target.value)} />
            </div>
          </div>

          {/* ── Équipement & garantie ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🔧 Équipement concerné</span>
              <span><GarantieIndicator value={current.sous_garantie_effectif} /></span>
            </div>
            <div className="form-row">
              <div className="form-group fg-grow">
                <label className="form-label">Équipement (du chantier)</label>
                <select className="form-select" value={fields.equipement ?? ''}
                        onChange={(e) => set('equipement', e.target.value)}>
                  <option value="">— Aucun (garantie manuelle) —</option>
                  {equipements.map((e) => (
                    <option key={e.id} value={e.id}>
                      {(e.produit_nom ?? 'Produit')} — {e.numero_serie ?? 'sans n° série'}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Sous garantie (si aucun équipement)</label>
                <select className="form-select" value={fields.sous_garantie}
                        onChange={(e) => set('sous_garantie', e.target.value)}
                        disabled={!!fields.equipement}>
                  {SOUS_GARANTIE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
            {linkedEquip && (
              <p className="gen-hint">
                {linkedEquip.date_fin_garantie
                  ? `Fin de garantie de l'équipement : ${formatDateFR(linkedEquip.date_fin_garantie)} — la garantie du ticket est calculée automatiquement.`
                  : "Garantie de l'équipement non renseignée."}
              </p>
            )}
          </div>

          {/* ── Suivi ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">📋 Suivi</span>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Technicien responsable</label>
                <select className="form-select" value={fields.technicien_responsable ?? ''}
                        onChange={(e) => set('technicien_responsable', e.target.value)}>
                  <option value="">— Non assigné —</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Date de résolution</label>
                <input type="date" className="form-control" value={fields.date_resolution ?? ''}
                       onChange={(e) => set('date_resolution', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Coût (interne)</label>
                <input type="number" step="any" className="form-control" value={fields.cout ?? ''}
                       onChange={(e) => set('cout', e.target.value)} />
              </div>
            </div>
            {saveError && <div className="form-error-box" role="alert">{saveError}</div>}
          </div>

          {/* ── Interventions ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🛠️ Interventions</span>
            </div>
            {interventions.length === 0 ? (
              <p className="gen-hint">Aucune intervention rattachée.</p>
            ) : (
              <table className="lines-table">
                <thead>
                  <tr><th>Type</th><th>Prévue</th><th>Réalisée</th><th>Technicien</th><th>Compte rendu</th></tr>
                </thead>
                <tbody>
                  {interventions.map((iv) => (
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
                        onChange={(e) => setInterv((s) => ({ ...s, type_intervention: e.target.value }))}>
                  {INTERVENTION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Date prévue</label>
                <input type="date" className="form-control" value={interv.date_prevue}
                       onChange={(e) => setInterv((s) => ({ ...s, date_prevue: e.target.value }))} />
              </div>
              <div className="form-group fg-grow">
                <label className="form-label">Compte rendu</label>
                <input className="form-control" value={interv.compte_rendu}
                       onChange={(e) => setInterv((s) => ({ ...s, compte_rendu: e.target.value }))} />
              </div>
              <div className="form-group" style={{ alignSelf: 'flex-end' }}>
                <button type="button" className="btn btn-outline"
                        disabled={intervBusy || !interv.type_intervention} onClick={addIntervention}>
                  Ajouter une intervention
                </button>
              </div>
            </div>
          </div>

          {/* ── Historique (chatter) ── */}
          <div className="form-section">
            <div className="form-section-header">
              <span className="form-section-title">🕐 Historique</span>
            </div>
            <div className="chatter-note-box">
              <input className="form-control" placeholder="Écrire une note…"
                     value={noteBody} onChange={(e) => setNoteBody(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); postNote() } }} />
              <button type="button" className="btn btn-outline" onClick={postNote}>Noter</button>
            </div>
            <div className="chatter-timeline">
              {historique.length === 0 && <p className="gen-hint">Aucune activité pour le moment.</p>}
              {historique.map((a) => (
                <div key={a.id} className={`chatter-item chatter-${a.kind}`}>
                  {a.kind === 'note' && <span>📝 <strong>Note&nbsp;:</strong> {a.body}</span>}
                  {a.kind === 'creation' && <span>✨ {a.body}</span>}
                  {a.kind === 'modification' && (
                    <span>✏️ <strong>{a.field_label}&nbsp;:</strong> {a.old_value} → <strong>{a.new_value}</strong></span>
                  )}
                  <span className="chatter-meta">— par {a.user_nom ?? '?'} · {timeAgo(a.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="modal-footer">
          {!current.annule && (
            <button type="button" className="btn btn-danger" onClick={annuler}>Annuler le ticket</button>
          )}
          <button type="button" className="btn btn-outline" onClick={onClose}>Fermer</button>
          <button type="button" className="btn btn-primary" disabled={saving} onClick={save}>
            {saving ? 'Enregistrement...' : 'Mettre à jour'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function TicketsPage() {
  const dispatch = useDispatch()
  const { items, loading } = useSelector((s) => s.tickets)
  const [filters, setFilters] = useState(EMPTY_TICKET_FILTERS)
  const [sort, setSort] = useState({ key: 'statut', dir: 'asc' })
  const [selected, setSelected] = useState(null)

  const reload = () => dispatch(fetchTickets())
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const technicienOptions = useMemo(
    () => [...new Set(items.map((it) => it.technicien_nom).filter(Boolean))].sort(),
    [items])

  const rows = useMemo(
    () => sortTickets(filterTickets(items, filters), sort.key, sort.dir),
    [items, filters, sort])

  const onSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  const arrow = (key) => (sort.key === key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '')

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Tickets SAV</h1>
          <div className="page-subtitle">{rows.length} ticket(s)</div>
        </div>
        <ExportButton
          fetcher={savApi.exportTickets}
          params={{
            ...(filters.q?.trim() ? { search: filters.q.trim() } : {}),
            ...(filters.statut ? { statut: filters.statut } : {}),
            ...(filters.type ? { type: filters.type } : {}),
            ...(filters.priorite ? { priorite: filters.priorite } : {}),
            ...(filters.ouvert === 'tous' ? { ouvert: 'tous' } : {}),
          }}
          filename="tickets-sav.xlsx"
        />
      </div>

      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="form-control" placeholder="Rechercher (référence, client, chantier, description)…"
               value={filters.q} onChange={(e) => setF('q', e.target.value)} style={{ flex: '1 1 220px' }} />
        <select className="form-select" value={filters.statut} onChange={(e) => setF('statut', e.target.value)}>
          <option value="">Tous statuts</option>
          {TICKET_STATUSES.map((k) => <option key={k} value={k}>{TICKET_STATUS_LABELS[k]}</option>)}
        </select>
        <select className="form-select" value={filters.type} onChange={(e) => setF('type', e.target.value)}>
          <option value="">Tous types</option>
          {TICKET_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select className="form-select" value={filters.priorite} onChange={(e) => setF('priorite', e.target.value)}>
          <option value="">Toutes priorités</option>
          {TICKET_PRIORITES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>
        <select className="form-select" value={filters.technicien} onChange={(e) => setF('technicien', e.target.value)}>
          <option value="">Tous techniciens</option>
          {technicienOptions.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className="form-select" value={filters.sous_garantie} onChange={(e) => setF('sous_garantie', e.target.value)}>
          <option value="">Garantie (tous)</option>
          {SOUS_GARANTIE_OPTIONS.map((o) => <option key={o.value} value={o.value}>Sous garantie : {o.label}</option>)}
        </select>
        <select className="form-select" value={filters.ouvert} onChange={(e) => setF('ouvert', e.target.value)}>
          <option value="ouverts">Ouverts seulement</option>
          <option value="tous">Tous (incl. clôturés/annulés)</option>
        </select>
      </div>

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="gen-hint">Aucun ticket. Ouvrez-en un depuis la fiche d'un chantier.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => onSort('reference')} style={{ cursor: 'pointer' }}>Référence{arrow('reference')}</th>
                <th>Client</th>
                <th className="m-hide">Chantier</th>
                <th onClick={() => onSort('statut')} style={{ cursor: 'pointer' }}>Statut{arrow('statut')}</th>
                <th className="m-hide">Type</th>
                <th onClick={() => onSort('priorite')} style={{ cursor: 'pointer' }}>Priorité{arrow('priorite')}</th>
                <th className="m-hide">Garantie</th>
                <th className="m-hide">Technicien</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} onClick={() => setSelected(t)} style={{ cursor: 'pointer' }}>
                  <td>{t.reference}{t.annule && <span className="lead-archived-badge"> Annulé</span>}</td>
                  <td>{t.client_nom ?? '—'}</td>
                  <td className="m-hide">{t.installation_reference ?? '—'}</td>
                  <td><StatutBadge statut={t.statut} /></td>
                  <td className="m-hide">{t.type_display ?? t.type}</td>
                  <td>{TICKET_PRIORITE_LABELS[t.priorite] ?? t.priorite}</td>
                  <td className="m-hide">{SOUS_GARANTIE_LABELS[t.sous_garantie_effectif] ?? '—'}</td>
                  <td className="m-hide">{t.technicien_nom ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <TicketDetail ticket={selected} onClose={() => setSelected(null)} onSaved={reload} />
      )}
    </div>
  )
}
