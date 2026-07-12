import { forwardRef } from 'react'
import * as ContextMenuPrimitive from '@radix-ui/react-context-menu'
import { Check, ChevronRight, Circle } from 'lucide-react'
import { cn } from '../lib/cn'
import { pressItem } from './interaction'

/* G28 — Menu contextuel (clic droit / appui long).
   VX126 — press partagé sur les items (assombrissement au clic).
   VX129 — pack de complétude : CheckboxItem (0 occurrence avant — ContextMenu
   n'avait même pas ça), RadioItem, Sub/SubTrigger/SubContent, Shortcut —
   calqués sur le pattern déjà validé de DropdownMenu.jsx. */
export const ContextMenu = ContextMenuPrimitive.Root
export const ContextMenuTrigger = ContextMenuPrimitive.Trigger
export const ContextMenuGroup = ContextMenuPrimitive.Group
export const ContextMenuRadioGroup = ContextMenuPrimitive.RadioGroup
export const ContextMenuSub = ContextMenuPrimitive.Sub

const menuContent =
  'z-[var(--z-dropdown)] min-w-44 overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-ui-lg ' +
  'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none'

const menuItem =
  'flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none ' +
  'focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-4 ' +
  pressItem

export const ContextMenuContent = forwardRef(function ContextMenuContent({ className, ...props }, ref) {
  return (
    <ContextMenuPrimitive.Portal>
      <ContextMenuPrimitive.Content
        ref={ref}
        className={cn(menuContent, className)}
        {...props}
      />
    </ContextMenuPrimitive.Portal>
  )
})

export const ContextMenuItem = forwardRef(function ContextMenuItem({ className, destructive, ...props }, ref) {
  return (
    <ContextMenuPrimitive.Item
      ref={ref}
      className={cn(
        menuItem,
        destructive && 'text-destructive focus:bg-destructive/10 focus:text-destructive',
        className,
      )}
      {...props}
    />
  )
})

export const ContextMenuCheckboxItem = forwardRef(function ContextMenuCheckboxItem(
  { className, children, checked, ...props },
  ref,
) {
  return (
    <ContextMenuPrimitive.CheckboxItem
      ref={ref}
      checked={checked}
      className={cn(menuItem, 'relative pl-7', className)}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <ContextMenuPrimitive.ItemIndicator>
          <Check className="size-3.5" />
        </ContextMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </ContextMenuPrimitive.CheckboxItem>
  )
})

export const ContextMenuRadioItem = forwardRef(function ContextMenuRadioItem(
  { className, children, ...props },
  ref,
) {
  return (
    <ContextMenuPrimitive.RadioItem
      ref={ref}
      className={cn(menuItem, 'relative pl-7', className)}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <ContextMenuPrimitive.ItemIndicator>
          <Circle className="size-2 fill-current" />
        </ContextMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </ContextMenuPrimitive.RadioItem>
  )
})

export const ContextMenuSubTrigger = forwardRef(function ContextMenuSubTrigger(
  { className, children, ...props },
  ref,
) {
  return (
    <ContextMenuPrimitive.SubTrigger
      ref={ref}
      className={cn(menuItem, 'data-[state=open]:bg-accent data-[state=open]:text-accent-foreground', className)}
      {...props}
    >
      {children}
      <ChevronRight className="ml-auto size-4 shrink-0" />
    </ContextMenuPrimitive.SubTrigger>
  )
})

export const ContextMenuSubContent = forwardRef(function ContextMenuSubContent({ className, ...props }, ref) {
  return (
    <ContextMenuPrimitive.Portal>
      <ContextMenuPrimitive.SubContent
        ref={ref}
        className={cn(menuContent, className)}
        {...props}
      />
    </ContextMenuPrimitive.Portal>
  )
})

/* Raccourci clavier aligné à droite de l'item — présentationnel (voir
   DropdownMenu.jsx). */
export const ContextMenuShortcut = forwardRef(function ContextMenuShortcut({ className, ...props }, ref) {
  return (
    <span
      ref={ref}
      className={cn('ml-auto pl-3 text-xs tracking-widest text-muted-foreground', className)}
      {...props}
    />
  )
})

export const ContextMenuLabel = forwardRef(function ContextMenuLabel({ className, ...props }, ref) {
  return (
    <ContextMenuPrimitive.Label
      ref={ref}
      className={cn('px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground', className)}
      {...props}
    />
  )
})

export const ContextMenuSeparator = forwardRef(function ContextMenuSeparator({ className, ...props }, ref) {
  return (
    <ContextMenuPrimitive.Separator ref={ref} className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
  )
})

export default ContextMenu
