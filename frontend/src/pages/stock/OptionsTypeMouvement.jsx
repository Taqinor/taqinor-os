import { SelectContent, SelectItem } from '../../ui'

/* Les trois types de mouvement de stock (liste déroulante) — partagé entre la
   saisie de mouvement et l'import OCR : un seul endroit, jamais recopié. */
export default function OptionsTypeMouvement() {
  return (
    <SelectContent>
      <SelectItem value="entree">Entrée (ajoute au stock)</SelectItem>
      <SelectItem value="sortie">Sortie (retire du stock)</SelectItem>
      <SelectItem value="ajustement">Ajustement (fixe le stock)</SelectItem>
    </SelectContent>
  )
}
