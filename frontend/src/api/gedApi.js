import api from './axios'

// GED — gestion documentaire (apps.ged). Cabinets (armoires racines) →
// dossiers arborescents (chemin matérialisé) → documents versionnés. Tout est
// scopé société côté serveur (jamais lu du corps de requête).
const gedApi = {
  // ── Cabinets (armoires racines) ──
  getCabinets: (params) => api.get('/ged/cabinets/', { params }),
  // Crée une armoire racine. `company` est posée côté serveur (jamais envoyée).
  createCabinet: (data) => api.post('/ged/cabinets/', data),

  // ── Dossiers arborescents ──
  // `params` : { cabinet, parent } — `parent='null'` pour les racines d'un
  // cabinet. Sans filtre, renvoie tous les dossiers de la société.
  getDossiers: (params) => api.get('/ged/dossiers/', { params }),
  getDescendants: (id) => api.get(`/ged/dossiers/${id}/descendants/`),
  // Crée un dossier. `data` : { cabinet, nom, parent? }. `company`/`path`
  // posés côté serveur ; le parent doit vivre dans le même cabinet.
  createDossier: (data) => api.post('/ged/dossiers/', data),
  // Renomme un dossier (PATCH partiel — seul `nom` change).
  renameDossier: (id, nom) => api.patch(`/ged/dossiers/${id}/`, { nom }),
  // Déplace un dossier sous un nouveau parent (null = remise à la racine).
  // Le backend recalcule le chemin matérialisé du sous-arbre + refuse les cycles.
  moveDossier: (id, parent) =>
    api.post(`/ged/dossiers/${id}/deplacer/`, { parent }),

  // ── Documents ──
  // `params` : { folder, coffre, tag } pour filtrer les documents (GED8/GED9).
  getDocuments: (params) => api.get('/ged/documents/', { params }),
  // Téléverse un fichier et crée le document + sa version 1 en UN appel
  // (multipart). `data` : { folder, file, nom?, description? }. Le fichier est
  // stocké via le pipeline MinIO partagé ; company/créateur posés côté serveur.
  uploadDocument: ({ folder, file, nom, description }) => {
    const fd = new FormData()
    fd.append('folder', folder)
    fd.append('file', file)
    if (nom) fd.append('nom', nom)
    if (description) fd.append('description', description)
    return api.post('/ged/documents/televerser/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ── GED13 — Recherche & filtres avancés ──
  // Recherche plein-texte Postgres (GED11) : `params` = { q }.
  searchDocuments: (params) => api.get('/ged/documents/recherche/', { params }),
  // Recherche sémantique (GED12, dégrade en plein-texte sans clé) : { q }.
  semanticSearch: (params) => api.get('/ged/documents/semantique/', { params }),
  // Taxonomie de tags (GED9) pour le filtre par tag.
  getTags: (params) => api.get('/ged/tags/', { params }),
}

export default gedApi
