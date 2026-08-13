import api from './axios'

/* ============================================================================
   Gestion du crédit client (apps/credit) — client API. Préfixe `/credit/`
   (axios ajoute déjà `/api/django`). La société est TOUJOURS posée côté
   serveur (jamais dans le corps). Aucun `prix_achat`/marge n'est jamais
   demandé ni affiché — le module crédit n'en expose aucun.
   ========================================================================== */

const creditApi = {
  // NTCRD3 — réglages crédit société (get-or-default / PATCH Directeur/Admin).
  getReglage: () => api.get('/credit/reglage/'),
  updateReglage: (data) => api.patch('/credit/reglage/', data),

  // NTCRD2 — limites de crédit par client.
  getLimites: (params) => api.get('/credit/limites/', { params }),
  createLimite: (data) => api.post('/credit/limites/', data),
  updateLimite: (id, data) => api.patch(`/credit/limites/${id}/`, data),

  // NTCRD10 — fiche crédit consolidée d'un client.
  getFicheClient: (clientId) => api.get(`/credit/clients/${clientId}/fiche/`),

  // NTCRD27 — limite suggérée (wizard « définir une limite »).
  getLimiteSuggeree: (clientId) =>
    api.get(`/credit/clients/${clientId}/limite-suggeree/`),

  // NTCRD19/20 — rapport d'exposition consolidée (+ export xlsx).
  getExposition: (params) => api.get('/credit/exposition/', { params }),
  exportExpositionXlsx: () =>
    api.get('/credit/exposition/', {
      params: { export: 'xlsx' },
      responseType: 'blob',
    }),

  // NTCRD12 — score crédit d'un client (lettre + position vs limite).
  getScoreClient: (clientId) => api.get(`/credit/clients/${clientId}/score/`),

  // NTCRD23 — pastilles d'état crédit pour une liste d'ids clients (batch).
  getBadges: (clientIds) =>
    api.get('/credit/badges/', { params: { client_ids: clientIds.join(',') } }),

  // NTCRD13/15 — conditions de paiement par segment.
  getConditionsSegment: (params) =>
    api.get('/credit/conditions-segment/', { params }),
  createConditionSegment: (data) =>
    api.post('/credit/conditions-segment/', data),
  updateConditionSegment: (id, data) =>
    api.patch(`/credit/conditions-segment/${id}/`, data),
  deleteConditionSegment: (id) =>
    api.delete(`/credit/conditions-segment/${id}/`),

  // PACT47/NTCRD39 — import en masse des limites (multipart). `apercu` ne fait
  // RIEN écrire côté serveur ; `ecraser` est l'opt-in explicite (défaut sûr =
  // remplissage seul). Les deux drapeaux partent en texte : le serveur ne
  // retient qu'un true/1/oui explicite (`_bool_strict`).
  importerLimites: (fichier, { apercu = false, ecraser = false } = {}) => {
    const corps = new FormData()
    corps.append('fichier', fichier)
    corps.append('apercu', apercu ? 'true' : 'false')
    corps.append('ecraser', ecraser ? 'true' : 'false')
    return api.post('/credit/import-limites/', corps)
  },

  // PACT48/NTCRD16-17 — assurance-crédit : registre DÉCLARATIF des polices et
  // des encours garantis par client (aucun appel assureur).
  getPolicesAssurance: (params) => api.get('/credit/polices-assurance/', { params }),
  createPoliceAssurance: (data) => api.post('/credit/polices-assurance/', data),
  updatePoliceAssurance: (id, data) =>
    api.patch(`/credit/polices-assurance/${id}/`, data),
  getEncoursGarantis: (params) => api.get('/credit/encours-garantis/', { params }),
  createEncoursGaranti: (data) => api.post('/credit/encours-garantis/', data),
  deleteEncoursGaranti: (id) => api.delete(`/credit/encours-garantis/${id}/`),

  // PACT50/NTCRD13 — rattachement d'un client à un segment crédit (le maillon
  // qui rend applicables les conditions de paiement du segment).
  getSegmentsClient: (params) => api.get('/credit/segments-client/', { params }),
  createSegmentClient: (data) => api.post('/credit/segments-client/', data),
  updateSegmentClient: (id, data) =>
    api.patch(`/credit/segments-client/${id}/`, data),
  deleteSegmentClient: (id) => api.delete(`/credit/segments-client/${id}/`),

  // PACT49/NTCRD26 — rapport agrégé des dérogations sur période (délai de
  // traitement en heures) + export XLSX/CSV aux colonnes STABLES du serveur.
  getRapportDerogations: (params) =>
    api.get('/credit/rapport-derogations/', { params }),
  exportRapportDerogations: (params, format = 'xlsx') =>
    api.get('/credit/rapport-derogations/', {
      params: { ...params, export: format },
      responseType: 'blob',
    }),

  // NTCRD9 — dérogations : demande + décision (approuver/rejeter).
  getDerogations: (params) => api.get('/credit/derogations/', { params }),
  createDerogation: (data) => api.post('/credit/derogations/', data),
  approuverDerogation: (id) =>
    api.post(`/credit/derogations/${id}/approuver/`),
  rejeterDerogation: (id) => api.post(`/credit/derogations/${id}/rejeter/`),
}

export default creditApi
