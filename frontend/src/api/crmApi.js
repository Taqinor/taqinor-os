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
}

export default crmApi
