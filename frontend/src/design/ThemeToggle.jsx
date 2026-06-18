import { Sun, Moon, Monitor } from 'lucide-react'
import { cn } from '../lib/cn'
import { useTheme } from './theme-context'

const OPTIONS = [
  { value: 'light', label: 'Clair', Icon: Sun },
  { value: 'system', label: 'Système', Icon: Monitor },
  { value: 'dark', label: 'Sombre', Icon: Moon },
]

/**
 * F18 — Sélecteur de thème segmenté (Clair / Système / Sombre). Accessible :
 * group de boutons, aria-pressed, libellés FR. Destiné au header (I35) et au
 * showcase ; réutilisable partout.
 */
export function ThemeToggle({ className }) {
  const { theme, setTheme } = useTheme()
  return (
    <div
      role="group"
      aria-label="Thème de l'interface"
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted p-0.5',
        className,
      )}
    >
      {OPTIONS.map((opt) => {
        const { value, label } = opt
        const Icon = opt.Icon
        const active = theme === value
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              'inline-flex items-center justify-center rounded-md px-2 py-1 text-xs font-medium',
              'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              active
                ? 'bg-card text-foreground shadow-ui-xs'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Icon className="size-3.5" aria-hidden="true" />
            <span className="ml-1.5 hidden sm:inline">{label}</span>
          </button>
        )
      })}
    </div>
  )
}

export default ThemeToggle
