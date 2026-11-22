// ACAL663 — champs de fiche lus par les modèles électriques du calepinage
// (cellules en série, coefficient de Isc, début et pente de réduction de
// puissance, entrées MPPT indépendantes, onduleurs compatibles d'un
// optimiseur). Sortis de `ProduitForm.jsx` (plus de 2 000 lignes : il ne
// grossit pas). Tous optionnels : un champ vide part à `null`, JAMAIS à 0
// (`champsFichePourType`).
import { FormField, Input, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../ui'
import {
  CHAMPS_ELECTRIQUES_FICHE, CHOIX_TRI, LIBELLES_FICHE, typeFicheBackend,
} from './pvondFicheTechnique.js'

const AIDE = 'Optionnel — laissez vide si la fiche constructeur ne le publie pas.'

export default function FicheChampsElectriques({ ficheType, ficheFields, setFicheField }) {
  const champs = CHAMPS_ELECTRIQUES_FICHE[typeFicheBackend(ficheType)]
  if (!champs) return null
  return (
    <>
      {champs.numeriques.map((cle) => (
        <FormField key={cle} label={LIBELLES_FICHE[cle]} htmlFor={`pf-ft-${cle}`} hint={AIDE}>
          <Input id={`pf-ft-${cle}`} type="number" min="0" step="any" inputMode="decimal"
                 value={ficheFields[cle]}
                 onChange={e => setFicheField(cle, e.target.value)} />
        </FormField>
      ))}
      {champs.tri.map((cle) => (
        <FormField key={cle} label={LIBELLES_FICHE[cle]} htmlFor={`pf-ft-${cle}`} hint={AIDE}>
          <Select value={ficheFields[cle] || '__none'}
                  onValueChange={v => setFicheField(cle, v === '__none' ? '' : v)}>
            <SelectTrigger id={`pf-ft-${cle}`}><SelectValue placeholder="— Non renseigné —" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">— Non renseigné —</SelectItem>
              {CHOIX_TRI.map(([valeur, libelle]) => (
                <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
      ))}
      {champs.liste.map((cle) => (
        <FormField key={cle} label={LIBELLES_FICHE[cle]} htmlFor={`pf-ft-${cle}`}
                   hint="Exemple : SKU-1, SKU-2. Laissez vide si la fiche ne les publie pas.">
          <Input id={`pf-ft-${cle}`} type="text" value={ficheFields[cle]}
                 onChange={e => setFicheField(cle, e.target.value)} />
        </FormField>
      ))}
    </>
  )
}
