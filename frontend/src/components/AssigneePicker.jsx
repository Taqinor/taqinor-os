/* G23 — Sélecteur de responsable façon Odoo : pastille avatar + nom, ouvre une
   liste d'employés avec leurs avatars. Réutilisé dans la fiche lead et sur la
   carte kanban. Reçoit la liste des employés (assignables) en prop pour éviter
   de refetcher par carte.

   Reconstruit sur le Popover (G28) + jetons sémantiques (la feuille
   assigneepicker.css est supprimée). Props/API/comportement préservés 1:1 :
   { users, value, onChange, size, disabled, allowUnassigned, compact }. */
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from '../lib/cn'
import Avatar from './Avatar'

export default function AssigneePicker({
  users = [],
  value,                // id du responsable courant (ou '' / null)
  onChange,             // (id|null) => void
  size = 24,
  disabled = false,
  allowUnassigned = true,
  compact = false,      // true = bouton pastille seule (carte kanban)
}) {
  const current = users.find((u) => String(u.id) === String(value)) || null
  const currentName = current?.username || null

  const pick = (id) => {
    if (String(id ?? '') !== String(value ?? '')) onChange?.(id)
  }

  return (
    <PopoverPrimitive.Root>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          title={currentName ? `Responsable : ${currentName}` : 'Assigner un responsable'}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            'ap-trigger',
            'inline-flex max-w-full items-center gap-2 text-sm text-foreground transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
            compact
              ? 'rounded-full'
              : 'rounded-full border border-border bg-card py-0.5 pl-0.5 pr-2.5 hover:border-muted-foreground/40 hover:bg-accent',
            disabled && 'cursor-default opacity-70',
          )}
        >
          <Avatar name={currentName} src={current?.avatar_url} size={size} />
          {!compact && (
            <span className="truncate font-semibold">{currentName || 'Non assigné'}</span>
          )}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align={compact ? 'end' : 'start'}
          sideOffset={4}
          onClick={(e) => e.stopPropagation()}
          className="ap-menu z-[var(--z-popover)] max-h-72 min-w-56 overflow-y-auto rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          {allowUnassigned && (
            <PopoverPrimitive.Close asChild>
              <button
                type="button"
                onClick={() => pick(null)}
                className="ap-item flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-accent focus-visible:bg-accent"
              >
                <Avatar name={null} size={22} />
                <span>Non assigné</span>
              </button>
            </PopoverPrimitive.Close>
          )}
          {users.map((u) => (
            <PopoverPrimitive.Close asChild key={u.id}>
              <button
                type="button"
                onClick={() => pick(u.id)}
                className="ap-item flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-accent focus-visible:bg-accent"
              >
                <Avatar name={u.username} src={u.avatar_url} size={22} />
                <span className="flex flex-col leading-tight">
                  {u.username}
                  {u.poste && <span className="text-xs font-medium text-muted-foreground">{u.poste}</span>}
                </span>
              </button>
            </PopoverPrimitive.Close>
          ))}
          {users.length === 0 && (
            <div className="px-2.5 py-2.5 text-center text-sm text-muted-foreground">
              Aucun employé disponible
            </div>
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
