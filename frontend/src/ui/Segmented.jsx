import { cn } from '../lib/cn'
import { press, pressCurve } from './interaction'

/* G25 — Contrôle segmenté (choix unique court). Contrôlé : `value` + `onChange`.
   `options` = [{ value, label, icon? }]. Accessible (role=radiogroup).
   VX126 — press partagé au clic (courbe identique à Button). */
export function Segmented({ options = [], value, onChange, size = 'md', className, ...props }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'
  return (
    <div
      role="radiogroup"
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted p-0.5',
        className,
      )}
      {...props}
    >
      {options.map((opt) => {
        const Icon = opt.icon
        const active = value === opt.value
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange?.(opt.value)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md font-medium transition-[color,background-color,box-shadow,transform]',
              pressCurve,
              'focus-ring',
              pad,
              press,
              active
                ? 'bg-card text-foreground shadow-ui-xs'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {Icon && <Icon className="size-3.5" aria-hidden="true" />}
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

export default Segmented
