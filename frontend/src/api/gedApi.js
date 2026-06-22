import api from './axios'

// GED — gestion documentaire (apps.ged). Cabinets (armoires racines) →
// dossiers arborescents (chemin matérialisé) → documents versionnés. Tout est
// scopé société côté serveur (jamais lu du corps de requête).
const gedApi = {
  // ── Cabinets (armoires racines) ──
  getCabinets: (params) => api.get('/ged/cabinets/', { params }),

  // ── Dossiers arborescents ──
  // `params` : { cabinet, parent } — `parent='null'` pour les racines d'un
  // cabinet. Sans filtre, renvoie tous les dossiers de la société.
  getDossiers: (params) => api.get('/ged/dossiers/', { params }),
  getDescendants: (id) => api.get(`/ged/dossiers/${id}/descendants/`),

  // ── Documents ──
  // `params` : { folder } pour lister les documents d'un dossier donné.
  getDocuments: (params) => api.get('/ged/documents/', { params }),
}

export default gedApi
