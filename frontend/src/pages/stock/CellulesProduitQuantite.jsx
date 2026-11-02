/* Deux premières cellules d'une ligne « produit × quantité » (désignation + SKU,
   quantité) — partagées par les fiches Réception et Retour fournisseur. */
export default function CellulesProduitQuantite({ l }) {
  return (
    <>
      <td className="px-3 py-2">
        {l.produit_nom}{l.produit_sku ? ` (${l.produit_sku})` : ''}
      </td>
      <td className="px-3 py-2 tabular-nums">{l.quantite}</td>
    </>
  )
}

/* En-tête « Produit · <quantité> · <3e colonne> » des mêmes fiches. */
export function EnteteProduitQuantite({ quantite, troisieme }) {
  return (
    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
      <tr>
        <th className="px-3 py-2 text-left font-semibold">Produit</th>
        <th className="px-3 py-2 text-left font-semibold">{quantite}</th>
        <th className="px-3 py-2 text-left font-semibold">{troisieme}</th>
      </tr>
    </thead>
  )
}
