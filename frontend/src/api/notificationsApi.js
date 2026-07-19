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

  // ── WIR154 — administration Notifications (admin) ──
  // FG4 — règles de routage par événement/rôle.
  getRoutingRules: (params) => api.get('/notifications/routing-rules/', { params }),
  saveRoutingRule: (id, data) => id
    ? api.patch(`/notifications/routing-rules/${id}/`, data)
    : api.post('/notifications/routing-rules/', data),
  deleteRoutingRule: (id) => api.delete(`/notifications/routing-rules/${id}/`),
  // FG5 — calendrier ouvré (singleton société) + jours fériés + diagnostic.
  getWorkingHours: () => api.get('/notifications/working-hours/'),
  saveWorkingHours: (data) =>
    api.patch('/notifications/working-hours/current/', data),
  getHolidays: (params) => api.get('/notifications/holidays/', { params }),
  createHoliday: (data) => api.post('/notifications/holidays/', data),
  deleteHoliday: (id) => api.delete(`/notifications/holidays/${id}/`),
  calendarCheck: (params) => api.get('/notifications/calendar/check/', { params }),
  // XKB5/XKB6 — annonces internes (créer/publier/cibler + accusé de lecture).
  getAnnonces: (params) => api.get('/notifications/annonces/', { params }),
  createAnnonce: (data) => api.post('/notifications/annonces/', data),
  deleteAnnonce: (id) => api.delete(`/notifications/annonces/${id}/`),
  publierAnnonce: (id) => api.post(`/notifications/annonces/${id}/publier/`),
  accuserLectureAnnonce: (id) =>
    api.post(`/notifications/annonces/${id}/accuser-lecture/`),
  // XMKT25 — registre des gabarits WhatsApp (créer/soumettre/décider).
  getWhatsAppTemplates: (params) =>
    api.get('/notifications/whatsapp-templates/', { params }),
  createWhatsAppTemplate: (data) =>
    api.post('/notifications/whatsapp-templates/', data),
  deleteWhatsAppTemplate: (id) =>
    api.delete(`/notifications/whatsapp-templates/${id}/`),
  submitWhatsAppTemplate: (id) =>
    api.post(`/notifications/whatsapp-templates/${id}/submit/`),
  decisionWhatsAppTemplate: (id, statut_approbation, motif_rejet) =>
    api.post(`/notifications/whatsapp-templates/${id}/decision/`, {
      statut_approbation, motif_rejet,
    }),
}

export default notificationsApi
