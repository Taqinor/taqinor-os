import { cn } from '../lib/cn'

/* G29 — Card + sous-parties. Surface tokenisée (clair/sombre).
   VX6 — discipline d'élévation F122 : une carte se DÉFINIT par son liseré 1px
   (shadow-card), elle ne « flotte » plus au repos (fin de shadow-ui-sm) ;
   seuls les calques au-dessus du flux (menu/modal/toast) portent une ombre. */
export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-card text-card-foreground shadow-card',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex flex-col gap-1 p-4 sm:p-5', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return (
    <h3
      className={cn('font-display text-base font-semibold leading-tight tracking-tight', className)}
      {...props}
    />
  )
}

export function CardDescription({ className, ...props }) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('p-4 pt-0 sm:p-5 sm:pt-0', className)} {...props} />
}

export function CardFooter({ className, ...props }) {
  return (
    <div className={cn('flex items-center gap-2 p-4 pt-0 sm:p-5 sm:pt-0', className)} {...props} />
  )
}

export default Card
