import api from './axios'

// API des rapports analytiques (lecture seule). Tout est scopé par société
// côté serveur. Les exports .xlsx sont récupérés en blob.
const reportingApi = {
  getDashboard: () => api.get('/reporting/dashboard/'),

  // T7b — tableau de bord valeur du pipeline
  getPipelineValue: (params = {}) =>
    api.get('/reporting/pipeline-value/', { params }),

  // T13 — rapport ventes / pipeline
  getSales: (params = {}) => api.get('/reporting/sales/', { params }),
  getSalesXlsx: (params = {}) =>
    api.get('/reporting/sales/', {
      params: { ...params, export: 'xlsx' }, responseType: 'blob',
    }),

  // T14 — rapport stock (interne)
  getStock: (params = {}) => api.get('/reporting/stock/', { params }),
  getStockXlsx: (params = {}) =>
    api.get('/reporting/stock/', {
      params: { ...params, export: 'xlsx' }, responseType: 'blob',
    }),

  // T15 — rapport service (chantiers + SAV)
  getService: (params = {}) => api.get('/reporting/service/', { params }),
  getServiceXlsx: (params = {}) =>
    api.get('/reporting/service/', {
      params: { ...params, export: 'xlsx' }, responseType: 'blob',
    }),

  // T12 — export comptable journal des ventes + TVA (toujours .xlsx)
  getJournalVentesXlsx: (params = {}) =>
    api.get('/reporting/journal-ventes/', { params, responseType: 'blob' }),

  // N32 — archive documentaire par client / par chantier
  getArchiveClient: (id) =>
    api.get(`/reporting/archive/client/${id}/`),
  getArchiveChantier: (id) =>
    api.get(`/reporting/archive/chantier/${id}/`),

  // N49 — CA récurrent (contrats d'entretien)
  getRecurringRevenue: (params = {}) =>
    api.get('/reporting/recurring-revenue/', { params }),

  // N70 — activité par utilisateur (agrégation)
  getUserActivity: (params = {}) =>
    api.get('/reporting/user-activity/', { params }),
}

export default reportingApi
