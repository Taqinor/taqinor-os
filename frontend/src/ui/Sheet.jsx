import { forwardRef } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../lib/cn'

/* G28 — Sheet : panneau coulissant (tiroir). Sur mobile, `side="bottom"` donne
   une bottom-sheet. Construit sur Radix Dialog (focus trap + Échap). */
export const Sheet = DialogPrimitive.Root
export const SheetTrigger = DialogPrimitive.Trigger
export const SheetClose = DialogPrimitive.Close

const SIDE = {
  right: 'inset-y-0 right-0 h-full w-[min(26rem,calc(100%-2rem))] border-l',
  left: 'inset-y-0 left-0 h-full w-[min(26rem,calc(100%-2rem))] border-r',
  bottom: 'inset-x-0 bottom-0 max-h-[85vh] w-full rounded-t-2xl border-t',
  top: 'inset-x-0 top-0 max-h-[85vh] w-full rounded-b-2xl border-b',
}

export const SheetContent = forwardRef(function SheetContent(
  { className, children, side = 'right', showClose = true, ...props },
  ref,
) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay
        className="fixed inset-0 z-[var(--z-overlay)] bg-nuit/60 backdrop-blur-sm data-[state=open]:animate-overlay-in data-[state=closed]:animate-overlay-out"
      />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'fixed z-[var(--z-modal)] flex flex-col gap-4 overflow-y-auto border-border bg-card p-5 text-card-foreground shadow-ui-lg',
          'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none',
          SIDE[side],
          className,
        )}
        {...props}
      >
        {children}
        {showClose && (
          <DialogPrimitive.Close
            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Fermer"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
})

export function SheetHeader({ className, ...props }) {
  return <div className={cn('flex flex-col gap-1 pr-6', className)} {...props} />
}
export const SheetTitle = forwardRef(function SheetTitle({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Title
      ref={ref}
      className={cn('font-display text-lg font-semibold leading-tight', className)}
      {...props}
    />
  )
})
export const SheetDescription = forwardRef(function SheetDescription({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Description ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />
  )
})

export default Sheet
