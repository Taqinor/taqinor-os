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

  // Interventions / ordres de travail
  getInterventions: (params) => api.get('/installations/interventions/', { params }),
  createIntervention: (data) => api.post('/installations/interventions/', data),
  updateIntervention: (id, data) => api.patch(`/installations/interventions/${id}/`, data),
  deleteIntervention: (id) => api.delete(`/installations/interventions/${id}/`),

  // Types d'intervention gérés (Paramètres → Chantiers). Types système protégés.
  getTypesIntervention: () => api.get('/installations/types-intervention/'),
  saveTypeIntervention: (id, data) => id
    ? api.patch(`/installations/types-intervention/${id}/`, data)
    : api.post('/installations/types-intervention/', data),
  deleteTypeIntervention: (id) => api.delete(`/installations/types-intervention/${id}/`),
}

export default installationsApi
