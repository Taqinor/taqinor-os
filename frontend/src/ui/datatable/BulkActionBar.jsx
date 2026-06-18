import { X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../Button'
import { IconButton } from '../IconButton'

/* ============================================================================
   H32 — Barre d'actions groupées flottante. CONFIGURABLE : les actions sont
   passées en props (`actions`), jamais codées en dur sur les leads. Apparaît
   quand au moins une ligne est sélectionnée ; ancrée en bas sur mobile,
   flottante centrée sur desktop.
   `actions` = [{ id, label, icon?, variant?, onClick(selection), destructive? }]
   ========================================================================== */
export function BulkActionBar({ count, actions = [], onClear, className }) {
  if (!count) return null
  return (
    <div
      role="region"
      aria-label={`${count} ligne(s) sélectionnée(s)`}
      className={cn(
        'fixed inset-x-0 bottom-0 z-[var(--z-sticky)] flex justify-center px-3 pb-3',
        'sm:bottom-6 pointer-events-none',
        className,
      )}
    >
      <div
        className={cn(
          'pointer-events-auto flex w-full max-w-2xl items-center gap-2 rounded-xl border border-border',
          'bg-popover/95 p-2 pl-3 text-popover-foreground shadow-ui-lg backdrop-blur',
          'animate-pop-in',
        )}
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <span className="inline-flex min-w-6 items-center justify-center rounded-md bg-primary px-1.5 py-0.5 text-xs font-semibold text-primary-foreground">
            {count}
          </span>
          <span className="hidden sm:inline text-muted-foreground">sélectionné{count > 1 ? 's' : ''}</span>
        </span>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          {actions.map((a) => {
            const Icon = a.icon
            return (
              <Button
                key={a.id}
                size="sm"
                variant={a.variant ?? (a.destructive ? 'destructive' : 'secondary')}
                onClick={() => a.onClick?.()}
              >
                {Icon && <Icon />}
                <span className={cn(a.iconOnlyMobile && 'hidden sm:inline')}>{a.label}</span>
              </Button>
            )
          })}
          <IconButton label="Annuler la sélection" variant="ghost" size="icon" onClick={onClear}>
            <X />
          </IconButton>
        </div>
      </div>
    </div>
  )
}

export default BulkActionBar
