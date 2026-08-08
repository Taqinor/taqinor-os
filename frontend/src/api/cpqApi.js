import api from './axios'

/* ============================================================================
   CPQ (apps.cpq) — client API.
   ----------------------------------------------------------------------------
   PACT129 — le configurateur CPQ n'avait AUCUN fichier client (module entier
   jamais exposé, Groupe PACT §E4). Ce fichier ne couvre POUR L'INSTANT que
   les prix contractuels (NTCPQ5, montés en onglet « Tarifs négociés » sur la
   fiche client) — le reste du module (règles produit, offres groupées,
   configurateur) reste hors périmètre de cette tâche.
   ========================================================================== */

const cpqApi = {
  // Aucun filtre serveur par client (`PrixContractuelViewSet` ne déclare pas
  // de `filterset_fields` — le filtrage par client se fait CÔTÉ CLIENT sur
  // la réponse, jamais un `?client=` inventé que le serveur ignorerait).
  getPrixContractuels: (params) => api.get('/cpq/prix-contractuels/', { params }),
  // `data` : { client, produit, prix_ht, date_debut?, date_fin?, motif? } —
  // réservé Directeur/Commercial responsable (403 serveur sinon).
  createPrixContractuel: (data) => api.post('/cpq/prix-contractuels/', data),
  updatePrixContractuel: (id, data) => api.patch(`/cpq/prix-contractuels/${id}/`, data),
  deletePrixContractuel: (id) => api.delete(`/cpq/prix-contractuels/${id}/`),
}

export default cpqApi
