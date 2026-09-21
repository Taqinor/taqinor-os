import api from './axios'

/* ============================================================================
   Hôtellerie & restauration (apps/hospitality) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /hospitality/... ».
   Groupe NTHOT (docs/plans/PLAN_VERTICALS.md).
   ========================================================================== */

const hospitalityApi = {
  // ── Types de chambre ──
  listTypesChambre: (params) => api.get('/hospitality/types-chambre/', { params }),
  createTypeChambre: (data) => api.post('/hospitality/types-chambre/', data),

  // ── Chambres (NTHOT1) ── ?statut= filtre le plan des chambres.
  listChambres: (params) => api.get('/hospitality/chambres/', { params }),
  getChambre: (id) => api.get(`/hospitality/chambres/${id}/`),
  createChambre: (data) => api.post('/hospitality/chambres/', data),
  updateChambre: (id, data) => api.patch(`/hospitality/chambres/${id}/`, data),

  // ── Plans tarifaires (NTHOT2) ──
  listPlansTarifaires: (params) => api.get('/hospitality/plans-tarifaires/', { params }),
  createPlanTarifaire: (data) => api.post('/hospitality/plans-tarifaires/', data),

  // ── Réservations (NTHOT3) ── ?statut=&date_arrivee= filtres.
  listReservations: (params) => api.get('/hospitality/reservations/', { params }),
  getReservation: (id) => api.get(`/hospitality/reservations/${id}/`),
  createReservation: (data) => api.post('/hospitality/reservations/', data),

  // ── Check-in / check-out (NTHOT5/NTHOT6) ── WIR146 : jusque-là exposés
  // côté client mais jamais consommés par aucun écran.
  checkIn: (id, data) => api.post(`/hospitality/reservations/${id}/check-in/`, data),
  checkOut: (id, data) => api.post(`/hospitality/reservations/${id}/check-out/`, data),
  fichesPolice: (id) => api.get(`/hospitality/reservations/${id}/fiches-police/`),
  fichePolicePdf: (id) =>
    api.get(`/hospitality/reservations/${id}/fiche-police-pdf/`, { responseType: 'blob' }),
  fichePolicePdfUrl: (id) =>
    `/api/django/hospitality/reservations/${id}/fiche-police-pdf/`,

  // ── Recettes / menu (NTHOT13) ── WIR146.
  listRecettes: (params) => api.get('/hospitality/recettes/', { params }),
  createRecette: (data) => api.post('/hospitality/recettes/', data),
  updateRecette: (id, data) => api.patch(`/hospitality/recettes/${id}/`, data),
  listIngredientsRecette: (recetteId) =>
    api.get(`/hospitality/recettes/${recetteId}/ingredients/`),
  ajouterIngredientRecette: (recetteId, data) =>
    api.post(`/hospitality/recettes/${recetteId}/ingredients/`, data),
  retirerIngredientRecette: (recetteId, ingredientId) =>
    api.delete(`/hospitality/recettes/${recetteId}/ingredients/${ingredientId}/`),

  // ── Salles & événements banquets (NTHOT17/NTHOT18/NTHOT19) ── WIR146.
  listSallesEvenement: (params) => api.get('/hospitality/salles-evenement/', { params }),
  createSalleEvenement: (data) => api.post('/hospitality/salles-evenement/', data),
  listEvenementsBanquet: (params) => api.get('/hospitality/evenements/', { params }),
  createEvenementBanquet: (data) => api.post('/hospitality/evenements/', data),
  updateEvenementBanquet: (id, data) => api.patch(`/hospitality/evenements/${id}/`, data),
  genererDevisEvenement: (id) =>
    api.post(`/hospitality/evenements/${id}/generer-devis/`),
  beoPdf: (id) =>
    api.get(`/hospitality/evenements/${id}/beo-pdf/`, { responseType: 'blob' }),

  // ── Folio (NTHOT7) ──
  getFolio: (id) => api.get(`/hospitality/folios/${id}/`),
  cloturerFolio: (id) => api.post(`/hospitality/folios/${id}/cloturer/`),

  // ── Housekeeping (NTHOT9) ──
  listTachesMenage: (params) => api.get('/hospitality/taches-menage/', { params }),
  terminerTacheMenage: (id) =>
    api.post(`/hospitality/taches-menage/${id}/terminer/`),

  // ── Tableau de bord RevPAR/ADR/TO (NTHOT11) ──
  tableauBord: (params) => api.get('/hospitality/tableau-bord/', { params }),

  // ── Main courante / passations d'équipe (NTHOT12) ── journal append-only.
  listMainCourante: (params) => api.get('/hospitality/main-courante/', { params }),
  createMainCourante: (data) => api.post('/hospitality/main-courante/', data),

  // ── WIR8 — Taxe de séjour paramétrable (singleton société) ──
  // Tant qu'aucune ligne n'est configurée, `services.cloturer_folio` retombe
  // silencieusement sur Decimal('0') — c'est le SEUL chemin d'écriture hors
  // admin Django.
  getParametresTaxeSejour: () => api.get('/hospitality/parametres-taxe-sejour/'),
  saveParametresTaxeSejour: (data) =>
    api.patch('/hospitality/parametres-taxe-sejour/', data),
}

export default hospitalityApi
