import api from '../../../api/axios'

/* ASTK216 — wrappers du poste scanner (contrat wms_casiers.json : routes
   scanner_resoudre / scanner_mouvement / scanner_retour_fournisseur).
   Module dédié (jamais stockApi.js : lanes d'écrans disjointes). */
const scannerApi = {
  resoudre: (code) => api.get('/stock/scanner/resoudre/', { params: { code } }),
  poserMouvement: (corps) => api.post('/stock/scanner/mouvement/', corps),
  retourFournisseur: (code, quantite) =>
    api.get('/stock/scanner/retour-fournisseur/', { params: { code, quantite } }),
  // Lectures serveur après un geste : ventilation et historique du produit.
  ventilationProduit: (produitId) => api.get(`/stock/produits/${produitId}/emplacements/`),
  historiqueProduit: (produitId) =>
    api.get('/stock/mouvements/', { params: { produit: produitId } }),
}

export default scannerApi
