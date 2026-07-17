import api from './axios'

// NTUX1/2 — vues sauvegardées serveur (personnelles + partagées d'équipe),
// fondation de la couche UX power-user. `ecran` est un identifiant stable
// côté frontend (ex. 'crm.leads', 'ventes.devis').
const uxviewsApi = {
  listSavedViews: (ecran) => api.get('/uxviews/saved-views/', { params: { ecran } }),
  createSavedView: (data) => api.post('/uxviews/saved-views/', data),
  updateSavedView: (id, data) => api.patch(`/uxviews/saved-views/${id}/`, data),
  deleteSavedView: (id) => api.delete(`/uxviews/saved-views/${id}/`),
  // NTUX2 — Directeur/Admin uniquement (403 côté serveur sinon).
  definirParDefautRole: (id, roleId) =>
    api.post(`/uxviews/saved-views/${id}/definir-par-defaut-role/`, { role: roleId }),
}

export default uxviewsApi
