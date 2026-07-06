import { useMemo, useState } from 'react'
import {
  DndContext, DragOverlay, PointerSensor, TouchSensor, useDraggable,
  useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { Badge } from '../../../ui'
import { StatutTache } from '../constants'
import ChronoButton from './ChronoWidget'

/* XPRJ11 — Vue kanban des Tache par colonne de statut (a_faire/en_cours/
   bloque/termine — statuts PROPRES au module, jamais STAGES.py). Glisser-
   déposer PATCH le statut ; alternative clavier via un <select> sous chaque
   carte (miroir du kanban CRM leads, KanbanView.jsx). Le parent gère
   l'optimistic update + rollback (onChangeStatut ne rejette jamais côté
   affichage : l'appelant restaure l'état en cas d'échec serveur). */

const COLONNES = [
  { key: 'a_faire', label: 'À faire' },
  { key: 'en_cours', label: 'En cours' },
  { key: 'bloque', label: 'Bloquée' },
  { key: 'termine', label: 'Terminée' },
]

function groupTachesByStatut(taches) {
  const parKey = Object.fromEntries(COLONNES.map((c) => [c.key, []]))
  for (const t of taches) {
    if (parKey[t.statut]) parKey[t.statut].push(t)
    else parKey.a_faire.push(t)
  }
  return COLONNES.map((c) => ({ ...c, taches: parKey[c.key], count: parKey[c.key].length }))
}

function StatutMover({ tache, onChangeStatut, busy }) {
  return (
    <div
      className="mt-2"
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <label className="sr-only" htmlFor={`tk-statut-${tache.id}`}>
        Changer le statut de {tache.libelle}
      </label>
      <select
        id={`tk-statut-${tache.id}`}
        className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={tache.statut}
        disabled={busy}
        onChange={(e) => onChangeStatut(tache, e.target.value)}
      >
        {COLONNES.map((c) => (
          <option key={c.key} value={c.key}>{c.label}</option>
        ))}
      </select>
    </div>
  )
}

function TacheCard({ tache }) {
  return (
    <div className="rounded-lg border bg-card p-3 shadow-ui-xs">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium">{tache.libelle}</span>
        {tache.code_wbs && <span className="text-xs text-muted-foreground">{tache.code_wbs}</span>}
      </div>
      {tache.assigne_nom && (
        <div className="mt-1 text-xs text-muted-foreground">{tache.assigne_nom}</div>
      )}
      {tache.date_fin_prevue && (
        <div className="mt-1 text-xs text-muted-foreground">Échéance : {tache.date_fin_prevue}</div>
      )}
      <div className="mt-2" onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()}>
        <ChronoButton tache={tache} />
      </div>
    </div>
  )
}

function DraggableCard({ tache, busy, onChangeStatut }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: tache.id,
    data: { tache },
    disabled: busy,
  })
  return (
    <div ref={setNodeRef} className={isDragging ? 'opacity-40' : ''}>
      <div {...listeners} {...attributes}>
        <TacheCard tache={tache} />
      </div>
      <StatutMover tache={tache} onChangeStatut={onChangeStatut} busy={busy} />
    </div>
  )
}

function StatutColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section
      ref={setNodeRef}
      className={`flex min-w-56 flex-1 flex-col gap-2 rounded-lg border bg-muted/20 p-2 ${isOver ? 'ring-2 ring-primary/40' : ''}`}
    >
      <header className="flex items-center justify-between px-1">
        <StatutTache status={col.key} />
        <Badge tone="neutral">{col.count}</Badge>
      </header>
      <div className="flex flex-col gap-2">
        {col.count === 0 ? (
          <div className="rounded-md border border-dashed p-3 text-center text-xs text-muted-foreground">
            Aucune tâche
          </div>
        ) : children}
      </div>
    </section>
  )
}

export default function TachesKanbanView({ taches, onChangeStatut, busyTacheId }) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )
  const columns = useMemo(() => groupTachesByStatut(taches), [taches])
  const [activeTache, setActiveTache] = useState(null)

  const handleDragStart = ({ active }) => setActiveTache(active.data.current?.tache ?? null)

  const handleDragEnd = ({ active, over }) => {
    setActiveTache(null)
    const tache = active.data.current?.tache
    if (!tache || !over || over.id === tache.statut) return
    onChangeStatut(tache, over.id)
  }

  const handleDragCancel = () => setActiveTache(null)

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="flex gap-3 overflow-x-auto pb-2">
        {columns.map((col) => (
          <StatutColumn key={col.key} col={col}>
            {col.taches.map((t) => (
              <DraggableCard
                key={t.id}
                tache={t}
                busy={t.id === busyTacheId}
                onChangeStatut={onChangeStatut}
              />
            ))}
          </StatutColumn>
        ))}
      </div>
      <DragOverlay>
        {activeTache ? <TacheCard tache={activeTache} /> : null}
      </DragOverlay>
    </DndContext>
  )
}
