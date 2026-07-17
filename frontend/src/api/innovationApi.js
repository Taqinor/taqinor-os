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

  // ── Autocomplétion contexte (NTIDE10) ──
  contextes: () => api.get('/innovation/idees/contextes/'),

  // ── Tableau de bord admin (NTIDE6) ──
  tableauBord: () => api.get('/innovation/idees/tableau-bord/'),

  // ── Machine à états (POST) — palier Directeur/Responsable (NTIDE5) ──
  examiner: (id) => api.post(`/innovation/idees/${id}/examiner/`),
  retenir: (id) => api.post(`/innovation/idees/${id}/retenir/`),
  realiser: (id) => api.post(`/innovation/idees/${id}/realiser/`),
  fermer: (id, note) => api.post(`/innovation/idees/${id}/fermer/`, { note }),

  // ── Chatter (historique, NTIDE5) ──
  historique: (id) => api.get(`/innovation/idees/${id}/historique/`),

  // ── Lier à un devis/ticket/chantier (NTIDE14, opaque string-FK) ──
  lier: (id, linkedType, linkedId) =>
    api.post(`/innovation/idees/${id}/lier/`,
      { linked_type: linkedType, linked_id: linkedId }),

  // ── Export .xlsx (NTIDE12, filtres statut/contexte/date appliqués) ──
  exportXlsx: (params) =>
    api.get('/innovation/idees/export-xlsx/', { params, responseType: 'blob' }),

  // ── Actions en masse (NTIDE13) : set_statut / add_tag / remove_tag / export ──
  bulk: (body) => {
    const isExport = body?.action === 'export'
    return api.post('/innovation/idees/bulk/', body,
      isExport ? { responseType: 'blob' } : undefined)
  },

  // ── Votes (NTIDE2) ──
  vote: (idee) => api.post('/innovation/votes/', { idee }),
  retirerVote: (voteId) => api.delete(`/innovation/votes/${voteId}/`),
  votesRecents: () => api.get('/innovation/votes/recents/'),
  mesVotes: () => api.get('/innovation/votes/mes-idees/'),

  // ── Paramètres → Avancé « Campagnes innovation » (NTIDE7, singleton) ──
  parametres: {
    get: () => api.get('/innovation/parametres/'),
    update: (data) => api.patch('/innovation/parametres/', data),
  },
}

export default innovationApi
