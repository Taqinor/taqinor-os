import { forwardRef } from 'react'
import * as RadioGroupPrimitive from '@radix-ui/react-radio-group'
import { cn } from '../lib/cn'
import { press, pressCurve } from './interaction'

/* G25 — Groupe de boutons radio (navigation flèches gérée par Radix).
   VX126 — `hover:border-primary/60` (cible « froide » dans les listes denses),
   press partagé, courbe alignée sur Button. */
export const RadioGroup = forwardRef(function RadioGroup({ className, ...props }, ref) {
  return (
    <RadioGroupPrimitive.Root ref={ref} className={cn('grid gap-2', className)} {...props} />
  )
})

export const RadioGroupItem = forwardRef(function RadioGroupItem({ className, ...props }, ref) {
  return (
    <RadioGroupPrimitive.Item
      ref={ref}
      className={cn(
        'aspect-square size-4.5 rounded-full border border-input bg-card text-primary shadow-ui-xs',
        'transition-[border-color,transform] focus-ring',
        pressCurve,
        'disabled:cursor-not-allowed disabled:opacity-50',
        'hover:border-primary/60 data-[state=checked]:border-primary',
        press,
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
        <span className="size-2 rounded-full bg-primary animate-pop-in" />
      </RadioGroupPrimitive.Indicator>
    </RadioGroupPrimitive.Item>
  )
})

export default RadioGroup
