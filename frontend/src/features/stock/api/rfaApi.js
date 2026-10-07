import api from '../../../api/axios'

/* ASTK222 — wrappers de l'écran « Remises arrière (RFA) » (contrat
   negoce_consignation_rfa.json, routes accords_rfa_fournisseur /
   accord_rfa_calcul / accord_rfa_generer_avoir). Module dédié (jamais
   stockApi.js : lanes d'écrans disjointes). */
const rfaApi = {
  listAccords: (params) => api.get('/stock/accords-rfa-fournisseur/', { params }),
  creerAccord: (corps) => api.post('/stock/accords-rfa-fournisseur/', corps),
  calcul: (id) => api.get(`/stock/accords-rfa-fournisseur/${id}/calcul/`),
  genererAvoir: (id) => api.post(`/stock/accords-rfa-fournisseur/${id}/generer-avoir/`),
  listFournisseurs: (params) => api.get('/stock/fournisseurs/', { params }),
}

export default rfaApi
