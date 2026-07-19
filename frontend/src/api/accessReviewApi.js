import api from './axios'

/* ============================================================================
   WIR135 — Client API « Gouvernance des accès » (apps/accessreview + rapport
   de certification roles).
   ----------------------------------------------------------------------------
   Miroir fin de `apps/accessreview/urls.py` (préfixe `/accessreview/`) et du
   rapport `revue-acces` de `apps/roles`. Tout est gouverné IsAdminRole côté
   serveur ; `company` forcée côté serveur. `api` préfixe déjà `/api/django`.
   ========================================================================== */

const accessReviewApi = {
  // NTSEC19 — campagnes de revue d'accès (lancement génère un item par compte).
  campaigns: {
    list: () => api.get('/accessreview/campaigns/'),
    get: (id) => api.get(`/accessreview/campaigns/${id}/`),
    create: (data) => api.post('/accessreview/campaigns/', data),
    remove: (id) => api.delete(`/accessreview/campaigns/${id}/`),
    // Attestation d'un item : { item, decision: 'maintenu'|'revoque', commentaire }.
    // `revoque` retire réellement le rôle via roles.services.
    attester: (id, data) => api.post(`/accessreview/campaigns/${id}/attester/`, data),
  },

  // NTSEC20 — règles de séparation des tâches (SoD) + rapport de violations.
  sodRules: {
    list: () => api.get('/accessreview/sod-rules/'),
    create: (data) => api.post('/accessreview/sod-rules/', data),
    remove: (id) => api.delete(`/accessreview/sod-rules/${id}/`),
    violations: () => api.get('/accessreview/sod-rules/violations/'),
    seedStandard: () => api.post('/accessreview/sod-rules/seed_standard/'),
  },

  // XPLT12 — rapport de certification des accès (roles), JSON + export CSV.
  revueAcces: () => api.get('/roles/revue-acces/'),
  revueAccesCsv: () =>
    api.get('/roles/revue-acces/', { params: { format: 'csv' }, responseType: 'blob' }),
}

export default accessReviewApi
