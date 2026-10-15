import { Segmented } from './Segmented'

/* Sélecteur de vue (Liste / Kanban / Calendrier / Carte) PARTAGÉ des listes
   Chantiers, Parc et Interventions. */
export function SelecteurVue({ view, onChange, options }) {
  return (
    <Segmented
      size="sm"
      value={view}
      onChange={onChange}
      aria-label="Changer de vue"
      options={options}
    />
  )
}
