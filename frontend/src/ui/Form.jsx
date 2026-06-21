import { createContext, forwardRef, useContext, useId } from 'react'
import { AlertCircle, AlertTriangle } from 'lucide-react'
import { cn } from '../lib/cn'
import { Label } from './Label'

/* G27 — Système de formulaire en primitifs composables : Form, FormSection,
   FormField, FormActions, FormErrorSummary. Mise en page « label au-dessus »,
   marqueurs requis, validation inline par champ, résumé d'erreurs, barre
   d'actions collante (mobile). Le système ne gère PAS l'état lui-même : il se
   pilote par props (values/errors fournis par l'appelant ou un futur Group J).
   La logique pure (validation, dirty, résumé) vit dans form-utils.js. */

const FieldContext = createContext(null)

// ── Form (conteneur) ────────────────────────────────────────────────────────
export const Form = forwardRef(function Form({ className, noValidate = true, ...props }, ref) {
  // noValidate par défaut : la validation HTML native ne doit jamais
  // rejeter/snapper des valeurs (cohérent avec le générateur de devis).
  // G127 — sur mobile, on réserve un peu d'espace bas (`pb-20 sm:pb-0`) pour que
  // la barre `FormActions` collante ne chevauche pas le dernier champ.
  return (
    <form ref={ref} noValidate={noValidate} className={cn('flex flex-col gap-6 pb-20 sm:pb-0', className)} {...props} />
  )
})

// ── FormSection (groupe titré) ──────────────────────────────────────────────
export function FormSection({ title, description, children, className, ...props }) {
  return (
    <section className={cn('flex flex-col gap-4', className)} {...props}>
      {(title || description) && (
        <div className="flex flex-col gap-0.5">
          {title && <h3 className="font-display text-base font-semibold text-foreground">{title}</h3>}
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </section>
  )
}

// ── FormField (label au-dessus + erreur/aide sous le contrôle) ──────────────
/* Fournit l'id/aria au contrôle enfant via FieldContext (cf. useFormField).
   Usage : <FormField label="…" required error={…} hint="…">
             <Input {...field.controlProps} />  (ou un primitif G22/G23) */
/* G127 — `errorKind` distingue deux styles d'erreur :
   - 'required' (champ obligatoire manquant) → icône triangle, ton « manque »,
   - 'format'   (valeur présente mais invalide) → icône cercle, ton « invalide ».
   Les deux restent en couleur destructive (token) ; l'icône + le libellé a11y
   diffèrent pour aider l'utilisateur à comprendre POURQUOI. */
const ERROR_KINDS = {
  required: { Icon: AlertTriangle, srLabel: 'Champ requis' },
  format: { Icon: AlertCircle, srLabel: 'Format invalide' },
}

export function FormField({
  label, required, error, errorKind = 'format', hint, htmlFor, className, fullWidth, children, ...props
}) {
  const autoId = useId()
  const id = htmlFor || autoId
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  // G127 — l'indice ET l'erreur peuvent coexister : on décrit le contrôle par les
  // deux (ordre : erreur d'abord pour qu'un lecteur d'écran l'annonce en premier).
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined

  const ctx = {
    id,
    invalid: !!error,
    controlProps: {
      id,
      'aria-invalid': error ? true : undefined,
      'aria-describedby': describedBy,
      'aria-required': required || undefined,
    },
  }

  const kind = ERROR_KINDS[errorKind] || ERROR_KINDS.format
  const ErrorIcon = kind.Icon

  return (
    <FieldContext.Provider value={ctx}>
      <div className={cn('flex flex-col gap-1.5', fullWidth && 'sm:col-span-2', className)} {...props}>
        {label && <Label htmlFor={id} required={required}>{label}</Label>}
        {children}
        {/* G127 — indice et erreur s'affichent ENSEMBLE (l'indice ne disparaît plus
            dès qu'il y a une erreur). L'indice passe en gris atténué quand une
            erreur l'accompagne pour garder la hiérarchie visuelle. */}
        {hint && (
          <p id={hintId} className={cn('text-xs text-muted-foreground', error && 'opacity-80')}>
            {hint}
          </p>
        )}
        {error && (
          <p
            id={errorId}
            role="alert"
            data-error-kind={errorKind}
            className="flex items-center gap-1 text-xs text-destructive"
          >
            <ErrorIcon className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="sr-only">{kind.srLabel} : </span>
            {error}
          </p>
        )}
      </div>
    </FieldContext.Provider>
  )
}

/** Hook pour le contrôle enfant : récupère id + aria + état invalide du champ. */
export function useFormField() {
  return useContext(FieldContext)
}

// ── FormErrorSummary (récap en tête de formulaire) ──────────────────────────
/* `errors` = [{ field, message }] (cf. form-utils.errorSummary). Chaque entrée
   est un lien vers le champ (#field-id) pour accessibilité clavier. */
export function FormErrorSummary({ errors, title = 'Veuillez corriger les erreurs suivantes', className }) {
  if (!errors || errors.length === 0) return null
  return (
    <div
      role="alert"
      tabIndex={-1}
      className={cn('rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm', className)}
    >
      <p className="mb-1.5 flex items-center gap-1.5 font-medium text-destructive">
        <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
        {title}
      </p>
      <ul className="ml-6 list-disc space-y-0.5 text-destructive">
        {errors.map(({ field, message }) => (
          <li key={field}>
            <a href={`#${field}`} className="underline-offset-2 hover:underline">{message}</a>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── FormActions (barre d'actions collante) ──────────────────────────────────
/* `sticky` (défaut) la colle en bas — pratique sur mobile pendant un long
   formulaire. Met l'action primaire à droite (inversée en colonne sur mobile). */
export function FormActions({ children, sticky = true, className, ...props }) {
  return (
    <div
      className={cn(
        'flex flex-col-reverse gap-2 border-t border-border bg-card pt-3 sm:flex-row sm:items-center sm:justify-end',
        sticky && 'sticky bottom-0 z-[var(--z-sticky)] -mx-4 px-4 pb-3 sm:-mx-5 sm:px-5',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export default Form
