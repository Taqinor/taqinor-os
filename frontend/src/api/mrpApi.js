// Groupe NTMFG — Production / MRP II. Client REST de l'app backend `mrp`
// (`/api/django/mrp/…`). Même pattern que les autres clients `*Api.js`
// (ex. `stockApi.js`) : fonctions fines, un aller-retour par appel.
import api from './axios'

const mrpApi = {
  // Postes de charge (NTMFG1)
  getPostesCharge: (params) => api.get('/mrp/postes-charge/', { params }),
  createPosteCharge: (data) => api.post('/mrp/postes-charge/', data),
  updatePosteCharge: (id, data) => api.patch(`/mrp/postes-charge/${id}/`, data),
  deletePosteCharge: (id) => api.delete(`/mrp/postes-charge/${id}/`),

  // Gammes opératoires (NTMFG2)
  getGammes: (params) => api.get('/mrp/gammes/', { params }),
  getGamme: (id) => api.get(`/mrp/gammes/${id}/`),
  createGamme: (data) => api.post('/mrp/gammes/', data),
  updateGamme: (id, data) => api.patch(`/mrp/gammes/${id}/`, data),
  getOperationsGamme: (params) => api.get('/mrp/operations-gamme/', { params }),
  createOperationGamme: (data) => api.post('/mrp/operations-gamme/', data),
  updateOperationGamme: (id, data) => api.patch(`/mrp/operations-gamme/${id}/`, data),
  deleteOperationGamme: (id) => api.delete(`/mrp/operations-gamme/${id}/`),

  // Ordres de Fabrication (NTMFG3/4/6)
  getOrdresFabrication: (params) => api.get('/mrp/ordres-fabrication/', { params }),
  getOrdreFabrication: (id) => api.get(`/mrp/ordres-fabrication/${id}/`),
  createOrdreFabrication: (data) => api.post('/mrp/ordres-fabrication/', data),
  updateOrdreFabrication: (id, data) => api.patch(`/mrp/ordres-fabrication/${id}/`, data),
  confirmerOrdreFabrication: (id) => api.post(`/mrp/ordres-fabrication/${id}/confirmer/`),
  cloturerOrdreFabrication: (id) => api.post(`/mrp/ordres-fabrication/${id}/cloturer/`),
  annulerOrdreFabrication: (id, motif) =>
    api.post(`/mrp/ordres-fabrication/${id}/annuler/`, { motif }),
  getDispoComposants: (id) => api.get(`/mrp/ordres-fabrication/${id}/dispo-composants/`),

  // Opérations d'OF (NTMFG3/7/8)
  getOperationsOF: (params) => api.get('/mrp/operations-of/', { params }),
  replanifierOperationOF: (id, data) =>
    api.patch(`/mrp/operations-of/${id}/replanifier/`, data),
  demarrerOperationOF: (id) => api.post(`/mrp/operations-of/${id}/demarrer/`),
  pauserOperationOF: (id) => api.post(`/mrp/operations-of/${id}/pauser/`),
  reprendreOperationOF: (id) => api.post(`/mrp/operations-of/${id}/reprendre/`),
  terminerOperationOF: (id, data) => api.post(`/mrp/operations-of/${id}/terminer/`, data),

  // MRP net (NTMFG5)
  mrpRun: (body) => api.post('/mrp/mrp-run/', body),

  // Charge par poste (NTMFG7)
  getChargePostes: (debut, fin) =>
    api.get('/mrp/charge-postes/', { params: { debut, fin } }),

  // Coût standard vs réel (NTMFG11) — interne, admin/responsable.
  getCoutsStandard: (params) => api.get('/mrp/couts-standard/', { params }),
  figerCoutStandard: (data) => api.post('/mrp/couts-standard/figer/', data),
  getAnalyseCouts: (params) => api.get('/mrp/analyse-couts/', { params }),

  // TRS/OEE par poste (NTMFG12)
  getOeePoste: (posteId, params) => api.get(`/mrp/postes-charge/${posteId}/oee/`, { params }),
  getOeeTousPostes: (params) => api.get('/mrp/oee-postes/', { params }),

  // Simulation de charge « et si » (NTMFG18) — aucune écriture.
  simulerCharge: (body) => api.post('/mrp/simuler-charge/', body),
}

export default mrpApi
