import api from './axios'

// Après-vente : parc d'équipements + tickets SAV.
const savApi = {
  // ── Équipements ──
  getEquipements: (params) => api.get('/sav/equipements/', { params }),
  getEquipement: (id) => api.get(`/sav/equipements/${id}/`),
  createEquipement: (data) => api.post('/sav/equipements/', data),
  updateEquipement: (id, data) => api.patch(`/sav/equipements/${id}/`, data),
  deleteEquipement: (id) => api.delete(`/sav/equipements/${id}/`),

  // ── Tickets SAV ──
  getTickets: (params) => api.get('/sav/tickets/', { params }),
  getTicket: (id) => api.get(`/sav/tickets/${id}/`),
  createTicket: (data) => api.post('/sav/tickets/', data),
  updateTicket: (id, data) => api.patch(`/sav/tickets/${id}/`, data),
  deleteTicket: (id) => api.delete(`/sav/tickets/${id}/`),
  getTicketHistorique: (id) => api.get(`/sav/tickets/${id}/historique/`),
  noterTicket: (id, body) => api.post(`/sav/tickets/${id}/noter/`, { body }),
  annulerTicket: (id, motif) => api.post(`/sav/tickets/${id}/annuler/`, { motif }),
  reactiverTicket: (id) => api.post(`/sav/tickets/${id}/reactiver/`),
}

export default savApi
