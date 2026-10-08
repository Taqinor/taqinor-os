import api from '../../../api/axios'

/* ASTK229 — wrappers de l'écran « Nomenclatures de stock (kits) » (contrat
   kits_stock.json, ASTK168). Module dédié (jamais stockApi.js). Un kit ne
   porte aucun prix propre ; `composants[].taux_perte_pct` est servi et
   inscriptible (absent d'un PUT, le serveur le conserve — ASTK96). */
const kitsApi = {
  listKits: (params) => api.get('/stock/kits/', { params }),
  getKit: (id) => api.get(`/stock/kits/${id}/`),
  creerKit: (data) => api.post('/stock/kits/', data),
  modifierKit: (id, data) => api.put(`/stock/kits/${id}/`, data),
  supprimerKit: (id) => api.delete(`/stock/kits/${id}/`),
  dupliquerKit: (id, data) => api.post(`/stock/kits/${id}/dupliquer/`, data ?? {}),
  revisions: (id) => api.get(`/stock/kits/${id}/revisions/`),
  disponibilite: (id) => api.get(`/stock/kits/${id}/disponibilite/`),
  remplacerComposant: (data) => api.post('/stock/kits/remplacer-composant/', data),
  // Sélecteur de produits (catalogue).
  listProduits: (params) => api.get('/stock/produits/', { params }),
}

export default kitsApi
