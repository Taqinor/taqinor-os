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
  // `params` : { folder, coffre, tag } pour filtrer les documents (GED8/GED9).
  getDocuments: (params) => api.get('/ged/documents/', { params }),

  // ── GED13 — Recherche & filtres avancés ──
  // Recherche plein-texte Postgres (GED11) : `params` = { q }.
  searchDocuments: (params) => api.get('/ged/documents/recherche/', { params }),
  // Recherche sémantique (GED12, dégrade en plein-texte sans clé) : { q }.
  semanticSearch: (params) => api.get('/ged/documents/semantique/', { params }),
  // Taxonomie de tags (GED9) pour le filtre par tag.
  getTags: (params) => api.get('/ged/tags/', { params }),
}

export default gedApi
