import { Combobox } from '../ui/Combobox'
import { rechercherEntreprises } from '../features/crm/rechercheEntreprises'

/* QC1 — champ « Rechercher une entreprise existante » : ne garde jamais de
   valeur, appelle `onChoisir(hit)` avec la correspondance choisie. */
export default function ComboboxEntreprise({ id, onChoisir }) {
  return (
    <Combobox
      id={id}
      value={null}
      onSearch={rechercherEntreprises}
      onChange={(_v, opt) => onChoisir(opt?.hit)}
      placeholder="Taper un nom d'entreprise…"
      searchPlaceholder="Nom ou ICE…"
      emptyText="Aucune correspondance dans vos données"
      clearable={false}
    />
  )
}
