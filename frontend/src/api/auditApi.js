import api from './axios'

// Journal d'activité (Feature G). Réservé aux porteurs de « journal_activite_voir ».
const auditApi = {
  // Statistiques bucketées (Jour=24h, Semaine/Mois=par jour) en Africa/Casablanca.
  getStats: (params) => api.get('/audit/stats/', { params }),
  // Liste paginée filtrable (plus récent d'abord).
  getEntries: (params) => api.get('/audit/entries/', { params }),
  // Données de la barre de filtres (utilisateurs, actions, modules).
  getMeta: () => api.get('/audit/meta/'),
}

export default auditApi
