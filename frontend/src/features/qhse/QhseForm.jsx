/* ============================================================================
   UX30–UX33 — Petits helpers de formulaire QHSE au-dessus des primitifs Radix.
   `FieldSelect` = un Select mono-valeur piloté par `{options:[{value,label}]}`,
   pour éviter de recâbler Trigger/Value/Content/Item dans chaque écran.
   ========================================================================== */
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

export function FieldSelect({
  value, onValueChange, options = [], placeholder = 'Sélectionner…', id,
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger id={id}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default FieldSelect
