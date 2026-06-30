import api from './axios'

// API & Webhooks (N89) — gestion des clés d'API publiques et des webhooks
// sortants depuis l'écran Paramètres. La clé en clair et le secret webhook ne
// reviennent qu'une seule fois (à la création/rotation) — l'écran les affiche
// alors immédiatement, jamais après.
const publicapiApi = {
  // Catalogue des scopes & évènements (pour cocher les droits/abonnements).
  getCatalogue: () => api.get('/publicapi/catalogue/'),

  // FG105 — référence statique FR de l'API publique (endpoints, auth, HMAC).
  getDocs: () => api.get('/publicapi/docs/'),

  // ── Clés API ──
  getKeys: () => api.get('/publicapi/keys/'),
  createKey: (data) => api.post('/publicapi/keys/', data), // → { ...key, key }
  revokeKey: (id) => api.post(`/publicapi/keys/${id}/revoke/`),
  deleteKey: (id) => api.delete(`/publicapi/keys/${id}/`),

  // ── Webhooks ──
  getWebhooks: () => api.get('/publicapi/webhooks/'),
  createWebhook: (data) => api.post('/publicapi/webhooks/', data), // → { ...hook, secret }
  updateWebhook: (id, data) => api.patch(`/publicapi/webhooks/${id}/`, data),
  rotateWebhookSecret: (id) => api.post(`/publicapi/webhooks/${id}/rotate_secret/`),
  deleteWebhook: (id) => api.delete(`/publicapi/webhooks/${id}/`),
  getWebhookDeliveries: (id) => api.get(`/publicapi/webhooks/${id}/deliveries/`),
}

export default publicapiApi
