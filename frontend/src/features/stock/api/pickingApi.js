import api from '../../../api/axios'

/* ASTK217 — wrappers de l'écran « Picking » (contrat wms_picking.json).
   Module dédié (jamais stockApi.js : lanes d'écrans disjointes). */
const pickingApi = {
  listVagues: (params) => api.get('/stock/vagues-picking/', { params }),
  creerVague: (corps) => api.post('/stock/vagues-picking/', corps),
  lancerVague: (id) => api.post(`/stock/vagues-picking/${id}/lancer/`),
  configurerLiberation: (id, corps) =>
    api.post(`/stock/vagues-picking/${id}/configurer-liberation/`, corps),
  prelever: (vagueId, ligneId, quantite) =>
    api.post(`/stock/vagues-picking/${vagueId}/lignes/${ligneId}/prelever/`, { quantite }),
  tacheRetour: (params) => api.get('/stock/tache-retour/', { params }),
  listPlansComptage: () => api.get('/stock/plans-comptage-tournant/'),
  genererComptages: () => api.post('/stock/plans-comptage-tournant/generer/'),
  productivite: (params) => api.get('/stock/entrepot/productivite/', { params }),
  pertes: (params) => api.get('/stock/entrepot/pertes/', { params }),
  listProduits: (params) => api.get('/stock/produits/', { params }),
}

export default pickingApi
