/* Activités planifiées (style Odoo) pour n'importe quel enregistrement.
   Réutilisable : passe model ('crm.lead', 'crm.client'…) + id. */
import { useEffect, useState } from 'react'
import recordsApi from '../api/recordsApi'
import AssigneePicker from './AssigneePicker'
import { DatePicker } from '../ui/DatePicker'
import { today as todayDate } from '../ui/date-utils'

const STATE_DOT = {
  overdue: { c: '#dc2626', t: 'En retard' },
  today: { c: '#f59e0b', t: "Aujourd'hui" },
  upcoming: { c: '#16a34a', t: 'À venir' },
  none: { c: '#cbd5e1', t: 'Sans échéance' },
  done: { c: '#94a3b8', t: 'Fait' },
}

const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// VX174 — la roue native iOS (`<input type="date">`) IGNORE `min` : un
// technicien pouvait choisir une échéance dans le passé sur iPhone malgré la
// contrainte métier "pas d'échéance passée". `ui/DatePicker` est borné en JS
// (isDateDisabled), donc infranchissable sur toute plateforme. Conversion
// Date <-> "aaaa-mm-jj" (format déjà utilisé par le state/l'API).
const dateFromYmd = (ymd) => (ymd ? new Date(`${ymd}T00:00:00`) : null)
const ymdFromDate = (d) => (d
  ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  : '')

