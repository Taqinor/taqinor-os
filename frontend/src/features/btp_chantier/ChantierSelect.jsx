import { useChantiers, chantierLabel } from './useChantiers'

/* PACT62 — sélecteur de chantier partagé (voir useChantiers.js). */
export default function ChantierSelect({
  value, onChange, label = 'Chantier', required = false, id,
}) {
  const { chantiers, loading } = useChantiers()
  return (
    <select
      id={id}
      aria-label={label}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      required={required}
      disabled={loading}
    >
      <option value="">{loading ? 'Chargement…' : 'Chantier…'}</option>
      {chantiers.map((c) => (
        <option key={c.id} value={c.id}>{chantierLabel(c)}</option>
      ))}
    </select>
  )
}
