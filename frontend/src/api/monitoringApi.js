import api from './axios'

// Monitoring (N50/N51/N52) — supervision de la production des systèmes installés.
const monitoringApi = {
  // ── Configs de supervision par système (N50) ──
  getConfigs: (params) => api.get('/monitoring/configs/', { params }),
  getConfigForInstallation: (installationId) =>
    api.get('/monitoring/configs/', { params: { installation: installationId } }),
  saveConfig: (id, data) => id
    ? api.patch(`/monitoring/configs/${id}/`, data)
    : api.post('/monitoring/configs/', data),
  getProviders: () => api.get('/monitoring/configs/providers/'),
  syncNow: (id) => api.post(`/monitoring/configs/${id}/sync-now/`, {}),

  // ── Relevés de production (N51) ──
  getReadings: (params) => api.get('/monitoring/readings/', { params }),
  addReading: (data) => api.post('/monitoring/readings/', data),
  deleteReading: (id) => api.delete(`/monitoring/readings/${id}/`),

  // ── Réglage société de sous-performance (N52) ──
  getSettings: () => api.get('/monitoring/settings/'),
  saveSettings: (data) => api.post('/monitoring/settings/', data),

  // ── O&M — vue parc / flotte (FG281, WR6) ──
  // Synthèse multi-systèmes : production totale, kWc, PR moyen, alertes.
  getFleet: (params) => api.get('/monitoring/configs/fleet/', { params }),
  // ── O&M — analytique par système (FG279, WR6) ──
  // PR / disponibilité / soiling / dégradation. ?window_days=365 (défaut).
  getOmMetrics: (configId, params) =>
    api.get(`/monitoring/configs/${configId}/om-metrics/`, { params }),
  // FG84 — historique mensuel attendu vs réel (?months=, ?export=csv).
  getHistory: (configId, params) =>
    api.get(`/monitoring/configs/${configId}/history/`, { params }),

  // ── Garanties de production (FG282/FG284, WR6) ──
  getWarranties: (params) => api.get('/monitoring/warranties/', { params }),
  saveWarranty: (id, data) => id
    ? api.patch(`/monitoring/warranties/${id}/`, data)
    : api.post('/monitoring/warranties/', data),
  deleteWarranty: (id) => api.delete(`/monitoring/warranties/${id}/`),
  // Écart production réelle vs garanti dégradé d'une année (?year=YYYY).
  getWarrantyStatus: (id, params) =>
    api.get(`/monitoring/warranties/${id}/status/`, { params }),
  // Courbe garantie vs mesuré par année (?years=, ?drift_threshold_pct=).
  getWarrantyCurve: (id, params) =>
    api.get(`/monitoring/warranties/${id}/curve/`, { params }),

  // ── Portail environnemental client (FG288, WR7) ──
  // Synthèse cumulée des systèmes d'un client (?client=ID requis).
  getClientPortal: (clientId) =>
    api.get('/monitoring/configs/client-portal/', { params: { client: clientId } }),

  // ── Suivi CO₂ (FG286, WR7) ──
  // CO₂ évité par système (?since=&until=).
  getCo2: (configId, params) =>
    api.get(`/monitoring/configs/${configId}/co2/`, { params }),
  // CO₂ évité par système ET cumulé sur le parc.
  getCo2Fleet: (params) =>
    api.get('/monitoring/configs/co2-fleet/', { params }),

  // ── Nettoyages + salissure (FG283, WR7) ──
  getCleanings: (params) => api.get('/monitoring/cleanings/', { params }),
  addCleaning: (data) => api.post('/monitoring/cleanings/', data),
  deleteCleaning: (id) => api.delete(`/monitoring/cleanings/${id}/`),
  // Évaluation de salissure d'un système (?window_days=).
  getSoiling: (configId, params) =>
    api.get(`/monitoring/configs/${configId}/soiling/`, { params }),

  // ── Rapport O&M périodique (FG289, WR7) ──
  // Données JSON du rapport (?period=monthly|quarterly).
  getOmReport: (configId, params) =>
    api.get(`/monitoring/configs/${configId}/om-report/`, { params }),
  // PDF du rapport (?period=&format=pdf) — blob téléchargeable.
  getOmReportPdf: (configId, params) =>
    api.get(`/monitoring/configs/${configId}/om-report/`, {
      params: { ...(params || {}), format: 'pdf' }, responseType: 'blob',
    }),
  // Envoi du rapport O&M par e-mail (PDF joint). body { period, recipient? }.
  emailOmReport: (configId, data) =>
    api.post(`/monitoring/configs/${configId}/email-om-report/`, data),
}

export default monitoringApi
