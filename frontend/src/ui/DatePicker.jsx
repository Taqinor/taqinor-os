import { forwardRef, useEffect, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { Calendar, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { cn } from '../lib/cn'
import { formatDate } from '../lib/format'
import { pressItem } from './interaction'
import {
  WEEKDAY_LABELS, MONTH_LABELS,
  startOfDay, today, isSameDay, isWithinRange, isDateDisabled,
  addDays, addMonths, buildMonthGrid, applyRangeSelection,
} from './date-utils'

/* G24 — Sélecteurs de date composés sur le Popover (G28) + maths de date pures
   (date-utils.js). Aucune lib de date. Clavier complet + ARIA grid. fr-FR. */

const fieldBase =
  'flex w-full items-center gap-2 rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'h-[var(--control-h)] px-[var(--control-px)] text-base sm:text-sm transition-colors ' +
  'focus-ring focus-visible:border-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30'

// ── Grille calendrier (cœur partagé par DatePicker et DateRangePicker) ──────
function CalendarGrid({
  month, onMonthChange,
  isSelected, isInRange, isRangeEnd,
  onPick, min, max, disabled,
  focusDate, onFocusDate,
}) {
  const cells = useMemo(
    () => buildMonthGrid(month.getFullYear(), month.getMonth()),
    [month],
  )
  const gridRef = useRef(null)
  const now = today()

  // Déplacement clavier sur la grille : flèches = ±1 jour / ±7 jours, etc.
  const onKeyDown = (e) => {
    let next = null
    switch (e.key) {
      case 'ArrowLeft': next = addDays(focusDate, -1); break
      case 'ArrowRight': next = addDays(focusDate, 1); break
      case 'ArrowUp': next = addDays(focusDate, -7); break
      case 'ArrowDown': next = addDays(focusDate, 7); break
      case 'PageUp': next = addMonths(focusDate, e.shiftKey ? -12 : -1); break
      case 'PageDown': next = addMonths(focusDate, e.shiftKey ? 12 : 1); break
      case 'Home': next = addDays(focusDate, -((focusDate.getDay() + 6) % 7)); break
      case 'End': next = addDays(focusDate, 6 - ((focusDate.getDay() + 6) % 7)); break
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (!isDateDisabled(focusDate, { min, max, disabled })) onPick(focusDate)
        return
      default: return
    }
    e.preventDefault()
    onFocusDate(next)
    if (next.getMonth() !== month.getMonth() || next.getFullYear() !== month.getFullYear()) {
      onMonthChange(new Date(next.getFullYear(), next.getMonth(), 1))
    }
  }

  // Quand la date focus change, on déplace réellement le focus DOM sur la cellule.
  useEffect(() => {
    const el = gridRef.current?.querySelector('[data-focused="true"]')
    if (el && document.activeElement !== el && gridRef.current?.contains(document.activeElement)) {
      el.focus()
    }
  }, [focusDate])

  return (
    <div className="w-[15.5rem]">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          aria-label="Mois précédent"
          className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-ring"
          onClick={() => onMonthChange(addMonths(month, -1))}
        >
          <ChevronLeft className="size-4" />
        </button>
        <div aria-live="polite" className="text-sm font-semibold tabular-nums">
          {MONTH_LABELS[month.getMonth()]} {month.getFullYear()}
        </div>
        <button
          type="button"
          aria-label="Mois suivant"
          className="grid size-7 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground focus-ring"
          onClick={() => onMonthChange(addMonths(month, 1))}
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      <div role="grid" className="select-none" ref={gridRef} onKeyDown={onKeyDown}>
        <div role="row" className="mb-1 grid grid-cols-7">
          {WEEKDAY_LABELS.map((w) => (
            <div key={w} role="columnheader" className="grid h-[var(--control-h-sm)] place-items-center text-xs font-medium text-muted-foreground">
              {w}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-y-0.5">
          {cells.map(({ date, inMonth }) => {
            const dis = isDateDisabled(date, { min, max, disabled })
            const sel = isSelected(date)
            const inRange = isInRange?.(date) ?? false
            const rangeEnd = isRangeEnd?.(date) ?? false
            const isToday = isSameDay(date, now)
            const isFocused = isSameDay(date, focusDate)
            return (
              <button
                key={date.getTime()}
                type="button"
                role="gridcell"
                aria-selected={sel || rangeEnd}
                aria-disabled={dis || undefined}
                aria-current={isToday ? 'date' : undefined}
                data-focused={isFocused || undefined}
                tabIndex={isFocused ? 0 : -1}
                disabled={dis}
                onClick={() => !dis && onPick(date)}
                className={cn(
                  // G128 — hauteur des cellules alignée sur le token de densité
                  // (compact ↔ confortable) plutôt qu'une hauteur fixe.
                  'grid h-[var(--control-h-sm)] place-items-center rounded-md text-sm tabular-nums transition-colors',
                  'focus-ring',
                  !dis && pressItem,
                  !inMonth && 'text-muted-foreground/50',
                  inMonth && !sel && !rangeEnd && 'text-foreground hover:bg-accent',
                  inRange && !sel && !rangeEnd && 'rounded-none bg-accent',
                  (sel || rangeEnd) && 'bg-primary font-semibold text-primary-foreground hover:bg-primary/90',
                  isToday && !sel && !rangeEnd && 'font-semibold text-primary',
                  dis && 'cursor-not-allowed text-muted-foreground/40 line-through hover:bg-transparent',
                )}
              >
                {date.getDate()}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── DatePicker (valeur simple) ──────────────────────────────────────────────
export const DatePicker = forwardRef(function DatePicker(
  { value, onChange, min, max, disabled, invalid, placeholder = 'jj/mm/aaaa', className, clearable = true, id, ...props },
  ref,
) {
  const [open, setOpen] = useState(false)
  const valDate = value ? startOfDay(new Date(value)) : null
  const [month, setMonth] = useState(valDate || today())
  const [focusDate, setFocusDate] = useState(valDate || today())

  // Recale le mois/jour focalisé à l'ouverture (hors effet → pas de cascade).
  const handleOpenChange = (next) => {
    setOpen(next)
    if (next) {
      const base = (value ? startOfDay(new Date(value)) : null) || today()
      setMonth(new Date(base.getFullYear(), base.getMonth(), 1))
      setFocusDate(base)
    }
  }

  const pick = (date) => {
    onChange?.(startOfDay(date))
    setOpen(false)
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={handleOpenChange}>
      <div className={cn('relative', className)}>
        <PopoverPrimitive.Trigger asChild>
          <button
            type="button"
            ref={ref}
            id={id}
            disabled={disabled}
            aria-invalid={invalid || undefined}
            className={cn(fieldBase, !valDate && 'text-muted-foreground')}
            {...props}
          >
            <Calendar className="size-4 shrink-0 text-muted-foreground" />
            <span className="flex-1 text-left">{valDate ? formatDate(valDate) : placeholder}</span>
          </button>
        </PopoverPrimitive.Trigger>
        {clearable && valDate && !disabled && (
          <button
            type="button"
            aria-label="Effacer la date"
            onClick={() => onChange?.(null)}
            className="absolute inset-y-0 right-2 my-auto grid size-5 place-items-center rounded text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={6}
          className="z-[var(--z-popover)] rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          <CalendarGrid
            month={month}
            onMonthChange={setMonth}
            isSelected={(d) => isSameDay(d, valDate)}
            onPick={pick}
            min={min}
            max={max}
            disabled={disabled === true ? undefined : disabled}
            focusDate={focusDate}
            onFocusDate={setFocusDate}
          />
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
})

// ── DateRangePicker (début → fin) ───────────────────────────────────────────
export const DateRangePicker = forwardRef(function DateRangePicker(
  { value, onChange, min, max, disabled, invalid, placeholder = 'Période…', className, id, ...props },
  ref,
) {
  const [open, setOpen] = useState(false)
  const start = value?.start ? startOfDay(new Date(value.start)) : null
  const end = value?.end ? startOfDay(new Date(value.end)) : null
  const [month, setMonth] = useState(start || today())
  const [focusDate, setFocusDate] = useState(start || today())

  // Recale le mois/jour focalisé à l'ouverture (hors effet → pas de cascade).
  const handleOpenChange = (next) => {
    setOpen(next)
    if (next) {
      const base = (value?.start ? startOfDay(new Date(value.start)) : null) || today()
      setMonth(new Date(base.getFullYear(), base.getMonth(), 1))
      setFocusDate(base)
    }
  }

  const pick = (date) => {
    const next = applyRangeSelection({ start, end }, date)
    onChange?.(next)
    if (next.start && next.end) setOpen(false)
  }

  const label = start
    ? end
      ? `${formatDate(start)} → ${formatDate(end)}`
      : `${formatDate(start)} → …`
    : placeholder

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={handleOpenChange}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          ref={ref}
          id={id}
          disabled={disabled}
          aria-invalid={invalid || undefined}
          className={cn(fieldBase, !start && 'text-muted-foreground', className)}
          {...props}
        >
          <Calendar className="size-4 shrink-0 text-muted-foreground" />
          <span className="flex-1 text-left tabular-nums">{label}</span>
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={6}
          className="z-[var(--z-popover)] rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          <CalendarGrid
            month={month}
            onMonthChange={setMonth}
            isSelected={(d) => isSameDay(d, start)}
            isRangeEnd={(d) => isSameDay(d, end)}
            isInRange={(d) => start && end && isWithinRange(d, start, end)}
            onPick={pick}
            min={min}
            max={max}
            disabled={disabled === true ? undefined : disabled}
            focusDate={focusDate}
            onFocusDate={setFocusDate}
          />
          {start && (
            <div className="mt-2 flex justify-end border-t border-border pt-2">
              <button
                type="button"
                onClick={() => { onChange?.({ start: null, end: null }); }}
                className="rounded text-xs text-muted-foreground hover:text-foreground"
              >
                Réinitialiser
              </button>
            </div>
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
})

export default DatePicker
