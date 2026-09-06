// NTRET1 / AUD230 — envoi réseau d'UNE vente comptoir, réutilisé par
// CaisseScreen.jsx (chemin en ligne) ET comme `sender` de la file offline
// (`offlineQueue.js`) au rejeu. Extrait de CaisseScreen.jsx (react-refresh/
// only-export-components : un fichier composant ne doit exporter QUE le
// composant) — aucun changement de comportement, même fonction, même import
// `posApi`.
import posApi from '../../api/posApi'

/* Envoi d'UNE vente comptoir au serveur, depuis un payload COMPLET (client +
   lignes + paiements + `uuid_client`).

   C'est le MÊME chemin en ligne et au rejeu : la vente porte son `uuid_client`
   dès la PREMIÈRE tentative, ce qui est la condition pour qu'un rejeu se
   dédupe. Sans cela la dédup serveur ne protégeait que la 1re des 3 étapes
   (`perform_create`), et rejouer une vente à moitié appliquée la dupliquait.

   Le rejeu reprend donc là où la coupure a laissé la vente :
     * vente déjà VALIDÉE (statut ≠ brouillon) → rien à refaire, on la rend ;
     * lignes déjà posées → on ne repose que celles qui manquent (le panier
       fusionne les lignes d'un même produit, `pos.addToCart` : un produit
       déjà présent côté serveur est donc bien la MÊME ligne) ;
     * puis validation avec les paiements.
   Fonction PURE de l'état React (elle ne lit que son payload) : elle peut donc
   servir de `sender` à la file, qui la rejouera longtemps après le démontage
   de l'écran. */
export async function envoyerVenteComptoir(payload) {
  const { uuid_client: uuidClient, client, lignes = [], paiements = [] } = payload || {}
  const venteRes = await posApi.createVente({
    ...(uuidClient ? { uuid_client: uuidClient } : {}),
    ...(client ? { client } : {}),
  })
  const vente = venteRes?.data || {}
  if (vente.statut && vente.statut !== 'brouillon') return vente
  const dejaPosees = new Set(
    (vente.lignes || []).map((l) => String(l.produit)))
  for (const ligne of lignes) {
    if (dejaPosees.has(String(ligne.produit))) continue
    await posApi.ajouterLigne(vente.id, ligne)
  }
  const finale = await posApi.validerVente(vente.id, { paiements })
  return finale?.data
}
