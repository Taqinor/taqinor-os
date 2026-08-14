import api from './axios'

/* ============================================================================
   Planification supply chain (apps/scm, Groupe NTSCM). Préfixe `/scm/`.
   Prévision de demande saisonnière, événements d'impact, classification ABC,
   politiques de stock (ROP/stock de sécurité), tableau de bord de réappro
   consolidé et cycle S&OP mensuel (demande/offre/finance).
   ========================================================================== */

const scmApi = {
  // NTSCM1/2/3 — prévisions de demande.
  previsionsDemande: (params) => api.get('/scm/previsions-demande/', { params }),
  genererPrevisions: (body) => api.post('/scm/previsions-demande/generer/', body),
  evenementsDemande: (params) => api.get('/scm/evenements-demande/', { params }),
  creerEvenementDemande: (body) => api.post('/scm/evenements-demande/', body),

  // NTSCM4 — classification ABC.
  classificationAbc: (params) => api.get('/scm/classification-abc/', { params }),
  recalculerClassificationAbc: (body = {}) =>
    api.post('/scm/classification-abc/recalculer/', body),

  // NTSCM6 — politiques de stock.
  politiquesStock: (params) => api.get('/scm/politiques-stock/', { params }),
  recalculerPolitiquesStock: () => api.post('/scm/politiques-stock/recalculer/', {}),

  // NTSCM7 — tableau de bord réappro consolidé.
  tableauBordReappro: (params) => api.get('/scm/tableau-bord-reappro/', { params }),
  creerBrouillonsBcfReappro: (body = {}) =>
    api.post('/scm/tableau-bord-reappro/creer-bcf/', body),

  // NTSCM12/13/14/15 — cycle de planification S&OP mensuel.
  cyclesSop: (params) => api.get('/scm/cycles-sop/', { params }),
  creerCycleSop: (body) => api.post('/scm/cycles-sop/', body),
  cycleSop: (id) => api.get(`/scm/cycles-sop/${id}/`),
  avancerStatutCycleSop: (id, body = {}) =>
    api.post(`/scm/cycles-sop/${id}/avancer-statut/`, body),
  reouvrirCycleSop: (id, body = {}) => api.post(`/scm/cycles-sop/${id}/reouvrir/`, body),
  historiqueCycleSop: (id) => api.get(`/scm/cycles-sop/${id}/historique/`),
  lignesDemandeCycleSop: (id) => api.get(`/scm/cycles-sop/${id}/lignes-demande/`),
  ajusterDemandeCycleSop: (id, body) =>
    api.post(`/scm/cycles-sop/${id}/ajuster-demande/`, body),
  calculerOffreCycleSop: (id) => api.post(`/scm/cycles-sop/${id}/calculer-offre/`, {}),
  ecartsCycleSop: (id) => api.get(`/scm/cycles-sop/${id}/ecarts/`),
  impactFinancierCycleSop: (id) => api.get(`/scm/cycles-sop/${id}/impact-financier/`),
  compteRenduCycleSop: (id) =>
    api.get(`/scm/cycles-sop/${id}/compte-rendu/`, { responseType: 'blob' }),

  // NTSCM16 — suggestions d'achat groupées multi-fournisseurs (MOQ/paliers).
  suggestionsAchatGroupe: () => api.get('/scm/suggestions-achat-groupe/'),

  // NTSCM18 — simulation « et si… » de rupture (lecture seule, en mémoire).
  simulerRupture: (produitId, body = {}) =>
    api.post(`/scm/produits/${produitId}/simuler/`, body),

  // NTSCM19 — allocation en pénurie multi-clients (proposition).
  proposerAllocationPenurie: (produitId, params = {}) =>
    api.get(`/scm/produits/${produitId}/proposer-allocation/`, { params }),

  // NTSCM20 — suggestions de transfert inter-sites (anticipatif).
  suggestionsTransfert: () => api.get('/scm/suggestions-transfert/'),

  // NTSCM24 — précision de prévision auto-mesurée (MAPE).
  precisionPrevisions: (params = {}) =>
    api.get('/scm/precision-previsions/', { params }),

  // NTSCM32 — export .xlsx du rapport « Écarts de prévision ».
  exportEcartsPrevision: (params = {}) =>
    api.get('/scm/precision-previsions/export/', { params, responseType: 'blob' }),

  // NTSCM25 — anomalies de demande (pic/creux inattendu).
  anomaliesDemande: () => api.get('/scm/anomalies-demande/'),
  detecterAnomaliesDemande: () => api.post('/scm/anomalies-demande/detecter/', {}),

  // NTSCM28 — tableau de bord SCM exécutif (KPI de synthèse).
  tableauBordExecutif: () => api.get('/scm/tableau-bord/'),

  // NTSCM29 — fiche PDF interne « Politique de stock ».
  fichePdfPolitiqueStock: (id) =>
    api.get(`/scm/politiques-stock/${id}/fiche-pdf/`, { responseType: 'blob' }),

  // NTSCM30 — assistant guidé « Créer une politique de stock » en lot.
  creerPolitiquesEnLot: (body) =>
    api.post('/scm/politiques-stock/creer-en-lot/', body),

  // NTSCM22 — réglages opt-in du cycle S&OP automatique (singleton société).
  parametresSop: () => api.get('/scm/parametres-sop/'),
  majParametresSop: (body) => api.patch('/scm/parametres-sop/', body),

  // NTSCM33 — écran de réglages SCM par société (horizon/niveaux/seuils).
  parametresScm: () => api.get('/scm/parametres/'),
  majParametresScm: (body) => api.patch('/scm/parametres/', body),
}

export default scmApi
