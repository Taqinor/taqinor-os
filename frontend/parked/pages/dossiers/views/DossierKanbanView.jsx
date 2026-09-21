// NTWFL21 — vue kanban des dossiers transverses : colonnes = `statut` de
// `core.Dossier`, glisser-déposer via @dnd-kit/core (même outillage que les
// kanbans leads/chantiers de l'app : DndContext + useDraggable/useDroppable +
// `features/kanban/kanbanA11y` pour les annonces lecteur d'écran). Le statut
// du dossier n'est PAS un entonnoir séquentiel (contrairement au funnel
// commercial ou au chantier) : n'importe quelle colonne peut recevoir la
// carte, sans règle « une étape à la fois ». Le parent gère la mutation
// (`onChangeStatus`, optimiste) ; cette vue ne mute rien directement.
import { useMemo, useState } from 'react'
import { User, CalendarDays } from 'lucide-react'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  buildKanbanAnnouncements,
  kanbanScreenReaderInstructions,
} from '../../../features/kanban/kanbanA11y'
import { Badge, StatusPill } from '../../../ui'
import { formatDate } from '../../../lib/format'
import { usePrefersReducedMotion } from '../../../hooks/usePrefersReducedMotion'
import {
  STATUT_DOSSIER_OPTIONS, prioriteTone, estEnRetard,
} from '../../../features/workflow/dossiers'

const DROP_ANIMATION = { duration: 180, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' }
const DROP_ANIMATION_REDUCED = { duration: 1, easing: 'linear' }

// Alternative CLAVIER/tactile au glisser-déposer : un <select> natif propose
// TOUS les autres statuts (aucune contrainte d'adjacence pour un dossier —
// contrairement à un entonnoir de vente ou de chantier). `stopPropagation` :
// manipuler le select ne démarre jamais un drag ni n'ouvre la fiche.
function StatusMover({ dossier, onChangeStatus }) {
  if (!onChangeStatus) return null
  const stop = (e) => e.stopPropagation()
  return (
    <div className="kb-stage-mover" onClick={stop} onPointerDown={stop} onTouchStart={stop}>
      <label className="sr-only" htmlFor={`dos-statut-${dossier.id}`}>
        Changer le statut du dossier {dossier.titre}
      </label>
      <select
        id={`dos-statut-${dossier.id}`}
        className="form-control kb-stage-select"
        value={dossier.statut}
        onChange={(e) => {
          const next = e.target.value
          if (next !== dossier.statut) onChangeStatus(dossier, next)
        }}
      >
        {STATUT_DOSSIER_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

function DossierCard({ dossier, aujourdHui }) {
  const enRetard = estEnRetard(dossier, aujourdHui)
  return (
    <div className="kb-card" style={{ '--kb-accent': 'var(--warning)' }}>
      <div className="kb-card-top">
        <span className="kc-card-ref">{dossier.type_dossier_label}</span>
        <Badge tone={prioriteTone(dossier.priorite)}>{dossier.priorite_label}</Badge>
      </div>
      <div className="kc-card-sub">{dossier.titre}</div>
      <div className="kc-chips">
        {dossier.proprietaire_username && (
          <span className="kc-chip"><User className="kc-chip-icon" aria-hidden="true" />{dossier.proprietaire_username}</span>
        )}
        {dossier.echeance && (
          <span className="kc-chip"><CalendarDays className="kc-chip-icon" aria-hidden="true" />{formatDate(dossier.echeance)}</span>
        )}
        {enRetard && <StatusPill tone="danger" label="En retard" dot={false} />}
      </div>
    </div>
  )
}

function DraggableCard({ dossier, aujourdHui, onOpen, onChangeStatus }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: dossier.id, data: { dossier },
  })
  return (
    <div ref={setNodeRef} className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}>
      <button
        type="button"
        className="kb-card-open"
        onClick={() => onOpen?.(dossier)}
        {...listeners}
        {...attributes}
      >
        <DossierCard dossier={dossier} aujourdHui={aujourdHui} />
      </button>
      <StatusMover dossier={dossier} onChangeStatus={onChangeStatus} />
    </div>
  )
}

function StatutColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section ref={setNodeRef} className={isOver ? 'kb-col kb-over' : 'kb-col'}>
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.items.length}</span>
        </div>
      </header>
      <div className="kb-col-body">
        {col.items.length === 0 ? (
          <div className="kb-col-empty">Aucun dossier</div>
        ) : children}
      </div>
    </section>
  )
}

export default function DossierKanbanView({ items, onOpen, onChangeStatus, aujourdHui }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )
  const [active, setActive] = useState(null)
  const prefersReducedMotion = usePrefersReducedMotion()

  const columns = useMemo(() => {
    const parCol = Object.fromEntries(STATUT_DOSSIER_OPTIONS.map((o) => [o.value, []]))
    for (const d of items ?? []) {
      (parCol[d.statut] ?? parCol[STATUT_DOSSIER_OPTIONS[0].value]).push(d)
    }
    return STATUT_DOSSIER_OPTIONS.map((o) => ({ key: o.value, label: o.label, items: parCol[o.value] }))
  }, [items])

  const announcements = useMemo(() => {
    const byId = new Map((items ?? []).map((d) => [d.id, d]))
    const labelFor = (id) => {
      const opt = STATUT_DOSSIER_OPTIONS.find((o) => o.value === id)
      if (opt) return opt.label
      return byId.get(id)?.titre ?? String(id)
    }
    return buildKanbanAnnouncements(labelFor)
  }, [items])

  const handleDragEnd = ({ active: a, over }) => {
    setActive(null)
    const dossier = a.data.current?.dossier
    if (!dossier || !over || over.id === dossier.statut) return
    onChangeStatus?.(dossier, over.id)
  }

  return (
    <DndContext
      sensors={sensors}
      accessibility={{ announcements, screenReaderInstructions: kanbanScreenReaderInstructions }}
      onDragStart={({ active: a }) => setActive(a.data.current?.dossier ?? null)}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActive(null)}
    >
      <div className="kb-board">
        {columns.map((col) => (
          <StatutColumn key={col.key} col={col}>
            {col.items.map((d) => (
              <DraggableCard
                key={d.id}
                dossier={d}
                aujourdHui={aujourdHui}
                onOpen={onOpen}
                onChangeStatus={onChangeStatus}
              />
            ))}
          </StatutColumn>
        ))}
      </div>
      <DragOverlay dropAnimation={prefersReducedMotion ? DROP_ANIMATION_REDUCED : DROP_ANIMATION}>
        {active ? (
          <div className={prefersReducedMotion ? 'kb-drag-overlay kb-drag-overlay--flat' : 'kb-drag-overlay'}>
            <DossierCard dossier={active} aujourdHui={aujourdHui} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
