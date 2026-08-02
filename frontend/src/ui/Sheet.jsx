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

// VX133 — Grammaire directionnelle : un panneau ancré à un bord glisse DEPUIS
// ce bord (au lieu du `pop-in` centré-zoomé hérité du popover générique, qui
// « pop » un Sheet latéral de 26rem depuis le centre de l'écran).
const SIDE_ANIMATION = {
  right: 'data-[state=open]:animate-slide-in-right data-[state=closed]:animate-slide-out-right',
  left: 'data-[state=open]:animate-slide-in-left data-[state=closed]:animate-slide-out-left',
  bottom: 'data-[state=open]:animate-slide-in-bottom data-[state=closed]:animate-slide-out-bottom',
  top: 'data-[state=open]:animate-slide-in-top data-[state=closed]:animate-slide-out-top',
}

/* VX43 — Glisser-vers-le-bas-pour-fermer, UNIQUEMENT sur les bottom-sheets
   (`side="bottom"`) : le geste terrain attendu (sheets iOS/Android). Zéro
   dépendance : touchstart/move/end sur le contenu, et un lâcher au-delà du
   seuil déclenche la fermeture RÉELLE via un clic programmatique sur
   `DialogPrimitive.Close` (le seul point d'accès à `onOpenChange` que Radix
   Dialog expose sans changer l'API du composant).

   ORDRE FONDATEUR 2026-08-01 — « la fenêtre du lead se ferme quand je balaie
   PENDANT le défilement du contenu ».
   ---------------------------------------------------------------------------
   CAUSE RACINE : `DialogPrimitive.Content` porte lui-même `overflow-y-auto` —
   le panneau EST le scrolleur, et les handlers de fermeture vivaient sur ce
   même élément. Descendu au milieu d'un long contenu, un balayage vers le bas
   (= « remonte le contenu », le geste le plus banal qui soit) armait la
   fermeture. Un seuil de distance ne pouvait pas trancher : les deux gestes
   sont le MÊME mouvement, seul le CONTEXTE les distingue.

   RÈGLE DES VRAIES APPS (iOS/Android, et ce que fait toute bottom-sheet
   sérieuse) : le geste n'appartient au SHEET que si plus aucun scrolleur entre
   le doigt et le panneau ne peut consommer une poussée vers le bas — c'est-à-
   dire si TOUT est déjà en haut (`scrollTop === 0`) AU TOUCHSTART. Sinon le
   geste appartient au scroll, et le sheet ne fait STRICTEMENT rien : pas de
   translation partielle, pas de retour élastique, aucune trace. La décision se
   prend UNE fois, au poser du doigt, et ne se rejuge jamais en cours de geste
   (sinon un contenu qui atteint son sommet en plein balayage armerait la
   fermeture au milieu du mouvement — précisément l'accident qu'on corrige).

   Deux façons de franchir : la DISTANCE (un tirage franc, `DRAG_CLOSE_THRESHOLD`)
   ou la VÉLOCITÉ (une chiquenaude courte mais nette). Sans le second, un geste
   rapide et bref — celui qu'on fait naturellement — ne fermait pas et le sheet
   revenait en place : « il ne veut pas se fermer ».

   Pendant la traîne : translation 1:1, AUCUNE transition (le panneau doit
   coller au doigt). Au relâchement seulement : une transition ramène le
   panneau à sa place — et elle est automatiquement neutralisée sous
   `prefers-reduced-motion` (`--motion-base` vaut 0ms, tokens.css). */
const DRAG_CLOSE_THRESHOLD = 80
// px/ms — une chiquenaude nette ferme sans parcourir les 80 px.
const DRAG_CLOSE_VELOCITY = 0.5
// …mais elle doit tout de même avoir bougé : un effleurement ne ferme rien.
const DRAG_FLICK_MIN = 24

/* Le geste peut-il encore être consommé par un défilement ? On remonte du
   nœud touché jusqu'au panneau INCLUS : si l'un d'eux est déjà descendu, le
   geste ne nous appartient pas. Balayer les ancêtres (et pas seulement le
   panneau) couvre les écrans qui imbriquent leur PROPRE scrolleur dans le
   sheet — la fenêtre lead en est une. */
