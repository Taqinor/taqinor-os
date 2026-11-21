import { formatPercent } from '../../../lib/format'
import { Stat } from '../../../ui'

/* ACAL709 — « De la consommation » : la part de la consommation couverte par
   le solaire (`autoconsommation.taux_couverture`, règle COUV-AUTO : autoconsommé
   ÷ consommation). Valeur SERVIE, jamais recalculée ; fraction × 100 pour le
   pourcentage seulement. `null` ⇒ « non calculée » + motif servi, jamais 0. */

const REPLI = 'Aucune consommation connue.'

export default function TuileCouverture({ autoconsommation }) {
  const taux = autoconsommation?.taux_couverture
  const connu = typeof taux === 'number'
  const batterie = connu && autoconsommation?.energie?.apres_batterie === true
  let hint = connu ? 'Part de la consommation couverte par le solaire' : (autoconsommation?.motif_absence || REPLI)
  if (batterie) hint += ' (batterie comprise)'
  return (
    <div data-testid="acal709-couverture">
      <Stat
        label="De la consommation"
        value={connu ? formatPercent(taux * 100, { decimals: 0 }) : 'non calculée'}
        hint={hint}
      />
    </div>
  )
}
