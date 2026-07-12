import { useRef } from 'react'
import { cn } from '../lib/cn'
import { press, pressCurve } from './interaction'

/* G25 — Contrôle segmenté (choix unique court). Contrôlé : `value` + `onChange`.
   `options` = [{ value, label, icon? }]. Accessible (role=radiogroup).
   VX126 — press partagé au clic (courbe identique à Button).
   VX238(a) — roving tabindex + navigation ArrowLeft/Right/Home/End sur le
   conteneur radiogroup (57 fichiers consommateurs) : Tab n'entre/ne sort du
   groupe QU'UNE fois (seule l'option sélectionnée est tabbable), les flèches
   déplacent le focus ET la sélection sans jamais quitter le groupe — même
   comportement qu'un vrai groupe d'<input type="radio">. */
export function Segmented({ options = [], value, onChange, size = 'md', className, ...props }) {
  const pad = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'
  const btnRefs = useRef({})
  const activeIndex = Math.max(0, options.findIndex(o => o.value === value))

  const selectAt = (index) => {
    const opt = options[index]
    if (!opt) return
    onChange?.(opt.value)
    // .focus() ne dépend pas de tabIndex — fonctionne même si la nouvelle
    // option n'a pas encore reçu tabIndex=0 au prochain rendu.
    btnRefs.current[opt.value]?.focus()
  }

  const onKeyDown = (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
    if (options.length === 0) return
    e.preventDefault()
    if (e.key === 'Home') { selectAt(0); return }
    if (e.key === 'End') { selectAt(options.length - 1); return }
    const dir = e.key === 'ArrowRight' ? 1 : -1
    selectAt((activeIndex + dir + options.length) % options.length)
  }

  return (
    <div
      role="radiogroup"
      onKeyDown={onKeyDown}
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border border-border bg-muted p-0.5',
        className,
      )}
      {...props}
    >
      {options.map((opt, i) => {
        const Icon = opt.icon
        const active = value === opt.value
        return (
          <button
            key={opt.value}
            ref={el => { btnRefs.current[opt.value] = el }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={i === activeIndex ? 0 : -1}
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
