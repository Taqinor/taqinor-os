// VNT74 (Groupe VNT, D-VNT-3) — une facture de la vente : référence, nature,
// pastille « Brouillon » ≠ « Émise » (une facture brouillon n'a aucune valeur
// comptable), total et payé — tels que servis dans `vente.factures[]`.
import { StatusPill } from '../../../ui'
import { formatMAD } from '../../../lib/format'

const NATURES = {
  acompte: 'Acompte',
  intermediaire: 'Tranche intermédiaire',
  solde: 'Solde',
  complete: 'Facture complète',
  bc: 'Facture du bon de commande',
  consolidee: 'Facture consolidée',
}

function pastille(statut) {
  if (statut === 'brouillon') return { label: 'Brouillon', tone: 'neutral' }
  if (statut === 'annulee') return { label: 'Annulée', tone: 'danger' }
  return { label: 'Émise', tone: 'info' }
}

export default function LigneFactureVente({ facture: f }) {
  const p = pastille(f.statut)
  return (
    <li className="grid gap-1 rounded-md border p-2 text-sm" data-testid={`facture-vente-${f.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{f.reference}</span>
        <StatusPill label={p.label} tone={p.tone} />
      </div>
      <div className="flex flex-wrap justify-between gap-2">
        <span className="text-muted-foreground">{NATURES[f.nature] ?? f.nature}</span>
        <span className="num">{formatMAD(f.total_ttc)}</span>
      </div>
      {Number.parseFloat(f.montant_paye ?? '0') > 0 && (
        <p className="text-muted-foreground">Payé : <span className="num">{formatMAD(f.montant_paye)}</span></p>
      )}
    </li>
  )
}
