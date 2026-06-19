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
}

export default installationsApi
