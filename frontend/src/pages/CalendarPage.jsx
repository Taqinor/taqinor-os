import { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../api/reportingApi'
import crmApi from '../api/crmApi'
import MonthGrid from '../components/MonthGrid'
import {
  Button, Spinner, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui'

// N84 — Calendrier / agenda : poses, mises en service, interventions, visites
// de maintenance et activités de suivi sur une grille mensuelle. Glisser un
// évènement éditable vers un autre jour le reprogramme (jamais une visite de
// maintenance, qui est calculée).
//
// VX25 — restylé sur les mêmes primitives que la vue calendrier CRM
// (leads/views/CalendarView.jsx) : MonthGrid partagé (composants/tokens),
// plus aucune couleur hex codée en dur (les 5 types d'évènement utilisent la
// palette --module-accent-* déjà définie en clair/sombre dans tokens.css).

const TYPES = [
  { key: 'pose', label: 'Poses', token: '--module-accent-azur' },
  { key: 'mise_en_service', label: 'Mises en service', token: '--module-accent-success' },
  { key: 'intervention', label: 'Interventions', token: '--module-accent-warning' },
  { key: 'visite_maintenance', label: 'Maintenance', token: '--module-accent-brass' },
  { key: 'activite', label: 'Activités', token: '--module-accent-nuit' },
]
const COLOR_VAR = Object.fromEntries(TYPES.map(t => [t.key, `var(${t.token})`]))
const ROUTE = {
  chantier: '/chantiers', activite: '/activites', contrat: '/sav/contrats',
}

const ymd = (d) => {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export default function CalendarPage() {
  const navigate = useNavigate()
  const today = useMemo(() => new Date(), [])
  const [monthStart, setMonthStart] = useState(
    () => new Date(today.getFullYear(), today.getMonth(), 1))
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

  // Bornes du mois affiché (semaines complètes, comme MonthGrid les calcule).
  const { from, to } = useMemo(() => {
    const year = monthStart.getFullYear()
    const month = monthStart.getMonth()
    const mondayOffset = (monthStart.getDay() + 6) % 7
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const total = Math.ceil((mondayOffset + daysInMonth) / 7) * 7
    const first = new Date(year, month, 1 - mondayOffset)
    const last = new Date(year, month, 1 - mondayOffset + total - 1)
    return { from: first, to: last }
  }, [monthStart])

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

  const renderCell = (cell) => {
    const key = cell.key
    const isPast = key < ymd(today)
    const dayEvents = byDay[key] || []
    return (
      <div
        key={key}
        className={[
          'cal-cell',
          cell.inMonth ? '' : 'cal-cell-out',
          cell.isToday ? 'cal-cell-today' : '',
        ].filter(Boolean).join(' ')}
        onDragOver={e => { e.preventDefault() }}
        onDrop={() => onDrop(cell.date)}
      >
        <span className="cal-day-number">{cell.dayNumber}</span>
        <div className="cal-chips">
          {dayEvents.map(ev => (
            <div
              key={ev.id}
              draggable={ev.editable}
              onDragStart={() => setDragId(ev.id)}
              onClick={() => openEvent(ev)}
              title={`${ev.type_label}${ev.assignee_nom
                ? ' — ' + ev.assignee_nom : ''}${isPast
                ? ' (en retard / passé)' : ''}`}
              className={`cp-event${isPast ? ' cp-event-past' : ''}`}
              style={{
                background: COLOR_VAR[ev.type] || 'var(--muted-foreground)',
                cursor: ev.editable ? 'grab' : 'pointer',
              }}
            >
              {ev.title}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header cp-page-header">
        <h2>Calendrier</h2>
        <div className="cp-header-actions">
          <Button variant="outline" size="sm" onClick={toggleSubscribe}>
            S'abonner au calendrier
          </Button>
          <Select value={assignee || 'all'} onValueChange={(v) => setAssignee(v === 'all' ? '' : v)}>
            <SelectTrigger className="w-56" aria-label="Filtrer par responsable">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les responsables</SelectItem>
              {users.map(u => (
                <SelectItem key={u.id} value={String(u.id)}>
                  {u.username || u.nom || `#${u.id}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {subOpen && (
        <div className="cp-subscribe-box">
          <p className="cp-subscribe-hint">
            Copiez ce lien et ajoutez-le comme calendrier « par URL » dans
            Google Agenda ou Outlook pour voir vos poses, interventions et
            visites de maintenance sur votre téléphone.
          </p>
          <div className="cp-subscribe-row">
            <Input className="cp-subscribe-input" readOnly value={subUrl}
              onFocus={e => e.target.select()}
              placeholder="Génération du lien…" />
            <Button variant="outline" size="sm" onClick={copySub} disabled={!subUrl}>
              {copied ? 'Copié !' : 'Copier'}
            </Button>
          </div>
        </div>
      )}

      <div className="cp-type-filters">
        {TYPES.map(t => (
          <button
            key={t.key}
            type="button"
            className={`cp-type-chip${hidden.has(t.key) ? ' cp-type-chip-off' : ''}`}
            style={{ '--cp-chip-color': `var(${t.token})` }}
            onClick={() => toggleType(t.key)}
          >
            <span className="cp-type-dot" />
            {t.label}
          </button>
        ))}
      </div>

      {err && <p className="cp-error" role="alert">{err}</p>}
      {loading && (
        <p className="page-loading"><Spinner /> Chargement…</p>
      )}

      <MonthGrid initialMonth={monthStart} onMonthChange={setMonthStart} renderCell={renderCell} />

      {!loading && monthEmpty && (
        <p className="cp-empty">Aucun évènement ce mois-ci</p>
      )}
    </div>
  )
}
