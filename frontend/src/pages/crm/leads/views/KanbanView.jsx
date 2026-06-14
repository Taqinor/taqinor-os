// Vue kanban des leads CRM, façon Odoo : 6 colonnes canoniques (stages.js,
// miroir de STAGES.py — jamais de liste d'étapes en dur ici), glisser-déposer
// via @dnd-kit/core. Le parent gère l'optimistic update : on ne mute rien.
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
import { formatMAD, groupLeadsByStage } from '../../../../features/crm/stages'
import LeadCard from './LeadCard'
import './kanban.css'

// Enveloppe draggable d'une carte ; l'original reste en place (style fantôme)
// pendant que le DragOverlay suit le pointeur.
function DraggableCard({ lead, busy, onOpen, onAutoQuote, users, onReassign }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: lead.id,
    data: { lead },
    disabled: busy,
  })
  return (
    <div
      ref={setNodeRef}
      className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
      {...listeners}
      {...attributes}
    >
      <LeadCard lead={lead} busy={busy} onOpen={onOpen} onAutoQuote={onAutoQuote}
                users={users} onReassign={onReassign} />
    </div>
  )
}

// Colonne d'étape : zone droppable, accent couleur, compteur, total devis.
function StageColumn({ col, children }) {
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
        {col.totalDevis > 0 && (
          <span className="kb-col-money">{formatMAD(col.totalDevis)}</span>
        )}
      </header>
      <div className="kb-col-body">
        {col.count === 0 ? (
          <div className="kb-col-empty">Aucun lead</div>
        ) : (
          children
        )}
      </div>
    </section>
  )
}

export default function KanbanView({
  leads,
  onOpenLead,
  onChangeStage,
  onAutoQuote,
  busyLeadId,
  users,
  onReassign,
}) {
  // distance 6px : un clic simple ouvre la fiche, le drag exige un mouvement ;
  // sur mobile, appui long 150 ms pour glisser, le scroll reste naturel.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
  )
  const columns = useMemo(() => groupLeadsByStage(leads), [leads])
  const [activeLead, setActiveLead] = useState(null)

  const handleDragStart = ({ active }) => {
    setActiveLead(active.data.current?.lead ?? null)
  }

  const handleDragEnd = ({ active, over }) => {
    setActiveLead(null)
    const lead = active.data.current?.lead
    if (lead && over && over.id !== lead.stage) {
      onChangeStage(lead, over.id)
    }
  }

  const handleDragCancel = () => setActiveLead(null)

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="kb-board">
        {columns.map((col) => (
          <StageColumn key={col.key} col={col}>
            {col.leads.map((lead) => (
              <DraggableCard
                key={lead.id}
                lead={lead}
                busy={lead.id === busyLeadId}
                onOpen={onOpenLead}
                onAutoQuote={onAutoQuote}
                users={users}
                onReassign={onReassign}
              />
            ))}
          </StageColumn>
        ))}
      </div>
      <DragOverlay>
        {activeLead ? (
          <div className="kb-drag-overlay">
            <LeadCard lead={activeLead} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
