import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchInstallations,
  updateInstallation,
  upsertInstallation,
} from '../../features/installations/store/installationsSlice'
import {
  EMPTY_FILTERS,
  filterInstallations,
  statusLabel,
  statusColor,
} from '../../features/installations/statuses'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import ExportButton from '../../components/ExportButton'
import FilterBar from './FilterBar'
import ListView from './views/ListView'
import KanbanView from './views/KanbanView'
import InstallationDetail from './InstallationDetail'
import '../crm/leads/views/calendar.css'
import '../../components/assigneepicker.css'
import '../crm/leads/leadspage.css'

const VIEW_KEY = 'taqinor.chantiers.view'
const VALID_VIEWS = ['liste', 'kanban', 'calendrier']

// Paramètre SERVEUR dérivé du filtre « annulés ».
const annuleParam = (annule) => {
  if (annule === 'seuls') return { annule: 'only' }
  if (annule === 'sans') return { annule: 'sans' }
  return {}
}

// ── Calendrier (inline) — miroir de la vue CRM, posé sur date_pose_prevue ──
const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MAX_CHIPS_PER_DAY = 3
const pad2 = (n) => String(n).padStart(2, '0')
const localKey = (y, m, d) => `${y}-${pad2(m)}-${pad2(d)}`

function poseKey(it) {
  const raw = it?.date_pose_prevue
  if (!raw || typeof raw !== 'string') return null
  const [y, m, d] = raw.split('-').map((p) => parseInt(p, 10))
  if (!y || !m || !d) return null
  return localKey(y, m, d)
}

function Chip({ item, onOpen }) {
  const dot = item.annule ? '#dc2626' : statusColor(item.statut)
  const name = item.reference || item.client_nom || '(Sans réf.)'
  return (
    <button
      type="button"
      className={`cal-chip${item.annule ? ' cal-chip-perdu' : ''}`}
      title={`${name} — ${statusLabel(item.statut)}`}
      onClick={() => onOpen(item)}
    >
      <span className="cal-chip-dot" style={{ background: dot }} />
      <span className="cal-chip-name">{name}</span>
    </button>
  )
}