function unScrolleurEstDescendu(cible, panneau) {
  let n = cible
  while (n && n.nodeType === 1) {
    if (n.scrollTop > 0) return true
    if (n === panneau) return false
    n = n.parentNode
  }
  return false
}

export const SheetContent = forwardRef(function SheetContent(
  { className, children, side = 'right', showClose = true, ...props },
  ref,
) {
  const draggable = side === 'bottom'
  const [dragY, setDragY] = useState(0)
  // `true` entre le lâcher et la fin du retour en place : c'est le SEUL moment
  // où le panneau porte une transition (pendant la traîne il colle au doigt).
  const [relache, setRelache] = useState(false)
  const arme = useRef(false)
  const dragging = useRef(false)
  const startY = useRef(0)
  const startT = useRef(0)
  const closeRef = useRef(null)

  const onTouchStart = (e) => {
    if (!draggable) return
    const t = e.touches?.[0]
    if (!t) return
    // LA décision, prise une fois pour toute la durée du geste.
    arme.current = !unScrolleurEstDescendu(e.target, e.currentTarget)
    if (!arme.current) return
    startY.current = t.clientY
    startT.current = e.timeStamp || Date.now()
    dragging.current = false
    setRelache(false)
  }
  const onTouchMove = (e) => {
    // Geste non armé (le contenu défilait) : on ne touche à RIEN. Pas de
    // translation partielle, pas d'état — le sheet est comme absent.
    if (!draggable || !arme.current) return
    const t = e.touches?.[0]
    if (!t) return
    const delta = t.clientY - startY.current
    // Parti vers le HAUT : le doigt scrolle le contenu, le geste ne nous
    // appartient plus — et il ne nous reviendra pas s'il redescend ensuite.
    if (delta <= 0) {
      if (!dragging.current) arme.current = false
      return
    }
    dragging.current = true
    setDragY(delta)
  }
  const onTouchEnd = (e) => {
    if (!draggable) return
    if (dragging.current) {
      const duree = Math.max(1, (e?.timeStamp || Date.now()) - startT.current)
      const vitesse = dragY / duree
      const franchi = dragY >= DRAG_CLOSE_THRESHOLD
        || (dragY >= DRAG_FLICK_MIN && vitesse >= DRAG_CLOSE_VELOCITY)
      if (franchi) {
        closeRef.current?.click()
      } else if (dragY) {
        // Sous le seuil : le panneau REVIENT, et c'est le seul mouvement
        // animé du geste.
        setRelache(true)
      }
    }
    arme.current = false
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
          'focus:outline-none',
          SIDE[side],
          SIDE_ANIMATION[side],
          // VX176 — un Sheet latéral (left/right) ou top est `inset-y-0
          // h-full`/proche du bord haut : son bord colle sous l'encoche en
          // PWA standalone sans l'inset. `bottom` n'a pas besoin de l'inset
          // haut (ancré au bord bas, max-h-[85vh]).
          side !== 'bottom' && 'safe-top',
          className,
        )}
        data-sheet-scroller={draggable ? '' : undefined}
        /* Traîne : 1:1, aucune transition (le panneau colle au doigt).
           Relâchement sous le seuil : retour animé — `--motion-base` vaut 0ms
           sous prefers-reduced-motion, la neutralisation est donc automatique. */
        style={
          draggable && dragY
            ? { transform: `translateY(${dragY}px)`, transition: 'none' }
            : draggable && relache
              ? { transform: 'translateY(0px)', transition: 'transform var(--motion-base) var(--ease-standard)' }
              : undefined
        }
        /* Le retour terminé, on RETIRE le style inline : un `transform`, même
           identité, fait du panneau le bloc conteneur de ses descendants
           `position: fixed` — on ne le laisse pas traîner après le geste. */
        onTransitionEnd={draggable ? (e) => {
          if (e.target === e.currentTarget && e.propertyName === 'transform') setRelache(false)
        } : undefined}
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
            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-ring"
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
