import { forwardRef } from 'react'
import * as HoverCardPrimitive from '@radix-ui/react-hover-card'
import { cn } from '../lib/cn'

/* G28 — HoverCard : aperçu au survol (desktop), avec délai.
   VX129 — flèche d'ancrage `arrow` (opt-in, voir Popover.jsx). */
export const HoverCard = HoverCardPrimitive.Root
export const HoverCardTrigger = HoverCardPrimitive.Trigger

export const HoverCardContent = forwardRef(function HoverCardContent(
  { className, align = 'center', sideOffset = 6, arrow = false, children, ...props },
  ref,
) {
  return (
    <HoverCardPrimitive.Portal>
      <HoverCardPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-[var(--z-popover)] w-72 rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-ui-lg',
          'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none',
          className,
        )}
        {...props}
      >
        {children}
        {arrow && <HoverCardPrimitive.Arrow className="fill-popover" width={11} height={5} />}
      </HoverCardPrimitive.Content>
    </HoverCardPrimitive.Portal>
  )
})

export default HoverCard
