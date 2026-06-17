import { useEffect, useMemo, useState } from 'react'
import {
  DndContext, DragOverlay, PointerSensor, TouchSensor,
  useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'
import {
  INTERVENTION_STATUSES, INTERVENTION_STATUS_LABELS, INTERVENTION_STATUS_COLORS,
  interventionColumn, interventionStatusLabel, interventionTypeLabel,
} from '../../features/installations/interventionStatuses'
import '../crm/leads/views/kanban.css'
import './views/kanban-chantier.css'

// F4 — Interventions : liste + kanban groupé par statut d'intervention, même
// langage visuel et même glisser-déposer que les kanbans lead/chantier. Le
// statut est la machine à états PROPRE de l'intervention (jamais le chantier).

const fmtDateFR = (iso) => {
  if (!iso) return null
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR')
}

function Card({ it, users, onReassign }) {
  const col = interventionColumn(it.statut)
  return (
    <div className="kb-card" style={{ '--kb-accent': INTERVENTION_STATUS_COLORS[col] }}>
      <div className="kb-card-title">{it.client_nom ?? `Intervention #${it.id}`}</div>
      <div className="kb-card-sub">{interventionTypeLabel(it.type_intervention)}</div>
      <div className="kb-card-meta">
        {it.site_ville && <span className="kb-chip">{it.site_ville}</span>}
        {fmtDateFR(it.date_prevue) && <span className="kb-chip">📅 {fmtDateFR(it.date_prevue)}</span>}
      </div>
      {(it.equipe_noms ?? []).length > 0 && (
        <div className="kb-card-meta">
          <span className="kb-chip">👷 {it.equipe_noms.join(', ')}</span>
        </div>
      )}
      <select
        className="form-select form-select-sm"
        value=""
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => { if (e.target.value) onReassign?.(it, e.target.value) }}
        style={{ marginTop: 6, fontSize: 12 }}
      >
        <option value="">— Réassigner l'équipe —</option>
        {(users ?? []).map((u) => (
          <option key={u.id} value={u.id}>{u.username ?? u.nom ?? `#${u.id}`}</option>
        ))}
      </select>
    </div>
  )
}

function DraggableCard({ it, users, onReassign }) {
  const { setNodeRef, listeners, attributes, isDragging } = useDraggable({ id: it.id, data: { it } })
  return (
    <div ref={setNodeRef} className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
         {...listeners} {...attributes}>
      <Card it={it} users={users} onReassign={onReassign} />
    </div>
  )
}

function Column({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section ref={setNodeRef} className={isOver ? 'kb-col kb-over' : 'kb-col'} style={{ '--kb-accent': col.color }}>
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.items.length}</span>
        </div>
      </header>
      <div className="kb-col-body">
        {col.items.length === 0 ? <div className="kb-col-empty">Aucune intervention</div> : children}
      </div>
    </section>
  )
}

function Kanban({ items, users, onChangeStatus, onReassign, onOpen }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )
  const [active, setActive] = useState(null)
  const columns = useMemo(() => {
    const byCol = Object.fromEntries(INTERVENTION_STATUSES.map((s) => [s, []]))
    for (const it of items ?? []) byCol[interventionColumn(it.statut)].push(it)
    return INTERVENTION_STATUSES.map((s) => ({
      key: s, label: INTERVENTION_STATUS_LABELS[s], color: INTERVENTION_STATUS_COLORS[s], items: byCol[s],
    }))
  }, [items])

  const handleDragEnd = ({ active: a, over }) => {
    setActive(null)
    const it = a.data.current?.it
    if (it && over && over.id !== interventionColumn(it.statut)) onChangeStatus?.(it, over.id)
  }

  return (
    <DndContext sensors={sensors}
                onDragStart={({ active: a }) => setActive(a.data.current?.it ?? null)}
                onDragEnd={handleDragEnd} onDragCancel={() => setActive(null)}>
      <div className="kb-board">
        {columns.map((col) => (
          <Column key={col.key} col={col}>
            {col.items.map((it) => (
              <div key={it.id} onClick={() => onOpen?.(it)}>
                <DraggableCard it={it} users={users} onReassign={onReassign} />
              </div>
            ))}
          </Column>
        ))}
      </div>
      <DragOverlay>{active ? <div className="kb-drag-overlay"><Card it={active} /></div> : null}</DragOverlay>
    </DndContext>
  )
}

