/* AOF180 — helper partagé de l'assistant de bascule d'équipement.
   Extrait de BasculeAssistant.jsx (react-refresh/only-export-components : un
   fichier de composant ne doit exporter QUE des composants).

   **AUCUN COÛT NE SORT D'ICI** (en-tête du Groupe AOF : l'économie est
   réservée au directeur). Le corps de la requête de bascule est construit par
   une ALLOWLIST STRICTE — toute clé absente de cette fonction ne peut pas
   partir sur le réseau (jamais de diffusion d'un objet produit entier, qui
   embarquerait `prix_achat` sans que personne le voie). */
export function payloadBascule({ produitId, motif, quantite }) {
  const corps = { nouveau_produit: produitId, motif: String(motif ?? '').trim() }
  if (quantite != null && quantite !== '') corps.quantite = quantite
  return corps
}
