import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { EQUIP_STATUTS } from './equipement'

/* Sélecteur du statut d'un équipement du parc (en service / remplacé / hors
   service) : fiche équipement SAV et fiche installation. Un seul endroit. */
export default function SelectStatutEquipement({ value, onValueChange }) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger><SelectValue /></SelectTrigger>
      <SelectContent>
        {EQUIP_STATUTS.map((s) => (
          <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
