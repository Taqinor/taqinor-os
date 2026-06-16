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
  // Édition groupée du catalogue (prix de vente, garantie, catégorie, marque)
  bulkProduits: (action, ids, params) =>
    api.post('/stock/produits/bulk/', { action, ids, params }),
  // Export .xlsx de la sélection (réponse binaire)
  exportProduitsXlsx: (ids) =>
    api.post('/stock/produits/bulk/', { action: 'export_xlsx', ids }, { responseType: 'blob' }),

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
}

export default stockApi
