import api from './axios'

// Reporting + recherche globale + notifications in-app (lecture seule).
const reportingApi = {
  getDashboard: () => api.get('/reporting/dashboard/'),
  // Recherche transverse : ?q=<terme> → résultats groupés par type.
  search: (q) => api.get('/reporting/search/', { params: { q } }),
  // Cloche de notifications (activités en retard, garanties, impayés).
  getNotifications: () => api.get('/reporting/notifications/'),
}

export default reportingApi
