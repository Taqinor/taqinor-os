import api from './axios'

/* ============================================================================
   UX38–UX42 — Client API de la Gestion de projet.
   ----------------------------------------------------------------------------
   Miroir 1:1 du backend `apps/gestion_projet` (préfixe `/gestion-projet/`,
   noter le TIRET). Toutes les données sont scopées société côté serveur ; le
   palier d'accès est Administrateur/Responsable. Aucun prix d'achat / marge
   n'est jamais rendu côté client — les montants passent par `formatMAD`.
   ========================================================================== */

const P = '/gestion-projet'

const gestionProjetApi = {
  // ── Projets (UX38) + machine à états serveur ──────────────────────────────
  getProjets: (params) => api.get(`${P}/projets/`, { params }),
  getProjet: (id) => api.get(`${P}/projets/${id}/`),
  createProjet: (data) => api.post(`${P}/projets/`, data),
  updateProjet: (id, data) => api.patch(`${P}/projets/${id}/`, data),
  deleteProjet: (id) => api.delete(`${P}/projets/${id}/`),
  // Transitions de statut (POST) — chacune valide l'état courant côté serveur.
  planifierProjet: (id) => api.post(`${P}/projets/${id}/planifier/`),
  demarrerProjet: (id) => api.post(`${P}/projets/${id}/demarrer/`),
  mettreEnPauseProjet: (id) => api.post(`${P}/projets/${id}/mettre-en-pause/`),
  reprendreProjet: (id) => api.post(`${P}/projets/${id}/reprendre/`),
  terminerProjet: (id) => api.post(`${P}/projets/${id}/terminer/`),
  annulerProjet: (id) => api.post(`${P}/projets/${id}/annuler/`),
  getProjetHistorique: (id) => api.get(`${P}/projets/${id}/historique/`),
  getProjetLiens: (id) => api.get(`${P}/projets/${id}/liens/`),
  getProjetTaches: (id) => api.get(`${P}/projets/${id}/taches/`),
  getProjetGantt: (id) => api.get(`${P}/projets/${id}/gantt/`),
  getProjetAvancement: (id) => api.get(`${P}/projets/${id}/avancement/`),
  getProjetJalons: (id) => api.get(`${P}/projets/${id}/jalons/`),
  instancierPhases: (id) => api.post(`${P}/projets/${id}/instancier-phases/`),
  prendreBaseline: (id, data) => api.post(`${P}/projets/${id}/baseline/`, data),
  getProjetBaselines: (id) => api.get(`${P}/projets/${id}/baselines/`),
  cloturerProjet: (id, data) => api.post(`${P}/projets/${id}/cloturer/`, data),
  getPortefeuille: (params) => api.get(`${P}/projets/portefeuille/`, { params }),
  getProjetCoutsEngagesReels: (id) =>
    api.get(`${P}/projets/${id}/couts-engages-reels/`),
  getProjetPnl: (id) => api.get(`${P}/projets/${id}/pnl/`),

  // ── Chantiers & liens (UX38) ──────────────────────────────────────────────
  getChantiers: (params) => api.get(`${P}/projet-chantiers/`, { params }),
  createChantier: (data) => api.post(`${P}/projet-chantiers/`, data),
  updateChantier: (id, data) => api.patch(`${P}/projet-chantiers/${id}/`, data),
  deleteChantier: (id) => api.delete(`${P}/projet-chantiers/${id}/`),
  getLiens: (params) => api.get(`${P}/projet-liens/`, { params }),
  createLien: (data) => api.post(`${P}/projet-liens/`, data),
  updateLien: (id, data) => api.patch(`${P}/projet-liens/${id}/`, data),
  deleteLien: (id) => api.delete(`${P}/projet-liens/${id}/`),
  getClotures: (params) => api.get(`${P}/clotures/`, { params }),
  updateCloture: (id, data) => api.patch(`${P}/clotures/${id}/`, data),

  // ── Planning Gantt (UX39) ─────────────────────────────────────────────────
  getPhases: (params) => api.get(`${P}/phases/`, { params }),
  createPhase: (data) => api.post(`${P}/phases/`, data),
  updatePhase: (id, data) => api.patch(`${P}/phases/${id}/`, data),
  deletePhase: (id) => api.delete(`${P}/phases/${id}/`),
  getTaches: (params) => api.get(`${P}/taches/`, { params }),
  createTache: (data) => api.post(`${P}/taches/`, data),
  updateTache: (id, data) => api.patch(`${P}/taches/${id}/`, data),
  deleteTache: (id) => api.delete(`${P}/taches/${id}/`),
  // Drag calendrier : reprogrammer une tâche (+ cascade successeurs) (XPRJ11).
  reprogrammerTache: (id, data) =>
    api.post(`${P}/taches/${id}/reprogrammer/`, data),
  getDependances: (params) => api.get(`${P}/dependances/`, { params }),
  createDependance: (data) => api.post(`${P}/dependances/`, data),
  deleteDependance: (id) => api.delete(`${P}/dependances/${id}/`),
  getJalons: (params) => api.get(`${P}/jalons/`, { params }),
  createJalon: (data) => api.post(`${P}/jalons/`, data),
  updateJalon: (id, data) => api.patch(`${P}/jalons/${id}/`, data),
  deleteJalon: (id) => api.delete(`${P}/jalons/${id}/`),
  getCalendriers: (params) => api.get(`${P}/calendriers/`, { params }),
  createCalendrier: (data) => api.post(`${P}/calendriers/`, data),
  updateCalendrier: (id, data) => api.patch(`${P}/calendriers/${id}/`, data),
  getJoursFeries: (params) => api.get(`${P}/jours-feries/`, { params }),
  createJourFerie: (data) => api.post(`${P}/jours-feries/`, data),
  deleteJourFerie: (id) => api.delete(`${P}/jours-feries/${id}/`),
  getBaselines: (params) => api.get(`${P}/baselines/`, { params }),

  // ── Ressources & capacité (UX40) ──────────────────────────────────────────
  getRessources: (params) => api.get(`${P}/ressources/`, { params }),
  createRessource: (data) => api.post(`${P}/ressources/`, data),
  updateRessource: (id, data) => api.patch(`${P}/ressources/${id}/`, data),
  deleteRessource: (id) => api.delete(`${P}/ressources/${id}/`),
  getPlanDeCharge: (params) =>
    api.get(`${P}/ressources/plan-de-charge/`, { params }),
  getConflitsAffectation: (params) =>
    api.get(`${P}/ressources/conflits-affectation/`, { params }),
  getEquipes: (params) => api.get(`${P}/equipes/`, { params }),
  createEquipe: (data) => api.post(`${P}/equipes/`, data),
  updateEquipe: (id, data) => api.patch(`${P}/equipes/${id}/`, data),
  deleteEquipe: (id) => api.delete(`${P}/equipes/${id}/`),
  getAffectations: (params) => api.get(`${P}/affectations/`, { params }),
  createAffectation: (data) => api.post(`${P}/affectations/`, data),
  updateAffectation: (id, data) => api.patch(`${P}/affectations/${id}/`, data),
  deleteAffectation: (id) => api.delete(`${P}/affectations/${id}/`),
  getIndisponibilites: (params) =>
    api.get(`${P}/indisponibilites/`, { params }),
  createIndisponibilite: (data) => api.post(`${P}/indisponibilites/`, data),
  deleteIndisponibilite: (id) => api.delete(`${P}/indisponibilites/${id}/`),
  getTimesheets: (params) => api.get(`${P}/timesheets/`, { params }),
  createTimesheet: (data) => api.post(`${P}/timesheets/`, data),
  updateTimesheet: (id, data) => api.patch(`${P}/timesheets/${id}/`, data),
  deleteTimesheet: (id) => api.delete(`${P}/timesheets/${id}/`),
  // Grille hebdomadaire de saisie des temps (XPRJ6).
  getGrilleSemaineTemps: (params) =>
    api.get(`${P}/timesheets/semaine/`, { params }),
  copierSemaineTimesheets: (data) =>
    api.post(`${P}/timesheets/copier-semaine/`, data),

  // ── Budget & P&L (UX41) ───────────────────────────────────────────────────
  getBudgets: (params) => api.get(`${P}/budgets/`, { params }),
  createBudget: (data) => api.post(`${P}/budgets/`, data),
  updateBudget: (id, data) => api.patch(`${P}/budgets/${id}/`, data),
  deleteBudget: (id) => api.delete(`${P}/budgets/${id}/`),
  getBudgetTotal: (id) => api.get(`${P}/budgets/${id}/total/`),
  getLignesBudget: (params) => api.get(`${P}/lignes-budget/`, { params }),
  createLigneBudget: (data) => api.post(`${P}/lignes-budget/`, data),
  updateLigneBudget: (id, data) =>
    api.patch(`${P}/lignes-budget/${id}/`, data),
  deleteLigneBudget: (id) => api.delete(`${P}/lignes-budget/${id}/`),

  // ── Risques, actions, CR & doc (UX42) ─────────────────────────────────────
  getRisques: (params) => api.get(`${P}/risques/`, { params }),
  createRisque: (data) => api.post(`${P}/risques/`, data),
  updateRisque: (id, data) => api.patch(`${P}/risques/${id}/`, data),
  deleteRisque: (id) => api.delete(`${P}/risques/${id}/`),
  getActions: (params) => api.get(`${P}/actions/`, { params }),
  createAction: (data) => api.post(`${P}/actions/`, data),
  updateAction: (id, data) => api.patch(`${P}/actions/${id}/`, data),
  deleteAction: (id) => api.delete(`${P}/actions/${id}/`),
  getComptesRendus: (params) => api.get(`${P}/comptes-rendus/`, { params }),
  createCompteRendu: (data) => api.post(`${P}/comptes-rendus/`, data),
  updateCompteRendu: (id, data) =>
    api.patch(`${P}/comptes-rendus/${id}/`, data),
  deleteCompteRendu: (id) => api.delete(`${P}/comptes-rendus/${id}/`),
  getDocuments: (params) => api.get(`${P}/documents/`, { params }),
  createDocument: (data) => api.post(`${P}/documents/`, data),
  deleteDocument: (id) => api.delete(`${P}/documents/${id}/`),
  getDocumentVersions: (id) => api.get(`${P}/documents/${id}/versions/`),
  getCommentaires: (params) => api.get(`${P}/commentaires/`, { params }),
  createCommentaire: (data) => api.post(`${P}/commentaires/`, data),
  deleteCommentaire: (id) => api.delete(`${P}/commentaires/${id}/`),
  getModeles: (params) => api.get(`${P}/modeles/`, { params }),
  createModele: (data) => api.post(`${P}/modeles/`, data),
  updateModele: (id, data) => api.patch(`${P}/modeles/${id}/`, data),
  deleteModele: (id) => api.delete(`${P}/modeles/${id}/`),
  instancierModele: (id, data) =>
    api.post(`${P}/modeles/${id}/instancier/`, data),
  getModeleTaches: (params) => api.get(`${P}/modele-taches/`, { params }),
  createModeleTache: (data) => api.post(`${P}/modele-taches/`, data),
  deleteModeleTache: (id) => api.delete(`${P}/modele-taches/${id}/`),
  getSousTraitants: (params) => api.get(`${P}/sous-traitants/`, { params }),
  createSousTraitant: (data) => api.post(`${P}/sous-traitants/`, data),
  updateSousTraitant: (id, data) =>
    api.patch(`${P}/sous-traitants/${id}/`, data),
  deleteSousTraitant: (id) => api.delete(`${P}/sous-traitants/${id}/`),
  getLotsSousTraitance: (params) =>
    api.get(`${P}/lots-sous-traitance/`, { params }),
  createLotSousTraitance: (data) =>
    api.post(`${P}/lots-sous-traitance/`, data),
  updateLotSousTraitance: (id, data) =>
    api.patch(`${P}/lots-sous-traitance/${id}/`, data),
  deleteLotSousTraitance: (id) =>
    api.delete(`${P}/lots-sous-traitance/${id}/`),
}

export default gestionProjetApi
