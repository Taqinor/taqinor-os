import api from './axios'

const installationsApi = {
  // Chantiers
  getInstallations: (params) => api.get('/installations/chantiers/', { params }),
  getInstallation: (id) => api.get(`/installations/chantiers/${id}/`),
  createInstallation: (data) => api.post('/installations/chantiers/', data),
  updateInstallation: (id, data) => api.patch(`/installations/chantiers/${id}/`, data),
  deleteInstallation: (id) => api.delete(`/installations/chantiers/${id}/`),
  createFromDevis: (devisId) =>
    api.post('/installations/chantiers/creer-depuis-devis/', { devis: devisId }),
  getHistorique: (id) => api.get(`/installations/chantiers/${id}/historique/`),
  noter: (id, body) => api.post(`/installations/chantiers/${id}/noter/`, { body }),
  miseEnService: (id, data) =>
    api.post(`/installations/chantiers/${id}/mise-en-service/`, data),
  annuler: (id, motif) => api.post(`/installations/chantiers/${id}/annuler/`, { motif }),
  reactiver: (id) => api.post(`/installations/chantiers/${id}/reactiver/`),
  // N4/N9 — checklist d'exécution + saisie de n° de série.
  getChecklist: (id) => api.get(`/installations/chantiers/${id}/checklist/`),
  cocherChecklist: (id, payload) =>
    api.post(`/installations/chantiers/${id}/cocher-checklist/`, payload),
  // N4 — étapes modèle de checklist (Paramètres → Chantiers).
  getChecklistEtapes: (templateId) =>
    api.get('/installations/checklist-etapes/',
      templateId ? { params: { template: templateId } } : undefined),
  saveChecklistEtape: (id, data) => id
    ? api.patch(`/installations/checklist-etapes/${id}/`, data)
    : api.post('/installations/checklist-etapes/', data),
  deleteChecklistEtape: (id) => api.delete(`/installations/checklist-etapes/${id}/`),

  // N74 — modèles nommés de checklist, auto-sélectionnés par type d'installation.
  getChecklistTemplates: () => api.get('/installations/checklist-templates/'),
  saveChecklistTemplate: (id, data) => id
    ? api.patch(`/installations/checklist-templates/${id}/`, data)
    : api.post('/installations/checklist-templates/', data),
  deleteChecklistTemplate: (id) => api.delete(`/installations/checklist-templates/${id}/`),

  // N13 — besoin matériel (lecture seule) + création d'un BCF brouillon.
  besoinMateriel: (id) => api.get(`/installations/chantiers/${id}/besoin-materiel/`),
  commanderBesoin: (id, fournisseurId) =>
    api.post(`/installations/chantiers/${id}/commander-besoin/`,
      fournisseurId ? { fournisseur: fournisseurId } : {}),

  // Interventions (sorties chantier) — F3/F4
  getInterventions: (params) => api.get('/installations/interventions/', { params }),
  createIntervention: (data) => api.post('/installations/interventions/', data),
  updateIntervention: (id, data) => api.patch(`/installations/interventions/${id}/`, data),
  deleteIntervention: (id) => api.delete(`/installations/interventions/${id}/`),
  getInterventionHistorique: (id) =>
    api.get(`/installations/interventions/${id}/historique/`),
  noterIntervention: (id, body) =>
    api.post(`/installations/interventions/${id}/noter/`, { body }),

  // F5 — Liste de préparation (matériel du chantier + outils du kit).
  getPreparation: (id) => api.get(`/installations/interventions/${id}/preparation/`),
  choisirKit: (id, kit) =>
    api.post(`/installations/interventions/${id}/choisir-kit/`, { kit }),
  cocherMateriel: (id, ligne, charge) =>
    api.post(`/installations/interventions/${id}/cocher-materiel/`, { ligne, charge }),
  cocherOutil: (id, ligne, coche) =>
    api.post(`/installations/interventions/${id}/cocher-outil/`, { ligne, coche }),
  confirmerCharge: (id) =>
    api.post(`/installations/interventions/${id}/confirmer-charge/`, {}),
  commanderManques: (id, fournisseur) =>
    api.post(`/installations/interventions/${id}/commander-manques/`,
      fournisseur ? { fournisseur } : {}),

  // F6 — Trajet & check-in GPS (géolocalisation navigateur, aucun service externe).
  departDepot: (id) => api.post(`/installations/interventions/${id}/depart-depot/`, {}),
  checkin: (id, lat, lng) =>
    api.post(`/installations/interventions/${id}/checkin/`, { lat, lng }),
  retourDepot: (id) => api.post(`/installations/interventions/${id}/retour/`, {}),

  // F7/F8 — Photos guidées par shot list (stockage objet générique).
  getPhotos: (id) => api.get(`/installations/interventions/${id}/photos/`),
  ajouterPhoto: (id, file, slot, phase) => {
    const fd = new FormData()
    fd.append('file', file)
    if (slot) fd.append('slot', slot)
    if (phase) fd.append('phase', phase)
    return api.post(`/installations/interventions/${id}/ajouter-photo/`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  supprimerPhoto: (id, photo) =>
    api.post(`/installations/interventions/${id}/supprimer-photo/`, { photo }),

  // F7/F8 — Créneaux de shot list (Paramètres → Documentation terrain).
  getShotlistSlots: () => api.get('/installations/shotlist-slots/'),
  saveShotlistSlot: (id, data) => id
    ? api.patch(`/installations/shotlist-slots/${id}/`, data)
    : api.post('/installations/shotlist-slots/', data),
  deleteShotlistSlot: (id) => api.delete(`/installations/shotlist-slots/${id}/`),

  // Types d'intervention gérés (Paramètres → Chantiers). Types système protégés.
  getTypesIntervention: () => api.get('/installations/types-intervention/'),
  saveTypeIntervention: (id, data) => id
    ? api.patch(`/installations/types-intervention/${id}/`, data)
    : api.post('/installations/types-intervention/', data),
  deleteTypeIntervention: (id) => api.delete(`/installations/types-intervention/${id}/`),

  // ── F9 — N° de série par composant (+ OCR swappable no-op) ──
  getSerials: (id) => api.get(`/installations/interventions/${id}/serials/`),
  ajouterSerial: (id, { produit, designation, slot, numero_serie, file }) => {
    const fd = new FormData()
    if (produit) fd.append('produit', produit)
    if (designation) fd.append('designation', designation)
    if (slot) fd.append('slot', slot)
    if (numero_serie != null) fd.append('numero_serie', numero_serie)
    if (file) fd.append('file', file)
    return api.post(`/installations/interventions/${id}/ajouter-serial/`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  modifierSerial: (id, payload) =>
    api.post(`/installations/interventions/${id}/modifier-serial/`, payload),
  supprimerSerial: (id, serial) =>
    api.post(`/installations/interventions/${id}/supprimer-serial/`, { serial }),

  // ── F10 — Annotation d'une photo (dessin + légende) ──
  annoterPhoto: (id, payload) =>
    api.post(`/installations/interventions/${id}/annoter-photo/`, payload),

  // ── F11/F12 — Réconciliation du matériel consommé ──
  getConsommation: (id) =>
    api.get(`/installations/interventions/${id}/consommation/`),
  ajouterLigneConsommation: (id, payload) =>
    api.post(`/installations/interventions/${id}/ajouter-ligne-consommation/`, payload),
  modifierLigneConsommation: (id, payload) =>
    api.post(`/installations/interventions/${id}/modifier-ligne-consommation/`, payload),
  supprimerLigneConsommation: (id, ligne) =>
    api.post(`/installations/interventions/${id}/supprimer-ligne-consommation/`, { ligne }),
  validerConsommation: (id) =>
    api.post(`/installations/interventions/${id}/valider-consommation/`, {}),
  overageReview: () =>
    api.get('/installations/interventions/overage-review/'),

  // ── F13/F14 — Mémos vocaux (+ transcription swappable no-op) ──
  getMemos: (id) => api.get(`/installations/interventions/${id}/memos/`),
  ajouterMemo: (id, file, cible) => {
    const fd = new FormData()
    fd.append('file', file)
    if (cible) fd.append('cible', cible)
    return api.post(`/installations/interventions/${id}/ajouter-memo/`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  modifierMemo: (id, memo, transcript) =>
    api.post(`/installations/interventions/${id}/modifier-memo/`, { memo, transcript }),
  supprimerMemo: (id, memo) =>
    api.post(`/installations/interventions/${id}/supprimer-memo/`, { memo }),

  // ── F15 — Temps d'équipe ──
  getCrewTime: (id) => api.get(`/installations/interventions/${id}/crew-time/`),

  // ── F16 — Réserves (punch-list) ──
  getReserves: (id) => api.get(`/installations/interventions/${id}/reserves/`),
  ajouterReserve: (id, payload) =>
    api.post(`/installations/interventions/${id}/ajouter-reserve/`, payload),
  modifierReserve: (id, payload) =>
    api.post(`/installations/interventions/${id}/modifier-reserve/`, payload),
  resoudreReserve: (id, payload) =>
    api.post(`/installations/interventions/${id}/resoudre-reserve/`, payload),

  // ── F17 — Retour d'outillage ──
  getToolReturn: (id) => api.get(`/installations/interventions/${id}/tool-return/`),
  cocherToolReturn: (id, payload) =>
    api.post(`/installations/interventions/${id}/cocher-tool-return/`, payload),
  confirmerToolReturn: (id) =>
    api.post(`/installations/interventions/${id}/confirmer-tool-return/`, {}),

  // ── F18 — Consignes de sécurité (sign-off) ──
  getSafety: (id) => api.get(`/installations/interventions/${id}/safety/`),
  cocherSafety: (id, cle, coche) =>
    api.post(`/installations/interventions/${id}/cocher-safety/`, { cle, coche }),
  signerSafety: (id) =>
    api.post(`/installations/interventions/${id}/signer-safety/`, {}),
  getConsignesSecurite: () => api.get('/installations/consignes-securite/'),
  saveConsigneSecurite: (id, data) => id
    ? api.patch(`/installations/consignes-securite/${id}/`, data)
    : api.post('/installations/consignes-securite/', data),
  deleteConsigneSecurite: (id) => api.delete(`/installations/consignes-securite/${id}/`),

  // ── F19 — Compte-rendu PDF (client-facing) ──
  compteRenduUrl: (id) =>
    `/api/django/installations/interventions/${id}/compte-rendu/`,

  // ── F20 — Contrôle qualité IA des photos (vision swappable, no-op) ──
  getPhotoQa: (id) => api.get(`/installations/interventions/${id}/photo-qa/`),

  // ── F23 — Code/QR de l'intervention ──
  getCode: (id) => api.get(`/installations/interventions/${id}/code/`),
}

export default installationsApi
