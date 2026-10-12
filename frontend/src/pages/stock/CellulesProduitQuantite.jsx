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
