// ZMFG3 — vue calendrier des tickets SAV (glisser pour replanifier, création
// rapide sur un créneau), sortie de TicketsPage.jsx (fichier ≥ 2 000 lignes, C20).
import { useCallback, useMemo, useState } from 'react'
import { AlertTriangle, Plus, ChevronRight, ChevronLeft } from 'lucide-react'
import {
  DndContext, PointerSensor, TouchSensor, useDraggable, useDroppable,
  useSensor, useSensors,
} from '@dnd-kit/core'
import savApi from '../../api/savApi'
import { toastErreurNonAffichee, toastWithUndo } from '../../lib/toast'
import { groupTicketsByDate } from './ticketCalendarUtils'
import { TICKET_STATUS_COLORS, TICKET_TYPES } from '../../features/sav/ticketStatuses'
import {
  Button, Textarea, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, FormField,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import { frError, formatDateFR } from './ticketsLogique'
import ComboboxClient from '../../components/ComboboxClient'

const CAL_WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const CAL_MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

const calYmd = (d) => {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

// Grille du mois : commence le lundi de la semaine du 1er, finit le dimanche
// de la semaine du dernier jour (toujours des lignes complètes de 7 colonnes).
function calMonthGrid(year, month) {
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7 // 0 = lundi
  const start = new Date(year, month, 1 - startOffset)
  const cells = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    cells.push(d)
  }
  if (cells[35].getMonth() !== month && cells[28].getMonth() !== month) {
    return cells.slice(0, 35)
  }
  return cells
}

function CalendarTicketCard({ ticket }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-card p-1.5 text-left text-xs shadow-sm hover:border-primary/40">
      <span className="flex items-center gap-1 font-medium">
        <span className="size-1.5 shrink-0 rounded-full"
              style={{ background: TICKET_STATUS_COLORS[ticket.statut] }} />
        {ticket.reference}
      </span>
      <span className="truncate text-muted-foreground">{ticket.client_nom ?? '—'}</span>
    </div>
  )
}

function DraggableCalendarCard({ ticket, onSelect }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `ticket-cal-${ticket.id}`, data: { ticket },
  })
  return (
    <div ref={setNodeRef} {...listeners} {...attributes}
         onClick={() => onSelect(ticket)}
         className={isDragging ? 'cursor-grabbing opacity-50' : 'cursor-grab'}>
      <CalendarTicketCard ticket={ticket} />
    </div>
  )
}

function CalendarDayCell({ date: cellDate, inMonth, isToday, tickets, onSelect, onQuickCreate }) {
  const key = calYmd(cellDate)
  const { setNodeRef, isOver } = useDroppable({ id: `day-${key}`, data: { date: key } })
  return (
    <div ref={setNodeRef}
         className={`group flex min-h-[6rem] flex-col gap-1 p-1 ${inMonth ? 'bg-card' : 'bg-muted/30'} ${isOver ? 'ring-2 ring-inset ring-primary' : ''}`}>
      <div className="flex items-center justify-between px-0.5">
        <span className={`text-xs ${inMonth ? 'text-foreground' : 'text-muted-foreground'} ${isToday ? 'font-bold' : ''}`}>
          {isToday
            ? <span className="rounded-full bg-primary px-1.5 py-0.5 text-primary-foreground">{cellDate.getDate()}</span>
            : cellDate.getDate()}
        </span>
        {/* Création rapide d'un ticket depuis ce créneau. */}
        <button type="button" title="Créer un ticket ce jour"
                onClick={() => onQuickCreate(key)}
                className="hidden size-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground group-hover:flex">
          <Plus className="size-3" aria-hidden="true" />
        </button>
      </div>
      <div className="flex flex-col gap-1">
        {tickets.map((t) => (
          <DraggableCalendarCard key={t.id} ticket={t} onSelect={onSelect} />
        ))}
      </div>
    </div>
  )
}

// Formulaire minimal de création rapide (référence auto côté serveur) :
// client (OBLIGATOIRE — WIR178, `Ticket.client` est un FK non nullable côté
// serveur, un payload sans client était un 400 garanti) + type + description,
// puis createTicket suivi de replanifierTicket sur la date cliquée dans le
// calendrier (affinable ensuite par glisser-déposer) — garde le composant
// simple : ouvrir la fiche standard n'est pas nécessaire, un POST minimal suffit.
// VX240(d) — dernier type de ticket utilisé (localStorage, modifiable),
// même patron que VX93 (lireLastTva/lireDernierMode) : le type ne reset plus
// silencieusement à « correctif » à chaque ouverture.
const TICKET_QC_TYPE_KEY = 'taqinor.tickets.quickCreate.lastType'
const lireLastTicketType = () => {
  try { return window.localStorage.getItem(TICKET_QC_TYPE_KEY) || 'correctif' }
  catch { return 'correctif' }
}
const ecrireLastTicketType = (v) => {
  try { if (v) window.localStorage.setItem(TICKET_QC_TYPE_KEY, v) }
  catch { console.warn('TicketsPage (ecrireLastTicketType) : localStorage indisponible (navigation privée, quota) : no-op') }
}

