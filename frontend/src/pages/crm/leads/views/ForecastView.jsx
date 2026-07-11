// XSAL15 — Vue kanban « Prévision » : les leads OUVERTS groupés par MOIS de
// `date_cloture_prevue` (posée par XSAL7), colonnes total brut + pondéré en
// tête (MÊME calcul que KanbanView : STAGE_PROBABILITY × total devis — jamais
// une seconde table de probabilités déclarée ici), glisser une carte vers un
// autre mois PATCHe `date_cloture_prevue` via l'endpoint existant. Colonne
// « Non daté » pour les leads sans date. L'équivalent de la forecast view
// d'Odoo — réutilise @dnd-kit déjà installé (aucune nouvelle dépendance).
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
  formatMAD, isPerdu, latestDevisTotal, CONVERSION_STAGE,
} from '../../../../features/crm/stages'
import { STAGE_PROBABILITY } from './KanbanView'
import LeadCard from './LeadCard'

const MONTH_LABELS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
const UNDATED_KEY = 'undated'

// Clé de mois locale 'YYYY-MM' à partir d'une date 'YYYY-MM-DD' — jamais via
// `new Date('YYYY-MM-DD')` (interprété en UTC), lecture directe de la chaîne.
function monthKey(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return null
  const m = dateStr.match(/^(\d{4})-(\d{2})/)
  return m ? `${m[1]}-${m[2]}` : null
}

function monthLabel(key) {
  const [y, m] = key.split('-')
  return `${MONTH_LABELS[parseInt(m, 10) - 1]} ${y}`
}

// Un lead est « ouvert » pour la prévision : ni perdu, ni déjà converti
// (SIGNED = couche funnel, règle #2 — jamais recodé en dur ici).
const isOpenLead = (lead) => !isPerdu(lead) && lead?.stage !== CONVERSION_STAGE

// Les N prochains mois (clé triable) à partir d'aujourd'hui, pour que les
// colonnes proches existent même sans lead dedans (repère visuel constant).
function upcomingMonthKeys(n = 6) {
  const now = new Date()
  const out = []
  for (let i = 0; i < n; i += 1) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return out
}

// Regroupe les leads ouverts par mois de date_cloture_prevue (+ colonne
// « Non daté ») ; total brut (dernier devis) + pondéré (STAGE_PROBABILITY ×
// brut, même calcul que KanbanView) en tête de chaque colonne.
function groupByMonth(leads) {
  const open = (leads ?? []).filter(isOpenLead)
  const byMonth = new Map()
  const ensure = (key) => {
    if (!byMonth.has(key)) byMonth.set(key, [])
    return byMonth.get(key)
  }
  for (const key of upcomingMonthKeys()) ensure(key)
  const undated = []
  for (const lead of open) {
    const key = monthKey(lead.date_cloture_prevue)
    if (key) ensure(key).push(lead)
    else undated.push(lead)
  }
  const monthKeys = [...byMonth.keys()].sort()
  const columns = monthKeys.map((key) => {
    const inMonth = byMonth.get(key)
    const totalBrut = inMonth.reduce((s, l) => s + latestDevisTotal(l), 0)
    const totalPondere = inMonth.reduce(
      (s, l) => s + latestDevisTotal(l) * (STAGE_PROBABILITY[l.stage] ?? 0), 0)
    return { key, label: monthLabel(key), leads: inMonth, totalBrut, totalPondere }
  })
  const undatedTotalBrut = undated.reduce((s, l) => s + latestDevisTotal(l), 0)
  const undatedTotalPondere = undated.reduce(
    (s, l) => s + latestDevisTotal(l) * (STAGE_PROBABILITY[l.stage] ?? 0), 0)
  columns.push({
    key: UNDATED_KEY, label: 'Non daté', leads: undated,
    totalBrut: undatedTotalBrut, totalPondere: undatedTotalPondere,
  })
  return columns
}

function DraggableCard({ lead, busy, onOpen, onAutoQuote, users, onReassign, onPlanifierRelance }) {
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
                users={users} onReassign={onReassign}
                onPlanifierRelance={onPlanifierRelance} />
    </div>
  )
}

function MonthColumn({ col, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section
      ref={setNodeRef}
      className={isOver ? 'kb-col fv-col kb-over' : 'kb-col fv-col'}
      // --kb-accent : même variable que StageColumn (KanbanView), posée ici à
      // un neutre de marque (les mois n'ont pas de couleur d'étape) — sans
      // elle, le halo/hover .kb-over (qui la référence sans repli) ne
      // rendrait rien pendant un glisser.
      style={{ '--kb-accent': 'var(--primary, #0b1f3a)' }}
    >
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.leads.length}</span>
        </div>
        {col.totalBrut > 0 && (
          <span className="kb-col-money">{formatMAD(col.totalBrut)}</span>
        )}
        {col.totalBrut > 0 && (
          <span
            className="kb-col-forecast block text-[11px] text-muted-foreground"
            title="Prévisionnel pondéré (probabilité par étape)"
          >
            Prév. {formatMAD(col.totalPondere)}
          </span>
        )}
      </header>
      <div className="kb-col-body">
        {col.leads.length === 0 ? (
          <div className="kb-col-empty">Aucun lead</div>
        ) : (
          children
        )}
      </div>
    </section>
  )
}

export default function ForecastView({
  leads, onOpenLead, onAutoQuote, busyLeadId, users, onReassign,
  onPlanifierRelance, onInlineSave,
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )
  const columns = useMemo(() => groupByMonth(leads), [leads])
  const [activeLead, setActiveLead] = useState(null)

  const handleDragStart = ({ active }) => {
    setActiveLead(active.data.current?.lead ?? null)
  }

  const handleDragEnd = ({ active, over }) => {
    setActiveLead(null)
    const lead = active.data.current?.lead
    if (!lead || !over) return
    const currentKey = monthKey(lead.date_cloture_prevue) ?? UNDATED_KEY
    if (over.id === currentKey) return
    // « Non daté » n'est jamais une cible valide (poser une carte là
    // reviendrait à effacer la date — geste non supporté par le glisser).
    if (over.id === UNDATED_KEY) return
    // Réutilise le PATCH existant (updateLead) — pas de nouvel endpoint.
    onInlineSave?.(lead, 'date_cloture_prevue', `${over.id}-01`)
  }

  const handleDragCancel = () => setActiveLead(null)

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="kb-board fv-board">
        {columns.map((col) => (
          <MonthColumn key={col.key} col={col}>
            {col.leads.map((lead) => (
              <DraggableCard
                key={lead.id}
                lead={lead}
                busy={lead.id === busyLeadId}
                onOpen={onOpenLead}
                onAutoQuote={onAutoQuote}
                users={users}
                onReassign={onReassign}
                onPlanifierRelance={onPlanifierRelance}
              />
            ))}
          </MonthColumn>
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
