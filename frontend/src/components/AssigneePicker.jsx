/* G23 — Sélecteur de responsable façon Odoo : pastille avatar + nom, ouvre une
   liste d'employés avec leurs avatars. Réutilisé dans la fiche lead et sur la
   carte kanban. Reçoit la liste des employés (assignables) en prop pour éviter
   de refetcher par carte.

   Reconstruit sur le Popover (G28) + jetons sémantiques (la feuille
   assigneepicker.css est supprimée). Props/API/comportement préservés 1:1 :
   { users, value, onChange, size, disabled, allowUnassigned, compact }.

   LW32 — l'avatar interne bascule sur `ui/Avatar` (Radix, tokenisé) au lieu
   de l'ancien `components/Avatar` (palette 15 hex inline, recon 04 §1) :
   couleur stable PAR RESPONSABLE via `--owner-color-{1..10}` (hash de l'ID,
   pas du nom — un renommage ne fait pas sauter la couleur). Rendu en jeton
   « soft » (même patron que les badges tonaux du fichier : fond = teinte
   diluée de la couleur, texte = la couleur pleine) pour un contraste AA
   garanti dans les deux thèmes sans dépendre d'un blanc figé. */
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from '../lib/cn'
import { Avatar, AvatarImage, AvatarFallback, initials } from '../ui/Avatar'

const OWNER_COLOR_SLOTS = 10
function ownerColorVar(id) {
  if (id == null || id === '') return 'var(--muted-foreground)'
  let h = 0
  for (const c of String(id)) h = (h * 31 + c.charCodeAt(0)) % 997
  return `var(--owner-color-${(h % OWNER_COLOR_SLOTS) + 1})`
}

function PickerAvatar({ userId, name, src, size }) {
  const colorVar = ownerColorVar(userId)
  return (
    <Avatar
      className="ring-0"
      style={{ width: size, height: size, minWidth: size }}
    >
      {src && <AvatarImage src={src} alt={name || 'Non assigné'} />}
      <AvatarFallback
        className="ap-avatar-fallback text-[10px] font-bold"
        style={{ background: `color-mix(in oklch, ${colorVar} 18%, var(--card))`, color: colorVar }}
      >
        {name ? initials(name) : '?'}
      </AvatarFallback>
    </Avatar>
  )
}

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
          <PickerAvatar userId={current?.id} name={currentName} src={current?.avatar_url} size={size} />
          {!compact && (
            <span className="ap-name truncate font-semibold">{currentName || 'Non assigné'}</span>
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
                <PickerAvatar userId={null} name={null} size={22} />
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
                <PickerAvatar userId={u.id} name={u.username} src={u.avatar_url} size={22} />
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
