import { forwardRef } from 'react'
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog'
import { cn } from '../lib/cn'
import { buttonVariants } from './Button'

/* G28 — AlertDialog : confirmation d'action destructive (pas de fermeture par
   clic extérieur ; choix explicite Annuler / Confirmer). */
export const AlertDialog = AlertDialogPrimitive.Root
export const AlertDialogTrigger = AlertDialogPrimitive.Trigger

export const AlertDialogContent = forwardRef(function AlertDialogContent({ className, ...props }, ref) {
  return (
    <AlertDialogPrimitive.Portal>
      <AlertDialogPrimitive.Overlay className="fixed inset-0 z-[var(--z-overlay)] bg-nuit/60 backdrop-blur-sm data-[state=open]:animate-overlay-in data-[state=closed]:animate-overlay-out" />
      <AlertDialogPrimitive.Content
        ref={ref}
        className={cn(
          // max-h + overflow : même correctif que Dialog (cf. Dialog.jsx). Sans
          // plafond de hauteur ni défilement interne, une AlertDialog haute
          // centrée par -translate-y-1/2 débordait HORS de l'écran sur iPhone
          // (boutons Annuler/Confirmer inaccessibles). 100dvh suit la hauteur
          // visible réelle d'iOS (barre d'adresse dynamique).
          'fixed left-1/2 top-1/2 z-[var(--z-modal)] grid max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 overflow-y-auto overscroll-contain',
          'rounded-xl border border-border bg-card p-5 text-card-foreground shadow-ui-lg',
          'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none',
          // VX176 — près de sa hauteur max, le haut de l'AlertDialog approche
          // le bord haut de l'écran (centrage vertical) : safe-area en PWA
          // standalone.
          'safe-top',
          className,
        )}
        {...props}
      />
    </AlertDialogPrimitive.Portal>
  )
})

export function AlertDialogHeader({ className, ...props }) {
  return <div className={cn('flex flex-col gap-1', className)} {...props} />
}
export function AlertDialogFooter({ className, ...props }) {
  return (
    <div className={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)} {...props} />
  )
}
export const AlertDialogTitle = forwardRef(function AlertDialogTitle({ className, ...props }, ref) {
  return (
    <AlertDialogPrimitive.Title ref={ref} className={cn('font-display text-lg font-semibold', className)} {...props} />
  )
})
export const AlertDialogDescription = forwardRef(function AlertDialogDescription({ className, ...props }, ref) {
  return (
    <AlertDialogPrimitive.Description ref={ref} className={cn('text-sm text-muted-foreground', className)} {...props} />
  )
})
export const AlertDialogCancel = forwardRef(function AlertDialogCancel({ className, ...props }, ref) {
  return (
    <AlertDialogPrimitive.Cancel ref={ref} className={cn(buttonVariants({ variant: 'outline' }), className)} {...props} />
  )
})
export const AlertDialogAction = forwardRef(function AlertDialogAction({ className, variant = 'destructive', ...props }, ref) {
  return (
    <AlertDialogPrimitive.Action ref={ref} className={cn(buttonVariants({ variant }), className)} {...props} />
  )
})

export default AlertDialog