export default function ActivitiesPanel({ model, id, users = [], onChange }) {
  const [types, setTypes] = useState([])
  const [activities, setActivities] = useState([])
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ activity_type: '', summary: '', due_date: todayStr(), assigned_to: '', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // Reprogrammation (« Reporter ») : id de l'activité en cours d'édition + la
  // nouvelle échéance saisie. '' = aucune reprogrammation ouverte.
  const [reschedId, setReschedId] = useState(null)
  const [reschedDate, setReschedDate] = useState('')

  // VX204 — un échec de chargement était INDISCERNABLE de « aucune relance
  // due » (l'état `error` existait déjà mais n'était jamais alimenté ici).
  const load = () => {
    recordsApi.getActivities(model, id)
      .then(r => { setActivities(r.data.results ?? r.data); setError(null) })
      .catch(() => setError('Impossible de charger les activités.'))
  }
  useEffect(() => {
    recordsApi.getActivityTypes()
      .then(r => {
        const list = r.data.results ?? r.data
        setTypes(list)
        setForm(f => ({ ...f, activity_type: f.activity_type || (list[0]?.id ?? '') }))
      }).catch(() => {})
    load()
  }, [model, id]) // eslint-disable-line react-hooks/exhaustive-deps

  const create = async () => {
    if (!form.activity_type) return
    // L'échéance ne peut pas être dans le passé : on bloque la création et on
    // explique, sans jamais recaler la valeur saisie.
    if (form.due_date && form.due_date < todayStr()) {
      setError("L'échéance ne peut pas être dans le passé.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await recordsApi.createActivity({ model, id, ...form, assigned_to: form.assigned_to || undefined })
      setForm(f => ({ ...f, summary: '', note: '', due_date: todayStr() }))
      setAdding(false)
      load(); onChange?.()
    } catch {
      setError('Action impossible — réessayez.')
    } finally { setBusy(false) }
  }

  const markDone = async (act) => {
    setError(null)
    try { await recordsApi.markActivityDone(act.id); load(); onChange?.() } catch { setError('Action impossible — réessayez.') }
  }
  const remove = async (act) => {
    if (!window.confirm('Supprimer cette activité ?')) return
    setError(null)
    try { await recordsApi.deleteActivity(act.id); load(); onChange?.() } catch { setError('Action impossible — réessayez.') }
  }

  // Reprogrammer (« Reporter ») : ouvre le date-picker pré-rempli sur l'échéance
  // actuelle, puis PATCH la due_date sans supprimer/recréer l'activité.
  const openResched = (act) => {
    setReschedId(act.id)
    setReschedDate(act.due_date || todayStr())
    setError(null)
  }
  const cancelResched = () => { setReschedId(null); setReschedDate('') }
  const saveResched = async (act) => {
    if (!reschedDate) return
    if (reschedDate < todayStr()) {
      setError("L'échéance ne peut pas être dans le passé.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      await recordsApi.updateActivity(act.id, { due_date: reschedDate })
      cancelResched()
      load(); onChange?.()
    } catch {
      setError('Action impossible — réessayez.')
    } finally { setBusy(false) }
  }

  const open = activities.filter(a => !a.done)
  const done = activities.filter(a => a.done)

  return (
    <div className="act-panel">
      <div className="act-head">
        <span className="act-count">{open.length} activité(s) ouverte(s)</span>
        <button type="button" className="btn btn-sm btn-primary" onClick={() => setAdding(v => !v)}>
          {adding ? 'Fermer' : '＋ Planifier une activité'}
        </button>
      </div>

      {adding && (
        <div className="act-form">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Type</label>
              <select className="form-select" value={form.activity_type}
                      onChange={e => setForm(f => ({ ...f, activity_type: Number(e.target.value) }))}>
                {types.map(t => <option key={t.id} value={t.id}>{t.icone} {t.nom}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Échéance</label>
              <DatePicker value={dateFromYmd(form.due_date)} min={todayDate()}
                          onChange={(d) => setForm(f => ({ ...f, due_date: ymdFromDate(d) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">Assigné à</label>
              <AssigneePicker users={users} value={form.assigned_to}
                              onChange={(uid) => setForm(f => ({ ...f, assigned_to: uid ?? '' }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Résumé</label>
            <input className="form-control" value={form.summary} placeholder="ex: Appeler pour la visite"
                   onChange={e => setForm(f => ({ ...f, summary: e.target.value }))} />
          </div>
          <div className="act-form-actions">
            <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={create}>
              {busy ? '…' : 'Créer'}
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="form-error" role="alert">
          {error}{' '}
          <button type="button" className="chatter-retry" onClick={load}>Réessayer</button>
        </p>
      )}

      <div className="act-list">
        {!error && open.length === 0 && done.length === 0 && (
          <p className="gen-hint">Aucune activité planifiée.</p>
        )}
        {open.map(a => {
          const s = STATE_DOT[a.state] || STATE_DOT.none
          return (
            <div key={a.id} className="act-item">
              <span className="act-dot" style={{ background: s.c }} title={s.t} />
              <span className="act-body">
                <strong>{a.activity_type_icone} {a.activity_type_nom}</strong>
                {a.summary ? ` — ${a.summary}` : ''}
                <span className="act-meta">
                  {a.due_date ? `échéance ${a.due_date}` : 'sans échéance'}
                  {a.assigned_to_nom ? ` · ${a.assigned_to_nom}` : ''}
                </span>
              </span>
              <span className="act-actions">
                {reschedId === a.id ? (
                  <>
                    <DatePicker value={dateFromYmd(reschedDate)} min={todayDate()}
                                onChange={(d) => setReschedDate(ymdFromDate(d))} />
                    <button type="button" className="btn btn-sm btn-primary" disabled={busy}
                            onClick={() => saveResched(a)}>{busy ? '…' : 'OK'}</button>
                    <button type="button" className="btn btn-sm btn-outline" onClick={cancelResched}>Annuler</button>
                  </>
                ) : (
                  <>
                    <button type="button" className="btn btn-sm btn-outline" onClick={() => markDone(a)}>✓ Fait</button>
                    <button type="button" className="btn btn-sm btn-outline" onClick={() => openResched(a)}>Reporter</button>
                    <button type="button" className="btn-icon-danger" title="Supprimer" onClick={() => remove(a)}>✕</button>
                  </>
                )}
              </span>
            </div>
          )
        })}
        {done.length > 0 && <div className="act-done-sep">Terminées</div>}
        {done.map(a => (
          <div key={a.id} className="act-item act-item-done">
            <span className="act-dot" style={{ background: '#94a3b8' }} />
            <span className="act-body">
              <strong>{a.activity_type_icone} {a.activity_type_nom}</strong>
              {a.summary ? ` — ${a.summary}` : ''}
              <span className="act-meta">fait{a.done_at ? ` le ${new Date(a.done_at).toLocaleDateString('fr-FR')}` : ''}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
