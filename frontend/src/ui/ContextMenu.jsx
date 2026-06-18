import { forwardRef } from 'react'
import * as ContextMenuPrimitive from '@radix-ui/react-context-menu'
import { cn } from '../lib/cn'

/* G28 — Menu contextuel (clic droit / appui long). */
export const ContextMenu = ContextMenuPrimitive.Root
export const ContextMenuTrigger = ContextMenuPrimitive.Trigger
export const ContextMenuGroup = ContextMenuPrimitive.Group

export const ContextMenuContent = forwardRef(function ContextMenuContent({ className, ...props }, ref) {
  return (
    <ContextMenuPrimitive.Portal>
      <ContextMenuPrimitive.Content
        ref={ref}
        className={cn(
          'z-[var(--z-dropdown)] min-w-44 overflow-hidden rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-ui-lg',
          'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none',
          className,
        )}
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
        'flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none',
        'focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&_svg]:size-4',
        destructive && 'text-destructive focus:bg-destructive/10 focus:text-destructive',
        className,
      )}
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
