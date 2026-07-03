import { useEffect } from 'react'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Spinner,
} from '../../ui'

/* WR6 — Sélecteur de système SUPERVISÉ, partagé par les écrans O&M. Reçoit les
   entrées de `useSupervisedSystems` ({ id (config), installation, label }).
   Quand il n'existe qu'un seul système supervisé, il est sélectionné d'office
   (moins de clics, et rend l'écran testable sans interaction). */
export default function SystemPicker({ systems, loading, value, onChange, label = 'Choisir un système installé…' }) {
  // Auto-sélection quand un seul système supervisé existe.
  useEffect(() => {
    if (!value && systems.length === 1) onChange(String(systems[0].id))
  }, [systems, value, onChange])

  if (loading) {
    return (
      <p className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <Spinner /> Chargement des systèmes…
      </p>
    )
  }

  return (
    <div className="min-w-[18rem]">
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger aria-label="Choisir un système supervisé">
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
          {systems.map((s) => (
            <SelectItem key={s.id} value={String(s.id)}>{s.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
