import api from './axios'

const installationsApi = {
  // Chantiers
  getInstallations: (params) => api.get('/installations/chantiers/', { params }),
  // Export .xlsx (respecte les filtres courants). Réponse blob.
  exportInstallations: (params = {}) =>
    api.get('/installations/chantiers/export/', { params, responseType: 'blob' }),
  getInstallation: (id) => api.get(`/installations/chantiers/${id}/`),
  createInstallation: (data) => api.post('/installations/chantiers/', data),
  updateInstallation: (id, data) => api.patch(`/installations/chantiers/${id}/`, data),
  deleteInstallation: (id) => api.delete(`/installations/chantiers/${id}/`),
  createFromDevis: (devisId) =>
    api.post('/installations/chantiers/creer-depuis-devis/', { devis: devisId }),
  getHistorique: (id) => api.get(`/installations/chantiers/${id}/historique/`),
  noter: (id, body) => api.post(`/installations/chantiers/${id}/noter/`, { body }),
  miseEnService: (id, data) =>
    api.post(`/installations/chantiers/${id}/mise-en-service/`, data),
  annuler: (id, motif) => api.post(`/installations/chantiers/${id}/annuler/`, { motif }),
  reactiver: (id) => api.post(`/installations/chantiers/${id}/reactiver/`),

  // Interventions / ordres de travail
  getInterventions: (params) => api.get('/installations/interventions/', { params }),
  createIntervention: (data) => api.post('/installations/interventions/', data),
  updateIntervention: (id, data) => api.patch(`/installations/interventions/${id}/`, data),
  deleteIntervention: (id) => api.delete(`/installations/interventions/${id}/`),

  // Types d'intervention gérés (Paramètres → Chantiers). La clé est posée
  // côté serveur ; un type utilisé par un ordre de travail ne peut être
  // supprimé (409 avec message FR).
  getTypesIntervention: () => api.get('/installations/types-intervention/'),
  saveTypeIntervention: (id, data) => id
    ? api.patch(`/installations/types-intervention/${id}/`, data)
    : api.post('/installations/types-intervention/', data),
  deleteTypeIntervention: (id) => api.delete(`/installations/types-intervention/${id}/`),
}

export default installationsApi
