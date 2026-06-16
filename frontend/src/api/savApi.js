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

  // ── Contrats de maintenance (visites préventives récurrentes) ──
  getContrats: (params) => api.get('/sav/contrats/', { params }),
  getContrat: (id) => api.get(`/sav/contrats/${id}/`),
  createContrat: (data) => api.post('/sav/contrats/', data),
  updateContrat: (id, data) => api.patch(`/sav/contrats/${id}/`, data),
  deleteContrat: (id) => api.delete(`/sav/contrats/${id}/`),
  // Vue « à venir » : échéances dues / bientôt dues (calculées à la lecture).
  // generer:true déclenche en plus la création des tickets dus (idempotent).
  getContratsAVenir: (generer = false) =>
    api.get('/sav/contrats/a-venir/', { params: generer ? { generer: '1' } : {} }),
  // Génère le ticket dû d'un contrat (idempotent).
  genererTicketsDus: (id) => api.post(`/sav/contrats/${id}/generer-dus/`),
}

export default savApi
