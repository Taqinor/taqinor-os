import api from './axios'

// Reporting + recherche globale + notifications in-app (lecture seule).
const reportingApi = {
  getDashboard: () => api.get('/reporting/dashboard/'),
  // Recherche transverse : ?q=<terme> → résultats groupés par type.
  search: (q) => api.get('/reporting/search/', { params: { q } }),
  // Cloche de notifications (activités en retard, garanties, impayés).
  getNotifications: () => api.get('/reporting/notifications/'),
  // Tableau de bord valeur du pipeline (par étape, prévision, devis, pertes).
  getPipeline: () => api.get('/reporting/pipeline/'),
  // Hub Rapports (T13/T14/T15) — ventes, stock, service.
  salesReport: () => api.get('/reporting/reports/sales/'),
  stockReport: () => api.get('/reporting/reports/stock/'),
  serviceReport: () => api.get('/reporting/reports/service/'),
  reportXlsx: (kind) =>
    api.get(`/reporting/reports/${kind}/`, { params: { export: 'xlsx' }, responseType: 'blob' }),
}

export default reportingApi
