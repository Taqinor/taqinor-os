import { forwardRef, useRef, useState } from 'react'
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

// VX43 — Glisser-vers-le-bas-pour-fermer, UNIQUEMENT sur les bottom-sheets
// (`side="bottom"`) : le geste terrain attendu (sheets iOS/Android). Zéro
// dépendance : touchstart/move/end sur le contenu, seuil de distance avant
// d'armer (anti-scroll-vertical-interne d'une longue liste de panneaux), et un
// lâcher au-delà du seuil déclenche la fermeture RÉELLE via un clic
// programmatique sur `DialogPrimitive.Close` (le seul point d'accès à
// `onOpenChange` que Radix Dialog expose sans changer l'API du composant).
const DRAG_CLOSE_THRESHOLD = 80

export const SheetContent = forwardRef(function SheetContent(
  { className, children, side = 'right', showClose = true, ...props },
  ref,
) {
  const draggable = side === 'bottom'
  const [dragY, setDragY] = useState(0)
  const dragging = useRef(false)
  const startY = useRef(0)
  const closeRef = useRef(null)

  const onTouchStart = (e) => {
    if (!draggable) return
    const t = e.touches?.[0]
    if (!t) return
    startY.current = t.clientY
    dragging.current = false
  }
  const onTouchMove = (e) => {
    if (!draggable) return
    const t = e.touches?.[0]
    if (!t) return
    const delta = t.clientY - startY.current
    // On n'arme le geste QUE vers le bas (un tirage vers le haut ne fait rien
    // ici — le contenu peut avoir son propre scroll interne vers le haut).
    if (delta <= 0) return
    dragging.current = true
    setDragY(delta)
  }
  const onTouchEnd = () => {
    if (!draggable) return
    if (dragging.current && dragY >= DRAG_CLOSE_THRESHOLD) {
      closeRef.current?.click()
    }
    dragging.current = false
    setDragY(0)
  }

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
          // VX176 — un Sheet latéral (left/right) ou top est `inset-y-0
          // h-full`/proche du bord haut : son bord colle sous l'encoche en
          // PWA standalone sans l'inset. `bottom` n'a pas besoin de l'inset
          // haut (ancré au bord bas, max-h-[85vh]).
          side !== 'bottom' && 'safe-top',
          className,
        )}
        style={draggable && dragY ? { transform: `translateY(${dragY}px)`, transition: 'none' } : undefined}
        onTouchStart={draggable ? onTouchStart : undefined}
        onTouchMove={draggable ? onTouchMove : undefined}
        onTouchEnd={draggable ? onTouchEnd : undefined}
        onTouchCancel={draggable ? onTouchEnd : undefined}
        {...props}
      >
        {/* VX43 — poignée visuelle de bottom-sheet : affordance « glisser pour
            fermer », posée seulement côté bottom (jamais sur right/left/top). */}
        {draggable && (
          <div
            aria-hidden="true"
            className="mx-auto -mt-1 mb-1 h-1.5 w-10 shrink-0 rounded-full bg-muted-foreground/30"
          />
        )}
        {children}
        {showClose && (
          <DialogPrimitive.Close
            ref={closeRef}
            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Fermer"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        )}
        {/* Fermeture programmatique du glisser-pour-fermer quand `showClose`
            est désactivé par l'écran : bouton invisible mais toujours présent
            pour que le clic programmatique du drag fonctionne malgré tout. */}
        {draggable && !showClose && (
          <DialogPrimitive.Close ref={closeRef} className="sr-only" aria-hidden="true" tabIndex={-1} />
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
