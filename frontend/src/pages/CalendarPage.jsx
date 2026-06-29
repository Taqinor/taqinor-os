import { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../api/reportingApi'
import crmApi from '../api/crmApi'

// N84 — Calendrier / agenda : poses, mises en service, interventions, visites
// de maintenance et activités de suivi sur une grille mensuelle. Glisser un
// évènement éditable vers un autre jour le reprogramme (jamais une visite de
// maintenance, qui est calculée).

const TYPES = [
  { key: 'pose', label: 'Poses', color: '#2563eb' },
  { key: 'mise_en_service', label: 'Mises en service', color: '#0d9488' },
  { key: 'intervention', label: 'Interventions', color: '#ea580c' },
  { key: 'visite_maintenance', label: 'Maintenance', color: '#7c3aed' },
  { key: 'activite', label: 'Activités', color: '#64748b' },
]
const COLOR = Object.fromEntries(TYPES.map(t => [t.key, t.color]))
const ROUTE = {
  chantier: '/chantiers', activite: '/activites', contrat: '/sav/contrats',
}
const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

const ymd = (d) => {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

// Cases visibles : la grille commence au lundi de la semaine du 1er du mois et
// se termine au dimanche de la semaine du dernier jour (toujours 7 colonnes).
function monthGrid(year, month) {
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7 // 0 = lundi
  const start = new Date(year, month, 1 - startOffset)
  const cells = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    cells.push(d)
  }
  // Retire la dernière semaine si elle déborde entièrement sur le mois suivant.
  if (cells[35].getMonth() !== month && cells[28].getMonth() !== month) {
    return cells.slice(0, 35)
  }
  return cells
}

export default function CalendarPage() {
  const navigate = useNavigate()
  const today = useMemo(() => new Date(), [])
  const [cursor, setCursor] = useState(
    () => ({ year: new Date().getFullYear(), month: new Date().getMonth() }))
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [hidden, setHidden] = useState(new Set())
  const [assignee, setAssignee] = useState('')
  const [users, setUsers] = useState([])
  const [dragId, setDragId] = useState(null)
  const [err, setErr] = useState('')
  // FG6 — abonnement ICS (Google/Outlook). On ne charge l'URL signée qu'au clic.
  const [subUrl, setSubUrl] = useState('')
  const [subOpen, setSubOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const cells = useMemo(
    () => monthGrid(cursor.year, cursor.month), [cursor])
  const from = cells[0]
  const to = cells[cells.length - 1]

  const load = useCallback(() => {
    const params = { from: ymd(from), to: ymd(to) }
    if (assignee) params.assignee = assignee
    reportingApi.getCalendar(params)
      .then(r => setEvents(r.data.events || []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [from, to, assignee])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    crmApi.getAssignableUsers()
      .then(r => setUsers(r.data || [])).catch(() => {})
  }, [])

  const byDay = useMemo(() => {
    const map = {}
    for (const ev of events) {
      if (hidden.has(ev.type)) continue
      ;(map[ev.date] = map[ev.date] || []).push(ev)
    }
    return map
  }, [events, hidden])

  // Aucun évènement visible ce mois-ci (après application des filtres de type).
  const monthEmpty = useMemo(
    () => Object.keys(byDay).length === 0, [byDay])

  const toggleType = (k) => setHidden(prev => {
    const next = new Set(prev)
    next.has(k) ? next.delete(k) : next.add(k)
    return next
  })

  const go = (delta) => setCursor(c => {
    const d = new Date(c.year, c.month + delta, 1)
    return { year: d.getFullYear(), month: d.getMonth() }
  })
  const goToday = () => setCursor(
    { year: today.getFullYear(), month: today.getMonth() })

  const openEvent = (ev) => {
    const route = ROUTE[ev.link_type]
    if (route) navigate(route)
  }

  // FG6 — « S'abonner au calendrier » : récupère l'URL ICS signée et l'affiche
  // pour la coller dans Google Agenda / Outlook (abonnement, pas un import).
  const toggleSubscribe = useCallback(() => {
    setCopied(false)
    setSubOpen(open => {
      const next = !open
      if (next && !subUrl) {
        reportingApi.getCalendarSubscription()
          .then(r => setSubUrl(r.data?.url || ''))
          .catch(() => setErr('Lien d’abonnement indisponible.'))
      }
      return next
    })
  }, [subUrl])

  const copySub = useCallback(() => {
    if (!subUrl) return
    navigator.clipboard?.writeText(subUrl)
      .then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
      .catch(() => {})
  }, [subUrl])

  const onDrop = async (cellDate) => {
    const ev = events.find(e => e.id === dragId)
    setDragId(null)
    if (!ev || !ev.editable) return
    const target = ymd(cellDate)
    if (target === ev.date) return
    setErr('')
    try {
      await reportingApi.rescheduleCalendar(
        { type: ev.type, id: ev.obj_id, date: target })
      load()
    } catch {
      setErr('Replanification impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2>Calendrier</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="btn btn-light" onClick={() => go(-1)}>‹</button>
          <button className="btn btn-light" onClick={goToday}>Aujourd'hui</button>
          <button className="btn btn-light" onClick={() => go(1)}>›</button>
          <button className="btn btn-light" onClick={toggleSubscribe}>
            S'abonner au calendrier
          </button>
          <strong style={{ minWidth: 150, textAlign: 'center' }}>
            {MONTHS[cursor.month]} {cursor.year}
          </strong>
          <select className="form-input" value={assignee}
            onChange={e => setAssignee(e.target.value)}
            style={{ maxWidth: 200 }}>
            <option value="">Tous les responsables</option>
            {users.map(u => (
              <option key={u.id} value={u.id}>
                {u.username || u.nom || `#${u.id}`}
              </option>
            ))}
          </select>
        </div>
      </div>

      {subOpen && (
        <div style={{ marginBottom: '0.75rem', padding: '0.75rem 1rem',
          background: '#f8fafc', border: '1px solid #e2e8f0',
          borderRadius: 8 }}>
          <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem',
            color: '#475569' }}>
            Copiez ce lien et ajoutez-le comme calendrier « par URL » dans
            Google Agenda ou Outlook pour voir vos poses, interventions et
            visites de maintenance sur votre téléphone.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input className="form-input" readOnly value={subUrl}
              onFocus={e => e.target.select()}
              placeholder="Génération du lien…"
              style={{ flex: '1 1 320px', minWidth: 0, fontSize: '0.8rem' }} />
            <button className="btn btn-light" onClick={copySub}
              disabled={!subUrl}>
              {copied ? 'Copié !' : 'Copier'}
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem',
        marginBottom: '0.75rem' }}>
        {TYPES.map(t => (
          <button key={t.key} onClick={() => toggleType(t.key)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 10px', borderRadius: 999, cursor: 'pointer',
              border: `1px solid ${t.color}`, fontSize: '0.8rem',
              background: hidden.has(t.key) ? 'transparent' : t.color,
              color: hidden.has(t.key) ? t.color : '#fff',
            }}>
            <span style={{ width: 8, height: 8, borderRadius: 999,
              background: hidden.has(t.key) ? t.color : '#fff' }} />
            {t.label}
          </button>
        ))}
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {loading && <p className="page-loading">Chargement…</p>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
        gap: 1, background: '#e2e8f0', border: '1px solid #e2e8f0',
        borderRadius: 8, overflow: 'hidden' }}>
        {WEEKDAYS.map(d => (
          <div key={d} style={{ background: '#f8fafc', padding: '6px 8px',
            fontSize: '0.75rem', fontWeight: 600, color: '#475569',
            textAlign: 'center' }}>{d}</div>
        ))}
        {cells.map((d) => {
          const key = ymd(d)
          const inMonth = d.getMonth() === cursor.month
          const isToday = key === ymd(today)
          // Jour passé : date < aujourd'hui (comparaison de chaîne AAAA-MM-JJ).
          const isPast = key < ymd(today)
          const dayEvents = byDay[key] || []
          return (
            <div key={key}
              onDragOver={e => { e.preventDefault() }}
              onDrop={() => onDrop(d)}
              style={{ background: inMonth ? '#fff' : '#f8fafc',
                minHeight: 96, padding: 4, display: 'flex',
                flexDirection: 'column', gap: 3 }}>
              <div style={{ fontSize: '0.72rem', textAlign: 'right',
                color: inMonth ? '#1e293b' : '#cbd5e1',
                fontWeight: isToday ? 700 : 400 }}>
                {isToday
                  ? <span style={{ background: '#0d1b3e', color: '#fff',
                    borderRadius: 999, padding: '1px 6px' }}>{d.getDate()}</span>
                  : d.getDate()}
              </div>
              {dayEvents.map(ev => (
                <div key={ev.id}
                  draggable={ev.editable}
                  onDragStart={() => setDragId(ev.id)}
                  onClick={() => openEvent(ev)}
                  title={`${ev.type_label}${ev.assignee_nom
                    ? ' — ' + ev.assignee_nom : ''}${isPast
                    ? ' (en retard / passé)' : ''}`}
                  style={{ background: COLOR[ev.type] || '#64748b',
                    color: '#fff', borderRadius: 4, padding: '2px 6px',
                    fontSize: '0.72rem', cursor: ev.editable ? 'grab'
                      : 'pointer', whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    // Évènement passé (date < aujourd'hui) : atténué + bord rouge
                    // pour signaler une pose passée ou une activité en retard.
                    opacity: isPast ? 0.55 : 1,
                    boxShadow: isPast ? 'inset 0 0 0 1.5px #dc2626' : 'none' }}>
                  {ev.title}
                </div>
              ))}
            </div>
          )
        })}
      </div>

      {!loading && monthEmpty && (
        <p style={{ marginTop: '0.75rem', textAlign: 'center',
          color: '#64748b', fontSize: '0.9rem' }}>
          Aucun évènement ce mois-ci
        </p>
      )}
    </div>
  )
}
