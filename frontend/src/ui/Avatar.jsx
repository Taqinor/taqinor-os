import { forwardRef } from 'react'
import * as AvatarPrimitive from '@radix-ui/react-avatar'
import { cn } from '../lib/cn'

/* G29 — Avatar (image + repli initiales) + AvatarGroup empilé. */
export const Avatar = forwardRef(function Avatar({ className, ...props }, ref) {
  return (
    <AvatarPrimitive.Root
      ref={ref}
      className={cn(
        'relative flex size-9 shrink-0 overflow-hidden rounded-full bg-muted ring-1 ring-border',
        className,
      )}
      {...props}
    />
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

export function AvatarGroup({ className, children, ...props }) {
  return (
    <div className={cn('flex -space-x-2 [&>*]:ring-2 [&>*]:ring-background', className)} {...props}>
      {children}
    </div>
  )
}

export default Avatar
