import api from './axios'

const ventesApi = {
  // Devis
  getDevis: (params) => api.get('/ventes/devis/', { params }),
  getDevisById: (id) => api.get(`/ventes/devis/${id}/`),
  createDevis: (data) => api.post('/ventes/devis/', data),
  updateDevis: (id, data) => api.put(`/ventes/devis/${id}/`, data),
  patchDevis: (id, data) => api.patch(`/ventes/devis/${id}/`, data),
  deleteDevis: (id) => api.delete(`/ventes/devis/${id}/`),
  genererPdfDevis: (id, options = {}) => api.post(`/ventes/devis/${id}/generer-pdf/`, options),
  telechargerPdfDevis: (id) => api.get(`/ventes/devis/${id}/telecharger-pdf/`, { responseType: 'blob' }),
  // Proposition client (chemin canonique /proposal) — rendue à la volée selon
  // le format (pdf_mode/onepage/full, include_etude…), récupérée en blob pour
  // l'aperçu inline (iframe) ET le téléchargement, sans quitter la fiche lead.
  getProposalPdf: (id, params = {}) =>
    api.get(`/ventes/devis/${id}/proposal/`, { params, responseType: 'blob' }),
  convertirDevisEnBC: (id) => api.post(`/ventes/devis/${id}/convertir-bc/`),
  // Échéancier devis → factures : génère la prochaine tranche (acompte → solde).
  genererFacture: (id) => api.post(`/ventes/devis/${id}/generer-facture/`),

  // Lignes de devis
  getLignesDevis: (params) => api.get('/ventes/devis-lignes/', { params }),
  createLigneDevis: (data) => api.post('/ventes/devis-lignes/', data),
  updateLigneDevis: (id, data) => api.put(`/ventes/devis-lignes/${id}/`, data),
  deleteLigneDevis: (id) => api.delete(`/ventes/devis-lignes/${id}/`),

  // Bons de commande
  getBonsCommande: (params) => api.get('/ventes/bons-commande/', { params }),
  getBonCommande: (id) => api.get(`/ventes/bons-commande/${id}/`),
  createBonCommande: (data) => api.post('/ventes/bons-commande/', data),
  updateBonCommande: (id, data) => api.put(`/ventes/bons-commande/${id}/`, data),
  patchBonCommande: (id, data) => api.patch(`/ventes/bons-commande/${id}/`, data),
  confirmerBC: (id) => api.post(`/ventes/bons-commande/${id}/confirmer/`),
  marquerLivreBC: (id) => api.post(`/ventes/bons-commande/${id}/marquer-livre/`),
  annulerBC: (id) => api.post(`/ventes/bons-commande/${id}/annuler/`),
  creerFactureBC: (id) => api.post(`/ventes/bons-commande/${id}/creer-facture/`),

  // Factures
  getFactures: (params) => api.get('/ventes/factures/', { params }),
  getFacture: (id) => api.get(`/ventes/factures/${id}/`),
  createFacture: (data) => api.post('/ventes/factures/', data),
  updateFacture: (id, data) => api.put(`/ventes/factures/${id}/`, data),
  patchFacture: (id, data) => api.patch(`/ventes/factures/${id}/`, data),
  genererPdfFacture: (id) => api.post(`/ventes/factures/${id}/generer-pdf/`),
  telechargerPdfFacture: (id) => api.get(`/ventes/factures/${id}/telecharger-pdf/`, { responseType: 'blob' }),
  envoyerEmailFacture: (id, email) => api.post(`/ventes/factures/${id}/envoyer-email/`, { email }),
  emettreFacture: (id) => api.post(`/ventes/factures/${id}/emettre/`),
  marquerPayeeFacture: (id) => api.post(`/ventes/factures/${id}/marquer-payee/`),
  annulerFacture: (id) => api.post(`/ventes/factures/${id}/annuler/`),
  // Paiements : enregistrement manuel + liste par facture.
  enregistrerPaiement: (id, data) => api.post(`/ventes/factures/${id}/enregistrer-paiement/`, data),
  getPaiementsFacture: (id) => api.get(`/ventes/factures/${id}/paiements/`),

  // Lignes de facture
  getLignesFacture: (params) => api.get('/ventes/factures-lignes/', { params }),
  createLigneFacture: (data) => api.post('/ventes/factures-lignes/', data),
  updateLigneFacture: (id, data) => api.put(`/ventes/factures-lignes/${id}/`, data),
  deleteLigneFacture: (id) => api.delete(`/ventes/factures-lignes/${id}/`),
}

export default ventesApi
