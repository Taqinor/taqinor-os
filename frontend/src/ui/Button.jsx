import { forwardRef } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'

/* G21 — Bouton : variantes, tailles, états (loading/disabled), focus-visible. */
export const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md',
    'font-medium select-none transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
    'disabled:pointer-events-none disabled:opacity-50',
    '[&_svg]:pointer-events-none [&_svg]:shrink-0',
  ],
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-ui-xs',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        outline: 'border border-input bg-card text-foreground hover:bg-accent hover:text-accent-foreground',
        ghost: 'text-foreground hover:bg-accent hover:text-accent-foreground',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-ui-xs',
        success: 'bg-success text-success-foreground hover:bg-success/90 shadow-ui-xs',
        link: 'text-primary underline-offset-4 hover:underline',
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
      {loading && !asChild && <Spinner className="size-4" />}
      {children}
    </Comp>
  )
})

export default Button
