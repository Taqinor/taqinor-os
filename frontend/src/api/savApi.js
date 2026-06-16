import api from './axios'

// Après-vente : parc d'équipements + tickets SAV.
const savApi = {
  // ── Équipements ──
  getEquipements: (params) => api.get('/sav/equipements/', { params }),
  // Export .xlsx (respecte les filtres courants). Réponse blob.
  exportEquipements: (params = {}) =>
    api.get('/sav/equipements/export/', { params, responseType: 'blob' }),
  getEquipement: (id) => api.get(`/sav/equipements/${id}/`),
  createEquipement: (data) => api.post('/sav/equipements/', data),
  updateEquipement: (id, data) => api.patch(`/sav/equipements/${id}/`, data),
  deleteEquipement: (id) => api.delete(`/sav/equipements/${id}/`),

  // ── Tickets SAV ──
  getTickets: (params) => api.get('/sav/tickets/', { params }),
  // Export .xlsx (respecte les filtres courants). Réponse blob.
  exportTickets: (params = {}) =>
    api.get('/sav/tickets/export/', { params, responseType: 'blob' }),
  getTicket: (id) => api.get(`/sav/tickets/${id}/`),
  createTicket: (data) => api.post('/sav/tickets/', data),
  updateTicket: (id, data) => api.patch(`/sav/tickets/${id}/`, data),
  deleteTicket: (id) => api.delete(`/sav/tickets/${id}/`),
  getTicketHistorique: (id) => api.get(`/sav/tickets/${id}/historique/`),
  noterTicket: (id, body) => api.post(`/sav/tickets/${id}/noter/`, { body }),
  annulerTicket: (id, motif) => api.post(`/sav/tickets/${id}/annuler/`, { motif }),
  reactiverTicket: (id) => api.post(`/sav/tickets/${id}/reactiver/`),
  // N45 — rapport d'intervention PDF (ticket résolu/clôturé). Réponse blob.
  getTicketRapportPdf: (id) =>
    api.get(`/sav/tickets/${id}/rapport-pdf/`, { responseType: 'blob' }),
  // N46 — pièces consommées sur le ticket (+ décrément de stock optionnel).
  getTicketPieces: (id) => api.get(`/sav/tickets/${id}/pieces/`),
  addTicketPiece: (id, data, decrement = false) =>
    api.post(`/sav/tickets/${id}/pieces/`, data,
      { params: decrement ? { decrement: '1' } : {} }),
  deleteTicketPiece: (id, pieceId) =>
    api.delete(`/sav/tickets/${id}/pieces/${pieceId}/`),

  // N48 — garanties qui expirent (horizon ?jours, défaut 90).
  getGarantiesExpirent: (jours) =>
    api.get('/sav/equipements/garanties-expirent/',
      { params: jours ? { jours } : {} }),
  // N48 — réclamations de garantie (CRUD).
  getReclamations: (params) => api.get('/sav/reclamations-garantie/', { params }),
  getReclamation: (id) => api.get(`/sav/reclamations-garantie/${id}/`),
  createReclamation: (data) => api.post('/sav/reclamations-garantie/', data),
  updateReclamation: (id, data) =>
    api.patch(`/sav/reclamations-garantie/${id}/`, data),
  deleteReclamation: (id) => api.delete(`/sav/reclamations-garantie/${id}/`),

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
  // N47 — contrats approchant leur renouvellement (date_fin dans l'horizon).
  getContratsARenouveler: () => api.get('/sav/contrats/a-renouveler/'),
  // N47 — marquer une visite préventive comme effectuée (avance dernière visite).
  visiteEffectuee: (id, date) =>
    api.post(`/sav/contrats/${id}/visite-effectuee/`, date ? { date } : {}),
  // N47 — rapport de maintenance PDF (optionnel ?ticket=<id>). Réponse blob.
  getContratRapportPdf: (id, ticketId) =>
    api.get(`/sav/contrats/${id}/rapport-pdf/`,
      { params: ticketId ? { ticket: ticketId } : {}, responseType: 'blob' }),
}

export default savApi
