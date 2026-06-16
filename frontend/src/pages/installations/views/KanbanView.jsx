// Vue kanban des chantiers, façon Odoo : 7 colonnes de statut (statuses.js,
// liste fermée en ordre d'entonnoir — jamais alphabétique), glisser-déposer
// via @dnd-kit/core. Même langage visuel que le kanban des leads (kb-*).
// Le parent gère l'optimistic update : on ne mute rien ici.
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
import { groupInstallationsByStatus } from '../../../features/installations/statuses'
import ChantierCard from './ChantierCard'
import '../../crm/leads/views/kanban.css'

function DraggableCard({ item, busy, onOpen, users, onReassign }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: item.id,
    data: { item },
    disabled: busy,
  })
  return (
    <div
      ref={setNodeRef}
      className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
      {...listeners}
      {...attributes}
    >
      <ChantierCard item={item} busy={busy} onOpen={onOpen}
                    users={users} onReassign={onReassign} />
    </div>
  )
}

function StatusColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section
      ref={setNodeRef}
      className={isOver ? 'kb-col kb-over' : 'kb-col'}
      style={{ '--kb-accent': col.color }}
    >
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.count}</span>
        </div>
      </header>
      <div className="kb-col-body">
        {col.count === 0 ? (
          <div className="kb-col-empty">Aucun chantier</div>
        ) : (
          children
        )}
      </div>
    </section>
  )
}

export default function KanbanView({
  items,
  onOpen,
  onChangeStatus,
  busyId,
  users,
  onReassign,
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
  )
  const columns = useMemo(() => groupInstallationsByStatus(items), [items])
  const [active, setActive] = useState(null)

  const handleDragStart = ({ active: a }) => {
    setActive(a.data.current?.item ?? null)
  }

  const handleDragEnd = ({ active: a, over }) => {
    setActive(null)
    const item = a.data.current?.item
    if (item && over && over.id !== item.statut) {
      onChangeStatus(item, over.id)
    }
  }

  const handleDragCancel = () => setActive(null)

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="kb-board">
        {columns.map((col) => (
          <StatusColumn key={col.key} col={col}>
            {col.items.map((item) => (
              <DraggableCard
                key={item.id}
                item={item}
                busy={item.id === busyId}
                onOpen={onOpen}
                users={users}
                onReassign={onReassign}
              />
            ))}
          </StatusColumn>
        ))}
      </div>
      <DragOverlay>
        {active ? (
          <div className="kb-drag-overlay">
            <ChantierCard item={active} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
