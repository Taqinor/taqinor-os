import { forwardRef } from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { Check, ChevronRight, Circle } from 'lucide-react'
import { cn } from '../lib/cn'
import { pressItem } from './interaction'

/* G28 — Menu déroulant (clavier géré par Radix).
   VX126 — press partagé sur les items (assombrissement au clic).
   VX129 — pack de complétude : RadioItem (choix exclusif), Sub/SubTrigger/
   SubContent (sous-menu), Shortcut (raccourci aligné à droite) — jusqu'ici
   0 occurrence des trois dans tout le repo. */
export const DropdownMenu = DropdownMenuPrimitive.Root
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
export const DropdownMenuGroup = DropdownMenuPrimitive.Group
export const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup
export const DropdownMenuSub = DropdownMenuPrimitive.Sub

const menuContent =
  'z-[var(--z-dropdown)] min-w-44 overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-ui-lg ' +
  'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none'

const menuItem =
  'flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none ' +
  'focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-4 ' +
  pressItem

export const DropdownMenuContent = forwardRef(function DropdownMenuContent(
  { className, sideOffset = 6, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(menuContent, className)}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  )
})

export const DropdownMenuItem = forwardRef(function DropdownMenuItem(
  { className, destructive, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.Item
      ref={ref}
      className={cn(menuItem, destructive && 'text-destructive focus:bg-destructive/10 focus:text-destructive', className)}
      {...props}
    />
  )
})

export const DropdownMenuCheckboxItem = forwardRef(function DropdownMenuCheckboxItem(
  { className, children, checked, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.CheckboxItem
      ref={ref}
      checked={checked}
      className={cn(menuItem, 'relative pl-7', className)}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <DropdownMenuPrimitive.ItemIndicator>
          <Check className="size-3.5" />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.CheckboxItem>
  )
})

export const DropdownMenuRadioItem = forwardRef(function DropdownMenuRadioItem(
  { className, children, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.RadioItem
      ref={ref}
      className={cn(menuItem, 'relative pl-7', className)}
      {...props}
    >
      <span className="absolute left-2 flex size-3.5 items-center justify-center">
        <DropdownMenuPrimitive.ItemIndicator>
          <Circle className="size-2 fill-current" />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.RadioItem>
  )
})

export const DropdownMenuSubTrigger = forwardRef(function DropdownMenuSubTrigger(
  { className, children, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.SubTrigger
      ref={ref}
      className={cn(menuItem, 'data-[state=open]:bg-accent data-[state=open]:text-accent-foreground', className)}
      {...props}
    >
      {children}
      <ChevronRight className="ml-auto size-4 shrink-0" />
    </DropdownMenuPrimitive.SubTrigger>
  )
})

export const DropdownMenuSubContent = forwardRef(function DropdownMenuSubContent(
  { className, ...props },
  ref,
) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.SubContent
        ref={ref}
        className={cn(menuContent, className)}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  )
})

/* Raccourci clavier aligné à droite de l'item (ex. « Ctrl+S »). Purement
   présentationnel — le raccourci réel reste géré par ShortcutsProvider. */
export const DropdownMenuShortcut = forwardRef(function DropdownMenuShortcut({ className, ...props }, ref) {
  return (
    <span
      ref={ref}
      className={cn('ml-auto pl-3 text-xs tracking-widest text-muted-foreground', className)}
      {...props}
    />
  )
})

export const DropdownMenuLabel = forwardRef(function DropdownMenuLabel({ className, ...props }, ref) {
  return (
    <DropdownMenuPrimitive.Label
      ref={ref}
      className={cn('px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground', className)}
      {...props}
    />
  )
})

export const DropdownMenuSeparator = forwardRef(function DropdownMenuSeparator({ className, ...props }, ref) {
  return (
    <DropdownMenuPrimitive.Separator ref={ref} className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
  )
})

export default DropdownMenu
