import { Label, Input, Textarea } from '../../../ui'

/* UX38–UX42 — Petits champs de formulaire partagés (label + contrôle).
   On s'appuie sur les primitives Input/Textarea du kit ; le select est un
   <select> natif stylé (léger, accessible, sans surcouche Radix pour ces
   formulaires denses). Aucun prix d'achat / marge n'est jamais saisi ici. */

export function Field({ label, htmlFor, required, hint, children }) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <Label htmlFor={htmlFor}>
          {label}
          {required && <span className="ml-0.5 text-destructive">*</span>}
        </Label>
      )}
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  )
}

export function TextField({ label, required, hint, ...props }) {
  return (
    <Field label={label} htmlFor={props.id} required={required} hint={hint}>
      <Input {...props} />
    </Field>
  )
}

export function TextAreaField({ label, required, hint, ...props }) {
  return (
    <Field label={label} htmlFor={props.id} required={required} hint={hint}>
      <Textarea {...props} />
    </Field>
  )
}

export function SelectField({
  label, required, hint, options = [], placeholder = '—', ...props
}) {
  return (
    <Field label={label} htmlFor={props.id} required={required} hint={hint}>
      <select
        className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        {...props}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </Field>
  )
}

export default Field
