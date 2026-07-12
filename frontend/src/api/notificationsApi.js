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

  // VX207 — décompte canonique unique d'attention (cloche/badge sidebar/
  // en-tête Ma file convergent tous sur ce seul endpoint) :
  // { actions_dues, en_retard, aujourdhui, approbations, mentions_non_lues }.
  attentionSummary: () => api.get('/notifications/attention-summary/'),

  // ── N92 — Web push (PWA), opt-in par appareil ──
  // Clé publique VAPID (chaîne vide tant que le push n'est pas configuré).
  getVapidPublicKey: () => api.get('/notifications/push/vapid-public-key/'),
  // `subscription` = objet PushSubscription.toJSON() ({ endpoint, keys }).
  pushSubscribe: (subscription) =>
    api.post('/notifications/push/subscribe/', subscription),
  pushUnsubscribe: (endpoint) =>
    api.post('/notifications/push/unsubscribe/', { endpoint }),
}

export default notificationsApi
