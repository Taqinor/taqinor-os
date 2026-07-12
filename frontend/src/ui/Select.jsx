import { forwardRef } from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'
import { pressItem } from './interaction'

/* G23 — Select natif accessible (clavier + type-ahead gérés par Radix).
   Pour une liste fixe et courte. Combobox/MultiSelect couvrent la recherche. */
export const Select = SelectPrimitive.Root
export const SelectGroup = SelectPrimitive.Group
export const SelectValue = SelectPrimitive.Value

const triggerBase =
  'flex w-full items-center justify-between gap-2 rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'h-[var(--control-h)] px-[var(--control-px)] text-base sm:text-sm transition-colors ' +
  'placeholder:text-muted-foreground data-[placeholder]:text-muted-foreground ' +
  'focus:outline-none focus-ring focus-visible:border-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30 ' +
  '[&>span]:line-clamp-1 [&>span]:text-left'

export const SelectTrigger = forwardRef(function SelectTrigger(
  { className, children, invalid, ...props },
  ref,
) {
  return (
    <SelectPrimitive.Trigger
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(triggerBase, className)}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="size-4 shrink-0 opacity-60" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  )
})

/* G126 — Squelette de chargement (3 lignes) calqué sur la densité des items. */
function SelectLoadingState({ loadingText }) {
  return (
    <div role="status" aria-live="polite" className="p-1">
      <span className="sr-only">{loadingText}</span>
      <div className="flex items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground">
        <Spinner className="size-4" aria-hidden="true" />
        <span aria-hidden="true">{loadingText}</span>
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center px-2 py-1.5" aria-hidden="true">
          <div
            className="h-3.5 animate-pulse rounded bg-muted"
            style={{ width: ['70%', '55%', '62%'][i] }}
          />
        </div>
      ))}
    </div>
  )
}

export const SelectContent = forwardRef(function SelectContent(
  { className, children, position = 'popper', loading = false, loadingText = 'Chargement…', ...props },
  ref,
) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        ref={ref}
        position={position}
        className={cn(
          // z-popover (au-dessus de --z-modal) et NON z-dropdown : sinon, ouvert
          // DANS une Dialog/Sheet/AlertDialog (toutes à --z-modal), le menu se
          // rend DERRIÈRE le modal — invisible et non cliquable (ex. changer le
          // rôle dans « Utilisateurs → éditer »). Les autres popovers (Assignee/
          // Produit/HoverCard) sont déjà à --z-popover pour la même raison.
          'relative z-[var(--z-popover)] max-h-72 min-w-[8rem] overflow-hidden rounded-lg border border-border bg-popover text-popover-foreground shadow-ui-lg',
          'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out',
          position === 'popper' && 'w-[var(--radix-select-trigger-width)]',
          className,
        )}
        {...props}
      >
        <SelectPrimitive.ScrollUpButton className="flex h-6 items-center justify-center text-muted-foreground">
          <ChevronUp className="size-4" />
        </SelectPrimitive.ScrollUpButton>
        <SelectPrimitive.Viewport className="p-1">
          {/* G126 — état de chargement (spinner + squelette) pendant une
              recherche/alimentation asynchrone des options. */}
          {loading ? <SelectLoadingState loadingText={loadingText} /> : children}
        </SelectPrimitive.Viewport>
        <SelectPrimitive.ScrollDownButton className="flex h-6 items-center justify-center text-muted-foreground">
          <ChevronDown className="size-4" />
        </SelectPrimitive.ScrollDownButton>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  )
})

export const SelectLabel = forwardRef(function SelectLabel({ className, ...props }, ref) {
  return (
    <SelectPrimitive.Label
      ref={ref}
      className={cn('px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground', className)}
      {...props}
    />
  )
})

export const SelectItem = forwardRef(function SelectItem({ className, children, ...props }, ref) {
  return (
    <SelectPrimitive.Item
      ref={ref}
      className={cn(
        'relative flex w-full cursor-pointer select-none items-center rounded-md py-1.5 pl-7 pr-2 text-sm outline-none',
        'focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        pressItem,
        className,
      )}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <Check className="size-3.5" />
        </SelectPrimitive.ItemIndicator>
      </span>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  )
})

export const SelectSeparator = forwardRef(function SelectSeparator({ className, ...props }, ref) {
  return <SelectPrimitive.Separator ref={ref} className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
})

export default Select
