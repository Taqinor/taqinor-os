import { useMemo, useState } from 'react'
import {
  DndContext, PointerSensor, useDraggable, useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button, IconButton } from '../../../ui'
import {
  buildMonthGrid, isSameDay, today as todayUtil, WEEKDAY_LABELS,
} from '../../../ui/date-utils'

/* XPRJ11 — Vue calendrier mensuelle des Tache par date_fin_prevue.
   Drag-to-reschedule appelle onReprogrammer(tache, nouvelleDateISO) qui
   délègue à l'action serveur `reprogrammer` (cascade successeurs conservée).
   Le parent gère l'optimistic update + rollback réseau (toast). */

const pad2 = (n) => String(n).padStart(2, '0')
const toISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`

function parseLocalISO(iso) {
  if (!iso) return null
  const [y, m, d] = iso.split('-').map((p) => parseInt(p, 10))
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

function TacheChip({ tache }) {
  return (
    <div className="truncate rounded border bg-card px-1.5 py-0.5 text-xs shadow-ui-xs" title={tache.libelle}>
      {tache.libelle}
    </div>
  )
}

function DraggableChip({ tache, busy }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `tache-${tache.id}`,
    data: { tache },
    disabled: busy,
  })
  return (
    <div ref={setNodeRef} {...listeners} {...attributes} className={isDragging ? 'opacity-40' : ''}>
      <TacheChip tache={tache} />
    </div>
  )
}

function DayCell({ cell, taches, busyTacheId }) {
  const key = toISO(cell.date)
  const { setNodeRef, isOver } = useDroppable({ id: key })
  const isToday = isSameDay(cell.date, todayUtil())
  return (
    <div
      ref={setNodeRef}
      className={[
        'flex min-h-24 flex-col gap-1 border p-1',
        cell.inMonth ? 'bg-card' : 'bg-muted/20 text-muted-foreground',
        isToday ? 'ring-2 ring-primary/50' : '',
        isOver ? 'bg-primary/10' : '',
      ].filter(Boolean).join(' ')}
    >
      <span className="text-xs font-medium">{cell.date.getDate()}</span>
      <div className="flex flex-col gap-1">
        {taches.map((t) => (
          <DraggableChip key={t.id} tache={t} busy={t.id === busyTacheId} />
        ))}
      </div>
    </div>
  )
}

export default function TachesCalendarView({ taches, onReprogrammer, busyTacheId }) {
  const [monthStart, setMonthStart] = useState(() => {
    const d = new Date()
    return new Date(d.getFullYear(), d.getMonth(), 1)
  })
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))

  const cells = useMemo(
    () => buildMonthGrid(monthStart.getFullYear(), monthStart.getMonth()),
    [monthStart],
  )

  const byDay = useMemo(() => {
    const map = new Map()
    for (const t of taches ?? []) {
      const d = parseLocalISO(t.date_fin_prevue)
      if (!d) continue
      const key = toISO(d)
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(t)
    }
    return map
  }, [taches])

  const title = (() => {
    const raw = monthStart.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
    return raw.charAt(0).toUpperCase() + raw.slice(1)
  })()

  const goMonth = (delta) =>
    setMonthStart((d) => new Date(d.getFullYear(), d.getMonth() + delta, 1))
  const goToday = () => {
    const d = new Date()
    setMonthStart(new Date(d.getFullYear(), d.getMonth(), 1))
  }

  const handleDragEnd = ({ active, over }) => {
    const tache = active.data.current?.tache
    if (!tache || !over) return
    const nouvelleDate = over.id
    if (nouvelleDate === tache.date_fin_prevue) return
    onReprogrammer(tache, nouvelleDate)
  }

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <IconButton variant="outline" label="Mois précédent" onClick={() => goMonth(-1)}>
              <ChevronLeft />
            </IconButton>
            <IconButton variant="outline" label="Mois suivant" onClick={() => goMonth(1)}>
              <ChevronRight />
            </IconButton>
          </div>
          <h3 className="font-display text-base font-semibold">{title}</h3>
          <Button size="sm" variant="outline" onClick={goToday}>Aujourd&apos;hui</Button>
        </div>
        <div className="grid grid-cols-7 gap-px overflow-hidden rounded-md border bg-border text-sm">
          {WEEKDAY_LABELS.map((lbl) => (
            <div key={lbl} className="bg-muted/40 p-1 text-center text-xs font-medium">{lbl}</div>
          ))}
          {cells.map((cell) => (
            <DayCell
              key={toISO(cell.date)}
              cell={cell}
              taches={byDay.get(toISO(cell.date)) ?? []}
              busyTacheId={busyTacheId}
            />
          ))}
        </div>
      </div>
    </DndContext>
  )
}
