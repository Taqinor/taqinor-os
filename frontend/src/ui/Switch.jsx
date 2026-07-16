import { forwardRef } from 'react'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import { cn } from '../lib/cn'
import { press, pressCurve } from './interaction'

/* G25 — Interrupteur on/off accessible.
   VX126 — press partagé (`interaction.js`) : la piste gagne le même retour
   pressé que Button ; le thumb « squish » légèrement (scale-x/y asymétrique)
   au clic pour un effet tactile, réservé au pointeur fin. Courbe alignée sur
   celle de Button (`pressCurve`) au lieu du `transition-colors` par défaut. */
export const Switch = forwardRef(function Switch({ className, ...props }, ref) {
  return (
    <SwitchPrimitive.Root
      ref={ref}
      className={cn(
        'group peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border border-transparent',
        'transition-colors focus-ring',
        pressCurve,
        'disabled:cursor-not-allowed disabled:opacity-50',
        'data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
        press,
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          'pointer-events-none block size-4 rounded-full bg-card shadow-ui-sm ring-0',
          'transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0.5',
          pressCurve,
          '[@media(hover:hover)]:group-active:scale-x-90',
        )}
      />
    </SwitchPrimitive.Root>
  )
})

export default Switch
