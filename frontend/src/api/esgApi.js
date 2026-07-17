import api from './axios'

/* ============================================================================
   ESG / RSE (apps/esg) — client API (Groupe NTESG).
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /esg/... ».
   Basenames DRF : periodes-esg (CRUD + figer/indicateurs/rapport-pdf/export),
   catalogue-esg (lecture seule + couverture), objectifs-esg (CRUD +
   trajectoire).
   ========================================================================== */

const esgApi = {
  // ── Périodes de reporting ESG (NTESG1) ──
  periodes: {
    list: (params) => api.get('/esg/periodes-esg/', { params }),
    get: (id) => api.get(`/esg/periodes-esg/${id}/`),
    create: (data) => api.post('/esg/periodes-esg/', data),
    update: (id, data) => api.patch(`/esg/periodes-esg/${id}/`, data),
    remove: (id) => api.delete(`/esg/periodes-esg/${id}/`),
    // Fige la période (gèle le snapshot) — irréversible côté données.
    figer: (id) => api.post(`/esg/periodes-esg/${id}/figer/`),
    // Données ESG effectives (snapshot gelé si figée, aperçu live sinon).
    indicateurs: (id) => api.get(`/esg/periodes-esg/${id}/indicateurs/`),
    // Rapport PDF GRI-lite (NTESG4) — téléchargement binaire.
    rapportPdf: (id) =>
      api.get(`/esg/periodes-esg/${id}/rapport-pdf/`, { responseType: 'blob' }),
    // Export xlsx multi-feuilles (NTESG5) — téléchargement binaire.
    exportXlsx: (id) =>
      api.get(`/esg/periodes-esg/${id}/export/`, {
        params: { format: 'xlsx' }, responseType: 'blob',
      }),
  },

  // ── Catalogue GRI-lite (NTESG3, lecture seule) ──
  catalogue: {
    list: (params) => api.get('/esg/catalogue-esg/', { params }),
    couverture: () => api.get('/esg/catalogue-esg/couverture/'),
  },

  // ── Objectifs de trajectoire ESG (NTESG7) ──
  objectifs: {
    list: (params) => api.get('/esg/objectifs-esg/', { params }),
    get: (id) => api.get(`/esg/objectifs-esg/${id}/`),
    create: (data) => api.post('/esg/objectifs-esg/', data),
    update: (id, data) => api.patch(`/esg/objectifs-esg/${id}/`, data),
    remove: (id) => api.delete(`/esg/objectifs-esg/${id}/`),
    trajectoire: (id) => api.get(`/esg/objectifs-esg/${id}/trajectoire/`),
  },
}

export default esgApi