export default function InterventionsPage() {
  const [items, setItems]   = useState([])
  const [users, setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [view, setView]     = useState('kanban')
  const [statutFilter, setStatutFilter] = useState('')

  const reload = () =>
    installationsApi.getInterventions()
      .then(r => { setItems(r.data?.results ?? r.data ?? []); setError(null) })
      .catch(e => setError(e?.response?.data ?? e.message))
      .finally(() => setLoading(false))

  useEffect(() => {
    reload()
    crmApi.getAssignableUsers().then(r => setUsers(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // Optimiste : on applique localement puis on persiste (PATCH statut/équipe).
  const onChangeStatus = (it, statut) => {
    setItems(list => list.map(x => (x.id === it.id ? { ...x, statut } : x)))
    installationsApi.updateIntervention(it.id, { statut }).then(reload).catch(reload)
  }
  const onReassign = (it, userId) => {
    installationsApi.updateIntervention(it.id, { equipe: [Number(userId)] }).then(reload).catch(reload)
  }

  const filtered = useMemo(
    () => (statutFilter ? items.filter(i => i.statut === statutFilter) : items),
    [items, statutFilter])

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Interventions
          {items.length > 0 && <span className="count-badge">{items.length}</span>}
        </h2>
        <div className="page-header-actions">
          <button className={`fb-pill${view === 'kanban' ? ' fb-pill-active' : ''}`}
                  onClick={() => setView('kanban')}>Kanban</button>
          <button className={`fb-pill${view === 'liste' ? ' fb-pill-active' : ''}`}
                  onClick={() => setView('liste')}>Liste</button>
        </div>
      </div>

      <p className="text-muted" style={{ marginTop: -8, fontSize: 13 }}>
        Sorties chantier. Le statut d'une intervention est suivi ici et n'affecte
        jamais le statut du chantier.
      </p>

      {loading && <p className="page-loading">Chargement des interventions…</p>}
      {error && <p className="page-error">Erreur : {JSON.stringify(error)}</p>}

      {!loading && !error && view === 'kanban' && (
        <Kanban items={items} users={users}
                onChangeStatus={onChangeStatus} onReassign={onReassign} />
      )}

      {!loading && !error && view === 'liste' && (
        <>
          <div style={{ margin: '8px 0' }}>
            <select className="form-select" style={{ maxWidth: 220 }} value={statutFilter}
                    onChange={e => setStatutFilter(e.target.value)}>
              <option value="">Tous les statuts</option>
              {INTERVENTION_STATUSES.map(s => (
                <option key={s} value={s}>{INTERVENTION_STATUS_LABELS[s]}</option>
              ))}
            </select>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Client</th><th>Ville</th><th>Type</th>
                <th>Date prévue</th><th>Équipe</th><th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(it => (
                <tr key={it.id}>
                  <td><strong>{it.client_nom ?? `#${it.id}`}</strong></td>
                  <td>{it.site_ville || <span className="text-muted">—</span>}</td>
                  <td>{interventionTypeLabel(it.type_intervention)}</td>
                  <td className="text-muted">{fmtDateFR(it.date_prevue) ?? '—'}</td>
                  <td>{(it.equipe_noms ?? []).join(', ') || <span className="text-muted">—</span>}</td>
                  <td>
                    <span className="badge" style={{
                      background: `${INTERVENTION_STATUS_COLORS[interventionColumn(it.statut)]}22`,
                      color: INTERVENTION_STATUS_COLORS[interventionColumn(it.statut)],
                      padding: '2px 8px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                    }}>{interventionStatusLabel(it.statut)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="empty-state">Aucune intervention.</p>
          )}
        </>
      )}
    </div>
  )
}
