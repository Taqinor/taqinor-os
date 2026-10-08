import api from '../../../api/axios'

/* ASTK221 — wrappers de l'écran « Consignation » (contrat
   negoce_consignation_rfa.json) : dépôts chez les clients, déclaration de
   consommation, relevé PDF, export, réglages négoce. Module dédié (jamais
   stockApi.js : lanes d'écrans disjointes). */
const negoceApi = {
  listConsignations: (params) => api.get('/stock/consignations/', { params }),
  creerConsignation: (corps) => api.post('/stock/consignations/', corps),
  declarerConsommation: (id, corps) =>
    api.post(`/stock/consignations/${id}/declarer-consommation/`, corps),
  releve: (id) => api.get(`/stock/consignations/${id}/releve/`),
  // Binaires (PDF / XLSX) : lus en Blob.
  relevePdf: (id) => api.get(`/stock/consignations/${id}/releve-pdf/`, { responseType: 'blob' }),
  exportXlsx: (params) =>
    api.get('/stock/consignations/export-xlsx/', { params, responseType: 'blob' }),
  // Réglages négoce (singleton de la société).
  getParametres: () => api.get('/stock/parametres-negoce/'),
  setParametres: (corps) => api.patch('/stock/parametres-negoce/', corps),
  // Sélecteurs.
  listClients: (params) => api.get('/crm/clients/', { params }),
  listProduits: (params) => api.get('/stock/produits/', { params }),
}

export default negoceApi
