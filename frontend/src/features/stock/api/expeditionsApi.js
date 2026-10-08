import api from '../../../api/axios'

/* ASTK220 — wrappers de l'écran « Expéditions » (contrat wms_expedition.json).
   Module dédié (jamais stockApi.js : lanes d'écrans disjointes). */
const expeditionsApi = {
  // Unités logistiques (colis / palettes).
  listUnites: (params) => api.get('/stock/unites-logistiques/', { params }),
  creerUnite: (data) => api.post('/stock/unites-logistiques/', data),
  ajouterLigne: (id, data) => api.post(`/stock/unites-logistiques/${id}/lignes/`, data),
  controlerScan: (id, data) => api.post(`/stock/unites-logistiques/${id}/controler-scan/`, data),
  deplacer: (id, data) => api.post(`/stock/unites-logistiques/${id}/deplacer/`, data),
  sceller: (id) => api.post(`/stock/unites-logistiques/${id}/sceller/`),
  modifierUnite: (id, data) => api.patch(`/stock/unites-logistiques/${id}/`, data),
  etiquetteUnitePdf: (id) =>
    api.get(`/stock/unites-logistiques/${id}/etiquette-pdf/`, { responseType: 'blob' }),
  // Plans de chargement.
  listPlans: (params) => api.get('/stock/plans-chargement/', { params }),
  creerPlan: (data) => api.post('/stock/plans-chargement/', data),
  ajouterUnitePlan: (id, data) => api.post(`/stock/plans-chargement/${id}/unites/`, data),
  verifierCapacite: (id) => api.get(`/stock/plans-chargement/${id}/verifier-capacite/`),
  // Expéditions transporteur.
  listExpeditions: (params) => api.get('/stock/expeditions/', { params }),
  creerExpedition: (data) => api.post('/stock/expeditions/', data),
  genererEtiquette: (id) => api.post(`/stock/expeditions/${id}/generer-etiquette/`),
  cmrPdf: (id) => api.get(`/stock/expeditions/${id}/cmr-pdf/`, { responseType: 'blob' }),
  tracking: (id) => api.get(`/stock/expeditions/${id}/tracking/`),
  tarifs: (params) => api.get('/stock/expeditions/tarifs/', { params }),
  // Retours client et rebuts.
  listRetours: (params) => api.get('/stock/retours-client/', { params }),
  creerRetour: (data) => api.post('/stock/retours-client/', data),
  receptionnerRetour: (id) => api.post(`/stock/retours-client/${id}/receptionner/`),
  inspecterRetour: (id, data) => api.post(`/stock/retours-client/${id}/inspecter/`, data),
  listRebuts: (params) => api.get('/stock/mouvements-rebut/', { params }),
  declarerRebut: (data) => api.post('/stock/mouvements-rebut/', data),
  // Sélecteurs.
  listProduits: (params) => api.get('/stock/produits/', { params }),
  listCasiers: () => api.get('/installations/bin-locations/'),
  listClients: (params) => api.get('/crm/clients/', { params }),
}

export default expeditionsApi
