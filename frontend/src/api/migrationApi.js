import api from './axios'

/* ============================================================================
   Migration ERP (apps/migration) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /migration/... ».
   Réservé au palier Administrateur/Directeur CÔTÉ SERVEUR (la garde d'écran
   n'est qu'un confort, jamais la sécurité).

   Les envois de fichier passent un FormData nu : axios pose lui-même la
   frontière multipart — fixer Content-Type à la main la casserait.
   ========================================================================== */

const migrationApi = {
  // ── Projets de migration ──
  listProjets: (params) => api.get('/migration/projets-migration/', { params }),
  getProjet: (id) => api.get(`/migration/projets-migration/${id}/`),
  createProjet: (data) => api.post('/migration/projets-migration/', data),
  updateProjet: (id, data) =>
    api.patch(`/migration/projets-migration/${id}/`, data),
  deleteProjet: (id) => api.delete(`/migration/projets-migration/${id}/`),
  terminerProjet: (id) =>
    api.post(`/migration/projets-migration/${id}/terminer/`),
  // Le PV est un PDF : on ouvre l'URL, on ne la « fetch » pas.
  rapportUrl: (id) => `/api/django/migration/projets-migration/${id}/rapport/`,

  // ── Lots de migration (un par entité) ──
  listLots: (projetId) =>
    api.get('/migration/lots-migration/', { params: { projet: projetId } }),
  createLot: (data) => api.post('/migration/lots-migration/', data),
  deleteLot: (id) => api.delete(`/migration/lots-migration/${id}/`),
  analyserLot: (id, fichier) => {
    const fd = new FormData()
    fd.append('fichier', fichier)
    return api.post(`/migration/lots-migration/${id}/analyser/`, fd)
  },
  chargerLot: (id, fichier) => {
    const fd = new FormData()
    fd.append('fichier', fichier)
    return api.post(`/migration/lots-migration/${id}/charger/`, fd)
  },
  reconcilierLot: (id) =>
    api.post(`/migration/lots-migration/${id}/reconcilier/`),
  derogerLot: (id, motif) =>
    api.post(`/migration/lots-migration/${id}/deroger/`, { motif }),
  terminerLot: (id) => api.post(`/migration/lots-migration/${id}/terminer/`),
}

export default migrationApi
