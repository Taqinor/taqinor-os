// VNT74 (Groupe VNT, D-VNT-3) — UNE facture de la vente dans le panneau : sa
// référence (`BROUILLON-<id>` tant qu'elle n'est pas émise), sa nature, la
// pastille « Brouillon » ≠ « Émise » ≠ « Payée », le total, le payé et les
// paiements. Lecture seule ici ; les gestes viennent avec VNT76/VNT77.
import { StatusPill } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'

const NATURES = {
  acompte: 'Acompte',
  intermediaire: 'Livraison du matériel',
  solde: 'Solde',
  complete: 'Facture complète',
  bc: 'Facture du bon de commande',
  consolidee: 'Facture consolidée',
}

const STATUTS_FACTURE = {
  brouillon: 'Brouillon',
  emise: 'Émise',
  partiellement_payee: 'Partiellement payée',
  payee: 'Payée',
  en_retard: 'En retard',
  annulee: 'Annulée',
}

const TONS = {
  brouillon: 'neutral', emise: 'info', partiellement_payee: 'warning',
  payee: 'success', en_retard: 'danger', annulee: 'danger',
}

export default function LigneFactureVente({ facture }) {
  const statut = facture.statut
  return (
    <li className="vente-facture" data-testid={`vente-facture-${facture.id}`}>
      <div className="vente-facture-tete">
        <span className="vente-facture-ref">{facture.reference}</span>
        <span className="gen-hint">{NATURES[facture.nature] ?? facture.nature}</span>
        <StatusPill status={statut} tone={TONS[statut]} label={STATUTS_FACTURE[statut] ?? statut} />
        <span className="num">{formatMAD(facture.total_ttc, { decimals: 0 })}</span>
        {Number(facture.montant_paye) > 0 && (
          <span className="gen-hint">payé {formatMAD(facture.montant_paye, { decimals: 0 })}</span>
        )}
      </div>
      {(facture.paiements ?? []).length > 0 && (
        <ul className="vente-paiements">
          {facture.paiements.map((p) => (
            <li key={p.id} data-testid={`vente-paiement-${p.id}`} className="gen-hint">
              {formatMAD(p.montant, { decimals: 0 })} · {formatDate(p.date_paiement)} · {p.mode_paiement}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}
