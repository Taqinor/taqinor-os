import api from './axios'

/* ============================================================================
   Innovation — boîte à idées interne (apps/innovation) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /innovation/... ».
   Un seul point d'import pour tous les écrans du module (NTIDE1-13).
   ========================================================================== */

const innovationApi = {
  // ── Idées (CRUD + filtres, NTIDE1/NTIDE4) ──
  // params: statut / contexte / owner / created_since / ordering.
  list: (params) => api.get('/innovation/idees/', { params }),
  get: (id) => api.get(`/innovation/idees/${id}/`),
  create: (data) => api.post('/innovation/idees/', data),
  update: (id, data) => api.patch(`/innovation/idees/${id}/`, data),

  // ── Votes (NTIDE2) ──
  vote: (idee) => api.post('/innovation/votes/', { idee }),
  retirerVote: (voteId) => api.delete(`/innovation/votes/${voteId}/`),
  votesRecents: () => api.get('/innovation/votes/recents/'),
  mesVotes: () => api.get('/innovation/votes/mes-idees/'),
}

export default innovationApi
