// « Batteries au départ » — banque de batteries en deux temps (C&I).
// Les panneaux et l'onduleur hybride restent dimensionnés pour la banque
// recommandée ; le devis ne porte que le nombre de batteries choisi ici, le
// reste s'ajoute plus tard. Ce n'est qu'une édition GUIDÉE de la quantité de
// l'unique ligne batterie de l'option « avec » : même geste que la cellule
// Qté du tableau (onQuantiteChange), donc totaux, variantes et verrou de
// quantité manuelle restent cohérents. Aucun appel d'API, aucun chiffre calculé.
import { Input, Label } from '../../../ui'
import { ligneBatterieUnique, quantiteRecommandee } from '../../../features/ventes/calc/batteriesDepart.js'

export default function ControleBatteriesDepart({
  lines, produits, banque, apercuBatterie, onQuantiteChange,
}) {
  const ligne = ligneBatterieUnique(lines, produits)
  if (!ligne) return null
  const reco = quantiteRecommandee(ligne, banque, apercuBatterie)
  const saisie = parseFloat(ligne.quantite)
  const manque = reco != null && Number.isFinite(saisie) && saisie >= 0 ? reco - saisie : 0
  return (
    <div className="grid gap-1.5" data-testid="gen-batteries-depart-bloc">
      <Label htmlFor="gen-batteries-depart">Batteries au départ</Label>
      <Input id="gen-batteries-depart" type="number" min="1" step="any"
             data-testid="gen-batteries-depart" value={ligne.quantite}
             onChange={e => onQuantiteChange(ligne._key, e.target.value)} />
      {reco != null && (
        <p className="text-xs text-muted-foreground" data-testid="gen-batteries-depart-reco">
          Recommandé : {reco}
          {manque > 0 && ` — ${manque} à ajouter plus tard (panneaux et onduleur déjà dimensionnés pour ${reco})`}
          {manque < 0 && ` — au-delà de la recommandation (${reco})`}
        </p>
      )}
    </div>
  )
}
