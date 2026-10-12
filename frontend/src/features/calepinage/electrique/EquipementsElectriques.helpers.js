// ENF22 — helpers extraits de EquipementsElectriques.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/** Les huit types posables — ÉNUMÉRATION FERMÉE (électrique_equipements.json). */
export const LIBELLES_TYPE = Object.fromEntries([
  ['onduleur', 'Onduleur'], ['coffret_dc', 'Coffret DC'], ['coffret_ac', 'Coffret AC'],
  ['compteur_production', 'Compteur de production'], ['compteur_reseau', 'Compteur réseau'],
  ['tgbt', 'TGBT'], ['batterie', 'Batterie'], ['parafoudre', 'Parafoudre'],
])

export const TYPES_EQUIPEMENT = Object.keys(LIBELLES_TYPE)

/** Le libellé français d'un type — un type hors énumération est NOMMÉ, jamais tu. */
export function libelleType(type) {
  return LIBELLES_TYPE[type] ?? `Type inconnu : ${type}`
}

/** La RÉFÉRENCE du produit rattaché — jamais une désignation devinée. */
export function libelleProduit(produitId) {
  return produitId === null || produitId === undefined
    ? 'Aucune fiche produit rattachée'
    : `Fiche produit #${produitId}`
}
