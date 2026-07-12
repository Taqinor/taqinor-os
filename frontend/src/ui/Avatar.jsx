import { Children, forwardRef } from 'react'
import * as AvatarPrimitive from '@radix-ui/react-avatar'
import { cn } from '../lib/cn'

/* G29 — Avatar (image + repli initiales) + AvatarGroup empilé.
   VX129 — pack de complétude : `size` (jusqu'ici taille FIXE size-9 partout),
   `status` (pastille de présence en/away/busy/offline), et `max` sur
   AvatarGroup (« +N » au lieu de tronquer silencieusement). */
const SIZE = {
  sm: 'size-7',
  md: 'size-9',
  lg: 'size-12',
}

const STATUS_TONE = {
  online: 'bg-success',
  away: 'bg-warning',
  busy: 'bg-destructive',
  offline: 'bg-muted-foreground',
}

const STATUS_LABEL = { online: 'En ligne', away: 'Absent', busy: 'Occupé', offline: 'Hors ligne' }

// `.avatar-root` : marqueur stable pour qu'AvatarGroup pose sa bague
// (`ring-2 ring-background`) SUR LE CERCLE, que `status` enveloppe l'avatar
// dans un conteneur relatif (pour sortir la pastille du `overflow-hidden`) ou
// non — le sélecteur `[&_.avatar-root]` fonctionne dans les deux cas, sans
// dépendre de la profondeur DOM (contrairement à un `[&>*]` fragile).
export const Avatar = forwardRef(function Avatar({ className, size = 'md', status, ...props }, ref) {
  const root = (
    <AvatarPrimitive.Root
      ref={ref}
      className={cn(
        'avatar-root relative flex shrink-0 overflow-hidden rounded-full bg-muted ring-1 ring-border',
        SIZE[size] ?? SIZE.md,
        className,
      )}
      {...props}
    />
  )
  if (!status) return root
  return (
    <span className="relative inline-flex shrink-0">
      {root}
      <span
        className={cn(
          'absolute right-0 bottom-0 size-2.5 rounded-full ring-2 ring-background',
          STATUS_TONE[status] ?? STATUS_TONE.offline,
        )}
        role="status"
        aria-label={STATUS_LABEL[status] ?? status}
      />
    </span>
  )
})

export const AvatarImage = forwardRef(function AvatarImage({ className, ...props }, ref) {
  return (
    <AvatarPrimitive.Image
      ref={ref}
      className={cn('aspect-square size-full object-cover', className)}
      {...props}
    />
  )
})

export const AvatarFallback = forwardRef(function AvatarFallback({ className, ...props }, ref) {
  return (
    <AvatarPrimitive.Fallback
      ref={ref}
      className={cn(
        'flex size-full items-center justify-center text-xs font-semibold text-muted-foreground',
        className,
      )}
      {...props}
    />
  )
})

/** Initiales depuis un nom (« Reda Kasri » → « RK »). */
export function initials(name) {
  return String(name ?? '')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
}

/** `max` : n'affiche que les `max` premiers avatars, le reste devient « +N »
    (jusqu'ici la liste débordait silencieusement hors du conteneur). */
export function AvatarGroup({ className, children, max, ...props }) {
  const items = Children.toArray(children)
  const shown = typeof max === 'number' ? items.slice(0, max) : items
  const overflow = items.length - shown.length

  return (
    <div
      className={cn('flex -space-x-2 [&_.avatar-root]:ring-2 [&_.avatar-root]:ring-background', className)}
      {...props}
    >
      {shown}
      {overflow > 0 && (
        <span
          className="relative flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground ring-2 ring-background"
          title={`+${overflow}`}
        >
          +{overflow}
        </span>
      )}
    </div>
  )
}

export default Avatar
