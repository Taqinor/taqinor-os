// N2 — Vue kanban des chantiers : colonnes = entonnoir chantier canonique
// (statuses.js, miroir du backend), glisser-déposer via @dnd-kit/core, même
// langage visuel que le kanban des leads. Le parent gère le changement de
// statut (optimistic) ; cette vue ne mute rien directement.
// J43 — cartes portées sur le système de design (StatusPill, Progress, Select)
// SANS toucher au câblage du drag (dnd-kit) : la structure kb-* est conservée.
import { useMemo, useState } from 'react'
import { MapPin, Zap, CalendarDays } from 'lucide-react'
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
import {
  StatusPill,
  Progress,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import '../../crm/leads/views/kanban.css'
import './kanban-chantier.css'

// Sentinelle « aucun installateur » (le Select du design system n'accepte pas '').
const NO_TECH = '__none__'

function ChantierCard({ inst, users, onReassign }) {
  const techValue = inst.technicien_responsable ? String(inst.technicien_responsable) : NO_TECH
  return (
    <div className="kb-card kc-card" style={{ '--kb-accent': STATUS_COLORS[canonicalStatus(inst.statut)] }}>
      <div className="kc-card-top">
        <span className="kc-card-ref">{inst.reference}</span>
        <StatusPill status={inst.statut} label={STATUS_LABELS[canonicalStatus(inst.statut)]} dot={false} />
      </div>
      <div className="kc-card-sub">{inst.client_nom ?? '—'}</div>
      <div className="kc-chips">
        {inst.site_ville && (
          <span className="kc-chip"><MapPin className="kc-chip-icon" aria-hidden="true" />{inst.site_ville}</span>
        )}
        {inst.puissance_installee_kwc && (
          <span className="kc-chip"><Zap className="kc-chip-icon" aria-hidden="true" />{inst.puissance_installee_kwc} kWc</span>
        )}
        {formatDate(inst.date_pose_prevue) !== '—' && (
          <span className="kc-chip"><CalendarDays className="kc-chip-icon" aria-hidden="true" />{formatDate(inst.date_pose_prevue)}</span>
        )}
      </div>
      {Number.isInteger(inst.checklist_completion) && (
        <div className="kc-progress">
          <Progress
            value={inst.checklist_completion}
            tone={inst.checklist_completion === 100 ? 'success' : 'primary'}
          />
          <span className="kc-progress-label">{inst.checklist_completion}%</span>
        </div>
      )}
      {/* Réassignation de l'installateur (même comportement que le kanban leads). */}
      {onReassign && (
        <div
          className="kc-reassign"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <Select
            value={techValue}
            onValueChange={(v) => onReassign(inst, v === NO_TECH ? null : v)}
          >
            <SelectTrigger className="h-8 text-xs" aria-label="Installateur">
              <SelectValue placeholder="Installateur" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_TECH}>— Installateur —</SelectItem>
              {(users ?? []).map((u) => (
                <SelectItem key={u.id} value={String(u.id)}>
                  {u.username ?? u.nom ?? `#${u.id}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
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
