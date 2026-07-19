import api from './axios'

// N72 / N73 — moteur d'automatisations sans code (règles « si ceci → alors
// cela » sur les événements propres de l'app) + étape d'approbation.
// XPLT18 — endpoint DJANGO `apps.agent` (chemin ABSOLU /api/django/…) : la
// proposition de règle par l'IA crée toujours un brouillon DÉSACTIVÉ, à
// confirmer ensuite via le bouton « Activer » déjà existant de la liste.
const automationApi = {
  // XPLT18 — propose→confirme : crée un brouillon de règle désactivé à partir
  // d'un déclencheur/action du catalogue fermé (jamais de code libre).
  proposeDraft: (data) => api.post('/agent/actions/automation-draft/', data),

  // ── Règles (N72) ──
  getRules: (params) => api.get('/automation/rules/', { params }),
  saveRule: (id, data) => id
    ? api.patch(`/automation/rules/${id}/`, data)
    : api.post('/automation/rules/', data),
  deleteRule: (id) => api.delete(`/automation/rules/${id}/`),
  toggleRule: (id) => api.post(`/automation/rules/${id}/toggle/`),

  // ── Journal d'exécutions (N72) ──
  getRuns: (params) => api.get('/automation/runs/', { params }),

  // ── Approbations (N73) ──
  getApprovals: (params) => api.get('/automation/approvals/', { params }),
  approve: (id) => api.post(`/automation/approvals/${id}/approve/`),
  reject: (id) => api.post(`/automation/approvals/${id}/reject/`),

  // ── FG3 : bibliothèque de modèles prédéfinis ──
  getTemplates: () => api.get('/automation/templates/'),

  // ── VX103 — Délégations d'absence (XKB3) : suppléant + plage de dates,
  // CRUD complet sur `automation/approval-delegations/`. ──
  getDelegations: (params) => api.get('/automation/approval-delegations/', { params }),
  createDelegation: (data) => api.post('/automation/approval-delegations/', data),
  deleteDelegation: (id) => api.delete(`/automation/approval-delegations/${id}/`),

  // ── WIR61 / XPLT4 — Webhooks entrants tokenisés (par règle webhook_inbound).
  // Le `token` et l'`url_path` sont générés côté serveur ; la rotation invalide
  // immédiatement l'ancien token. `hmac_secret` optionnel (signature entrante).
  getWebhooks: (params) => api.get('/automation/incoming-webhooks/', { params }),
  createWebhook: (data) => api.post('/automation/incoming-webhooks/', data),
  rotateWebhook: (id) => api.post(`/automation/incoming-webhooks/${id}/rotate/`),
  updateWebhook: (id, data) => api.patch(`/automation/incoming-webhooks/${id}/`, data),
  deleteWebhook: (id) => api.delete(`/automation/incoming-webhooks/${id}/`),
}

export default automationApi
