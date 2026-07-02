import api from './axios'

/* ============================================================================
   Litiges & réclamations (apps/litiges) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /litiges/... ».
   Un seul point d'import pour tous les écrans du module (UX44).
   Basename DRF confirmé côté backend : reclamations. @actions liste :
   tableau-bord / analyse-concurrents. @actions détail : prendre-en-charge /
   resoudre / rejeter (machine à états, statut posé côté serveur) + historique /
   noter (chatter).
   ========================================================================== */

const litigesApi = {
  // ── Réclamations (CRUD + recherche/filtres) ──
  // ?search= (reference/objet/description), ?ordering= (id/gravite/date_creation).
  // ``statut`` est en lecture seule (read_only) : jamais posté au PATCH ; il
  // évolue via les transitions ci-dessous. ``bloque_relances`` est modifiable.
  list: (params) => api.get('/litiges/reclamations/', { params }),
  get: (id) => api.get(`/litiges/reclamations/${id}/`),
  create: (data) => api.post('/litiges/reclamations/', data),
  update: (id, data) => api.patch(`/litiges/reclamations/${id}/`, data),
  remove: (id) => api.delete(`/litiges/reclamations/${id}/`),

  // ── Cockpit / intelligence (lecture seule) ──
  // ?debut=YYYY-MM-DD&fin=YYYY-MM-DD (bornes inclusives, optionnelles).
  tableauBord: (params) =>
    api.get('/litiges/reclamations/tableau-bord/', { params }),
  analyseConcurrents: () =>
    api.get('/litiges/reclamations/analyse-concurrents/'),

  // ── Machine à états (POST, aucun corps requis) ──
  prendreEnCharge: (id) =>
    api.post(`/litiges/reclamations/${id}/prendre-en-charge/`),
  resoudre: (id) => api.post(`/litiges/reclamations/${id}/resoudre/`),
  rejeter: (id) => api.post(`/litiges/reclamations/${id}/rejeter/`),

  // ── Chatter (historique + note libre) ──
  historique: (id) => api.get(`/litiges/reclamations/${id}/historique/`),
  noter: (id, message) =>
    api.post(`/litiges/reclamations/${id}/noter/`, { message }),
}

export default litigesApi
