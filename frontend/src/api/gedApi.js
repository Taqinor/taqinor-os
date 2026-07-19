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

  // XGED12 — Capture mobile photo → PDF multi-pages classé en GED. `photos`
  // : tableau de `File`/`Blob` (déjà recadrées/pivotées côté client via
  // canvas), une par page dans l'ordre de capture. `folder` cible ; `nom`/
  // `description` optionnels. L'assemblage PDF (Pillow) est CÔTÉ SERVEUR ;
  // le résultat passe par le MÊME chemin que `televerser` (document + v1).
  assemblerPhotos: ({ folder, photos, nom, description }) => {
    const fd = new FormData()
    fd.append('folder', folder)
    photos.forEach((photo) => fd.append('photos', photo))
    if (nom) fd.append('nom', nom)
    if (description) fd.append('description', description)
    return api.post('/ged/documents/assembler-photos/', fd, {
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

  // ══════════════════════════════════════════════════════════════════════
  // XGED1/XGED2 — Cérémonie de signature PUBLIQUE (sans login, loi 53-05).
  // Résolue par jeton uniquement ; ces routes sont AllowAny côté serveur.
  // ══════════════════════════════════════════════════════════════════════
  // Consulte une demande de signature mono-signataire (métadonnées + champs).
  getSignaturePublique: (token) => api.get(`/ged/signature/${token}/`),
  // Signe : { consentement, signature_texte?, signature_tracee?, valeurs_champs? }.
  signerPublique: (token, data) =>
    api.post(`/ged/signature/${token}/`, { action: 'signer', ...(data ?? {}) }),
  // Refuse : { motif }.
  refuserPublique: (token, data) =>
    api.post(`/ged/signature/${token}/`, { action: 'refuser', ...(data ?? {}) }),

  // XGED2 — jeton PROPRE à un destinataire du circuit multi-signataires.
  getSignatairePublique: (token) => api.get(`/ged/signataire/${token}/`),
  signerSignataire: (token, data) =>
    api.post(`/ged/signataire/${token}/`, { action: 'signer', ...(data ?? {}) }),
  refuserSignataire: (token, data) =>
    api.post(`/ged/signataire/${token}/`, { action: 'refuser', ...(data ?? {}) }),
  // ZGED2 — code d'authentification extra (OTP) avant de débloquer la signature.
  envoyerCodeSignataire: (token) =>
    api.post(`/ged/signataire/${token}/`, { action: 'envoyer-code' }),
  validerCodeSignataire: (token, code) =>
    api.post(`/ged/signataire/${token}/`, { action: 'valider-code', code }),

  // ══════════════════════════════════════════════════════════════════════
  // XGED7 — Lien PUBLIC de DÉPÔT (upload-request, sans login).
  // ══════════════════════════════════════════════════════════════════════
  // Infos du lien (message d'instruction + quota restant).
  getDepotPublic: (token) => api.get(`/ged/depot/${token}/`),
  // Dépose un fichier via le lien. `data` : { file, nom?, email? }.
  deposerPublique: (token, { file, nom, email }) => {
    const fd = new FormData()
    fd.append('file', file)
    if (nom) fd.append('nom', nom)
    if (email) fd.append('email', email)
    return api.post(`/ged/depot/${token}/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // XGED2 — circuit multi-signataires (ordre/rôle) sur une demande.
  // Création groupée : `data` = { document, destinataires:[{nom,email?,
  // telephone?,role?,ordre?,role_signataire?}], routage?, expires_at?,
  // relance_cadence_jours? } → services.creer_demande_multi_signataires.
  creerDemandeMultiSignataires: (data) =>
    api.post('/ged/demandes-signature/creer-multi/', data),
  // Destinataires (LECTURE SEULE — créés via creer-multi).
  getSignatairesDemande: (params) =>
    api.get('/ged/signataires-demande/', { params }),
  // Rôles de signataire réutilisables (approbateur/témoin/…), CRUD.
  getRolesSignataire: (params) => api.get('/ged/roles-signataire/', { params }),
  // XGED3 — champs de signature positionnés (page/x/y) sur une demande, CRUD.
  getChampsSignature: (params) => api.get('/ged/champs-signature/', { params }),
  createChampSignature: (data) => api.post('/ged/champs-signature/', data),
  deleteChampSignature: (id) => api.delete(`/ged/champs-signature/${id}/`),
  getTypesChampSignature: (params) =>
    api.get('/ged/types-champ-signature/', { params }),
  // ZGED3 — tableau de bord / kanban des demandes de signature.
  getTableauBordSignatures: (params) =>
    api.get('/ged/demandes-signature/tableau-bord/', { params }),
  // XGED2 — annuler une demande (action émetteur).
  annulerDemandeSignature: (id) =>
    api.post(`/ged/demandes-signature/${id}/annuler/`),

  // GED14 — aperçu inline même-origine d'une version (proxy binaire Django).
  // URL directe (consommée par <iframe>/<img> src, pas un appel axios JSON).
  apercuVersionUrl: (versionId) =>
    `/api/django/ged/versions/${versionId}/apercu/`,
  // Versions d'un document (pour choisir la version à prévisualiser).
  getVersions: (params) => api.get('/ged/versions/', { params }),

  // ══════════════════════════════════════════════════════════════════════
  // GED26 — Corbeille (soft-delete réversible + purge définitive).
  // ══════════════════════════════════════════════════════════════════════
  getCorbeille: (params) => api.get('/ged/documents/corbeille/', { params }),
  mettreEnCorbeille: (id) =>
    api.post(`/ged/documents/${id}/mettre-en-corbeille/`),
  restaurerCorbeille: (id) =>
    api.post(`/ged/documents/${id}/restaurer-corbeille/`),
  purgerDocument: (id) => api.post(`/ged/documents/${id}/purger/`),

  // GED16 — Check-out / check-in (verrou d'extraction).
  checkOutDocument: (id) => api.post(`/ged/documents/${id}/check-out/`),
  checkInDocument: (id) => api.post(`/ged/documents/${id}/check-in/`),

  // XGED14 — Opérations en lot sur une multi-sélection de documents.
  // `data` : { documents:[<id>,...], operation:'tagger'|'detaguer'|'deplacer'|
  // 'corbeille'|'partager'|'demander_signature'|'demander_revue', params?:{} }.
  operationsLot: (data) => api.post('/ged/documents/operations-lot/', data),

  // ══════════════════════════════════════════════════════════════════════
  // WIR70 — surfaces GED déjà exposées mais sans consommateur frontend.
  // ══════════════════════════════════════════════════════════════════════
  // Timeline d'un document (audit chronologique).
  getTimeline: (id) => api.get(`/ged/documents/${id}/timeline/`),
  // Rapport ACL « qui voit ce document et pourquoi » (+ export CSV).
  getPermissionsEffectives: (id) =>
    api.get(`/ged/documents/${id}/permissions-effectives/`),
  exportPermissionsEffectivesCsv: (id) =>
    api.get(`/ged/documents/${id}/permissions-effectives/`,
      { params: { format: 'csv' }, responseType: 'blob' }),
  // ZGED7 — favori personnel (toggle) : renvoie { favori: bool } après bascule.
  toggleFavoriDocument: (id, favori) =>
    api.post(`/ged/documents/${id}/favori/`, { favori }),
  // GED35 — mes documents récents / mes favoris (personnels, jamais d'un collègue).
  getMesRecents: (params) => api.get('/ged/mes-recents/', { params }),
  getMesFavoris: () => api.get('/ged/mes-favoris/'),
  // XGED26 — analytique workflow & signature (gestion/admin).
  getAnalytique: (params) => api.get('/ged/analytique/', { params }),
  // Vues enregistrées (filtres sauvegardés) partagées de la société.
  getVues: (params) => api.get('/ged/vues/', { params }),
  // Lien de dépôt public tokenisé (la page publique PublicDepotPage fonctionne).
  getDepotsPublics: (params) => api.get('/ged/depots-publics/', { params }),
  createDepotPublic: (data) => api.post('/ged/depots-publics/', data),
}

export default gedApi
