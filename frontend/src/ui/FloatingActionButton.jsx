// VX42 — Bouton d'action flottant (FAB) : le pouce vit dans le tiers bas de
// l'écran sur le terrain (technicien ganté, une main occupée). `position:
// fixed`, respecte la zone sûre iOS (`env(safe-area-inset-bottom)`) et se
// pose AU-DESSUS de la barre d'onglets basse (`.bottom-tabbar`, 52 px + son
// propre safe-area) — jamais superposé dessus. N'apparaît qu'en dessous de
// 768 px (media query CSS, cohérent avec `.bottom-tabbar`) : sur desktop
// l'action principale a déjà sa place dans la page.
import { forwardRef } from 'react'
import { cn } from '../lib/cn'

export const FloatingActionButton = forwardRef(function FloatingActionButton(
  { label, icon, onClick, className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        'fab-button inline-flex items-center gap-2 rounded-full',
        'bg-primary text-primary-foreground shadow-ui-md',
        'hover:bg-primary/90 active:bg-primary/80',
        'focus-ring',
        'transition-[transform,box-shadow] duration-150 [@media(hover:hover)]:active:scale-[0.96]',
        className,
      )}
      {...props}
    >
      {icon}
      <span className="fab-label">{label}</span>
    </button>
  )
})

export default FloatingActionButton
