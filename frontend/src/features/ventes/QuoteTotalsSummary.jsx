// VX139 — un seul bloc de présentation des totaux + une seule devise pour les
// deux éditeurs de devis (`DevisForm.jsx` et `DevisGenerator.jsx`). Avant :
// `DevisForm` affichait un suffixe « DH » codé en dur (`toFixed`/concat)
// pendant que le générateur affichait « MAD » via `formatMoney` — le vendeur
// qui crée puis édite le MÊME document voyait deux devises différentes. Fix :
// un seul composant de présentation, formaté par `formatMAD` (une seule
// source de vérité, RULE VX75), consommé par les deux écrans.
//
// Chaîne canonique : Sous-total HT → Remise → Total HT → TVA → Total TTC.
// `subtotalHT`/`totalHT`/`totalTVA`/`totalTTC` sont TOUJOURS fournis par
// l'appelant (aucun calcul métier ici — pur affichage) ; `remiseLabel` et
// `remiseMontant` sont optionnels (masqués si absents ou nuls).

import { formatMAD } from '../../lib/format'

export default function QuoteTotalsSummary({
  subtotalHT,
  remiseLabel,
  remiseMontant,
  totalHT,
  tauxTva,
  totalTVA,
  totalTTC,
  className = '',
}) {
  return (
    <div className={`ml-auto w-full max-w-xs rounded-lg border border-border bg-muted/30 p-3 text-sm ${className}`}>
      <div className="flex justify-between py-0.5">
        <span className="text-muted-foreground">Sous-total HT</span>
        <span className="tabular-nums">{formatMAD(subtotalHT)}</span>
      </div>
      {!!remiseMontant && (
        <div className="flex justify-between py-0.5 text-warning">
          <span>{remiseLabel}</span>
          <span className="tabular-nums">−{formatMAD(remiseMontant)}</span>
        </div>
      )}
      <div className="flex justify-between py-0.5">
        <span className="text-muted-foreground">Total HT</span>
        <strong className="tabular-nums">{formatMAD(totalHT)}</strong>
      </div>
      <div className="flex justify-between py-0.5">
        <span className="text-muted-foreground">TVA ({tauxTva}%)</span>
        <span className="tabular-nums">{formatMAD(totalTVA)}</span>
      </div>
      <div className="mt-1 flex justify-between border-t border-border pt-1.5 text-base">
        <span className="font-semibold">Total TTC</span>
        <strong className="tabular-nums text-primary">{formatMAD(totalTTC)}</strong>
      </div>
    </div>
  )
}
