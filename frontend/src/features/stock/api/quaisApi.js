import api from '../../../api/axios'

/* ASTK218 — wrappers de l'écran « Quais & rendez-vous » (contrat
   wms_quais.json). Module dédié (jamais stockApi.js : lanes d'écrans
   disjointes). */
const quaisApi = {
  listQuais: (params) => api.get('/stock/quais/', { params }),
  saveQuai: (id, data) => (id
    ? api.patch(`/stock/quais/${id}/`, data)
    : api.post('/stock/quais/', data)),
  planning: (params) => api.get('/stock/quais/planning/', { params }),
  listRendezVous: (params) => api.get('/stock/rendez-vous-transporteur/', { params }),
  creerRendezVous: (data) => api.post('/stock/rendez-vous-transporteur/', data),
  // Annuler = statut `annule` (libère le créneau).
  annulerRendezVous: (id) => api.patch(`/stock/rendez-vous-transporteur/${id}/`, { statut: 'annule' }),
  listUnites: (params) => api.get('/stock/unites-logistiques/', { params }),
  exportAsn: (id) => api.get(`/stock/unites-logistiques/${id}/export-asn/`),
  // L'ASN importé est le document JSON lui-même (corps de la requête).
  importAsn: (document) => api.post('/stock/unites-logistiques/import-asn/', document),
  listEmplacements: () => api.get('/stock/emplacements/'),
}

export default quaisApi
