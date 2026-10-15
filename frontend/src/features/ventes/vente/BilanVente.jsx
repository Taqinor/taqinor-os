// VNT74 (Groupe VNT, D-VNT-3) — le bilan de la vente, LU du serveur
// (`d.vente`, contrat `ventes/contract_samples/vente_etat.json`) : prix
// convenu, acompte, facturé, payé, reste. L'écran ne recalcule aucun montant.
import { formatMAD } from '../../../lib/format'

const positif = (v) => Number.parseFloat(v ?? '0') > 0

export default function BilanVente({ vente }) {
  const acompte = (vente.factures || []).find((f) => f.nature === 'acompte')
  const lignes = [
    ['Prix convenu', vente.prix_convenu_ttc],
    acompte
      ? ['Acompte', acompte.total_ttc]
      : positif(vente.acompte_propose) && ['Acompte proposé', vente.acompte_propose],
    ['Facturé', vente.emis_ttc],
    positif(vente.brouillons_ttc) && ['En brouillon', vente.brouillons_ttc],
    ['Payé', vente.paye_ttc],
    ['Reste à facturer', vente.reste_a_facturer_ttc],
    ['Reste à payer', vente.reste_a_payer_ttc],
  ].filter(Boolean)
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm sm:grid-cols-2" data-testid="bilan-vente">
      {lignes.map(([libelle, montant]) => (
        <div key={libelle} className="flex justify-between gap-2">
          <dt className="text-muted-foreground">{libelle}</dt>
          <dd className="num">{formatMAD(montant)}</dd>
        </div>
      ))}
    </dl>
  )
}
