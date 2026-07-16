import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
import { Download, ChevronLeft, ChevronRight, Link2 } from 'lucide-react'
import { fetchInstallations, updateInstallation } from '../../features/installations/store/installationsSlice'
import {
  EMPTY_FILTERS,
  filterInstallations,
  statusLabel,
  statusColor,
  upcomingPoses,
  funnelSummary,
  installerLoad,
  isNewlyAssigned,
} from '../../features/installations/statuses'
import importApi from '../../api/importApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import crmApi from '../../api/crmApi'
import {
  Button,
  Badge,
  Segmented,
  Spinner,
  EmptyState,
  Card,
  StatusAccentCard,
  toast,
} from '../../ui'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import FilterBar from './FilterBar'
import ListView from './views/ListView'
import KanbanView from './views/KanbanView'
import InstallationsSkeleton from './views/InstallationsSkeleton'
import InstallationDetail from './InstallationDetail'

const VIEW_KEY = 'taqinor.chantiers.view'
const VALID_VIEWS = ['liste', 'kanban', 'calendrier']

// VX218 — horodatage de la dernière visite de l'écran (localStorage), pour
// distinguer un chantier NOUVELLEMENT confié d'un ancien (badge « Nouveau »).
// Accès défensif : un environnement sans localStorage (SSR, navigation privée
// bloquée) ne casse jamais l'écran, il désactive juste le badge.
const LAST_SEEN_KEY = 'taqinor.chantiers.lastSeen'

function safeStorage() {
  try {
    return typeof window !== 'undefined' && window.localStorage
      ? window.localStorage
      : null
  } catch {
    return null
  }
}

function readLastSeen() {
  try {
    return safeStorage()?.getItem(LAST_SEEN_KEY) ?? null
  } catch {
    return null
  }
}

function writeLastSeen(iso) {
  try {
    safeStorage()?.setItem(LAST_SEEN_KEY, iso)
  } catch { /* stockage indisponible */ }
}

