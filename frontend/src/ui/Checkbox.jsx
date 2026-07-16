import { forwardRef } from 'react'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check, Minus } from 'lucide-react'
import { cn } from '../lib/cn'
import { press, pressCurve } from './interaction'

/* G25 — Case à cocher (états: coché / indéterminé / désactivé), focus-visible.
   VX126 — `hover:border-primary/60` (cible « froide » dans les listes denses
   sinon indiscernable au survol), press partagé, et la coche/tiret gagnent un
   scale-in au lieu d'apparaître à cru. */
export const Checkbox = forwardRef(function Checkbox({ className, ...props }, ref) {
  return (
    <CheckboxPrimitive.Root
      ref={ref}
      className={cn(
        'peer size-4.5 shrink-0 rounded border border-input bg-card shadow-ui-xs',
        'transition-[color,background-color,border-color,box-shadow,transform] focus-ring',
        pressCurve,
        'disabled:cursor-not-allowed disabled:opacity-50',
        'hover:border-primary/60',
        'data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
        'data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary data-[state=indeterminate]:text-primary-foreground',
        press,
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator className="flex items-center justify-center text-current data-[state=checked]:animate-pop-in data-[state=indeterminate]:animate-pop-in">
        {props.checked === 'indeterminate' ? (
          <Minus className="size-3.5" strokeWidth={3} />
        ) : (
          <Check className="size-3.5" strokeWidth={3} />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
})

export default Checkbox
