import { cn } from '../../lib/cn'

/* ============================================================================
   NTIDE4 — Sélecteur natif léger pour les filtres de liste (une valeur, court).
   ----------------------------------------------------------------------------
   Contrat ``value`` / ``onChange(value)`` / ``options:[{value,label}]`` au-dessus
   d'un ``<select>`` natif : accessible, testable (``getByRole('combobox')``).
   Copié du patron ``apps/litiges`` (FilterSelect.jsx) — chaque feature garde
   son propre petit helper plutôt qu'un import cross-feature.
   ========================================================================== */

export function FilterSelect({ value, onChange, options = [], className, ...props }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm text-foreground',
        'shadow-ui-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

export default FilterSelect
