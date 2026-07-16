import { forwardRef } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '../lib/cn'

/* G28 — Dialog modal (focus trap + restauration gérés par Radix). */
export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

export const DialogOverlay = forwardRef(function DialogOverlay({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Overlay
      ref={ref}
      className={cn(
        'fixed inset-0 z-[var(--z-overlay)] bg-nuit/60 backdrop-blur-sm',
        'data-[state=open]:animate-overlay-in data-[state=closed]:animate-overlay-out',
        className,
      )}
      {...props}
    />
  )
})

export const DialogContent = forwardRef(function DialogContent(
  { className, children, showClose = true, variant = 'default', ...props },
  ref,
) {
  return (
    <DialogPrimitive.Portal>
      <DialogOverlay />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          variant === 'command'
            ? // VX134(a) — variante « command » (palette ⌘K) : ANCRÉE EN HAUT,
              // jamais centrée verticalement — slide-down `--motion-fast`
              // dédié (command-in/out, tokens.css), pas le pop-in centré-zoomé
              // pensé pour un dialogue de confirmation.
              'fixed left-1/2 top-[12vh] z-[var(--z-modal)] grid max-h-[calc(88vh-2rem)] w-[calc(100%-2rem)] max-w-lg gap-4 overflow-y-auto overscroll-contain data-[state=open]:animate-command-in data-[state=closed]:animate-command-out'
            : // max-h + overflow : sans plafond de hauteur ni défilement interne, un
              // formulaire long (ex. « éditer un utilisateur ») centré par
              // -translate-y-1/2 débordait HORS de l'écran sur iPhone (haut et bas
              // rognés, rôle + bouton Enregistrer inaccessibles). 100dvh suit la
              // hauteur visible réelle d'iOS (barre d'adresse dynamique).
              'fixed left-1/2 top-1/2 z-[var(--z-modal)] grid max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 overflow-y-auto overscroll-contain data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out',
          'rounded-xl border border-border bg-card p-5 text-card-foreground shadow-ui-lg',
          'focus:outline-none',
          // VX176 — près de sa hauteur max, le haut de la Dialog approche le
          // bord haut de l'écran (centrage vertical) : safe-area en PWA
          // standalone.
          'safe-top',
          className,
        )}
        {...props}
      >
        {children}
        {showClose && (
          <DialogPrimitive.Close
            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-ring"
            aria-label="Fermer"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
})

export function DialogHeader({ className, ...props }) {
  return <div className={cn('flex flex-col gap-1 pr-6', className)} {...props} />
}
export function DialogFooter({ className, ...props }) {
  return (
    <div className={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)} {...props} />
  )
}
export const DialogTitle = forwardRef(function DialogTitle({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Title
      ref={ref}
      className={cn('font-display text-lg font-semibold leading-tight', className)}
      {...props}
    />
  )
})
export const DialogDescription = forwardRef(function DialogDescription({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Description
      ref={ref}
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  )
})

export default Dialog
