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
  // N45 — rapport d'intervention (PDF régénéré à la demande, sans prix d'achat).
  rapportPdf: (id) => api.get(`/sav/tickets/${id}/rapport-pdf/`, { responseType: 'blob' }),

  // T16 — contrats de maintenance.
  getContrats: (params) => api.get('/sav/contrats-maintenance/', { params }),
  saveContrat: (id, data) => id
    ? api.patch(`/sav/contrats-maintenance/${id}/`, data)
    : api.post('/sav/contrats-maintenance/', data),
  deleteContrat: (id) => api.delete(`/sav/contrats-maintenance/${id}/`),
  genererVisitesDues: () => api.post('/sav/contrats-maintenance/generer-dus/'),
}

export default savApi
