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
  // WIR116/FG85/XSAV19 — étiquettes QR imprimables (HTML prêt à imprimer).
  // `public:true` encode le lien public /e/<token> ; sinon le jeton interne
  // EQUIP:<id> (scan interne inchangé). Renvoie un blob text/html.
  etiquettesEquipements: (ids = [], { symbology = 'qr', public: pub = true } = {}) =>
    api.get('/sav/equipements/etiquettes/', {
      params: {
        ...(ids.length ? { ids: ids.join(',') } : {}),
        symbology,
        ...(pub ? { public: 1 } : {}),
      },
      responseType: 'blob',
    }),
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
  // XSAV23 — insère une réponse type (macro) en un clic ; body reste
  // optionnel (le serveur rend la macro s'il est vide).
  noterTicketAvecMacro: (id, reponseTypeId, body) =>
    api.post(`/sav/tickets/${id}/noter/`,
      body ? { reponse_type_id: reponseTypeId, body } : { reponse_type_id: reponseTypeId }),
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
  // ZMFG8 — vue unifiée Ajout/Retrait/Recyclage des pièces du ticket.
  getTicketPiecesUnifiees: (id) => api.get(`/sav/tickets/${id}/pieces-unifiees/`),

  // XSAV12 — fusionne un ticket doublon dans ce ticket (principal).
  fusionnerTicket: (id, doublonId) =>
    api.post(`/sav/tickets/${id}/fusionner/`, { doublon_id: doublonId }),
  // XSAV21 — tickets résolus similaires (panneau « Résolutions similaires »).
  getTicketsSimilaires: (id, limit) =>
    api.get(`/sav/tickets/${id}/similaires/`, { params: limit ? { limit } : {} }),
  // XSAV25 — pièces catalogue compatibles avec l'équipement lié (picker de pièces).
  getPiecesCompatibles: (id) => api.get(`/sav/tickets/${id}/pieces-compatibles/`),
  // XSAV28 — triage IA du ticket (propose→confirme, jamais auto-appliqué).
  getTriageIa: (id) => api.get(`/sav/tickets/${id}/triage-ia/`),
  // ZSAV8 — convertit le ticket en opportunité CRM (upsell/remplacement).
  creerLeadDepuisTicket: (id) => api.post(`/sav/tickets/${id}/creer-lead/`),
  // ZSAV9 — suivre/ne plus suivre un ticket (notifications).
  suivreTicket: (id) => api.post(`/sav/tickets/${id}/suivre/`),
  neplusSuivreTicket: (id) => api.delete(`/sav/tickets/${id}/suivre/`),
  // XSAV27 — prêt/échange anticipé d'équipement (loaner).
  getPretsEquipement: (id) => api.get(`/sav/tickets/${id}/prets-equipement/`),
  creerPretEquipement: (id, body) => api.post(`/sav/tickets/${id}/prets-equipement/`, body),
  retournerPretEquipement: (id, pretId, dateRetourReelle) =>
    api.post(`/sav/tickets/${id}/prets-equipement/${pretId}/retourner/`,
      dateRetourReelle ? { date_retour_reelle: dateRetourReelle } : {}),
  // XSAV5 — pause/reprise SLA « en attente client ».
  attenteClientTicket: (id) => api.post(`/sav/tickets/${id}/attente-client/`),
  reprendreTicket: (id) => api.post(`/sav/tickets/${id}/reprendre/`),
  // ZSAV3 — activités planifiées à échéance du ticket.
  getTicketActivites: (id) => api.get(`/sav/tickets/${id}/activites/`),
  addTicketActivite: (id, body) => api.post(`/sav/tickets/${id}/activites/`, body),
  cocherTicketActivite: (id, activiteId) =>
    api.post(`/sav/tickets/${id}/activites/${activiteId}/cocher/`),
  // ZMFG5 — suggestions d'articles KB pour pré-remplir l'onglet Instructions.
  getInstructionsSuggestions: (id) => api.get(`/sav/tickets/${id}/instructions-suggestions/`),
  // ZMFG6 — feuille de maintenance (worksheet) remplie sur le ticket.
  getTicketWorksheet: (id) => api.get(`/sav/tickets/${id}/worksheet/`),
  creerTicketWorksheet: (id, modeleId) =>
    api.post(`/sav/tickets/${id}/worksheet/`, { modele_id: modeleId }),
  updateTicketWorksheet: (id, body) => api.patch(`/sav/tickets/${id}/worksheet/`, body),

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

  // FG87 — base de connaissances SAV (articles KB).
  getKbArticles: (params) => api.get('/sav/kb-articles/', { params }),
  getKbArticle: (id) => api.get(`/sav/kb-articles/${id}/`),
  saveKbArticle: (id, data) => id
    ? api.patch(`/sav/kb-articles/${id}/`, data)
    : api.post('/sav/kb-articles/', data),
  deleteKbArticle: (id) => api.delete(`/sav/kb-articles/${id}/`),

  // XSAV23 — réponses types (macros) pour le chatter ticket.
  getReponsesType: (params) => api.get('/sav/reponses-type/', { params }),
  saveReponseType: (id, data) => id
    ? api.patch(`/sav/reponses-type/${id}/`, data)
    : api.post('/sav/reponses-type/', data),
  deleteReponseType: (id) => api.delete(`/sav/reponses-type/${id}/`),

  // XSAV25 — compatibilités pièces (Paramètres).
  getCompatibilitesPiece: (params) => api.get('/sav/compatibilites-piece/', { params }),
  saveCompatibilitePiece: (id, data) => id
    ? api.patch(`/sav/compatibilites-piece/${id}/`, data)
    : api.post('/sav/compatibilites-piece/', data),
  deleteCompatibilitePiece: (id) => api.delete(`/sav/compatibilites-piece/${id}/`),

  // XSAV14 — taxonomie panne : causes / remèdes de défaillance (Paramètres).
  getCausesDefaillance: (params) => api.get('/sav/causes-defaillance/', { params }),
  saveCauseDefaillance: (id, data) => id
    ? api.patch(`/sav/causes-defaillance/${id}/`, data)
    : api.post('/sav/causes-defaillance/', data),
  deleteCauseDefaillance: (id) => api.delete(`/sav/causes-defaillance/${id}/`),
  getRemedesDefaillance: (params) => api.get('/sav/remedes-defaillance/', { params }),
  saveRemedeDefaillance: (id, data) => id
    ? api.patch(`/sav/remedes-defaillance/${id}/`, data)
    : api.post('/sav/remedes-defaillance/', data),
  deleteRemedeDefaillance: (id) => api.delete(`/sav/remedes-defaillance/${id}/`),

  // ZSAV2 — catégories de ticket (Paramètres + filtre liste).
  getCategoriesTicket: (params) => api.get('/sav/categories-ticket/', { params }),
  saveCategorieTicket: (id, data) => id
    ? api.patch(`/sav/categories-ticket/${id}/`, data)
    : api.post('/sav/categories-ticket/', data),
  deleteCategorieTicket: (id) => api.delete(`/sav/categories-ticket/${id}/`),

  // ZMFG1 — équipes de maintenance (Paramètres).
  getEquipesMaintenance: (params) => api.get('/sav/equipes-maintenance/', { params }),
  saveEquipeMaintenance: (id, data) => id
    ? api.patch(`/sav/equipes-maintenance/${id}/`, data)
    : api.post('/sav/equipes-maintenance/', data),
  deleteEquipeMaintenance: (id) => api.delete(`/sav/equipes-maintenance/${id}/`),

  // ZMFG2 — catégories d'équipement (Paramètres + filtre parc).
  getCategoriesEquipement: (params) => api.get('/sav/categories-equipement/', { params }),
  saveCategorieEquipement: (id, data) => id
    ? api.patch(`/sav/categories-equipement/${id}/`, data)
    : api.post('/sav/categories-equipement/', data),
  deleteCategorieEquipement: (id) => api.delete(`/sav/categories-equipement/${id}/`),

  // ZMFG6 — modèles de feuille de maintenance (Paramètres).
  getWorksheetModeles: (params) => api.get('/sav/worksheet-modeles/', { params }),
  saveWorksheetModele: (id, data) => id
    ? api.patch(`/sav/worksheet-modeles/${id}/`, data)
    : api.post('/sav/worksheet-modeles/', data),
  deleteWorksheetModele: (id) => api.delete(`/sav/worksheet-modeles/${id}/`),

  // Alarmes onduleur (FG280) — distinctes du ticket SAV.
  getAlarmes: (params) => api.get('/sav/alarmes-onduleur/', { params }),
  acquitterAlarme: (id) => api.post(`/sav/alarmes-onduleur/${id}/acquitter/`),
  escaladerAlarme: (id, ticketId) =>
    api.post(`/sav/alarmes-onduleur/${id}/escalader/`, ticketId ? { ticket: ticketId } : {}),

  // ── Insights SAV (backend/apps/reporting) ──
  // XSAV8 — rapport de conformité SLA + KPI avancés (responsable/admin).
  getSavSlaReport: (params) => api.get('/reporting/insights/sav-sla/', { params }),
  // XSAV14 — Pareto des pannes par produit/fournisseur.
  getSavPareto: (params) => api.get('/sav/insights/sav-pannes/', { params }),
  // XSAV15 — fiabilité (MTBF/MTTR/coût) de tout le parc.
  getSavFiabiliteParc: (params) => api.get('/sav/insights/sav-fiabilite/', { params }),
  // ZMFG4 — tableau de bord maintenance par équipe.
  getSavResumeParEquipe: () => api.get('/sav/insights/sav-resume-equipe/'),
  // ZSAV6 — file d'action : tickets ouverts groupés par action attendue.
  getSavFileAction: () => api.get('/sav/tickets/file-action/'),
}

export default savApi
