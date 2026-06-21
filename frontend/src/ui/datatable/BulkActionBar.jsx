import { X, MoreHorizontal } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Button } from '../Button'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel,
} from '../DropdownMenu'

/* ============================================================================
   H32/H132 — Barre d'actions groupées flottante. CONFIGURABLE : les actions sont
   passées en props (`actions`), jamais codées en dur sur les leads. Dès qu'au
   moins une ligne est sélectionnée, la barre GLISSE en bas-centre (fixe,
   persistante au défilement) ; ancrée en bas sur mobile, flottante centrée sur
   desktop.
   `actions` = [{ id, label, icon?, variant?, onClick(selection), destructive? }]
   H132 — au-delà de 3 actions, les suivantes passent dans un menu de débordement
   « Plus », et un bouton « Tout désélectionner » remet la sélection à zéro.
   ========================================================================== */

const MAX_INLINE = 3

export function BulkActionBar({ count, actions = [], onClear, className }) {
  if (!count) return null
  const inline = actions.slice(0, MAX_INLINE)
  const overflow = actions.slice(MAX_INLINE)
  return (
    <div
      role="region"
      aria-label={`${count} ligne(s) sélectionnée(s)`}
      className={cn(
        'fixed inset-x-0 bottom-0 z-[var(--z-sticky)] flex justify-center px-3 pb-3',
        'sm:bottom-6 pointer-events-none',
        className,
      )}
    >
      <div
        className={cn(
          'pointer-events-auto flex w-full max-w-2xl items-center gap-2 rounded-xl border border-border',
          'bg-popover/95 p-2 pl-3 text-popover-foreground shadow-ui-lg backdrop-blur',
          // H132 — entrée glissée/animée depuis le bas (respecte prefers-reduced-motion
          // via la définition de l'animation ; pop-in combine fondu + léger zoom).
          'animate-pop-in',
        )}
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <span className="inline-flex min-w-6 items-center justify-center rounded-md bg-primary px-1.5 py-0.5 text-xs font-semibold text-primary-foreground">
            {count}
          </span>
          <span className="hidden sm:inline text-muted-foreground">sélectionné{count > 1 ? 's' : ''}</span>
        </span>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
          {inline.map((a) => {
            const Icon = a.icon
            return (
              <Button
                key={a.id}
                size="sm"
                variant={a.variant ?? (a.destructive ? 'destructive' : 'secondary')}
                onClick={() => a.onClick?.()}
              >
                {Icon && <Icon />}
                <span className={cn(a.iconOnlyMobile && 'hidden sm:inline')}>{a.label}</span>
              </Button>
            )
          })}
          {overflow.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="secondary">
                  <MoreHorizontal />
                  <span>Plus</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top">
                <DropdownMenuLabel>Autres actions</DropdownMenuLabel>
                {overflow.map((a) => {
                  const Icon = a.icon
                  return (
                    <DropdownMenuItem key={a.id} destructive={a.destructive} onSelect={() => a.onClick?.()}>
                      {Icon && <Icon />} {a.label}
                    </DropdownMenuItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button variant="ghost" size="sm" onClick={onClear} aria-label="Tout désélectionner">
            <X />
            <span className="hidden sm:inline">Tout désélectionner</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

export default BulkActionBar
