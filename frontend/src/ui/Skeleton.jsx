import { cn } from '../lib/cn'

/* G30 — Skeleton de chargement (respecte prefers-reduced-motion via motion-safe). */
export function Skeleton({ className, ...props }) {
  return (
    <div
      aria-hidden="true"
      className={cn('motion-safe:animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  )
}

/** Bloc de lignes de texte squelette. */
export function SkeletonText({ lines = 3, className }) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {Array.from({ length: lines }).map((unused, i) => (
        <Skeleton key={i} className={cn('h-3.5', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}

export default Skeleton
