import { forwardRef } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'

/* G21 / G125 — Bouton : six états complets pilotés par tokens —
   default / hover / focus-visible / active / disabled / loading.
   Le press tactile `active:scale-[0.97]` (~150 ms, cubic-bezier(0.23,1,0.32,1))
   est RÉSERVÉ aux pointeurs fins via `@media (hover:hover)` : sur mobile le
   « survol émulé » ne doit jamais déclencher le press. La transition couvre
   désormais aussi `transform` (pour le press) en plus des couleurs.
   VX124 — le variant `default` (CTA primaire) gagne une ombre TEINTÉE brass
   au survol (`--shadow-primary-hover`, tokens.css) au lieu du gris-nuit
   neutre partagé par tous les autres variants. */
export const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md',
    'font-medium select-none transition-[color,background-color,border-color,box-shadow,transform]',
    'duration-150 [transition-timing-function:cubic-bezier(0.23,1,0.32,1)]',
    'focus-ring',
    'disabled:pointer-events-none disabled:opacity-50',
    '[@media(hover:hover)]:active:scale-[0.97]',
    'aria-busy:cursor-progress',
    '[&_svg]:pointer-events-none [&_svg]:shrink-0',
  ],
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary/80 shadow-ui-xs hover:shadow-ui-primary-hover',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 active:bg-secondary/70',
        outline: 'border border-input bg-card text-foreground hover:bg-accent hover:text-accent-foreground active:bg-accent/80',
        ghost: 'text-foreground hover:bg-accent hover:text-accent-foreground active:bg-accent/80',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90 active:bg-destructive/80 shadow-ui-xs',
        success: 'bg-success text-success-foreground hover:bg-success/90 active:bg-success/80 shadow-ui-xs',
        link: 'text-primary underline-offset-4 hover:underline active:text-primary/80',
      },
      size: {
        sm: 'h-[var(--control-h-sm)] px-3 text-xs [&_svg]:size-3.5',
        md: 'h-[var(--control-h)] px-[var(--control-px)] text-sm [&_svg]:size-4',
        lg: 'h-[var(--control-h-lg)] px-5 text-sm [&_svg]:size-4',
        icon: 'h-[var(--control-h)] w-[var(--control-h)] [&_svg]:size-4',
      },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  },
)

export const Button = forwardRef(function Button(
  { className, variant, size, asChild = false, loading = false, disabled, children, ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {asChild ? children : (
        <>
          {loading && <Spinner className="size-4" />}
          {children}
        </>
      )}
    </Comp>
  )
})

export default Button
