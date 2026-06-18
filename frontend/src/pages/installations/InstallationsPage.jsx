import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Download, ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchInstallations, updateInstallation } from '../../features/installations/store/installationsSlice'
import {
  EMPTY_FILTERS,
  filterInstallations,
  statusLabel,
  statusColor,
} from '../../features/installations/statuses'
import importApi, { downloadXlsx } from '../../api/importApi'
import crmApi from '../../api/crmApi'
import {
  Button,
  Badge,
  Segmented,
  Spinner,
  EmptyState,
  Card,
} from '../../ui'
import FilterBar from './FilterBar'
import ListView from './views/ListView'
import KanbanView from './views/KanbanView'
import InstallationDetail from './InstallationDetail'

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
        <div className="cal-nav flex items-center gap-1">
          <Button type="button" size="sm" variant="outline"
                  onClick={() => goMonth(-1)} aria-label="Mois précédent">
            <ChevronLeft />
          </Button>
          <Button type="button" size="sm" variant="outline"
                  onClick={() => goMonth(1)} aria-label="Mois suivant">
            <ChevronRight />
          </Button>
        </div>
        <h3 className="cal-title">{title}</h3>
        <Button type="button" size="sm" variant="outline" onClick={goToday}>
          Aujourd&apos;hui
        </Button>
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
  const [users, setUsers] = useState([])
  useEffect(() => {
    crmApi.getAssignableUsers().then(r => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // N2 — glisser une carte change le statut ; un select réassigne l'installateur.
  const onChangeStatus = (inst, statut) =>
    dispatch(updateInstallation({ id: inst.id, data: { statut } }))
  const onReassign = (inst, technicien) =>
    dispatch(updateInstallation({ id: inst.id, data: { technicien_responsable: technicien } }))

  // Le filtre « annulés » est une dimension SERVEUR : on refait l'appel avec
  // le bon paramètre quand il change (les autres filtres restent côté client).
  const refetch = () => dispatch(fetchInstallations(annuleParam(filters.annule)))
  useEffect(() => {
    dispatch(fetchInstallations(annuleParam(filters.annule)))
  }, [dispatch, filters.annule])

  const onOpen = (it) => setSelected(it)
  const onClose = () => setSelected(null)
  const onSaved = () => { refetch(); setSelected(null) }

  if (loading) {
    return (
      <div className="page lp-page">
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Spinner /> Chargement des chantiers…
        </div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="page lp-page">
        <EmptyState
          title="Impossible de charger les chantiers"
          description={typeof error === 'string' ? error : 'Une erreur est survenue. Réessayez.'}
          action={<Button size="sm" onClick={refetch}>Réessayer</Button>}
          className="my-8 border-destructive/40"
        />
      </div>
    )
  }

  return (
    <div className="page lp-page">
      <div className="page-header lp-header">
        <h2 className="flex items-center gap-2">
          Chantiers
          <Badge tone="primary">{filtered.length}</Badge>
        </h2>
        <div className="page-header-actions lp-header-actions flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => importApi.exportList('chantiers', filtered.map(i => i.id))
              .then(r => downloadXlsx(r.data, 'chantiers.xlsx')).catch(() => {})}
          >
            <Download /> Exporter Excel
          </Button>
          <Segmented
            size="sm"
            value={view}
            onChange={setView}
            aria-label="Changer de vue"
            options={[
              { value: 'liste', label: 'Liste' },
              { value: 'kanban', label: 'Kanban' },
              { value: 'calendrier', label: 'Calendrier' },
            ]}
          />
        </div>
      </div>

      <FilterBar filters={filters} setFilters={setFilters} items={items} />

      <div className="lp-view-area">
        {view === 'liste' && <ListView items={filtered} onOpen={onOpen} />}
        {view === 'kanban' && (
          <KanbanView items={filtered} onOpen={onOpen} onChangeStatus={onChangeStatus}
                      users={users} onReassign={onReassign} />
        )}
        {view === 'calendrier' && (
          filtered.length === 0 ? (
            <Card className="p-0">
              <EmptyState
                title="Aucun chantier à planifier"
                description="Aucun chantier ne correspond aux filtres actuels."
                className="border-0"
              />
            </Card>
          ) : (
            <CalendarView items={filtered} onOpen={onOpen} />
          )
        )}
      </div>

      {selected && (
        <InstallationDetail installation={selected} onClose={onClose} onSaved={onSaved} />
      )}
    </div>
  )
}
