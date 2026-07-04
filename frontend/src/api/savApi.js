import api from './axios'

// Après-vente : parc d'équipements + tickets SAV.
const savApi = {
  // ── Équipements ──
  getEquipements: (params) => api.get('/sav/equipements/', { params }),
  getEquipement: (id) => api.get(`/sav/equipements/${id}/`),
  createEquipement: (data) => api.post('/sav/equipements/', data),
  updateEquipement: (id, data) => api.patch(`/sav/equipements/${id}/`, data),
  deleteEquipement: (id) => api.delete(`/sav/equipements/${id}/`),
  // FG290 — registre des garanties par parc (échéancier de fin de garantie).
  getRegistreGaranties: (params) =>
    api.get('/sav/equipements/registre-garanties/', { params }),

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
  // ZSAV10 — actions groupées atomiques (statut/technicien/priorite/annuler)
  // en une seule requête, remplace le fan-out de PATCH par ligne.
  actionsGroupeesTickets: (ids, operation, extra = {}) =>
    api.post('/sav/tickets/actions-groupees/', { ids, operation, ...extra }),
  // YDOCF1 — machine d'états gardée : `statut` n'est plus PATCHable
  // directement, les transitions passent par ces actions dédiées.
  planifierTicket: (id) => api.post(`/sav/tickets/${id}/planifier/`),
  demarrerTicket: (id) => api.post(`/sav/tickets/${id}/demarrer/`),
  resoudreTicket: (id, canalResolution) =>
    api.post(`/sav/tickets/${id}/resoudre/`,
      canalResolution ? { canal_resolution: canalResolution } : {}),
  cloturerTicket: (id) => api.post(`/sav/tickets/${id}/cloturer/`),
  // N45 — rapport d'intervention (PDF régénéré à la demande, sans prix d'achat).
  rapportPdf: (id) => api.get(`/sav/tickets/${id}/rapport-pdf/`, { responseType: 'blob' }),
  // N46 — pièces consommées sur un ticket (le stock peut être décrémenté).
  getTicketPieces: (id) => api.get(`/sav/tickets/${id}/pieces/`),
  addTicketPiece: (id, body) => api.post(`/sav/tickets/${id}/pieces/`, body),
  removeTicketPiece: (id, pieceId) =>
    api.delete(`/sav/tickets/${id}/pieces/${pieceId}/`),

  // FG81 — première réponse (horloge SLA) : idempotent, date optionnelle.
  premierReponseTicket: (id, at) =>
    api.post(`/sav/tickets/${id}/premier-reponse/`, at ? { at } : {}),
  // FG86 — lien de suivi client tokenisé (créé à la première demande).
  lienClientTicket: (id) => api.get(`/sav/tickets/${id}/lien-client/`),
  // FG82 — checklist de maintenance du ticket (init depuis template + items).
  getTicketChecklist: (id) => api.get(`/sav/tickets/${id}/checklist/`),
  initTicketChecklist: (id, templateId) =>
    api.post(`/sav/tickets/${id}/checklist/`, { template_id: templateId }),
  patchTicketChecklistItem: (id, payload) =>
    api.patch(`/sav/tickets/${id}/checklist/`, payload),
  getChecklistTemplates: () => api.get('/sav/checklist-templates/'),

  // T16 — contrats de maintenance.
  getContrats: (params) => api.get('/sav/contrats-maintenance/', { params }),
  saveContrat: (id, data) => id
    ? api.patch(`/sav/contrats-maintenance/${id}/`, data)
    : api.post('/sav/contrats-maintenance/', data),
  deleteContrat: (id) => api.delete(`/sav/contrats-maintenance/${id}/`),
  genererVisitesDues: () => api.post('/sav/contrats-maintenance/generer-dus/'),
  // N47 — rapport court de visite de maintenance (PDF, sans prix d'achat).
  // L675 — date de visite optionnelle (?date=AAAA-MM-JJ ; défaut derniere_visite).
  maintenanceRapportPdf: (id, date) =>
    api.get(`/sav/contrats-maintenance/${id}/rapport-pdf/`,
      { responseType: 'blob', params: date ? { date } : {} }),
}

export default savApi
