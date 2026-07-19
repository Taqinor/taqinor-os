import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR161 — Journal d'appels commercial (click-to-call log, FG208).
   ----------------------------------------------------------------------------
   `AppelTelephoniqueViewSet` (route /marketing/appels/) posait `company` et
   `auteur` côté serveur mais n'avait ni wrapper API ni écran. Cet écran simple
   permet à un commercial d'ENREGISTRER un appel (lié à un lead/client via son
   id + numéro) et de le CONSULTER dans le journal. Aucun champ sensible.
   ========================================================================== */

const DIRECTIONS = [
  { value: 'sortant', label: 'Sortant' },
  { value: 'entrant', label: 'Entrant' },
]
const ISSUES = [
  { value: 'repondu', label: 'Répondu' },
  { value: 'sans_reponse', label: 'Sans réponse' },
  { value: 'rappel', label: 'À rappeler' },
  { value: 'faux_numero', label: 'Faux numéro' },
]

function emptyForm() {
  return {
    numero: '', direction: 'sortant', issue: 'repondu',
    lead_id: '', duree_secondes: '', a_rappeler_le: '', note: '',
  }
}

export default function JournalAppelsScreen() {
  const [appels, setAppels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.appels.list()
      .then(r => setAppels(marketingApi.unwrapList(r)))
      .catch(() => setAppels([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const closeForm = () => { setShowForm(false); setForm(emptyForm()); setErr('') }

  const submit = async (e) => {
    e.preventDefault()
    if (!form.numero.trim()) { setErr('Le numéro est requis.'); return }
    setSaving(true); setErr('')
    const payload = {
      numero: form.numero.trim(),
      direction: form.direction,
      issue: form.issue,
      note: form.note,
    }
    if (form.lead_id !== '') payload.lead_id = Number(form.lead_id)
    if (form.duree_secondes !== '') payload.duree_secondes = Number(form.duree_secondes)
    if (form.a_rappeler_le) payload.a_rappeler_le = form.a_rappeler_le
    try {
      await marketingApi.appels.create(payload)
      closeForm()
      load()
    } catch (ex) {
      const data = ex?.response?.data
      setErr(data?.numero || data?.detail || "Enregistrement de l'appel impossible.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Journal d'appels</h2>
        {!showForm && (
          <button className="btn btn-primary" data-testid="appels-nouveau"
            onClick={() => setShowForm(true)}>Enregistrer un appel</button>
        )}
      </div>

      {err && <p style={{ color: '#dc2626' }} role="alert">{err}</p>}

      {showForm && (
        <form onSubmit={submit} className="card" data-testid="appel-form"
          style={{ marginBottom: '1.25rem', display: 'grid', gap: '0.75rem', maxWidth: 520 }} noValidate>
          <label>
            Numéro *
            <input className="form-control" value={form.numero}
              onChange={e => setField('numero', e.target.value)}
              placeholder="+212 6 12 34 56 78" aria-label="Numéro" />
          </label>
          <label>
            Lead / client (id)
            <input className="form-control" type="number" value={form.lead_id}
              onChange={e => setField('lead_id', e.target.value)}
              placeholder="id du lead (optionnel)" aria-label="Lead / client (id)" />
          </label>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <label style={{ flex: 1 }}>
              Direction
              <select className="form-control" value={form.direction}
                onChange={e => setField('direction', e.target.value)} aria-label="Direction">
                {DIRECTIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </label>
            <label style={{ flex: 1 }}>
              Issue
              <select className="form-control" value={form.issue}
                onChange={e => setField('issue', e.target.value)} aria-label="Issue">
                {ISSUES.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
              </select>
            </label>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <label style={{ flex: 1 }}>
              Durée (s)
              <input className="form-control" type="number" value={form.duree_secondes}
                onChange={e => setField('duree_secondes', e.target.value)} aria-label="Durée (s)" />
            </label>
            <label style={{ flex: 1 }}>
              À rappeler le
              <input className="form-control" type="date" value={form.a_rappeler_le}
                onChange={e => setField('a_rappeler_le', e.target.value)} aria-label="À rappeler le" />
            </label>
          </div>
          <label>
            Note
            <textarea className="form-control" value={form.note}
              onChange={e => setField('note', e.target.value)} rows={2} aria-label="Note" />
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? '…' : 'Enregistrer'}
            </button>
            <button className="btn btn-light" type="button" onClick={closeForm}>Annuler</button>
          </div>
        </form>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="appels-table">
            <thead>
              <tr><th>Date</th><th>Numéro</th><th>Direction</th><th>Issue</th><th>Note</th><th>Par</th></tr>
            </thead>
            <tbody>
              {appels.map(a => (
                <tr key={a.id} data-testid="appel-row">
                  <td>{a.date_appel ? formatDateTime(a.date_appel) : '—'}</td>
                  <td>{a.numero}</td>
                  <td>{a.direction_display || a.direction}</td>
                  <td>{a.issue_display || a.issue}</td>
                  <td>{a.note || '—'}</td>
                  <td>{a.auteur_nom || '—'}</td>
                </tr>
              ))}
              {appels.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun appel enregistré
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
