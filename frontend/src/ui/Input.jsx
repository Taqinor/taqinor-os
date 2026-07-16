import { forwardRef } from 'react'
import { cn } from '../lib/cn'

/* G22 — Champ texte. 16px sur mobile (anti-zoom iOS) → text-base sm:text-sm.
   `invalid` câble aria-invalid + style. `leading`/`trailing` = ornements
   (icône, unité). Hauteur pilotée par la densité (F20).
   VX124 — `caret-color: var(--primary)` : le curseur de saisie prend la
   teinte de marque au lieu du noir système, sur le champ le plus regardé
   de l'ERP (générateur de devis).
   VX127 — `readOnly` ≠ `disabled` : jusqu'ici un champ en lecture seule
   n'existait pas — soit éditable, soit `disabled` (opacité 60 %, texte NON
   sélectionnable/copiable). `read-only:` (variant natif Tailwind, HTML
   `readonly`) donne un fond distinct + curseur par défaut, texte pleine
   opacité et TOUJOURS sélectionnable/copiable (contrairement à disabled). */
const baseField =
  'flex w-full rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'transition-colors placeholder:text-muted-foreground caret-primary ' +
  'focus-ring focus-visible:border-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-60 ' +
  'read-only:cursor-default read-only:bg-muted/40 read-only:opacity-100 ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30 ' +
  'text-base sm:text-sm'

// VX174 — politique de saisie iOS cohérente. Sans défaut, 29 fichiers
// overridaient au coup par coup `autoCapitalize`/`autoCorrect` : références
// (`DEV-202607-…`), emails, ICE/IF, SKU, plaques auto-capitalisées/corrigées
// par le clavier iPhone. `sanitize` force les 4 attributs pertinents en un
// seul prop, cohérent partout où il est posé (un prop explicite reste
// prioritaire — spread APRÈS le préréglage).
export const SANITIZE_PRESETS = {
  // Codes/références/identifiants : jamais de capitalisation/correction.
  code: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false, autoComplete: 'off', inputMode: 'text' },
  email: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false, autoComplete: 'email', inputMode: 'email' },
  name: { autoCapitalize: 'words', autoCorrect: 'off', spellCheck: false, autoComplete: 'name' },
  // Coupe tout (cas générique sans sémantique de complétion connue).
  off: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false, autoComplete: 'off' },
}

export const Input = forwardRef(function Input(
  { className, type = 'text', invalid, leading, trailing, sanitize, ...props },
  ref,
) {
  const sanitizeProps = sanitize ? SANITIZE_PRESETS[sanitize] : null
  const field = (
    <input
      ref={ref}
      type={type}
      aria-invalid={invalid || undefined}
      {...sanitizeProps}
      className={cn(
        baseField,
        'h-[var(--control-h)] px-[var(--control-px)] py-0',
        leading && 'pl-9',
        trailing && 'pr-12',
        className,
      )}
      {...props}
    />
  )
  if (!leading && !trailing) return field
  return (
    <div className="relative w-full">
      {leading && (
        <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground [&_svg]:size-4">
          {leading}
        </span>
      )}
      {field}
      {trailing && (
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-sm text-muted-foreground">
          {trailing}
        </span>
      )}
    </div>
  )
})

export default Input
