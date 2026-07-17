import api from './axios'

/* ============================================================================
   NTFPA — Client API de la FP&A (apps/fpa).
   ----------------------------------------------------------------------------
   Miroir 1:1 du backend `apps/fpa` (préfixe `/fpa/`). Données scopées société
   côté serveur ; accès Directeur/FP&A. Budget MACRO par société/département/
   période, DISTINCT du budget micro par chantier (gestion_projet). Les
   montants passent par `formatMAD` côté écran — jamais de prix d'achat/marge.
   ========================================================================== */

const P = '/fpa'

const fpaApi = {
  // ── Départements (NTFPA1) ──
  getDepartements: (params) => api.get(`${P}/departements/`, { params }),
  getDepartementsTree: () => api.get(`${P}/departements/`, { params: { tree: 1 } }),
  createDepartement: (data) => api.post(`${P}/departements/`, data),
  updateDepartement: (id, data) => api.patch(`${P}/departements/${id}/`, data),
  deleteDepartement: (id) => api.delete(`${P}/departements/${id}/`),

  // ── Cycles budgétaires (NTFPA2/7) ──
  getCycles: (params) => api.get(`${P}/cycles-budgetaires/`, { params }),
  getCycle: (id) => api.get(`${P}/cycles-budgetaires/${id}/`),
  createCycle: (data) => api.post(`${P}/cycles-budgetaires/`, data),
  ouvrirSaisie: (id) => api.post(`${P}/cycles-budgetaires/${id}/ouvrir-saisie/`),
  cloreCycle: (id) => api.post(`${P}/cycles-budgetaires/${id}/clore/`),
  dupliquerCycle: (id, nouveau_nom) =>
    api.post(`${P}/cycles-budgetaires/${id}/dupliquer/`, { nouveau_nom }),
  exportCycle: (id) => api.get(`${P}/cycles-budgetaires/${id}/export/`, { responseType: 'blob' }),

  // ── Lignes de budget département (NTFPA3/4/5) ──
  getLignesBudget: (params) => api.get(`${P}/lignes-budget-departement/`, { params }),
  createLigneBudget: (data) => api.post(`${P}/lignes-budget-departement/`, data),
  updateLigneBudget: (id, data) => api.patch(`${P}/lignes-budget-departement/${id}/`, data),
  soumettreBudget: (params) =>
    api.post(`${P}/lignes-budget-departement/soumettre/`, {}, { params }),
  validerBudget: (params) =>
    api.post(`${P}/lignes-budget-departement/valider/`, {}, { params }),
  rejeterBudget: (params, motif) =>
    api.post(`${P}/lignes-budget-departement/rejeter/`, { motif }, { params }),

  // ── Prévisions glissantes (NTFPA8/13) ──
  getPrevisions: (params) => api.get(`${P}/previsions-glissantes/`, { params }),
  getPrevision: (id) => api.get(`${P}/previsions-glissantes/${id}/`),
  genererPrevision: (data) => api.post(`${P}/previsions-glissantes/generer/`, data),
  updateLignePrevision: (id, data) =>
    api.patch(`${P}/lignes-prevision-glissante/${id}/`, data),

  // ── Hypothèses de recrutement (NTFPA10) ──
  getHypotheses: (params) => api.get(`${P}/hypotheses-recrutement/`, { params }),
  createHypothese: (data) => api.post(`${P}/hypotheses-recrutement/`, data),
  updateHypothese: (id, data) => api.patch(`${P}/hypotheses-recrutement/${id}/`, data),

  // ── Drivers (NTFPA9/11/12) ──
  projeterMasseSalariale: (data) =>
    api.post(`${P}/drivers/masse-salariale/projeter/`, data),
  revenuPipeline: (params) => api.get(`${P}/drivers/revenu-pipeline/`, { params }),
  revenuEngage: (params) => api.get(`${P}/drivers/revenu-engage/`, { params }),

  // ── Scénarios (NTFPA15/16/17/18) ──
  getScenarios: (params) => api.get(`${P}/scenarios/`, { params }),
  createScenario: (data) => api.post(`${P}/scenarios/`, data),
  comparerScenarios: (params) => api.get(`${P}/scenarios/comparer/`, { params }),
  promouvoirScenario: (id) => api.post(`${P}/scenarios/${id}/promouvoir/`),
  sensibilite: (params) => api.get(`${P}/scenarios/sensibilite/`, { params }),
  getLignesScenario: (params) => api.get(`${P}/lignes-scenario/`, { params }),
  createLigneScenario: (data) => api.post(`${P}/lignes-scenario/`, data),

  // ── Variance (NTFPA19/20/22) ──
  variance: (params) => api.get(`${P}/variance/`, { params }),
  getCommentairesVariance: (params) => api.get(`${P}/commentaires-variance/`, { params }),
  createCommentaireVariance: (data) => api.post(`${P}/commentaires-variance/`, data),

  // ── Mapping catégorie ↔ compte CGNC (NTFPA21) ──
  getMappings: (params) => api.get(`${P}/mapping-categories/`, { params }),
  createMapping: (data) => api.post(`${P}/mapping-categories/`, data),
  updateMapping: (id, data) => api.patch(`${P}/mapping-categories/${id}/`, data),

  // ── Consolidation & dashboard (NTFPA23/24/25) ──
  consolidation: (params) => api.get(`${P}/consolidation/`, { params }),
}

export default fpaApi
