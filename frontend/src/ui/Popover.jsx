import { forwardRef } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from '../lib/cn'

/* G28 — Popover (contenu flottant ancré).
   VX129 — flèche d'ancrage `arrow` (opt-in, contrairement à Tooltip qui la
   pose toujours) : Popover sert dans beaucoup de contextes déjà denses
   (Combobox/DatePicker…) où une flèche serait du bruit — additif, jamais par
   défaut, pour ne régresser aucun écran existant. */
export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger
export const PopoverAnchor = PopoverPrimitive.Anchor
export const PopoverClose = PopoverPrimitive.Close

export const PopoverContent = forwardRef(function PopoverContent(
  { className, align = 'center', sideOffset = 6, arrow = false, children, ...props },
  ref,
) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-[var(--z-popover)] w-72 rounded-lg border border-border bg-popover p-3 text-popover-foreground shadow-ui-lg',
          'data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none',
          className,
        )}
        {...props}
      >
        {children}
        {arrow && <PopoverPrimitive.Arrow className="fill-popover" width={11} height={5} />}
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  )
})

export default Popover
