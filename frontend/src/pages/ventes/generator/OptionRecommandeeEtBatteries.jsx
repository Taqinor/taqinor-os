// « Option Recommandée » et, pour un devis commercial ou industriel,
// « Batteries au départ » — deux cellules voisines de la carte « Paramètres »,
// sorties de `DevisGenerator.jsx` (fichier de plus de 2 000 lignes qui ne doit
// pas grossir). Le bloc « Option Recommandée » est rendu à l'identique.
import {
  Label, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import IndicationRegistre from './IndicationRegistre'
import ControleBatteriesDepart from './ControleBatteriesDepart'

export default function OptionRecommandeeEtBatteries({
  recommendedChoice, setRecommendedChoice, imposees, overridesBusy, regenererOverride,
  marcheCi, lines, produits, onQuantiteChange, banque, apercuBatterie,
}) {
  return (
    <>
      <div className="grid gap-1.5">
        <Label htmlFor="gen-reco">Option Recommandée</Label>
        <Select value={recommendedChoice} onValueChange={setRecommendedChoice}>
          <SelectTrigger id="gen-reco"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="Auto">Auto (défaut)</SelectItem>
            <SelectItem value="Aucune recommandation">Aucune recommandation</SelectItem>
            <SelectItem value="Sans batterie">Sans batterie</SelectItem>
            <SelectItem value="Avec batterie">Avec batterie</SelectItem>
          </SelectContent>
        </Select>
        {'recommended_option' in imposees && (
          <IndicationRegistre chemin="recommended_option" busy={overridesBusy}
                              onRegenerer={regenererOverride} />
        )}
      </div>
      {/* Fondateur 17/11/2026 — proposer moins de batteries au départ : les
          panneaux et l'onduleur restent dimensionnés pour la banque recommandée. */}
      {marcheCi && (
        <ControleBatteriesDepart
          lines={lines} produits={produits} onQuantiteChange={onQuantiteChange}
          banque={banque} apercuBatterie={apercuBatterie} />
      )}
    </>
  )
}
