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
}

export default monitoringApi
