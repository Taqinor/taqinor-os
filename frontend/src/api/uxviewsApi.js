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
  // NTUX23 — rapport « configuration des vues actives » (Directeur/Admin
  // uniquement, 403 côté serveur sinon) : TOUTES les vues de la company
  // (au-delà du filtre perso/équipe de listSavedViews), + export .xlsx.
  listAllSavedViews: () => api.get('/uxviews/saved-views/toutes-company/'),
  exportSavedViewsXlsx: () => api.get('/uxviews/saved-views/export-xlsx/', { responseType: 'blob' }),
  // NTUX34 — import CSV/XLSX de vues sauvegardées entre environnements
  // (Directeur/Admin uniquement, 403 côté serveur sinon) : renvoie
  // `{created: [...vues...], erreurs: [{ligne, message}]}`, jamais un
  // tout-ou-rien (les lignes valides sont importées même si d'autres échouent).
  importSavedViews: (file) => {
    const form = new FormData()
    form.append('fichier', file)
    return api.post('/uxviews/saved-views/importer/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export default uxviewsApi
