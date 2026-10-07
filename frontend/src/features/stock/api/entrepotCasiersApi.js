import api from '../../../api/axios'

/* ASTK215 — wrappers de l'écran « Casiers » (contrat wms_casiers.json).
   Module dédié (jamais stockApi.js : lanes d'écrans disjointes). Le préfixe
   /api/django est posé par l'instance axios. */
const entrepotCasiersApi = {
  // Seuils de réappro par casier (CRUD).
  listSeuils: (params) => api.get('/stock/seuils-reappro-casier/', { params }),
  createSeuil: (data) => api.post('/stock/seuils-reappro-casier/', data),
  updateSeuil: (id, data) => api.patch(`/stock/seuils-reappro-casier/${id}/`, data),
  deleteSeuil: (id) => api.delete(`/stock/seuils-reappro-casier/${id}/`),
  // Tâches de réappro interne.
  listTaches: (params) => api.get('/stock/taches-reappro-interne/', { params }),
  // « Exécuter » : action serveur NOUVELLE (ASTK213) — non appelée tant qu'elle n'existe pas.
  // Casiers sous seuil (GET = lecture ; POST = génère les tâches).
  casiersSousSeuil: () => api.get('/stock/casiers-a-reapprovisionner/'),
  genererTaches: () => api.post('/stock/casiers-a-reapprovisionner/'),
  // Historique d'un casier (auteur affiché).
  historiqueCasier: (binId) => api.get(`/stock/casiers/${binId}/historique/`),
  // Planche d'étiquettes (binaire).
  etiquettesPdf: (emplacement, symbology = 'qr') =>
    api.get('/stock/casiers/etiquettes-pdf/', {
      params: { emplacement, symbology }, responseType: 'blob',
    }),
  reslotting: (params) => api.get('/stock/reslotting-suggestions/', { params }),
  // Sélecteurs.
  // Casiers adressables (BinLocation) : l'id attendu par seuil/tâches/historique.
  listCasiers: () => api.get('/installations/bin-locations/'),
  // Emplacements de stock : la planche d'étiquettes se demande par emplacement.
  listEmplacements: () => api.get('/stock/emplacements/'),
  listProduits: (params) => api.get('/stock/produits/', { params }),
}

export default entrepotCasiersApi
