import api from './axios'

const installationsApi = {
  // Chantiers
  getInstallations: (params) => api.get('/installations/chantiers/', { params }),
  // Export .xlsx (respecte les filtres courants). Réponse blob.
  exportInstallations: (params = {}) =>
    api.get('/installations/chantiers/export/', { params, responseType: 'blob' }),
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

  // Checklist d'exécution (N3) — auto-remplie côté serveur ; bascule d'étape.
  getChecklist: (id) => api.get(`/installations/chantiers/${id}/checklist/`),
  toggleChecklistItem: (id, itemId, done) =>
    api.post(`/installations/chantiers/${id}/checklist/${itemId}/toggle/`,
      done === undefined ? {} : { done }),

  // Documents après-vente (PDF clients) — réponses blob (application/pdf).
  // N21 — PV de réception des travaux.
  pvReceptionPdf: (id) =>
    api.get(`/documents/chantiers/${id}/pv-reception/`, { responseType: 'blob' }),
  // N22 — Bon de livraison.
  bonLivraisonPdf: (id) =>
    api.get(`/documents/chantiers/${id}/bon-livraison/`, { responseType: 'blob' }),
  // N23 — Dossier de remise (handover pack).
  dossierRemisePdf: (id) =>
    api.get(`/documents/chantiers/${id}/dossier-remise/`, { responseType: 'blob' }),
  // N24 — Attestation (type = 'installation' | 'fin_travaux').
  attestationPdf: (id, type = 'installation') =>
    api.get(`/documents/chantiers/${id}/attestation/`, {
      params: { type }, responseType: 'blob',
    }),

  // Besoin matériel par chantier (N13) — dérivé du devis source vs stock.
  // Lecture seule ; signale les manques (manque > 0).
  getBesoinMateriel: (id) =>
    api.get(`/installations/chantiers/${id}/besoin-materiel/`),
  // Crée un BonCommandeFournisseur BROUILLON pour les manques. `fournisseur`
  // optionnel (sinon celui du premier produit en pénurie).
  commanderBesoin: (id, fournisseurId) =>
    api.post(`/installations/chantiers/${id}/commander-besoin/`,
      fournisseurId ? { fournisseur: fournisseurId } : {}),

  // Interventions / ordres de travail
  getInterventions: (params) => api.get('/installations/interventions/', { params }),
  createIntervention: (data) => api.post('/installations/interventions/', data),
  updateIntervention: (id, data) => api.patch(`/installations/interventions/${id}/`, data),
  deleteIntervention: (id) => api.delete(`/installations/interventions/${id}/`),

  // Types d'intervention gérés (Paramètres → Chantiers). La clé est posée
  // côté serveur ; un type utilisé par un ordre de travail ne peut être
  // supprimé (409 avec message FR).
  getTypesIntervention: () => api.get('/installations/types-intervention/'),
  saveTypeIntervention: (id, data) => id
    ? api.patch(`/installations/types-intervention/${id}/`, data)
    : api.post('/installations/types-intervention/', data),
  deleteTypeIntervention: (id) => api.delete(`/installations/types-intervention/${id}/`),
}

export default installationsApi
