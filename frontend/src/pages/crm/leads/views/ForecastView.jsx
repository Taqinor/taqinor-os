// XSAL15 — Vue kanban « Prévision » : les leads OUVERTS groupés par MOIS de
// `date_cloture_prevue` (posée par XSAL7), colonnes total brut + pondéré en
// tête (MÊME calcul que KanbanView : STAGE_PROBABILITY × total devis — jamais
// une seconde table de probabilités déclarée ici), glisser une carte vers un
// autre mois PATCHe `date_cloture_prevue` via l'endpoint existant. Colonne
// « Non daté » pour les leads sans date. L'équivalent de la forecast view
// d'Odoo — réutilise @dnd-kit déjà installé (aucune nouvelle dépendance).
import { useCallback, useMemo, useState } from 'react'
import { CalendarClock } from 'lucide-react'
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
  formatMAD, isPerdu, latestDevisTotal, CONVERSION_STAGE,
} from '../../../../features/crm/stages'
import {
  buildKanbanAnnouncements,
  kanbanScreenReaderInstructions,
} from '../../../../features/kanban/kanbanA11y'
import { useOptimisticSave } from '../../../../hooks/useOptimisticSave'
import { toast } from '../../../../ui/confirm'
import { EmptyState } from '../../../../ui'
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

// LB5 (bug-fix) — `onMarkPerdu` threadé jusqu'à LeadCard : sans lui, la
// mini-popover « ✗ Perdu » de la carte appellerait un prop absent et
// échouerait silencieusement (LeadCard ne fait plus JAMAIS de crmApi direct,
// LB5). Avant ce fix, ForecastView ne passait déjà rien (ni `onChanged` ni
// mutation) — corriger ici évite d'introduire une régression sur cette vue.
//
// LB28 — équivalent clavier du glisser (parité KanbanView/StageMover) : un
// <select> mois par carte, MÊME hook `useOptimisticSave` (affordance
// « Enregistrement… »/« Enregistré », rollback auto en cas d'échec réseau).
// « Non daté » reste une cible interdite (même règle que le glisser :
// `over.id === UNDATED_KEY` est ignorée dans handleDragEnd) — l'option n'est
// offerte QUE si c'est déjà la valeur courante (carte encore sans date), donc
// jamais sélectionnable comme NOUVELLE cible.
function MonthMover({ lead, monthOptions, onCommitDate, busy }) {
  const currentKey = monthKey(lead.date_cloture_prevue) ?? UNDATED_KEY
  const { value, statusLabel, isSaving, rowProps, save } = useOptimisticSave(
    currentKey,
    {
      onError: () => toast.error('Replanification non enregistrée — réessayez.'),
    },
  )
  if (!onCommitDate) return null
  const onChange = (e) => {
    const next = e.target.value
    if (next === value) return
    save(next, (v) => onCommitDate(lead, v))
  }
  const options = currentKey === UNDATED_KEY
    ? [{ value: UNDATED_KEY, label: 'Non daté' }, ...monthOptions]
    : monthOptions
  // stopPropagation : interagir avec le select ne doit jamais démarrer un drag.
  return (
    <div
      className="fv-month-mover"
      {...rowProps}
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
      onTouchStart={(e) => e.stopPropagation()}
    >
      <label className="sr-only" htmlFor={`fv-month-${lead.id}`}>
        Replanifier {lead.nom || 'ce lead'}
      </label>
      <select
        id={`fv-month-${lead.id}`}
        className="form-control fv-month-select"
        value={value}
        disabled={isSaving || busy}
        onChange={onChange}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {statusLabel && (
        <span className="fv-month-status text-xs text-muted-foreground">
          {statusLabel}
        </span>
      )}
    </div>
  )
}

// LB28 — listeners de drag isolés sur une poignée (la carte), plus sur TOUTE
// la ligne : le sélecteur de mois (MonthMover) vit HORS du conteneur
// `{...listeners}`, même isolation que StageMover/KanbanView — sinon un clic
// clavier/souris sur le select démarrerait un drag au lieu d'ouvrir la liste.
function DraggableCard({
  lead, busy, onOpen, onAutoQuote, users, onReassign, onPlanifierRelance, onMarkPerdu,
  monthOptions, onCommitDate,
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: lead.id,
    data: { lead },
    disabled: busy,
  })
  return (
    <div
      ref={setNodeRef}
      className={isDragging ? 'kb-drag-wrap kb-drag-source' : 'kb-drag-wrap'}
    >
      <div {...listeners} {...attributes}>
        <LeadCard lead={lead} busy={busy} onOpen={onOpen} onAutoQuote={onAutoQuote}
                  users={users} onReassign={onReassign}
                  onPlanifierRelance={onPlanifierRelance} onMarkPerdu={onMarkPerdu} />
      </div>
      <MonthMover lead={lead} monthOptions={monthOptions} onCommitDate={onCommitDate} busy={busy} />
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
          // LB28 — hint de drop par colonne (blueprint D2) : « Non daté »
          // n'est JAMAIS une cible valide (handleDragEnd l'ignore), l'inviter
          // à y déposer une carte serait mensonger — seule une vraie colonne
          // de mois affiche l'invitation.
          col.key === UNDATED_KEY ? (
            <div className="kb-col-empty">Aucun lead</div>
          ) : (
            <div className="fv-col-drop-hint">Déposer un lead ici</div>
          )
        ) : (
          children
        )}
      </div>
    </section>
  )
}

