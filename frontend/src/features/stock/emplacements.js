// N15 — Stock multi-emplacements : helpers PURS (sans réseau) pour la
// ventilation par emplacement et la validation d'un transfert côté client.
//
// Le total `Produit.quantite_stock` reste canonique : l'emplacement PRINCIPAL
// détient le reste (total − somme des non principaux). Aucun transfert ne change
// ce total — il ne fait que déplacer une quantité d'un emplacement à un autre.

// Quantité actuelle disponible dans un emplacement, à partir d'une ventilation
// [{emplacement_id, quantite, ...}] renvoyée par l'API.
export function quantiteEmplacement(breakdown, emplacementId) {
  const row = (breakdown || []).find(
    (b) => String(b.emplacement_id) === String(emplacementId))
  return row ? Number(row.quantite) || 0 : 0
}

// Total de stock reconstitué depuis la ventilation (doit égaler quantite_stock).
export function totalVentile(breakdown) {
  return (breakdown || []).reduce((s, b) => s + (Number(b.quantite) || 0), 0)
}

// Valide un transfert côté client AVANT l'appel API. Renvoie une chaîne
// d'erreur en français, ou null si tout est bon. La règle serveur fait foi ;
// ceci évite simplement des aller-retours inutiles et guide la saisie.
export function validateTransfert({ breakdown, source, destination, quantite }) {
  const q = Number(quantite)
  if (!source || !destination) return 'Choisissez la source et la destination.'
  if (String(source) === String(destination)) {
    return 'La source et la destination doivent être différentes.'
  }
  if (!Number.isFinite(q) || q <= 0) return 'La quantité doit être positive.'
  if (!Number.isInteger(q)) return 'La quantité doit être un nombre entier.'
  const dispo = quantiteEmplacement(breakdown, source)
  if (q > dispo) return `Quantité insuffisante à la source (${dispo} disponible).`
  return null
}
