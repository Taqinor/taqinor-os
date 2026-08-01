import { forwardRef } from 'react'
import * as SliderPrimitive from '@radix-ui/react-slider'
import { cn } from '../lib/cn'
import { pressCurve } from './interaction'

/* G25 — Curseur (mono ou multi-poignées), clavier géré par Radix.
   VX126 — le thumb gagne un halo (ring) + léger scale-up au grab (`active:`,
   réservé au pointeur fin), courbe alignée sur Button via `pressCurve`.

   Accessibilité : c'est le THUMB qui porte `role="slider"`, pas la racine. Un
   `aria-label` laissé sur la racine (un `<span>` sans rôle) est donc ignoré par
   les technologies d'assistance : le curseur était annoncé SANS NOM. On
   redirige `aria-label`/`aria-labelledby` vers chaque poignée, seule porteuse
   du rôle. */
export const Slider = forwardRef(function Slider(
  { className, 'aria-label': ariaLabel, 'aria-labelledby': ariaLabelledBy, ...props }, ref,
) {
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
          aria-label={ariaLabel}
          aria-labelledby={ariaLabelledBy}
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
