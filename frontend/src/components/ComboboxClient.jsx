import { Combobox } from '../ui/Combobox'
import { rechercherClients } from '../features/crm/rechercheEntreprises'

/* Sélecteur de client des créations rapides SAV (ticket) : mêmes libellés
   partout, `invalid` posé par l'appelant. */
export default function ComboboxClient({ id, value, onChange, invalid }) {
  return (
    <Combobox
      id={id}
      autoFocus
      value={value}
      onChange={onChange}
      onSearch={rechercherClients}
      placeholder="— Sélectionner un client —"
      searchPlaceholder="Nom ou ICE…"
      emptyText="Aucun client dans vos données"
      invalid={invalid}
    />
  )
}
