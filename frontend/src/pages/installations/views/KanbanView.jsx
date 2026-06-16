// N2 — Vue kanban des chantiers : colonnes = entonnoir chantier canonique
// (statuses.js, miroir du backend), glisser-déposer via @dnd-kit/core, même
// langage visuel que le kanban des leads. Le parent gère le changement de
// statut (optimistic) ; cette vue ne mute rien directement.
import { useMemo, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  STATUS_COLORS,
  canonicalStatus,
} from '../../../features/installations/statuses'
import '../../crm/leads/views/kanban.css'
import './kanban-chantier.css'

const formatDateFR = (iso) => {
  if (!iso) return null
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR')
}

function ChantierCard({ inst, users, onReassign }) {
  return (
    <div className="kb-card" style={{ '--kb-accent': STATUS_COLORS[canonicalStatus(inst.statut)] }}>
      <div className="kb-card-title">{inst.reference}</div>
      <div className="kb-card-sub">{inst.client_nom ?? '—'}</div>
      <div className="kb-card-meta">
        {inst.site_ville && <span className="kb-chip">{inst.site_ville}</span>}
        {inst.puissance_installee_kwc && (
          <span className="kb-chip">{inst.puissance_installee_kwc} kWc</span>
        )}
      </div>
      {formatDateFR(inst.date_pose_prevue) && (
        <div className="kb-card-meta">
          <span className="kb-chip">📅 {formatDateFR(inst.date_pose_prevue)}</span>
        </div>
      )}
      {Number.isInteger(inst.checklist_completion) && (
        <div className="kb-card-meta">
          <span className="kb-chip">✓ {inst.checklist_completion}%</span>
        </div>
      )}
      {/* Réassignation de l'installateur (même comportement que le kanban leads). */}
      <select
        className="form-select form-select-sm"
        value={inst.technicien_responsable ?? ''}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
        onChange={(e) => onReassign?.(inst, e.target.value || null)}
        style={{ marginTop: 6, fontSize: 12 }}
      >
        <option value="">— Installateur —</option>
        {(users ?? []).map((u) => (
          <option key={u.id} value={u.id}>{u.username ?? u.nom ?? `#${u.id}`}</option>
        ))}
      </select>
    </div>
  )
}

function DraggableCard({ inst, users, onReassign }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: inst.id, data: { inst },
  })
  return (
    <div ref={setNodeRef}
         className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
         {...listeners} {...attributes}>
      <ChantierCard inst={inst} users={users} onReassign={onReassign} />
    </div>
  )
}

function StatusColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section ref={setNodeRef} className={isOver ? 'kb-col kb-over' : 'kb-col'}
             style={{ '--kb-accent': col.color }}>
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.items.length}</span>
        </div>
      </header>
      <div className="kb-col-body">
        {col.items.length === 0 ? (
          <div className="kb-col-empty">Aucun chantier</div>
        ) : children}
      </div>
    </section>
  )
}

export default function KanbanView({ items, onOpen, onChangeStatus, users, onReassign }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )
  const [active, setActive] = useState(null)

  const columns = useMemo(() => {
    const byCol = Object.fromEntries(INSTALLATION_STATUSES.map((s) => [s, []]))
    for (const it of items ?? []) {
      const col = canonicalStatus(it.statut)
      if (byCol[col]) byCol[col].push(it)
      else (byCol[INSTALLATION_STATUSES[0]]).push(it)
    }
    return INSTALLATION_STATUSES.map((s) => ({
      key: s, label: STATUS_LABELS[s], color: STATUS_COLORS[s], items: byCol[s],
    }))
  }, [items])

  const handleDragEnd = ({ active: a, over }) => {
    setActive(null)
    const inst = a.data.current?.inst
    if (inst && over && over.id !== canonicalStatus(inst.statut)) {
      onChangeStatus?.(inst, over.id)
    }
  }

  return (
    <DndContext sensors={sensors}
                onDragStart={({ active: a }) => setActive(a.data.current?.inst ?? null)}
                onDragEnd={handleDragEnd}
                onDragCancel={() => setActive(null)}>
      <div className="kb-board">
        {columns.map((col) => (
          <StatusColumn key={col.key} col={col}>
            {col.items.map((inst) => (
              <div key={inst.id} onClick={() => onOpen?.(inst)}>
                <DraggableCard inst={inst} users={users} onReassign={onReassign} />
              </div>
            ))}
          </StatusColumn>
        ))}
      </div>
      <DragOverlay>
        {active ? (
          <div className="kb-drag-overlay">
            <ChantierCard inst={active} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
