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
  mergeLeads: (id, others) => api.post(`/crm/leads/${id}/merge/`, { others }),
}

export default crmApi
