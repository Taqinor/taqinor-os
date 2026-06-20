import api from './axios'

// N72 / N73 — moteur d'automatisations sans code (règles « si ceci → alors
// cela » sur les événements propres de l'app) + étape d'approbation.
const automationApi = {
  // ── Règles (N72) ──
  getRules: (params) => api.get('/automation/rules/', { params }),
  saveRule: (id, data) => id
    ? api.patch(`/automation/rules/${id}/`, data)
    : api.post('/automation/rules/', data),
  deleteRule: (id) => api.delete(`/automation/rules/${id}/`),
  toggleRule: (id) => api.post(`/automation/rules/${id}/toggle/`),

  // ── Journal d'exécutions (N72) ──
  getRuns: (params) => api.get('/automation/runs/', { params }),

  // ── Approbations (N73) ──
  getApprovals: (params) => api.get('/automation/approvals/', { params }),
  approve: (id) => api.post(`/automation/approvals/${id}/approve/`),
  reject: (id) => api.post(`/automation/approvals/${id}/reject/`),
}

export default automationApi
