import { cn } from '../lib/cn'

/* G30 — État vide : message + action suivante claire. `icon` = composant lucide. */
export function EmptyState({ icon, title, description, action, className, ...props }) {
  const Icon = icon
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border',
        'px-6 py-12 text-center',
        className,
      )}
      {...props}
    >
      {Icon && (
        <span className="flex size-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-5" aria-hidden="true" />
        </span>
      )}
      {title && <p className="font-display text-base font-semibold text-foreground">{title}</p>}
      {description && (
        <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export default EmptyState
