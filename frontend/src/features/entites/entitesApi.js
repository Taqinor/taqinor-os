import api from '../../api/axios'

/* ============================================================================
   API du module Entités (Groupe NTADM) — préfixe `/entites/`. Fine couche
   axios ; la société est TOUJOURS posée côté serveur. Reflète exactement
   `apps/entites/urls.py`.
   ========================================================================== */

const entitesApi = {
  list: (params) => api.get('/entites/entites/', { params }),
  tree: () => api.get('/entites/entites/', { params: { tree: 1 } }),
  get: (id) => api.get(`/entites/entites/${id}/`),
  create: (data) => api.post('/entites/entites/', data),
  update: (id, data) => api.patch(`/entites/entites/${id}/`, data),
  desactiver: (id) => api.post(`/entites/entites/${id}/desactiver/`),
  historique: (id) => api.get(`/entites/entites/${id}/historique/`),
  noter: (id, body) => api.post(`/entites/entites/${id}/noter/`, { body }),
  // NTADM28 — export xlsx du référentiel (téléchargement binaire).
  export: () =>
    api.get('/entites/entites/export/', { responseType: 'blob' }),
  // NTADM43 — import CSV (dry-run par défaut ; `commit` écrit réellement).
  importer: (fichier, commit = false) => {
    const fd = new FormData()
    fd.append('fichier', fichier)
    if (commit) fd.append('commit', '1')
    return api.post('/entites/entites/importer/', fd)
  },
}

export default entitesApi
