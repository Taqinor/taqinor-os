import { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import comptaApi from '../../api/comptaApi'
import {
  SOURCE_TYPES, SOURCE_COLOR, CHANNELS, WEEKDAYS, MONTHS,
  ymd, monthGrid, normalizeEvents, groupByDay, routeForEvent,
  isDraggable, buildReschedulePayload,
} from './marketing'

/* ============================================================================
   XMKT30 / WIR65 — Calendrier marketing unifié.
   ----------------------------------------------------------------------------
   Agrège les 5 sources company-scoped servies par l'endpoint backend
   (`CalendrierMarketingView`, apps/compta/views.py) : campagnes (planifiee_le,
   XMKT7), posts sociaux (XMKT35), étapes de séquences dues, événements
   (XMKT28) et relances de devis abandonnés (FG203). Filtrable par canal ;
   drag-to-reschedule (HTML5 natif, comme reporting/CalendarPage.jsx — pas de
   lib externe) réservé aux campagnes non parties. Clic → ouvre l'objet.
   ========================================================================== */

export default function MarketingCalendarScreen() {
  const navigate = useNavigate()
  const today = useMemo(() => new Date(), [])
  const [cursor, setCursor] = useState(
    () => ({ year: new Date().getFullYear(), month: new Date().getMonth() }))
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [hiddenSources, setHiddenSources] = useState(new Set())
  const [channel, setChannel] = useState('')
  const [dragId, setDragId] = useState(null)
  const [err, setErr] = useState('')

  const cells = useMemo(
    () => monthGrid(cursor.year, cursor.month), [cursor])
  const from = cells[0]
  const to = cells[cells.length - 1]

  const load = useCallback(() => {
    setLoading(true)
    const params = { from: ymd(from), to: ymd(to) }
    if (channel) params.channel = channel
    comptaApi.calendrierMarketing.get(params)
      .then(r => setEvents(normalizeEvents(r.data)))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [from, to, channel])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const byDay = useMemo(
    () => groupByDay(events, { hiddenSources, channel }),
    [events, hiddenSources, channel])

  const monthEmpty = useMemo(
    () => Object.keys(byDay).length === 0, [byDay])

  const toggleSource = (k) => setHiddenSources(prev => {
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
    const route = routeForEvent(ev)
    if (route) navigate(route)
  }

  const onDrop = async (cellDate) => {
    const ev = events.find(e => e.id === dragId)
    setDragId(null)
    if (!ev || !isDraggable(ev)) return
    const target = ymd(cellDate)
    if (target === ev.date) return
    setErr('')
    try {
      await comptaApi.calendrierMarketing.reschedule(
        buildReschedulePayload(ev, target))
      load()
    } catch {
      setErr('Replanification impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2>Calendrier marketing</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="btn btn-light" data-testid="mkt-cal-prev"
            onClick={() => go(-1)}>‹</button>
          <button className="btn btn-light" data-testid="mkt-cal-today"
            onClick={goToday}>Aujourd'hui</button>
          <button className="btn btn-light" data-testid="mkt-cal-next"
            onClick={() => go(1)}>›</button>
          <strong style={{ minWidth: 150, textAlign: 'center' }}>
            {MONTHS[cursor.month]} {cursor.year}
          </strong>
          <select className="form-input" data-testid="mkt-cal-channel"
            value={channel} onChange={e => setChannel(e.target.value)}
            style={{ maxWidth: 200 }}>
            <option value="">Tous les canaux</option>
            {CHANNELS.map(c => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem',
        marginBottom: '0.75rem' }}>
        {SOURCE_TYPES.map(t => (
          <button key={t.key} data-testid={`mkt-cal-source-${t.key}`}
            onClick={() => toggleSource(t.key)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '3px 10px', borderRadius: 999, cursor: 'pointer',
              border: `1px solid ${t.color}`, fontSize: '0.8rem',
              background: hiddenSources.has(t.key) ? 'transparent' : t.color,
              color: hiddenSources.has(t.key) ? t.color : '#fff',
            }}>
            <span style={{ width: 8, height: 8, borderRadius: 999,
              background: hiddenSources.has(t.key) ? t.color : '#fff' }} />
            {t.label}
          </button>
        ))}
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {loading && <p className="page-loading">Chargement…</p>}

      <div data-testid="mkt-cal-grid" style={{ display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)', gap: 1, background: '#e2e8f0',
        border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
        {WEEKDAYS.map(d => (
          <div key={d} style={{ background: '#f8fafc', padding: '6px 8px',
            fontSize: '0.75rem', fontWeight: 600, color: '#475569',
            textAlign: 'center' }}>{d}</div>
        ))}
        {cells.map((d) => {
          const key = ymd(d)
          const inMonth = d.getMonth() === cursor.month
          const isToday = key === ymd(today)
          const isPast = key < ymd(today)
          const dayEvents = byDay[key] || []
          return (
            <div key={key} data-testid={`mkt-cal-day-${key}`}
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
                <div key={ev.id} data-testid="mkt-cal-event"
                  draggable={isDraggable(ev)}
                  onDragStart={() => setDragId(ev.id)}
                  onClick={() => openEvent(ev)}
                  title={`${ev.title}${ev.channel ? ' — ' + ev.channel : ''}${isPast
                    ? ' (passé)' : ''}`}
                  style={{ background: SOURCE_COLOR[ev.source] || '#64748b',
                    color: '#fff', borderRadius: 4, padding: '2px 6px',
                    fontSize: '0.72rem', cursor: isDraggable(ev) ? 'grab'
                      : 'pointer', whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis',
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