// Paramètres SERVEUR dérivés des filtres « annulés » et « Mes chantiers ».
const serverParams = (filters) => {
  const p = {}
  if (filters.annule === 'seuls') p.annule = 'only'
  else if (filters.annule === 'sans') p.annule = 'sans'
  if (filters.mine === 'only') p.mine = 'only'
  return p
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

// VX149 — même mécanisme d'accent que le kanban interventions
// (`ui/StatusAccentCard`, `--kb-accent`) au lieu d'un `style={{background}}`
// posé à la main sur le point : le point lit désormais l'accent via CSS
// (`.cal-chip-dot` → `background: var(--kb-accent)`).
function Chip({ item, onOpen, onDragStart }) {
  const dot = item.annule ? '#dc2626' : statusColor(item.statut)
  const name = item.reference || item.client_nom || '(Sans réf.)'
  return (
    <StatusAccentCard
      as="button"
      variant="bare"
      accent={dot}
      type="button"
      draggable={!item.annule}
      onDragStart={(e) => onDragStart?.(e, item)}
      className={`cal-chip${item.annule ? ' cal-chip-perdu' : ''}`}
      title={`${name} — ${statusLabel(item.statut)}`}
      onClick={() => onOpen(item)}
    >
      <span className="cal-chip-dot" />
      <span className="cal-chip-name">{name}</span>
    </StatusAccentCard>
  )
}

function CalendarView({ items, onOpen, onReschedule }) {
  const [monthStart, setMonthStart] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [expandedDays, setExpandedDays] = useState({})
  const [dragId, setDragId] = useState(null)

  // N4 — glisser-déposer : déposer une puce sur un autre jour met à jour
  // date_pose_prevue via le parent (qui journalise le changement côté serveur).
  const handleDragStart = (e, item) => {
    setDragId(item.id)
    try { e.dataTransfer.setData('text/plain', String(item.id)) } catch { /* */ }
    e.dataTransfer.effectAllowed = 'move'
  }
  const handleDrop = (cellKey) => {
    const item = (items ?? []).find((it) => it.id === dragId)
    setDragId(null)
    if (item && poseKey(item) !== cellKey) onReschedule?.(item, cellKey)
  }

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

  // Aucune pose planifiée pour le mois affiché (aucune cellule du mois ne porte
  // de chantier) → indice FR explicite plutôt qu'un calendrier vide silencieux.
  const moisVide = cells.every(
    (cell) => !cell.inMonth || (byDay.get(cell.key) ?? []).length === 0)

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

      {moisVide && (
        <p className="cal-empty-month py-2 text-center text-sm text-muted-foreground">
          Aucune pose planifiée ce mois.
        </p>
      )}

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
                dragId ? 'cal-cell-droppable' : '',
              ].filter(Boolean).join(' ')}
              onDragOver={(e) => { if (dragId) e.preventDefault() }}
              onDrop={(e) => { e.preventDefault(); handleDrop(cell.key) }}
            >
              <span className="cal-day-number">{cell.dayNumber}</span>
              <div className="cal-chips">
                {visible.map((it) => (
                  <Chip key={it.id} item={it} onOpen={onOpen} onDragStart={handleDragStart} />
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
  const currentUser = useSelector(s => s.auth?.user)

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

  // VX218 — badge « Nouveau » : chantiers assignés à moi depuis ma dernière
  // visite (lue UNE fois au montage — figée pour la session, sinon le badge
  // s'effacerait tout seul dès le premier rendu). Ouvrir l'écran efface le
  // marqueur pour la PROCHAINE visite (jamais la visite en cours).
  const [lastSeen] = useState(() => readLastSeen())
  useEffect(() => {
    writeLastSeen(new Date().toISOString())
  }, [])
  const nouveaux = useMemo(
    () => (items ?? []).filter((it) => isNewlyAssigned(it, currentUser?.id, lastSeen)),
    [items, currentUser, lastSeen],
  )
  const nouveauxIds = useMemo(() => new Set(nouveaux.map((it) => it.id)), [nouveaux])

  const filtered = useMemo(() => {
    const base = filterInstallations(items, filters)
    return filters.nouveaux ? base.filter((it) => nouveauxIds.has(it.id)) : base
  }, [items, filters, nouveauxIds])

  // N13/N14 — synthèses calculées à la lecture (aucun appel serveur en plus) :
  // poses à venir (≤ 7 j) et répartition funnel + nombre en retard.
  const aVenir = useMemo(() => upcomingPoses(items, 7), [items])
  const synthese = useMemo(() => funnelSummary(items), [items])
  const charge = useMemo(() => installerLoad(filtered, 14), [filtered])

  const [selected, setSelected] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  // VX172 — pending visible sur « Exporter Excel » (VX49 pose déjà le toast
  // d'erreur ; ceci ajoute juste l'état chargement manquant).
  const [xlsxBusy, setXlsxBusy] = useState(false)
  const [users, setUsers] = useState([])
  useEffect(() => {
    crmApi.getAssignableUsers().then(r => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // Les filtres « annulés » et « Mes chantiers » sont des dimensions SERVEUR :
  // on refait l'appel quand ils changent (les autres filtres restent côté client).
  const refetch = () => dispatch(fetchInstallations(serverParams(filters)))

  // N2 — glisser une carte change le statut ; un select réassigne l'installateur.
  // En cas d'échec serveur : message FR + resynchronisation (rollback) du tableau.
  const onChangeStatus = (inst, statut) =>
    dispatch(updateInstallation({ id: inst.id, data: { statut } })).unwrap()
      .catch(() => { toast.error('Changement de statut impossible.'); refetch() })
  const onReassign = (inst, technicien) =>
    dispatch(updateInstallation({ id: inst.id, data: { technicien_responsable: technicien } })).unwrap()
      .catch(() => { toast.error('Réassignation impossible.'); refetch() })
  // N4 — replanifier la pose via glisser-déposer sur le calendrier (le serveur
  // journalise le changement de date dans le chatter).
  const onReschedule = (inst, dateKey) =>
    dispatch(updateInstallation({ id: inst.id, data: { date_pose_prevue: dateKey } })).unwrap()
      .catch(() => { toast.error('Replanification impossible.'); refetch() })
  useEffect(() => {
    dispatch(fetchInstallations(serverParams(filters)))
    // intentionally narrow: only `annule`/`mine` are server-side dimensions
    // (see comment above); the other filter fields are applied client-side
    // and must NOT retrigger a server refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, filters.annule, filters.mine])

  // VX79 — lien interne partageable : /chantiers?id=<pk> ouvre le panneau du
  // chantier ciblé (patron ?lead= de LeadsPage — état DÉRIVÉ, aucun effet).
  // Fermer retire le paramètre pour ne pas ré-ouvrir la fiche. Un id absent des
  // chantiers chargés est signalé par un EmptyState inline (jamais page blanche).
  const wantedId = searchParams.get('id')
  const deepItem = useMemo(() => {
    if (!wantedId) return null
    return (items ?? []).find((it) => String(it.id) === String(wantedId)) ?? null
  }, [wantedId, items])
  // VX79 — id demandé mais introuvable (une fois le chargement terminé) : on
  // affiche un EmptyState inline plutôt qu'un panneau vide ou une page blanche.
  const deepMissing = !!wantedId && !loading && !deepItem

  const clearDeepLink = () => {
    if (searchParams.has('id')) {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.delete('id')
        return next
      }, { replace: true })
    }
  }
  const onOpen = (it) => setSelected(it)
  const onClose = () => { setSelected(null); clearDeepLink() }
  const onSaved = () => { refetch(); setSelected(null); clearDeepLink() }

  // VX79 — « Copier le lien » : URL INTERNE de l'ERP (jamais un lien public) que
  // l'on peut envoyer à un collègue — /chantiers?id=<pk> rouvre le même chantier.
  const copierLien = async (it) => {
    const url = `${window.location.origin}/chantiers?id=${it.id}`
    try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
    toast.success('Lien du chantier copié.')
  }

  // Panneau ouvert : sélection manuelle OU chantier ciblé par le lien profond.
  const detailItem = selected ?? deepItem

  // J143 — chargement différé anti-scintillement (foundation useDelayedLoading) :
  // rien sous 300 ms, spinner discret jusqu'à 500 ms, puis squelette calqué sur
  // la vue active (kanban / liste / calendrier). Le squelette ne s'affiche que
  // lors d'un PREMIER chargement (aucun chantier déjà à l'écran) — un refetch en
  // arrière-plan garde le tableau en place.
  const firstLoad = loading && items.length === 0
  const { showSpinner, showSkeleton } = useDelayedLoading(firstLoad)
  if (firstLoad && !showSkeleton) {
    // Phase imperceptible (rien) ou spinner discret — on ne monte pas encore le
    // squelette pour ne pas clignoter sur un chargement rapide.
    return (
      <div className="page lp-page">
        {showSpinner && (
          <div
            role="status"
            aria-live="polite"
            className="flex items-center gap-2 py-16 text-sm text-muted-foreground"
          >
            <Spinner /> Chargement des chantiers…
          </div>
        )}
      </div>
    )
  }

  // L'erreur ne couvre tout l'écran QUE si rien n'est chargé (échec initial).
  // Avec des chantiers déjà à l'écran, une erreur de fond (ex. écriture refusée)
  // s'affiche en bandeau au-dessus du tableau sans démonter le board, les
  // modales ouvertes ni la position de défilement.
  if (error && items.length === 0) {
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
      {error && (
        <div role="alert"
             className="mb-2 flex flex-wrap items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <span className="flex-1">
            {typeof error === 'string' ? error : 'Une erreur est survenue. Réessayez.'}
          </span>
          <Button size="sm" variant="outline" onClick={refetch}>Réessayer</Button>
        </div>
      )}
      <div className="page-header lp-header">
        <h2 className="flex flex-wrap items-center gap-2">
          Chantiers
          <Badge tone="primary">{filtered.length}</Badge>
          {aVenir.length > 0 && (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full bg-info/10 px-2 py-0.5 text-xs font-semibold text-info"
              onClick={() => setFilters((f) => ({ ...f, statut: 'planifie' }))}
              title="Filtrer les chantiers planifiés"
            >
              {aVenir.length} pose(s) à venir (≤ 7 j)
            </button>
          )}
          {/* VX218 — raccourci « Mes nouveaux chantiers » : chantiers qui
              m'ont été assignés depuis ma dernière visite. */}
          {nouveaux.length > 0 && (
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-semibold text-success"
              onClick={() => setFilters((f) => ({ ...f, mine: 'only', nouveaux: true }))}
              title="Filtrer mes chantiers nouvellement assignés"
              data-testid="chantiers-nouveaux-shortcut"
            >
              {nouveaux.length} nouveau(x) chantier(s)
            </button>
          )}
        </h2>
        <div className="page-header-actions lp-header-actions flex flex-wrap items-center gap-2">
          {/* VX79 — « Copier le lien » du chantier ouvert : URL INTERNE
              partageable (/chantiers?id=<pk>), pour l'envoyer à un collègue. */}
          {detailItem && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => copierLien(detailItem)}
              title="Copier le lien interne de ce chantier (à envoyer à un collègue)"
            >
              <Link2 /> Copier le lien
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={xlsxBusy}
            onClick={() => {
              const pending = downloadBlobInGesture()
              setXlsxBusy(true)
              importApi.exportList('chantiers', filtered.map(i => i.id))
                .then(r => pending.deliver(r.data, 'chantiers.xlsx'))
                .catch(() => {})
                .finally(() => setXlsxBusy(false))
            }}
          >
            {xlsxBusy ? <Spinner /> : <Download />} Exporter Excel
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

      {/* VX79 — lien profond ?id=<pk> pointant vers un chantier introuvable :
          EmptyState inline (jamais une page blanche). */}
      {deepMissing && (
        <EmptyState
          title="Chantier introuvable"
          description="Le chantier de ce lien n'existe plus ou n'est pas accessible."
          action={<Button size="sm" variant="outline" onClick={clearDeepLink}>Fermer</Button>}
          className="my-2 border-warning/40"
        />
      )}

      {/* N14 — synthèse funnel : compte par statut + nb en retard. */}
      <div className="flex flex-wrap items-center gap-2 py-1 text-xs">
        {synthese.rows.map((r) => (
          <button
            key={r.key}
            type="button"
            className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 font-medium text-muted-foreground hover:bg-muted"
            onClick={() => setFilters((f) => ({ ...f, statut: r.key }))}
            title={`Filtrer : ${r.label}`}
          >
            <span className="size-2 rounded-full" style={{ background: statusColor(r.key) }} />
            {r.label}
            <span className="tabular-nums font-semibold text-foreground">{r.count}</span>
          </button>
        ))}
        {synthese.retard > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 font-semibold text-destructive">
            {synthese.retard} pose(s) en retard
          </span>
        )}
      </div>

      {/* N14 — charge installateur (poses à venir ≤ 14 j) sur Kanban/Calendrier. */}
      {(view === 'kanban' || view === 'calendrier') && charge.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 py-1 text-xs">
          <span className="font-semibold text-muted-foreground">Charge (≤ 14 j) :</span>
          {charge.map((c) => (
            <span key={c.nom}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5">
              {c.nom}
              <span className="tabular-nums font-semibold text-foreground">{c.count}</span>
            </span>
          ))}
        </div>
      )}

      <div className="lp-view-area">
        {showSkeleton && (
          <>
            <span className="sr-only" role="status" aria-live="polite">
              Chargement des chantiers…
            </span>
            <InstallationsSkeleton view={view} />
          </>
        )}
        {!showSkeleton && view === 'liste' && (
          <ListView items={filtered} onOpen={onOpen} users={users}
                    onChangeStatus={onChangeStatus} onReassign={onReassign}
                    nouveauxIds={nouveauxIds} />
        )}
        {!showSkeleton && view === 'kanban' && (
          <KanbanView items={filtered} onOpen={onOpen} onChangeStatus={onChangeStatus}
                      users={users} onReassign={onReassign} nouveauxIds={nouveauxIds} />
        )}
        {!showSkeleton && view === 'calendrier' && (
          filtered.length === 0 ? (
            <Card className="p-0">
              <EmptyState
                title="Aucun chantier à planifier"
                description="Aucun chantier ne correspond aux filtres actuels."
                className="border-0"
              />
            </Card>
          ) : (
            <CalendarView items={filtered} onOpen={onOpen} onReschedule={onReschedule} />
          )
        )}
      </div>

      {detailItem && (
        <InstallationDetail installation={detailItem} onClose={onClose} onSaved={onSaved} />
      )}
    </div>
  )
}
