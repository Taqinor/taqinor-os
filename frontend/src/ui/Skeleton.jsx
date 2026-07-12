import { cn } from '../lib/cn'

/* G30 / L153 — Squelettes de chargement (respectent prefers-reduced-motion —
   toute animation se fige automatiquement via le garde global `*` d'index.css).
   Variantes calquées sur la forme du contenu : ligne, bloc de texte, avatar,
   carte, ligne de tableau — pour ne jamais provoquer de saut de mise en page
   quand le vrai contenu arrive.
   VX132 — balayage lumineux directionnel (`.skeleton-shimmer`, tokens.css)
   au lieu du pulse Tailwind par défaut (simple pulsation d'opacité, sans
   direction). CSS pur, zéro dépendance. */
export function Skeleton({ className, ...props }) {
  return (
    <div aria-hidden="true" className={cn('skeleton-shimmer rounded-md', className)} {...props} />
  )
}

/** Une seule ligne (hauteur de texte) — pour un libellé/valeur isolé. */
export function SkeletonLine({ className, ...props }) {
  return <Skeleton className={cn('h-3.5 w-full', className)} {...props} />
}

/** Bloc de lignes de texte squelette (la dernière plus courte). */
export function SkeletonText({ lines = 3, className }) {
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {Array.from({ length: lines }).map((unused, i) => (
        <Skeleton key={i} className={cn('h-3.5', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}

/** Pastille ronde (avatar / icône). `size-9` par défaut. */
export function SkeletonAvatar({ className, ...props }) {
  return <Skeleton className={cn('size-9 rounded-full', className)} {...props} />
}

/** Carte : un en-tête (avatar + deux lignes) puis un bloc de texte. */
export function SkeletonCard({ className }) {
  return (
    <div
      aria-hidden="true"
      className={cn('rounded-xl border border-border bg-card p-4', className)}
    >
      <div className="flex items-center gap-3">
        <SkeletonAvatar />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton className="h-3.5 w-1/2" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      </div>
      <SkeletonText lines={3} className="mt-4" />
    </div>
  )
}

/**
 * Ligne de tableau squelette — autant de cellules que `columns`.
 * À placer dans un <tbody> pour des semantics valides.
 */
export function SkeletonTableRow({ columns = 4, className }) {
  return (
    <tr aria-hidden="true" className={className}>
      {Array.from({ length: columns }).map((unused, i) => (
        <td key={i} className="px-3 py-2">
          <Skeleton className={cn('h-3.5', i === 0 ? 'w-3/4' : 'w-1/2')} />
        </td>
      ))}
    </tr>
  )
}

export default Skeleton
