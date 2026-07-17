import api from './axios'

/* ============================================================================
   Gestion du crédit client (apps/credit) — client API. Préfixe `/credit/`
   (axios ajoute déjà `/api/django`). La société est TOUJOURS posée côté
   serveur (jamais dans le corps). Aucun `prix_achat`/marge n'est jamais
   demandé ni affiché — le module crédit n'en expose aucun.
   ========================================================================== */

const creditApi = {
  // NTCRD3 — réglages crédit société (get-or-default / PATCH Directeur/Admin).
  getReglage: () => api.get('/credit/reglage/'),
  updateReglage: (data) => api.patch('/credit/reglage/', data),

  // NTCRD2 — limites de crédit par client.
  getLimites: (params) => api.get('/credit/limites/', { params }),
  createLimite: (data) => api.post('/credit/limites/', data),
  updateLimite: (id, data) => api.patch(`/credit/limites/${id}/`, data),

  // NTCRD10 — fiche crédit consolidée d'un client.
  getFicheClient: (clientId) => api.get(`/credit/clients/${clientId}/fiche/`),

  // NTCRD12 — score crédit d'un client (lettre + position vs limite).
  getScoreClient: (clientId) => api.get(`/credit/clients/${clientId}/score/`),

  // NTCRD13/15 — conditions de paiement par segment.
  getConditionsSegment: (params) =>
    api.get('/credit/conditions-segment/', { params }),
  createConditionSegment: (data) =>
    api.post('/credit/conditions-segment/', data),
  updateConditionSegment: (id, data) =>
    api.patch(`/credit/conditions-segment/${id}/`, data),
  deleteConditionSegment: (id) =>
    api.delete(`/credit/conditions-segment/${id}/`),

  // NTCRD9 — dérogations : demande + décision (approuver/rejeter).
  getDerogations: (params) => api.get('/credit/derogations/', { params }),
  createDerogation: (data) => api.post('/credit/derogations/', data),
  approuverDerogation: (id) =>
    api.post(`/credit/derogations/${id}/approuver/`),
  rejeterDerogation: (id) => api.post(`/credit/derogations/${id}/rejeter/`),
}

export default creditApi
