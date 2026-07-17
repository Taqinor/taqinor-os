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

  // FG106 — crée un lead (mode 'lead') ou un lead + devis brouillon
  // (mode 'devis') depuis les champs extraits par l'OCR. L'écriture passe par
  // les services CRM/ventes côté serveur. → { lead_id, devis_id?, ... }
  ocrToCrm: (payload) => api.post('/publicapi/ocr-to-crm/', payload),

  // ── Clés API ──
  getKeys: () => api.get('/publicapi/keys/'),
  createKey: (data) => api.post('/publicapi/keys/', data), // → { ...key, key }
  revokeKey: (id) => api.post(`/publicapi/keys/${id}/revoke/`),
  deleteKey: (id) => api.delete(`/publicapi/keys/${id}/`),
  // NTAPI23 — rotation sans coupure : nouvelle clé + grace period sur l'ancienne.
  rotateKey: (id, grace_jours) =>
    api.post(`/publicapi/keys/${id}/rotate/`, grace_jours ? { grace_jours } : {}),

  // ── Webhooks ──
  getWebhooks: () => api.get('/publicapi/webhooks/'),
  createWebhook: (data) => api.post('/publicapi/webhooks/', data), // → { ...hook, secret }
  updateWebhook: (id, data) => api.patch(`/publicapi/webhooks/${id}/`, data),
  rotateWebhookSecret: (id) => api.post(`/publicapi/webhooks/${id}/rotate_secret/`),
  deleteWebhook: (id) => api.delete(`/publicapi/webhooks/${id}/`),
  getWebhookDeliveries: (id) => api.get(`/publicapi/webhooks/${id}/deliveries/`),
  // NTAPI25 — rejoue une livraison existante / envoie un ping de test.
  replayDelivery: (webhookId, deliveryId) =>
    api.post(`/publicapi/webhooks/${webhookId}/deliveries/${deliveryId}/replay/`),
  testPingWebhook: (webhookId) => api.post(`/publicapi/webhooks/${webhookId}/test/`),

  // NTAPI7/22 — plan d'API nommé + usage consommé (jour/mois).
  getPlan: () => api.get('/publicapi/plan/'),

  // NTAPI24 — fil « changelog API » : endpoint public sous /api/public/
  // (aucune clé requise), donc chemin ABSOLU pour ne pas passer par le
  // préfixe /api/django/publicapi/ ajouté automatiquement par l'intercepteur.
  getChangelog: (params) => api.get('/api/public/changelog/', { params }),

  // NTAPI20/21 — document OpenAPI 3.1 public + essai de démonstration
  // (session admin, scopé au bac à sable NTAPI27 côté serveur).
  getOpenApiSchema: () => api.get('/api/public/openapi.json'),
  sandboxTry: (resource) => api.post('/publicapi/sandbox/try/', { resource }),
}

export default publicapiApi
