import api from './axios'

const crmApi = {
  getClients: (params) => api.get('/crm/clients/', { params }),
  getClient: (id) => api.get(`/crm/clients/${id}/`),
  createClient: (data) => api.post('/crm/clients/', data),
  updateClient: (id, data) => api.put(`/crm/clients/${id}/`, data),
  patchClient: (id, data) => api.patch(`/crm/clients/${id}/`, data),
  deleteClient: (id) => api.delete(`/crm/clients/${id}/`),
  exportClientsXlsx: (ids) =>
    api.post('/crm/clients/export-xlsx/', { ids }, { responseType: 'blob' }),

  // Leads / opportunities
  getLeads: (params) => api.get('/crm/leads/', { params }),
  getLead: (id) => api.get(`/crm/leads/${id}/`),
  createLead: (data) => api.post('/crm/leads/', data),
  updateLead: (id, data) => api.patch(`/crm/leads/${id}/`, data),
  // Garde serveur du « Devis auto » : 200 {ok:true} si le lead est prêt,
  // 400 {detail:'Manque : …'} sinon — la règle vit côté backend.
  checkDevisAuto: (id) => api.post(`/crm/leads/${id}/devis-auto/`),
  // Archivage réversible (Commerciale) + suppression définitive (admin).
  archiverLead: (id) => api.post(`/crm/leads/${id}/archiver/`),
  restaurerLead: (id) => api.post(`/crm/leads/${id}/restaurer/`),
  deleteLead: (id) => api.delete(`/crm/leads/${id}/`),
  getHistoriqueLead: (id) => api.get(`/crm/leads/${id}/historique/`),
  // Employés assignables (id, username, poste, avatar_url) — ouvert à la
  // Commerciale (le sélecteur de responsable doit marcher pour elle aussi).
  getAssignableUsers: () => api.get('/crm/assignable-users/'),
  // Actions EN MASSE sur une sélection de leads (liste + kanban). Le corps
  // porte {ids, action, …paramètres} ; la règle métier vit côté serveur.
  bulkLeads: (payload) => api.post('/crm/leads/bulk/', payload),
  // Export Excel (.xlsx) d'une sélection — réponse binaire (blob).
  exportLeadsXlsx: (ids) =>
    api.post('/crm/leads/export-xlsx/', { ids }, { responseType: 'blob' }),
  // Contrôle pré-création/édition des doublons par téléphone/email (société
  // côté serveur). Avertissement NON bloquant dans le formulaire de lead.
  checkDuplicates: (params) => api.get('/crm/leads/check-duplicates/', { params }),
  // Doublons + fusion de leads (sans perte).
  getLeadDuplicates: (id) => api.get(`/crm/leads/${id}/duplicates/`),
  // Atelier doublons : tous les clusters de la société (survivant suggéré).
  getDoublons: (params) => api.get('/crm/leads/doublons/', { params }),
  mergeLeads: (id, others) => api.post(`/crm/leads/${id}/merge/`, { others }),
  // Envoyer par WhatsApp : construit un lien wa.me prêt à envoyer pour un ou
  // plusieurs devis du lead (le commercial appuie lui-même sur Envoyer).
  whatsappDevis: (id, payload) =>
    api.post(`/crm/leads/${id}/whatsapp-devis/`, payload),
  // FG30 — Interaction typée (appel/email) dans le chatter du lead.
  logInteraction: (id, payload) =>
    api.post(`/crm/leads/${id}/log-interaction/`, payload),
  // FG36 — Modèles de messages WhatsApp/SMS.
  getMessageTemplates: (params) => api.get('/crm/message-templates/', { params }),
  getMessageTemplate: (id) => api.get(`/crm/message-templates/${id}/`),
  saveMessageTemplate: (id, data) =>
    id ? api.patch(`/crm/message-templates/${id}/`, data)
       : api.post('/crm/message-templates/', data),
  deleteMessageTemplate: (id) => api.delete(`/crm/message-templates/${id}/`),
  renderMessageTemplate: (id, payload) =>
    api.post(`/crm/message-templates/${id}/render/`, payload),

  // Listes gérées (Paramètres → CRM).
  getTags: () => api.get('/crm/tags/'),
  saveTag: (id, data) => id ? api.patch(`/crm/tags/${id}/`, data) : api.post('/crm/tags/', data),
  deleteTag: (id) => api.delete(`/crm/tags/${id}/`),
  getMotifsPerte: () => api.get('/crm/motifs-perte/'),
  saveMotifPerte: (id, data) => id ? api.patch(`/crm/motifs-perte/${id}/`, data) : api.post('/crm/motifs-perte/', data),
  deleteMotifPerte: (id) => api.delete(`/crm/motifs-perte/${id}/`),
  // Canaux / sources de lead gérés (Paramètres → CRM). 'site_web' est protégé.
  getCanaux: () => api.get('/crm/canaux/'),
  saveCanal: (id, data) => id ? api.patch(`/crm/canaux/${id}/`, data) : api.post('/crm/canaux/', data),
  deleteCanal: (id) => api.delete(`/crm/canaux/${id}/`),

  // N98 — parrainage / programme de recommandation.
  getParrainages: (params) => api.get('/crm/parrainages/', { params }),
  saveParrainage: (id, data) => id
    ? api.patch(`/crm/parrainages/${id}/`, data)
    : api.post('/crm/parrainages/', data),
  deleteParrainage: (id) => api.delete(`/crm/parrainages/${id}/`),
  parrainageStats: () => api.get('/crm/parrainages/stats/'),

  // QJ20 — Rendez-vous (visites commerciales/techniques).
  getAppointments: (leadId) => api.get('/crm/appointments/', { params: { lead: leadId } }),
  createAppointment: (data) => api.post('/crm/appointments/', data),
  updateAppointment: (id, data) => api.patch(`/crm/appointments/${id}/`, data),
  deleteAppointment: (id) => api.delete(`/crm/appointments/${id}/`),
}

export default crmApi
