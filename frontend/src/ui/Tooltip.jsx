import { forwardRef } from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from '../lib/cn'

/* G28 / G124 — Tooltip thémable. Envelopper l'app (ou une zone) dans
   <TooltipProvider>. Les couleurs viennent des tokens `popover` /
   `popover-foreground` (s'adaptent clair ↔ sombre), plus une flèche assortie.
   Le délai d'ouverture par défaut est harmonisé ici (et au niveau du Provider). */

// Délai d'ouverture harmonisé : 200 ms, partagé par le Provider et chaque Tooltip
// (Radix le lit sur Provider OU sur Root ; on le pose aux deux pour cohérence).
const TOOLTIP_DELAY = 200

export function TooltipProvider({ delayDuration = TOOLTIP_DELAY, ...props }) {
  return <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />
}

export function Tooltip({ delayDuration = TOOLTIP_DELAY, ...props }) {
  return <TooltipPrimitive.Root delayDuration={delayDuration} {...props} />
}

export const TooltipTrigger = TooltipPrimitive.Trigger

export const TooltipContent = forwardRef(function TooltipContent(
  { className, sideOffset = 5, children, ...props },
  ref,
) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'z-[var(--z-popover)] max-w-xs rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs font-medium text-popover-foreground shadow-ui-md',
          'data-[state=delayed-open]:animate-pop-in data-[state=closed]:animate-pop-out',
          className,
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="fill-popover" width={11} height={5} />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
})

/** Raccourci : <SimpleTooltip label="…"><button/></SimpleTooltip> */
export function SimpleTooltip({ label, children, ...props }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent {...props}>{label}</TooltipContent>
    </Tooltip>
  )
}

export default Tooltip
