import { forwardRef } from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from '../lib/cn'

/* G28 — Tooltip. Envelopper l'app (ou une zone) dans <TooltipProvider>. */
export const TooltipProvider = TooltipPrimitive.Provider
export const Tooltip = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export const TooltipContent = forwardRef(function TooltipContent(
  { className, sideOffset = 5, ...props },
  ref,
) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'z-[var(--z-popover)] max-w-xs rounded-md bg-nuit px-2.5 py-1.5 text-xs font-medium text-white shadow-ui-md',
          'data-[state=delayed-open]:animate-pop-in data-[state=closed]:animate-pop-out',
          className,
        )}
        {...props}
      />
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
