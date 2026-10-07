import api from '../../../api/axios'

/* ASTK223 — wrappers de la gestion des liens 3PL (contrat
   negoce_consignation_rfa.json, route portails_tiers). Administration réservée
   à l'admin côté serveur. Module dédié (jamais stockApi.js). */
const portailsTiersApi = {
  list: (params) => api.get('/stock/portails-tiers/', { params }),
  // Le jeton est généré côté serveur : seul le nom du dépositaire est envoyé.
  generer: (tiersNom) => api.post('/stock/portails-tiers/', { tiers_nom: tiersNom }),
  // La révocation passe `revoked=true` (jamais un DELETE).
  revoquer: (id) => api.patch(`/stock/portails-tiers/${id}/`, { revoked: true }),
}

export default portailsTiersApi
