import api from './axios'

// T11 — définitions de champs personnalisés par module (lead, client, produit).
const customFieldsApi = {
  getDefs: (module) =>
    api.get('/custom-fields/definitions/', { params: module ? { module } : {} }),
  saveDef: (id, data) => id
    ? api.patch(`/custom-fields/definitions/${id}/`, data)
    : api.post('/custom-fields/definitions/', data),
  deleteDef: (id) => api.delete(`/custom-fields/definitions/${id}/`),
  // L813 — réordonne les définitions d'un module (liste d'ids dans l'ordre).
  reorder: (ids) =>
    api.post('/custom-fields/definitions/reorder/', { ids }),
}

export default customFieldsApi