export default function ForecastView({
  leads, onOpenLead, onAutoQuote, busyLeadId, users, onReassign,
  onPlanifierRelance, onInlineSave, onMarkPerdu,
}) {
  // VX192 (parité KanbanView) — sensor clavier natif (@dnd-kit/core), 0
  // dépendance : sans lui, le seul chemin de replanification était la souris.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )
  const columns = useMemo(() => groupByMonth(leads), [leads])
  // LB28 — options du <select> mois (MonthMover), calculées UNE fois pour
  // toutes les cartes (jamais une seconde table de mois par carte) ; exclut
  // « Non daté » (jamais une cible valide, même règle que le glisser).
  const monthOptions = useMemo(
    () => columns
      .filter((c) => c.key !== UNDATED_KEY)
      .map((c) => ({ value: c.key, label: c.label })),
    [columns],
  )
  const [activeLead, setActiveLead] = useState(null)
  // LB28 — busy-lock réel : AUCUN `busyLeadId` parent n'est jamais posé pour
  // un glisser Prévision (seul `changeStage`/KanbanView le pilote) — verrou
  // LOCAL équivalent, partagé par le glisser ET le <select> clavier
  // (MonthMover), pour qu'un second geste sur la MÊME carte pendant un
  // enregistrement en cours soit refusé des deux côtés à la fois.
  const [savingId, setSavingId] = useState(null)

  // VX192 — annonces FR : id de lead → nom, id de colonne → libellé de mois
  // (ou « Non daté »). Même helper partagé que KanbanView (kanbanA11y) —
  // jamais une seconde implémentation d'annonces.
  const announcements = useMemo(() => {
    const byId = new Map((leads ?? []).map((l) => [l.id, l]))
    const labelFor = (id) => {
      if (id === UNDATED_KEY) return 'Non daté'
      if (typeof id === 'string' && /^\d{4}-\d{2}$/.test(id)) return monthLabel(id)
      const l = byId.get(id)
      return l?.nom || `#${id}`
    }
    return buildKanbanAnnouncements(labelFor)
  }, [leads])

  // LB28 — point d'entrée UNIQUE du PATCH `date_cloture_prevue`, utilisé par
  // le glisser (handleDragEnd) ET le <select> clavier (MonthMover.onCommitDate)
  // : pose/lève le verrou LOCAL `savingId` autour de l'appel réseau existant
  // (onInlineSave, aucun nouvel endpoint). Ne avale JAMAIS l'erreur ici — le
  // rejet remonte pour que useOptimisticSave (chemin clavier) fasse son
  // rollback ; handleDragEnd (chemin souris) l'avale lui-même (fire-and-forget
  // déjà silencieux avant ce fix, un échec laisse simplement la carte dans sa
  // colonne d'origine puisque les colonnes dérivent de `leads`, jamais d'un
  // état optimiste local).
  const commitDate = useCallback((lead, targetKey) => {
    setSavingId(lead.id)
    return Promise.resolve(onInlineSave?.(lead, 'date_cloture_prevue', `${targetKey}-01`))
      .finally(() => setSavingId(null))
  }, [onInlineSave])

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
    commitDate(lead, over.id).catch(() => { /* fire-and-forget, cf. commitDate */ })
  }

  const handleDragCancel = () => setActiveLead(null)

  // LB28 — EmptyState global sur les leads OUVERTS (et non le tableau brut
  // `leads` reçu, qui peut contenir des perdus/signés) : couvre à la fois
  // « 0 lead du tout » et « tous filtrés/fermés » (recon2-03 #9 gap connu —
  // ForecastView ne recevait jusqu'ici AUCUN empty state, même vide elle
  // affichait 7 colonnes texte).
  const openCount = columns.reduce((s, col) => s + col.leads.length, 0)
  if (openCount === 0) {
    return (
      <EmptyState
        icon={CalendarClock}
        title="Aucun lead"
        description="Aucun lead ne correspond à ces filtres."
      />
    )
  }

  return (
    <DndContext
      sensors={sensors}
      accessibility={{
        announcements,
        screenReaderInstructions: kanbanScreenReaderInstructions,
      }}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      {/* LB41 — même contrat que le kanban : le board est le scrolleur unique
          des deux axes, focalisable pour le défilement clavier. */}
      <div className="kb-board fv-board" tabIndex={0} aria-label="Board de prévision">
        {columns.map((col) => (
          <MonthColumn key={col.key} col={col}>
            {col.leads.map((lead) => (
              <DraggableCard
                key={lead.id}
                lead={lead}
                busy={lead.id === busyLeadId || lead.id === savingId}
                onOpen={onOpenLead}
                onAutoQuote={onAutoQuote}
                users={users}
                onReassign={onReassign}
                onPlanifierRelance={onPlanifierRelance}
                onMarkPerdu={onMarkPerdu}
                monthOptions={monthOptions}
                onCommitDate={commitDate}
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
