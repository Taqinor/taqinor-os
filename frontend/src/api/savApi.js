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
  // XSAV15 — MTBF/MTTR/coût cumulé de CET équipement (coût gated prix_achat_voir côté serveur).
  getEquipementFiabilite: (id) => api.get(`/sav/equipements/${id}/fiabilite/`),
  // ZMFG11 — prochaine défaillance estimée (MTBF) + prochain entretien dû.
  getEquipementEstimations: (id) => api.get(`/sav/equipements/${id}/estimations-maintenance/`),
  // XSAV16 — journal d'immobilisation (downtime) : GET liste, POST ouvre une fenêtre.
  getEquipementDowntime: (id) => api.get(`/sav/equipements/${id}/downtime/`),
  ouvrirEquipementDowntime: (id, body) => api.post(`/sav/equipements/${id}/downtime/`, body ?? {}),
  cloturerEquipementDowntime: (id, downtimeId, fin) =>
    api.post(`/sav/equipements/${id}/downtime/${downtimeId}/cloturer/`, fin ? { fin } : {}),
  // XSAV16 — disponibilité % sur une période (défaut 30 derniers jours).
  getEquipementDisponibilite: (id, params) =>
    api.get(`/sav/equipements/${id}/disponibilite/`, { params }),
  // XSAV17 — relevés compteur (heures/kWh) : GET historique, POST enregistre.
  getEquipementReleves: (id) => api.get(`/sav/equipements/${id}/releves-compteur/`),
  addEquipementReleve: (id, body) => api.post(`/sav/equipements/${id}/releves-compteur/`, body),
  // ZMFG12 — mise au rebut motivée / réactivation (réservé responsable/admin).
  mettreAuRebutEquipement: (id, motif) =>
    api.post(`/sav/equipements/${id}/mettre-au-rebut/`, { motif }),
  reactiverRebutEquipement: (id) => api.post(`/sav/equipements/${id}/reactiver-rebut/`),

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
  // XSAV11 — réouverture d'un ticket vers « nouveau » (transition gardée ;
  // autorisée depuis planifié/résolu/clôturé, refusée depuis en_cours).
  reouvrirTicket: (id) => api.post(`/sav/tickets/${id}/reouvrir/`),
  // ZMFG3 — vue calendrier : replanifie CE ticket (préventif ou correctif) à
  // une nouvelle date_tournee (glisser-déposer d'une carte vers un autre jour).
  replanifierTicket: (id, dateTournee) =>
    api.post(`/sav/tickets/${id}/replanifier/`, { date_tournee: dateTournee }),
  // N45 — rapport d'intervention (PDF régénéré à la demande, sans prix d'achat).
  rapportPdf: (id) => api.get(`/sav/tickets/${id}/rapport-pdf/`, { responseType: 'blob' }),
  // XSAV3 — devis de réparation hors garantie depuis le ticket (pré-rempli
  // depuis les pièces consommées, prix de VENTE catalogue).
  creerDevisTicket: (id, body) => api.post(`/sav/tickets/${id}/creer-devis/`, body ?? {}),
  // XFSM1 — facture brouillon hors garantie (ou couverte à 0 DH) depuis le ticket.
  genererFactureTicket: (id, override) =>
    api.post(`/sav/tickets/${id}/generer-facture/`, override ? { override: true } : {}),
  // XCTR4 — facture le ticket selon le routage de couverture calculé
  // (garantie / contrat O&M / facturable).
  facturerTicket: (id) => api.post(`/sav/tickets/${id}/facturer/`),
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

  // FG83 — réclamations garantie fournisseur (flux RMA).
  getWarrantyClaims: (params) => api.get('/sav/warranty-claims/', { params }),
  getWarrantyClaim: (id) => api.get(`/sav/warranty-claims/${id}/`),
  saveWarrantyClaim: (id, data) => id
    ? api.patch(`/sav/warranty-claims/${id}/`, data)
    : api.post('/sav/warranty-claims/', data),
  deleteWarrantyClaim: (id) => api.delete(`/sav/warranty-claims/${id}/`),
}

export default savApi
