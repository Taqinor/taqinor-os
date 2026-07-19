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
    // Comparateur N vs N-1 (NTESG11) — écarts entre deux périodes scopées.
    comparer: (periodeId, referenceId) =>
      api.get('/esg/periodes-esg/comparer/', {
        params: { periode: periodeId, reference: referenceId },
      }),
    // Export DPEF-friendly (NTESG14) — gabarit Markdown, téléchargement binaire.
    dpef: (id) =>
      api.get(`/esg/periodes-esg/${id}/dpef/`, { responseType: 'blob' }),
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
    // Badge de maturité ESG interne (NTESG15) — auto-évaluation, jamais une
    // certification externe (voir `disclaimer` dans la réponse).
    badgeMaturite: () => api.get('/esg/catalogue-esg/badge-maturite/'),
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

  // ── Parties prenantes ESG / matérialité (NTESG12) ──
  partiesPrenantes: {
    list: (params) => api.get('/esg/parties-prenantes-esg/', { params }),
    create: (data) => api.post('/esg/parties-prenantes-esg/', data),
    update: (id, data) => api.patch(`/esg/parties-prenantes-esg/${id}/`, data),
    remove: (id) => api.delete(`/esg/parties-prenantes-esg/${id}/`),
  },
}

export default esgApi
