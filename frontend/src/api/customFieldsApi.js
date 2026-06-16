import api from './axios'

// API des champs personnalisés (T11). Tout est scopé société côté serveur.
// Les chemins relatifs sont préfixés par /api/django via l'intercepteur axios.
const customFieldsApi = {
  // Schéma d'un module pour les formulaires/listes : définitions actives +
  // clés standard masquées. module ∈ {'lead','client','produit'}.
  getSchema: (module) => api.get(`/customfields/schema/${module}/`),

  // CRUD des définitions (admin). Filtrable par module.
  listDefinitions: (module) =>
    api.get('/customfields/definitions/', { params: module ? { module } : {} }),
  createDefinition: (data) => api.post('/customfields/definitions/', data),
  updateDefinition: (id, data) => api.patch(`/customfields/definitions/${id}/`, data),
  deleteDefinition: (id) => api.delete(`/customfields/definitions/${id}/`),
  reorderDefinitions: (ids) => api.post('/customfields/definitions/reorder/', { ids }),

  // Champs standard masqués (admin).
  listHidden: (module) =>
    api.get('/customfields/hidden-fields/', { params: module ? { module } : {} }),
  hideField: (module, field_key) =>
    api.post('/customfields/hidden-fields/', { module, field_key }),
  unhideField: (id) => api.delete(`/customfields/hidden-fields/${id}/`),

  // Réinitialiser un module par défaut (admin) : ré-affiche le standard masqué
  // + archive les champs personnalisés (valeurs conservées).
  restoreDefaults: (module) => api.post(`/customfields/restore/${module}/`),
}

export default customFieldsApi
