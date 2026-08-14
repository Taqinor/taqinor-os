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
}

export default scmApi
