import api from '../../../api/axios'

/* ASTK224 — wrappers de l'écran « Qualité & rappels » (contrat
   wms_rappels_qualite.json). Module dédié (jamais stockApi.js). */
const qualiteApi = {
  // Rappels.
  listRappels: (params) => api.get('/stock/alertes-rappel/', { params }),
  declarerRappel: (data) => api.post('/stock/alertes-rappel/', data),
  impactRappel: (id) => api.get(`/stock/alertes-rappel/${id}/impact/`),
  cloturerRappel: (id) => api.post(`/stock/alertes-rappel/${id}/cloturer/`),
  // Blocages qualité.
  listBlocages: (params) => api.get('/stock/blocages-qualite/', { params }),
  leverBlocage: (id) => api.post(`/stock/blocages-qualite/${id}/lever/`),
  leverQuarantaine: (data) => api.post('/stock/blocages-qualite/lever-quarantaine/', data),
  // Plans d'échantillonnage (contrôle qualité à réception).
  listPlans: (params) => api.get('/stock/plans-echantillonnage/', { params }),
  creerPlan: (data) => api.post('/stock/plans-echantillonnage/', data),
  // Casiers compatibles par classe de danger.
  listHazmat: (params) => api.get('/stock/casiers-hazmat/', { params }),
  creerHazmat: (data) => api.post('/stock/casiers-hazmat/', data),
  // Sélecteurs.
  listProduits: (params) => api.get('/stock/produits/', { params }),
  listCasiers: () => api.get('/installations/bin-locations/'),
  listCategories: () => api.get('/stock/categories/'),
}

export default qualiteApi
