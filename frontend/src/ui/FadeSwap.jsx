import { cn } from '../lib/cn'

/* VX132 — <FadeSwap> : transition croisée générique squelette → contenu. Le
   passage était un SWAP SEC partout jusqu'ici (le squelette disparaît, le
   contenu apparaît, sans transition) ; ici les deux calques se superposent
   brièvement pendant un fondu enchaîné (`--motion-base`), sans dépendance
   d'animation (aucune lib de transition dans le repo) — CSS pur, deux
   calques `absolute`/flux normal qui échangent leur rôle. Respecte
   reduced-motion nativement : la transition d'OPACITÉ est de celles que le
   garde global d'index.css CONSERVE sous `prefers-reduced-motion` (seul le
   MOUVEMENT/l'échelle sont coupés — voir la règle M62/N163). */
export function FadeSwap({ loading, skeleton, children, className }) {
  return (
    <div className={cn('relative', className)}>
      <div
        aria-hidden={!loading}
        className={cn(
          'transition-opacity duration-[var(--motion-base)]',
          loading ? 'opacity-100' : 'pointer-events-none absolute inset-0 opacity-0',
        )}
      >
        {skeleton}
      </div>
      <div
        aria-hidden={loading}
        className={cn(
          'transition-opacity duration-[var(--motion-base)]',
          loading ? 'pointer-events-none absolute inset-0 opacity-0' : 'opacity-100',
        )}
      >
        {children}
      </div>
    </div>
  )
}

export default FadeSwap
