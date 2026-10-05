import { getField } from '../draftCore'
import { enumOptions } from './enumOptions'

// ACAL345 — UN seul <select> d'énumération de la fiche lead (auparavant
// recopié dans SectionEnergie et SectionPro).
export default function SelectEnum({ id, cle, ctx, choix }) {
  const { state, setField, errors } = ctx
  return (
    <select
      id={id} className={errors[cle] ? 'form-select is-invalid' : 'form-select'}
      aria-invalid={errors[cle] ? true : undefined}
      value={getField(state, cle) ?? ''} onChange={(e) => setField(cle, e.target.value)}
    >
      {enumOptions(choix)}
    </select>
  )
}
