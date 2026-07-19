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

  // ── WIR62 / XKB2 — Demandes d'approbation ad-hoc ──
  // Types (admin) : définition d'un type de demande (nom, champs requis,
  // palier approbateur). CRUD sur `automation/approval-request-types/`.
  getApprovalRequestTypes: (params) =>
    api.get('/automation/approval-request-types/', { params }),
  saveApprovalRequestType: (id, data) => id
    ? api.patch(`/automation/approval-request-types/${id}/`, data)
    : api.post('/automation/approval-request-types/', data),
  deleteApprovalRequestType: (id) =>
    api.delete(`/automation/approval-request-types/${id}/`),
  // Demandes (employé soumet, approbateur décide). ?status=pending / ?mine=1.
  getApprovalRequests: (params) =>
    api.get('/automation/approval-requests/', { params }),
  createApprovalRequest: (data) =>
    api.post('/automation/approval-requests/', data),
  approveApprovalRequest: (id, note) =>
    api.post(`/automation/approval-requests/${id}/approve/`, { note }),
  rejectApprovalRequest: (id, note) =>
    api.post(`/automation/approval-requests/${id}/reject/`, { note }),
  demandeInfoApprovalRequest: (id, motif) =>
    api.post(`/automation/approval-requests/${id}/demande-info/`, { motif }),
  resoumettreApprovalRequest: (id, payload) =>
    api.post(`/automation/approval-requests/${id}/resoumettre/`, { payload }),
}

export default automationApi
