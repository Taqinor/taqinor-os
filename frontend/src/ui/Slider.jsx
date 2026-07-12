import { forwardRef } from 'react'
import * as SliderPrimitive from '@radix-ui/react-slider'
import { cn } from '../lib/cn'
import { pressCurve } from './interaction'

/* G25 — Curseur (mono ou multi-poignées), clavier géré par Radix.
   VX126 — le thumb gagne un halo (ring) + léger scale-up au grab (`active:`,
   réservé au pointeur fin), courbe alignée sur Button via `pressCurve`. */
export const Slider = forwardRef(function Slider({ className, ...props }, ref) {
  const count = Array.isArray(props.value)
    ? props.value.length
    : Array.isArray(props.defaultValue)
      ? props.defaultValue.length
      : 1
  return (
    <SliderPrimitive.Root
      ref={ref}
      className={cn('relative flex w-full touch-none select-none items-center', className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-muted">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      {Array.from({ length: count }).map((unused, i) => (
        <SliderPrimitive.Thumb
          key={i}
          className={cn(
            'block size-4 rounded-full border border-primary bg-card shadow-ui-sm',
            'transition-[colors,transform,box-shadow] focus-ring',
            pressCurve,
            'disabled:pointer-events-none disabled:opacity-50',
            '[@media(hover:hover)]:active:scale-110 [@media(hover:hover)]:active:ring-4 [@media(hover:hover)]:active:ring-primary/20',
          )}
        />
      ))}
    </SliderPrimitive.Root>
  )
})

export default Slider
