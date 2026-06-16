import api from './axios'

const crmApi = {
  getClients: (params) => api.get('/crm/clients/', { params }),
  getClient: (id) => api.get(`/crm/clients/${id}/`),
  createClient: (data) => api.post('/crm/clients/', data),
  updateClient: (id, data) => api.put(`/crm/clients/${id}/`, data),
  patchClient: (id, data) => api.patch(`/crm/clients/${id}/`, data),
  deleteClient: (id) => api.delete(`/crm/clients/${id}/`),

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
  // Doublons + fusion de leads (sans perte).
  getLeadDuplicates: (id) => api.get(`/crm/leads/${id}/duplicates/`),
  // Atelier doublons : tous les clusters de la société (survivant suggéré).
  getDoublons: (params) => api.get('/crm/leads/doublons/', { params }),
  mergeLeads: (id, others) => api.post(`/crm/leads/${id}/merge/`, { others }),
  // Envoyer par WhatsApp : construit un lien wa.me prêt à envoyer pour un ou
  // plusieurs devis du lead (le commercial appuie lui-même sur Envoyer).
  whatsappDevis: (id, payload) =>
    api.post(`/crm/leads/${id}/whatsapp-devis/`, payload),

  // Actions « en masse » sur une sélection de leads (T3). Le corps porte
  // {action, ids, params}. Toutes les actions journalisent « en masse » côté
  // serveur ; l'export renvoie un fichier .xlsx (responseType blob).
  bulkLeads: (action, ids, params = {}) =>
    api.post('/crm/leads/bulk/', { action, ids, params }),
  exportLeads: (ids, params = {}) =>
    api.post('/crm/leads/bulk/', { action: 'export', ids, params },
      { responseType: 'blob' }),

  // Recherche globale (leads, clients, devis, factures, chantiers,
  // équipements, tickets SAV) — tout scopé société.
  globalSearch: (q) => api.get('/crm/search/', { params: { q } }),
  // Notifications in-app calculées à la volée (activités en retard, garanties
  // bientôt expirées, factures impayées).
  getNotifications: () => api.get('/crm/notifications/'),

  // Listes gérées (Paramètres → CRM).
  getTags: () => api.get('/crm/tags/'),
  saveTag: (id, data) => id ? api.patch(`/crm/tags/${id}/`, data) : api.post('/crm/tags/', data),
  deleteTag: (id) => api.delete(`/crm/tags/${id}/`),
  getMotifsPerte: () => api.get('/crm/motifs-perte/'),
  saveMotifPerte: (id, data) => id ? api.patch(`/crm/motifs-perte/${id}/`, data) : api.post('/crm/motifs-perte/', data),
  deleteMotifPerte: (id) => api.delete(`/crm/motifs-perte/${id}/`),
  // Canaux / sources de lead gérés. La clé `site_web` est protégée (ni
  // renommable ni supprimable) ; un canal utilisé par un lead ne peut être
  // supprimé (409 avec message FR). À la création on n'envoie que `label`.
  getCanaux: () => api.get('/crm/canaux/'),
  saveCanal: (id, data) => id ? api.patch(`/crm/canaux/${id}/`, data) : api.post('/crm/canaux/', data),
  deleteCanal: (id) => api.delete(`/crm/canaux/${id}/`),
}

export default crmApi
