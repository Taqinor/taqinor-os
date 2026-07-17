import api from './axios'

const crmApi = {
  // VX55 — `config` optionnel (ex. { signal }) pour l'annulation
  // AbortController câblée depuis les thunks (createAsyncThunk {signal}).
  getClients: (params, config) => api.get('/crm/clients/', { params, ...config }),
  getClient: (id) => api.get(`/crm/clients/${id}/`),
  // QC1 — autocomplete entreprise sur les données PROPRES de la société
  // (clients + fournisseurs + leads, recherche floue nom/ICE, scopée société).
  searchClients: (q) => api.get('/crm/clients/search/', { params: { q } }),
  createClient: (data) => api.post('/crm/clients/', data),
  updateClient: (id, data) => api.put(`/crm/clients/${id}/`, data),
  patchClient: (id, data) => api.patch(`/crm/clients/${id}/`, data),
  deleteClient: (id) => api.delete(`/crm/clients/${id}/`),
  exportClientsXlsx: (ids) =>
    api.post('/crm/clients/export-xlsx/', { ids }, { responseType: 'blob' }),
  // FG26 — RGPD : bundle d'accès du sujet (lecture, responsable/admin) et
  // anonymisation irréversible des PII (admin uniquement, côté serveur).
  clientDataExport: (id) => api.get(`/crm/clients/${id}/data-export/`),
  anonymizeClient: (id) => api.post(`/crm/clients/${id}/anonymize/`),
  // XSAL9 — rollup CA groupe (société mère + filiales, récursif).
  getClientConsolidation: (id) => api.get(`/crm/clients/${id}/consolidation/`),

  // Leads / opportunities
  // VX55 — même `config` optionnel (signal d'annulation) que getClients.
  getLeads: (params, config) => api.get('/crm/leads/', { params, ...config }),
  getLead: (id) => api.get(`/crm/leads/${id}/`),
  createLead: (data) => api.post('/crm/leads/', data),
  updateLead: (id, data) => api.patch(`/crm/leads/${id}/`, data),
  // Garde serveur du « Devis auto » : 200 {ok:true} si le lead est prêt,
  // 400 {detail:'Manque : …'} sinon — la règle vit côté backend.
  checkDevisAuto: (id) => api.post(`/crm/leads/${id}/devis-auto/`),
  // Archivage réversible (Commerciale) + suppression RÉVERSIBLE (admin, VX96 :
  // soft-delete + corbeille 30 min). `deleteLead` renvoie { corbeille_id } ;
  // `restaurerCorbeille` annule la suppression via le TrashViewSet partagé.
  archiverLead: (id) => api.post(`/crm/leads/${id}/archiver/`),
  restaurerLead: (id) => api.post(`/crm/leads/${id}/restaurer/`),
  deleteLead: (id) => api.delete(`/crm/leads/${id}/`),
  restaurerCorbeille: (corbeilleId) =>
    api.post(`/core/corbeille/${corbeilleId}/restaurer/`),
  getHistoriqueLead: (id) => api.get(`/crm/leads/${id}/historique/`),
  // NTMOB4 — file de relance du jour (FG31/VX83, crm.selectors.relances_du_jour).
  // ?scope=overdue|today|week (défaut today). {count, results:[Lead]}.
  getRelances: (params) => api.get('/crm/leads/relances/', { params }),
  // Employés assignables (id, username, poste, avatar_url) — ouvert à la
  // Commerciale (le sélecteur de responsable doit marcher pour elle aussi).
  getAssignableUsers: () => api.get('/crm/assignable-users/'),
  // Actions EN MASSE sur une sélection de leads (liste + kanban). Le corps
  // porte {ids, action, …paramètres} ; la règle métier vit côté serveur.
  bulkLeads: (payload) => api.post('/crm/leads/bulk/', payload),
  // Export Excel (.xlsx) d'une sélection — réponse binaire (blob).
  exportLeadsXlsx: (ids) =>
    api.post('/crm/leads/export-xlsx/', { ids }, { responseType: 'blob' }),
  // Contrôle pré-création/édition des doublons par téléphone/email (société
  // côté serveur). Avertissement NON bloquant dans le formulaire de lead.
  checkDuplicates: (params) => api.get('/crm/leads/check-duplicates/', { params }),
  // XSAL8 — scan de carte de visite (photo) → pré-remplissage du lead
  // express. Ne crée jamais de lead ; renvoie {nom, prenom, societe,
  // telephone, email, doublons}. 503 si l'OCR n'est pas configuré (clé absente).
  scanCarteVisite: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/crm/leads/scan-carte/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // Doublons + fusion de leads (sans perte).
  getLeadDuplicates: (id) => api.get(`/crm/leads/${id}/duplicates/`),
  // Atelier doublons : tous les clusters de la société (survivant suggéré).
  getDoublons: (params) => api.get('/crm/leads/doublons/', { params }),
  mergeLeads: (id, others) => api.post(`/crm/leads/${id}/merge/`, { others }),
  // Envoyer par WhatsApp : construit un lien wa.me prêt à envoyer pour un ou
  // plusieurs devis du lead (le commercial appuie lui-même sur Envoyer).
  whatsappDevis: (id, payload) =>
    api.post(`/crm/leads/${id}/whatsapp-devis/`, payload),
  // FG30 — Interaction typée (appel/email) dans le chatter du lead.
  logInteraction: (id, payload) =>
    api.post(`/crm/leads/${id}/log-interaction/`, payload),
  // FG36 — Modèles de messages WhatsApp/SMS.
  getMessageTemplates: (params) => api.get('/crm/message-templates/', { params }),
  getMessageTemplate: (id) => api.get(`/crm/message-templates/${id}/`),
  saveMessageTemplate: (id, data) =>
    id ? api.patch(`/crm/message-templates/${id}/`, data)
       : api.post('/crm/message-templates/', data),
  deleteMessageTemplate: (id) => api.delete(`/crm/message-templates/${id}/`),
  renderMessageTemplate: (id, payload) =>
    api.post(`/crm/message-templates/${id}/render/`, payload),

  // Listes gérées (Paramètres → CRM).
  getTags: () => api.get('/crm/tags/'),
  saveTag: (id, data) => id ? api.patch(`/crm/tags/${id}/`, data) : api.post('/crm/tags/', data),
  deleteTag: (id) => api.delete(`/crm/tags/${id}/`),
  getMotifsPerte: () => api.get('/crm/motifs-perte/'),
  saveMotifPerte: (id, data) => id ? api.patch(`/crm/motifs-perte/${id}/`, data) : api.post('/crm/motifs-perte/', data),
  deleteMotifPerte: (id) => api.delete(`/crm/motifs-perte/${id}/`),
  // Canaux / sources de lead gérés (Paramètres → CRM). 'site_web' est protégé.
  getCanaux: () => api.get('/crm/canaux/'),
  saveCanal: (id, data) => id ? api.patch(`/crm/canaux/${id}/`, data) : api.post('/crm/canaux/', data),
  deleteCanal: (id) => api.delete(`/crm/canaux/${id}/`),

  // N98 — parrainage / programme de recommandation.
  getParrainages: (params) => api.get('/crm/parrainages/', { params }),
  saveParrainage: (id, data) => id
    ? api.patch(`/crm/parrainages/${id}/`, data)
    : api.post('/crm/parrainages/', data),
  deleteParrainage: (id) => api.delete(`/crm/parrainages/${id}/`),
  parrainageStats: () => api.get('/crm/parrainages/stats/'),

  // FG204 — journal multi-touch du lead (timeline + résumé d'attribution).
  getLeadPointsContact: (id) => api.get(`/crm/leads/${id}/points-contact/`),
  // FG38 — correspondance lead ↔ client existant (retour client / doublon).
  getLeadClientMatch: (id) => api.get(`/crm/leads/${id}/client-match/`),
  // FG34 — ROI agrégé par canal / campagne UTM (surface consultative).
  getRoiSources: (params) => api.get('/crm/leads/roi-sources/', { params }),
  // FG28 — leads NEW non contactés au-delà du SLA société.
  getSlaBreach: () => api.get('/crm/leads/sla-breach/'),
  // FG39 — objectifs commerciaux : atteinte (réalisé vs cible).
  getObjectifsAttainment: (params) =>
    api.get('/crm/objectifs/attainment/', { params }),
  getObjectifAttainment: (id) => api.get(`/crm/objectifs/${id}/attainment/`),

  // QJ20 — Rendez-vous (visites commerciales/techniques).
  getAppointments: (leadId) => api.get('/crm/appointments/', { params: { lead: leadId } }),
  createAppointment: (data) => api.post('/crm/appointments/', data),
  updateAppointment: (id, data) => api.patch(`/crm/appointments/${id}/`, data),
  deleteAppointment: (id) => api.delete(`/crm/appointments/${id}/`),
  // VX245(a) — `.ics` d'événement unique pour CE rendez-vous (blob : le
  // téléchargement authentifié passe par axios, jamais un `<a href>` brut
  // qui n'enverrait pas le jeton Bearer).
  getAppointmentIcs: (id) =>
    api.get(`/crm/appointments/${id}/ics/`, { responseType: 'blob' }),
  // VX245(b) — aperçu du message de confirmation WhatsApp (date/heure +
  // lien .ics) ; n'envoie RIEN, ouvre wa.me seulement après confirmation.
  confirmerAppointmentWhatsapp: (id) =>
    api.post(`/crm/appointments/${id}/confirmer-whatsapp/`),

  // ZSAL2 — Plans d'activité (checklists commerciales applicables en un clic).
  getPlansActivite: () => api.get('/crm/plans-activite/'),
  appliquerPlanActivite: (leadId, planId) =>
    api.post(`/crm/leads/${leadId}/appliquer-plan/`, { plan_id: planId }),

  // ZSAL3 — Tableau de bord « Mes équipes ».
  getEquipesStatistiques: () => api.get('/crm/equipes/statistiques/'),
  // ZSAL3 — Équipes commerciales (admin CRUD, Paramètres → CRM).
  getEquipes: (params) => api.get('/crm/equipes/', { params }),
  saveEquipe: (id, data) =>
    id ? api.patch(`/crm/equipes/${id}/`, data) : api.post('/crm/equipes/', data),
  deleteEquipe: (id) => api.delete(`/crm/equipes/${id}/`),

  // ZSAL4 — Conversion lead → client explicite (nouveau / lier / aucun).
  convertirLeadEnClient: (leadId, payload) =>
    api.post(`/crm/leads/${leadId}/convertir-client/`, payload),

  // ZSAL6 — Rapport d'attribution des leads (par commercial + par source).
  getAttributionLeads: (params) =>
    api.get('/crm/rapports/attribution/', { params }),

  // QX16 — Payloads leads site web (« jamais perdre un lead ») : rejeu des
  // captures dont le mapping a échoué ou qui n'ont jamais été rattachées.
  getWebsiteLeadPayloads: (params) =>
    api.get('/crm/website-lead-payloads/', { params }),
  replayWebsiteLeadPayload: (id) =>
    api.post(`/crm/website-lead-payloads/${id}/replay/`),
}

export default crmApi
