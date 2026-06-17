import api from './axios'

const stockApi = {
  // Produits
  getProduits: (params) => api.get('/stock/produits/', { params }),
  getProduit: (id) => api.get(`/stock/produits/${id}/`),
  createProduit: (data) => api.post('/stock/produits/', data),
  updateProduit: (id, data) => api.patch(`/stock/produits/${id}/`, data),
  patchProduit: (id, data) => api.patch(`/stock/produits/${id}/`, data),
  deleteProduit: (id) => api.delete(`/stock/produits/${id}/`),
  getProduitsArchived: () => api.get('/stock/produits/', { params: { show_archived: 'true' } }),
  unarchiveProduit: (id) => api.patch(`/stock/produits/${id}/unarchive/`),
  forceDeleteProduit: (id) => api.delete(`/stock/produits/${id}/force-delete/`),

  // Catégories
  getCategories: (params) => api.get('/stock/categories/', { params }),
  createCategorie: (data) => api.post('/stock/categories/', data),
  updateCategorie: (id, data) => api.put(`/stock/categories/${id}/`, data),
  deleteCategorie: (id) => api.delete(`/stock/categories/${id}/`),

  // Fournisseurs
  getFournisseurs: (params) => api.get('/stock/fournisseurs/', { params }),
  createFournisseur: (data) => api.post('/stock/fournisseurs/', data),
  updateFournisseur: (id, data) => api.put(`/stock/fournisseurs/${id}/`, data),
  deleteFournisseur: (id) => api.delete(`/stock/fournisseurs/${id}/`),

  // Mouvements
  getMouvements: (params) => api.get('/stock/mouvements/', { params }),
  createMouvement: (data) => api.post('/stock/mouvements/', data),

  // Édition en masse du catalogue (T8) + export Excel d'une sélection.
  bulkProduits: (payload) => api.post('/stock/produits/bulk/', payload),
  // N16 — inventaire physique : comptage par produit → ajustement de stock.
  inventaire: (payload) => api.post('/stock/produits/inventaire/', payload),
  exportProduitsXlsx: (ids) =>
    api.post('/stock/produits/export-xlsx/', { ids }, { responseType: 'blob' }),
  // Marques gérées (Paramètres → Stock). Une marque utilisée n'est pas supprimable.
  getMarques: () => api.get('/stock/marques/'),
  saveMarque: (id, data) => id
    ? api.patch(`/stock/marques/${id}/`, data) : api.post('/stock/marques/', data),
  deleteMarque: (id) => api.delete(`/stock/marques/${id}/`),

  // Outillage (équipement durable — F1). Séparé des SKU vendables.
  getOutillage: (params) => api.get('/stock/outillage/', { params }),
  createOutil: (data) => api.post('/stock/outillage/', data),
  updateOutil: (id, data) => api.patch(`/stock/outillage/${id}/`, data),
  deleteOutil: (id) => api.delete(`/stock/outillage/${id}/`),

  // Bons de commande FOURNISSEUR (achats — N11). Les prix d'achat sont INTERNES.
  getBonsCommandeFournisseur: (params) =>
    api.get('/stock/bons-commande-fournisseur/', { params }),
  getBonCommandeFournisseur: (id) =>
    api.get(`/stock/bons-commande-fournisseur/${id}/`),
  createBonCommandeFournisseur: (data) =>
    api.post('/stock/bons-commande-fournisseur/', data),
  updateBonCommandeFournisseur: (id, data) =>
    api.patch(`/stock/bons-commande-fournisseur/${id}/`, data),
  deleteBonCommandeFournisseur: (id) =>
    api.delete(`/stock/bons-commande-fournisseur/${id}/`),
  envoyerBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/envoyer/`),
  recevoirBcf: (id, receptions) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/recevoir/`, { receptions }),
  annulerBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/annuler/`),
  bcfPdf: (id) =>
    api.get(`/stock/bons-commande-fournisseur/${id}/pdf/`, { responseType: 'blob' }),
}

export default stockApi