function CalendarQuickCreateDialog({ date: openDate, onClose, onCreated }) {
  const [clientId, setClientId] = useState(null)
  const [description, setDescription] = useState('')
  const [type, setType] = useState(lireLastTicketType)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async () => {
    setErr(null)
    if (!clientId) { setErr('Le client est requis.'); return }
    setBusy(true)
    try {
      const r = await savApi.createTicket({
        client: parseInt(clientId, 10), type, description: description || undefined,
      })
      // Pose la date planifiée sur le ticket fraîchement créé.
      await savApi.replanifierTicket(r.data.id, openDate)
      ecrireLastTicketType(type)  // VX240(d) — mémorise le type pour la prochaine création
      onCreated?.()
      onClose()
    } catch (e) {
      setErr(frError(e, 'Échec de la création.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AlertDialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Nouveau ticket — {formatDateFR(openDate)}</AlertDialogTitle>
          <AlertDialogDescription>
            Créer un ticket planifié à cette date.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="grid gap-3">
          <FormField label="Client" htmlFor="cqc-client">
            {/* VX240(d) — la modale s'ouvrait sans aucun autofocus. */}
            <ComboboxClient id="cqc-client" value={clientId} onChange={(v) => setClientId(v)}
                            invalid={err && !clientId ? true : undefined} />
          </FormField>
          <FormField label="Type">
            <Select value={type} onValueChange={setType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {TICKET_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Description">
            <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </FormField>
          {err && (
            <div role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" /> <span>{err}</span>
            </div>
          )}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction disabled={busy} onClick={(e) => { e.preventDefault(); submit() }}>
            Créer
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function TicketCalendarView({ tickets, onSelect, onReload }) {
  const today = useMemo(() => new Date(), [])
  const [cursor, setCursor] = useState(
    () => ({ year: today.getFullYear(), month: today.getMonth() }))
  const [quickCreateDate, setQuickCreateDate] = useState(null)
  const [dragTicket, setDragTicket] = useState(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )

  const cells = useMemo(() => calMonthGrid(cursor.year, cursor.month), [cursor])
  const byDay = useMemo(() => groupTicketsByDate(tickets), [tickets])

  const go = (delta) => setCursor((c) => {
    const d = new Date(c.year, c.month + delta, 1)
    return { year: d.getFullYear(), month: d.getMonth() }
  })
  const goToday = () => setCursor({ year: today.getFullYear(), month: today.getMonth() })

  const handleDragEnd = useCallback(async ({ active, over }) => {
    setDragTicket(null)
    const ticket = active?.data?.current?.ticket
    const targetDate = over?.data?.current?.date
    if (!ticket || !targetDate || targetDate === ticket.date_tournee) return
    // AERR31 — résultat nommé + « Annuler » (appel inverse) ; un refus ne
    // produit que le toast d'erreur global (axios), jamais un second message.
    try {
      await savApi.replanifierTicket(ticket.id, targetDate)
      const ancienne = ticket.date_tournee
      toastWithUndo({
        message: `${ticket.reference} replanifié au ${targetDate.slice(8, 10)}/${targetDate.slice(5, 7)}`,
        onUndo: () => savApi.replanifierTicket(ticket.id, ancienne).then(() => onReload?.(), () => {}),
      })
      onReload?.()
    } catch (err) { toastErreurNonAffichee(err, 'Replanification impossible.') }
  }, [onReload])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => go(-1)}><ChevronLeft /></Button>
        <Button variant="outline" size="sm" onClick={goToday}>Aujourd'hui</Button>
        <Button variant="outline" size="sm" onClick={() => go(1)}><ChevronRight /></Button>
        <strong className="min-w-[140px] text-center text-sm">
          {CAL_MONTHS[cursor.month]} {cursor.year}
        </strong>
      </div>

      <DndContext sensors={sensors}
                  onDragStart={({ active }) => setDragTicket(active?.data?.current?.ticket ?? null)}
                  onDragEnd={handleDragEnd}
                  onDragCancel={() => setDragTicket(null)}>
        <div className="grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-border bg-border">
          {CAL_WEEKDAYS.map((d) => (
            <div key={d} className="bg-muted px-2 py-1.5 text-center text-xs font-semibold text-muted-foreground">
              {d}
            </div>
          ))}
          {cells.map((d) => {
            const key = calYmd(d)
            return (
              <CalendarDayCell
                key={key}
                date={d}
                inMonth={d.getMonth() === cursor.month}
                isToday={key === calYmd(today)}
                tickets={byDay[key] || []}
                onSelect={onSelect}
                onQuickCreate={setQuickCreateDate}
              />
            )
          })}
        </div>
      </DndContext>

      {!dragTicket && Object.keys(byDay).length === 0 && (
        <p className="text-center text-sm text-muted-foreground">
          Aucun ticket planifié (date de tournée) ce mois-ci.
        </p>
      )}

      {quickCreateDate && (
        <CalendarQuickCreateDialog
          date={quickCreateDate}
          onClose={() => setQuickCreateDate(null)}
          onCreated={() => onReload?.()}
        />
      )}
    </div>
  )
}
