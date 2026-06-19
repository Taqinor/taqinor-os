import api from './axios'

// N75 — moteur de notifications unifié : in-app persisté + préférences de canaux
// par événement (in-app / WhatsApp / email). Toutes les routes sont propres à
// l'utilisateur courant (portée côté serveur).
const notificationsApi = {
  // ── Mes notifications in-app ──
  list: (params) => api.get('/notifications/notifications/', { params }),
  unreadCount: () => api.get('/notifications/notifications/unread-count/'),
  markRead: (id) => api.post(`/notifications/notifications/${id}/read/`),
  markUnread: (id) => api.post(`/notifications/notifications/${id}/unread/`),
  markAllRead: () => api.post('/notifications/notifications/read-all/'),

  // ── Préférences de canaux par événement ──
  getPreferences: () => api.get('/notifications/preferences/'),
  // `eventType` = clé d'événement (ex. 'lead_assigned').
  savePreference: (eventType, data) =>
    api.patch(`/notifications/preferences/${eventType}/`, data),
}

export default notificationsApi
