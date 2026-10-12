// VNT74 (Groupe VNT, D-VNT-3) — le bilan chiffré de la vente, LU du serveur
// (`d.vente`, contrat `ventes/contract_samples/vente_etat.json`). L'écran ne
// redérive aucun montant : chaque ligne affiche la chaîne servie.
import { formatMAD } from '../../../lib/format'

const LIGNES = [
  ['prix_convenu_ttc', 'Prix convenu'],
  ['emis_ttc', 'Facturé (émis)'],
  ['brouillons_ttc', 'En brouillon'],
  ['paye_ttc', 'Payé'],
  ['reste_a_facturer_ttc', 'Reste à facturer'],
  ['reste_a_payer_ttc', 'Reste à payer'],
]

export default function BilanVente({ vente }) {
  return (
    <dl className="vente-bilan grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2" data-testid="vente-bilan">
      {LIGNES.map(([cle, libelle]) => (
        <div key={cle} className="vente-bilan-ligne flex items-baseline justify-between gap-2" data-cle={cle}>
          <dt>{libelle}</dt>
          <dd className="num">{formatMAD(vente?.[cle], { decimals: 0 })}</dd>
        </div>
      ))}
    </dl>
  )
}
