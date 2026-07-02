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

  // ══════════════════════════════════════════════════════════════════════
  // UX45 — Approbation & signature électronique.
  // ══════════════════════════════════════════════════════════════════════
  // GED18 — Demandes d'approbation / revue (lecture seule en CRUD ; création
  // via `documents/<id>/demander-revue/`, décision via approuver/rejeter).
  // `params` : { document, statut, en_attente }.
  getDemandesApprobation: (params) =>
    api.get('/ged/demandes-approbation/', { params }),
  // Lance une demande d'approbation sur un document.
  // `data` : { approbateur?, commentaire? }.
  demanderRevue: (documentId, data) =>
    api.post(`/ged/documents/${documentId}/demander-revue/`, data ?? {}),
  // Approuve une demande (avance le document revue→approuvé). `data` : { commentaire? }.
  approuverDemande: (id, data) =>
    api.post(`/ged/demandes-approbation/${id}/approuver/`, data ?? {}),
  // Rejette une demande (renvoie le document en correction). `data` : { commentaire? }.
  rejeterDemande: (id, data) =>
    api.post(`/ged/demandes-approbation/${id}/rejeter/`, data ?? {}),

  // GED27/28 — Modèles de documents (fusion → PDF). `params` : { actif }.
  getModelesDocument: (params) =>
    api.get('/ged/modeles-document/', { params }),
  createModeleDocument: (data) => api.post('/ged/modeles-document/', data),
  // Fusionne + rend le PDF, sans stocker (renvoie un blob PDF).
  rendreModele: (id, contexte) =>
    api.post(`/ged/modeles-document/${id}/rendre/`, { contexte: contexte ?? {} },
      { responseType: 'blob' }),
  // Fusionne, rend le PDF et le DÉPOSE comme document GED. Renvoie { document, created }.
  genererModele: (id, contexte) =>
    api.post(`/ged/modeles-document/${id}/generer/`, { contexte: contexte ?? {} }),

  // GED30 — Demandes de signature électronique (stub no-op sans provider).
  // `params` : { document, statut }.
  getDemandesSignature: (params) =>
    api.get('/ged/demandes-signature/', { params }),
  // Crée une demande de signature. `data` : { document, signataire_nom, signataire_email }.
  createDemandeSignature: (data) => api.post('/ged/demandes-signature/', data),
  // Enregistre la complétion d'une signature (webhook/manuel). `data` : { provider_ref? }.
  marquerSigne: (id, data) =>
    api.post(`/ged/demandes-signature/${id}/marquer-signe/`, data ?? {}),

  // ══════════════════════════════════════════════════════════════════════
  // UX46 — Rétention, archivage légal & partage.
  // ══════════════════════════════════════════════════════════════════════
  // GED22 — Politiques de rétention. `params` : { actif }.
  getPolitiquesRetention: (params) =>
    api.get('/ged/politiques-retention/', { params }),
  createPolitiqueRetention: (data) =>
    api.post('/ged/politiques-retention/', data),
  updatePolitiqueRetention: (id, data) =>
    api.patch(`/ged/politiques-retention/${id}/`, data),
  deletePolitiqueRetention: (id) =>
    api.delete(`/ged/politiques-retention/${id}/`),
  // Documents ÉCHUS au regard de leur politique (consultatif — ne supprime rien).
  getDocumentsEchus: () => api.get('/ged/politiques-retention/echus/'),

  // GED23 — Archivages légaux (write-once). `params` : { document }.
  getArchivagesLegaux: (params) =>
    api.get('/ged/archivages-legaux/', { params }),
  // Archive légalement un document. `data` : { document, motif?, retain_until? }.
  createArchivageLegal: (data) => api.post('/ged/archivages-legaux/', data),

  // GED24 — Legal holds (gel anti-suppression). `params` : { document, actif }.
  getLegalHolds: (params) => api.get('/ged/legal-holds/', { params }),
  // Pose un legal hold. `data` : { document, motif? }.
  createLegalHold: (data) => api.post('/ged/legal-holds/', data),
  // Lève ce hold (et tout hold actif du même document). Renvoie { leves }.
  leverLegalHold: (id) => api.post(`/ged/legal-holds/${id}/lever/`),

  // GED20 — Partages publics tokenisés. `params` : { document, actif }.
  getPartages: (params) => api.get('/ged/partages/', { params }),
  // Crée un partage. `data` : { document, expires_at?, password?, quota_max?, watermark? }.
  createPartage: (data) => api.post('/ged/partages/', data),
  // Révoque un partage (kill-switch actif=False).
  revoquerPartage: (id) => api.post(`/ged/partages/${id}/revoquer/`),

  // GED36 — Quota de stockage société. Lecture d'état + réglage admin.
  getQuotaStockage: (params) => api.get('/ged/quotas-stockage/', { params }),
  getQuotaEtat: () => api.get('/ged/quotas-stockage/etat/'),
  // Fixe le quota (idempotent par société). `data` : { quota_octets }.
  setQuotaStockage: (data) => api.post('/ged/quotas-stockage/', data),

  // GED35 — Journal d'audit d'accès (lecture seule, responsable/admin).
  // `params` : { document, utilisateur, type_acces }.
  getJournalAcces: (params) => api.get('/ged/journal-acces/', { params }),

  // ══════════════════════════════════════════════════════════════════════
  // UX47 — Tags & liens transverses.
  // ══════════════════════════════════════════════════════════════════════
  // GED9 — Taxonomie de tags. `params` : { parent }.
  createTag: (data) => api.post('/ged/tags/', data),
  updateTag: (id, data) => api.patch(`/ged/tags/${id}/`, data),
  deleteTag: (id) => api.delete(`/ged/tags/${id}/`),
  // Documents portant ce tag (option `?descendants=1`).
  getTagDocuments: (id, params) =>
    api.get(`/ged/tags/${id}/documents/`, { params }),

  // GED9 — Affectations tag↔document (M2M explicite). `params` : { document, tag }.
  getTagAssignments: (params) =>
    api.get('/ged/tag-assignments/', { params }),
  // Affecte un tag à un document. `data` : { document, tag }.
  createTagAssignment: (data) => api.post('/ged/tag-assignments/', data),
  deleteTagAssignment: (id) => api.delete(`/ged/tag-assignments/${id}/`),

  // GED6 — Liens polymorphes document↔objet métier. `params` : { document } OU
  // reverse lookup { model, id } (ex. model='ventes.devis').
  getLiens: (params) => api.get('/ged/liens/', { params }),
  // Crée un lien. `data` : { document, model, id }.
  createLien: (data) => api.post('/ged/liens/', data),
  deleteLien: (id) => api.delete(`/ged/liens/${id}/`),

  // Documents (réutilisé par les écrans avancés pour peupler les sélecteurs).
  getDocumentsList: (params) => api.get('/ged/documents/', { params }),
}

export default gedApi