function CalendarView({ items, onOpen }) {
  const [monthStart, setMonthStart] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [expandedDays, setExpandedDays] = useState({})

  const goToday = () => {
    const now = new Date()
    setMonthStart(new Date(now.getFullYear(), now.getMonth(), 1))
  }
  const goMonth = (delta) =>
    setMonthStart((d) => new Date(d.getFullYear(), d.getMonth() + delta, 1))
  const toggleDay = (key) =>
    setExpandedDays((prev) => ({ ...prev, [key]: !prev[key] }))

  const rawTitle = monthStart.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  const title = rawTitle.charAt(0).toUpperCase() + rawTitle.slice(1)

  const byDay = useMemo(() => {
    const map = new Map()
    for (const it of items ?? []) {
      const key = poseKey(it)
      if (!key) continue
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(it)
    }
    return map
  }, [items])

  const cells = useMemo(() => {
    const year = monthStart.getFullYear()
    const month = monthStart.getMonth()
    const mondayOffset = (monthStart.getDay() + 6) % 7
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const total = Math.ceil((mondayOffset + daysInMonth) / 7) * 7
    const out = []
    for (let i = 0; i < total; i += 1) {
      const date = new Date(year, month, 1 - mondayOffset + i)
      out.push({
        key: localKey(date.getFullYear(), date.getMonth() + 1, date.getDate()),
        dayNumber: date.getDate(),
        inMonth: date.getMonth() === month,
      })
    }
    return out
  }, [monthStart])

  const now = new Date()
  const todayKey = localKey(now.getFullYear(), now.getMonth() + 1, now.getDate())

  return (
    <div className="cal-root">
      <div className="cal-header">
        <div className="cal-nav">
          <button type="button" className="btn btn-sm btn-outline cal-nav-btn"
                  onClick={() => goMonth(-1)} aria-label="Mois précédent">◀</button>
          <button type="button" className="btn btn-sm btn-outline cal-nav-btn"
                  onClick={() => goMonth(1)} aria-label="Mois suivant">▶</button>
        </div>
        <h3 className="cal-title">{title}</h3>
        <button type="button" className="btn btn-sm btn-outline cal-today-btn" onClick={goToday}>
          Aujourd&apos;hui
        </button>
      </div>

      <div className="cal-grid" role="grid" aria-label={`Calendrier ${title}`}>
        {WEEKDAYS.map((day) => (
          <div key={day} className="cal-weekday">{day}</div>
        ))}
        {cells.map((cell) => {
          const dayItems = byDay.get(cell.key) ?? []
          const expanded = Boolean(expandedDays[cell.key])
          const visible =
            expanded || dayItems.length <= MAX_CHIPS_PER_DAY
              ? dayItems
              : dayItems.slice(0, MAX_CHIPS_PER_DAY)
          const hidden = dayItems.length - visible.length
          return (
            <div
              key={cell.key}
              className={[
                'cal-cell',
                cell.inMonth ? '' : 'cal-cell-out',
                cell.key === todayKey ? 'cal-cell-today' : '',
              ].filter(Boolean).join(' ')}
            >
              <span className="cal-day-number">{cell.dayNumber}</span>
              <div className="cal-chips">
                {visible.map((it) => (
                  <Chip key={it.id} item={it} onOpen={onOpen} />
                ))}
                {hidden > 0 && (
                  <button type="button" className="cal-more" onClick={() => toggleDay(cell.key)}>
                    +{hidden} autres
                  </button>
                )}
                {expanded && dayItems.length > MAX_CHIPS_PER_DAY && (
                  <button type="button" className="cal-more" onClick={() => toggleDay(cell.key)}>
                    Réduire
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function InstallationsPage() {
  const dispatch = useDispatch()
  const { items, loading, error } = useSelector(s => s.installations)

  const [view, setView] = useState(() => {
    try {
      const saved = localStorage.getItem(VIEW_KEY)
      return VALID_VIEWS.includes(saved) ? saved : 'liste'
    } catch {
      return 'liste'
    }
  })
  useEffect(() => {
    try { localStorage.setItem(VIEW_KEY, view) } catch { /* stockage indisponible */ }
  }, [view])

  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const filtered = useMemo(() => filterInstallations(items, filters), [items, filters])

  const [selected, setSelected] = useState(null)

  // Employés assignables (avatar + nom) pour le sélecteur de technicien des
  // cartes kanban. Ouvert à la Commerciale (endpoint dédié, comme les leads).
  const [users, setUsers] = useState([])
  useEffect(() => {
    crmApi.getAssignableUsers()
      .then(r => setUsers(r.data.results ?? r.data)).catch(() => {})
  }, [])

  // Changement de statut optimiste (kanban) avec retour-arrière.
  const [busyId, setBusyId] = useState(null)
  const [statusError, setStatusError] = useState(null)
  useEffect(() => {
    if (!statusError) return undefined
    const t = setTimeout(() => setStatusError(null), 6000)
    return () => clearTimeout(t)
  }, [statusError])

  // Le filtre « annulés » est une dimension SERVEUR : on refait l'appel avec
  // le bon paramètre quand il change (les autres filtres restent côté client).
  const refetch = () => dispatch(fetchInstallations(annuleParam(filters.annule)))
  useEffect(() => {
    dispatch(fetchInstallations(annuleParam(filters.annule)))
  }, [dispatch, filters.annule])

  const onOpen = (it) => setSelected(it)
  const onClose = () => setSelected(null)
  const onSaved = () => { refetch(); setSelected(null) }

  // Glisser-déposer kanban : change le statut (PATCH). « Annulé » reste un
  // drapeau, jamais une colonne — le statut suit son propre ordre fermé.
  const changeStatus = async (item, newStatus) => {
    if (!item || item.statut === newStatus) return
    const prev = item.statut
    setBusyId(item.id)
    dispatch(upsertInstallation({ ...item, statut: newStatus }))
    try {
      await dispatch(updateInstallation({ id: item.id, data: { statut: newStatus } })).unwrap()
    } catch {
      dispatch(upsertInstallation({ ...item, statut: prev }))
      setStatusError("Le changement de statut n'a pas pu être enregistré — réessayez.")
    } finally {
      setBusyId(null)
    }
  }

  // (Ré)assignation rapide du technicien depuis une carte kanban.
  const reassign = async (item, userId) => {
    try {
      await dispatch(updateInstallation({
        id: item.id, data: { technicien_responsable: userId },
      })).unwrap()
      refetch()
    } catch {
      setStatusError("La réassignation n'a pas pu être enregistrée — réessayez.")
    }
  }

  if (loading) return <p className="page-loading">Chargement des chantiers...</p>
  if (error) return <p className="page-error">Erreur : {JSON.stringify(error)}</p>

  return (
    <div className="page lp-page">
      <div className="page-header lp-header">
        <h2>
          Chantiers
          <span className="count-badge">{filtered.length}</span>
        </h2>
        <div className="page-header-actions lp-header-actions">
          <ExportButton
            fetcher={installationsApi.exportInstallations}
            params={{
              ...annuleParam(filters.annule),
              ...(filters.statut ? { statut: filters.statut } : {}),
              ...(filters.type_installation
                ? { type_installation: filters.type_installation } : {}),
              ...(filters.q?.trim() ? { search: filters.q.trim() } : {}),
            }}
            filename="chantiers.xlsx"
          />
          <div className="fb-pills" role="group" aria-label="Changer de vue">
            <button
              type="button"
              className={`fb-pill${view === 'liste' ? ' fb-pill-active' : ''}`}
              onClick={() => setView('liste')}
            >
              Liste
            </button>
            <button
              type="button"
              className={`fb-pill${view === 'kanban' ? ' fb-pill-active' : ''}`}
              onClick={() => setView('kanban')}
            >
              Kanban
            </button>
            <button
              type="button"
              className={`fb-pill${view === 'calendrier' ? ' fb-pill-active' : ''}`}
              onClick={() => setView('calendrier')}
            >
              Calendrier
            </button>
          </div>
        </div>
      </div>

      <FilterBar filters={filters} setFilters={setFilters} items={items} />

      {statusError && (
        <div className="lp-stage-error" role="alert">
          <span>{statusError}</span>
          <button
            type="button"
            className="lp-stage-error-close"
            aria-label="Fermer le message d'erreur"
            onClick={() => setStatusError(null)}
          >
            ✕
          </button>
        </div>
      )}

      <div className="lp-view-area">
        {view === 'liste' && <ListView items={filtered} onOpen={onOpen} />}
        {view === 'kanban' && (
          <KanbanView
            items={filtered}
            onOpen={onOpen}
            onChangeStatus={changeStatus}
            busyId={busyId}
            users={users}
            onReassign={reassign}
          />
        )}
        {view === 'calendrier' && <CalendarView items={filtered} onOpen={onOpen} />}
      </div>

      {selected && (
        <InstallationDetail installation={selected} onClose={onClose} onSaved={onSaved} />
      )}
    </div>
  )
}
