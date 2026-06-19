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
  // Révision : crée une nouvelle version (v2, v3…) d'un devis.
  reviserDevis: (id) => api.post(`/ventes/devis/${id}/reviser/`),
  // Approbation admin de la remise (T17) — débloque l'envoi.
  approuverRemise: (id) => api.post(`/ventes/devis/${id}/approuver-remise/`),
  // N25 — acceptation explicite (date + nom), déclencheur de chantier + chatter.
  accepterDevis: (id, payload = {}) => api.post(`/ventes/devis/${id}/accepter/`, payload),
  historiqueDevis: (id) => api.get(`/ventes/devis/${id}/historique/`),
  noterDevis: (id, body) => api.post(`/ventes/devis/${id}/noter/`, { body }),
  // Export comptable : journal des ventes + résumé TVA (.xlsx) sur une période.
  journalVentes: (params) =>
    api.get('/ventes/journal-ventes/', { params, responseType: 'blob' }),
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
  // Envoyer par WhatsApp : lien wa.me prêt à envoyer (modele 'facture'/'relance').
  whatsappFacture: (id, payload = {}) => api.post(`/ventes/factures/${id}/whatsapp/`, payload),
  // N38 — export structuré UBL 2.1 (aperçu BROUILLON, jamais transmis) en XML.
  telechargerUbl: (id) => api.get(`/ventes/factures/${id}/ubl/`, { responseType: 'blob' }),
  // N31 — audit admin de la numérotation séquentielle (trous/doublons).
  auditNumerotation: () => api.get('/ventes/numerotation-audit/'),
  emettreFacture: (id) => api.post(`/ventes/factures/${id}/emettre/`),
  marquerPayeeFacture: (id) => api.post(`/ventes/factures/${id}/marquer-payee/`),
  annulerFacture: (id) => api.post(`/ventes/factures/${id}/annuler/`),
  // Paiements : enregistrement manuel + liste par facture.
  enregistrerPaiement: (id, data) => api.post(`/ventes/factures/${id}/enregistrer-paiement/`, data),
  getPaiementsFacture: (id) => api.get(`/ventes/factures/${id}/paiements/`),
  // Encaissements : liste lecture seule de TOUS les paiements de la société
  // (PaiementViewSet), bornée serveur. ?ordering= pour le tri.
  getPaiements: (params) => api.get('/ventes/paiements/', { params }),

  // Avoirs (notes de crédit)
  creerAvoir: (factureId, data) => api.post(`/ventes/factures/${factureId}/creer-avoir/`, data),
  getAvoirs: (params) => api.get('/ventes/avoirs/', { params }),
  annulerAvoir: (id) => api.post(`/ventes/avoirs/${id}/annuler/`),
  telechargerAvoirPdf: (id) => api.get(`/ventes/avoirs/${id}/telecharger-pdf/`, { responseType: 'blob' }),

  // Recouvrement (vue/consigne/impression — jamais d'envoi)
  getRelances: () => api.get('/ventes/relances/'),
  relancerFacture: (id, data) => api.post(`/ventes/factures/${id}/relancer/`, data),
  exclureRelance: (id, exclu) => api.post(`/ventes/factures/${id}/exclure-relance/`, { exclu }),
  getRelancesFacture: (id) => api.get(`/ventes/factures/${id}/relances/`),
  // N87 — fil des emails (envoyés/reçus) d'une facture + état du compte d'envoi.
  getEmailsFacture: (id) => api.get(`/ventes/factures/${id}/emails/`),
  getEmailConfig: () => api.get('/ventes/email-config/'),
  getBalanceAgee: () => api.get('/ventes/balance-agee/'),
  getClientReleve: (clientId) => api.get(`/ventes/clients/${clientId}/releve/`),
  getClientRelevePdf: (clientId) => api.get(`/ventes/clients/${clientId}/releve-pdf/`, { responseType: 'blob' }),
  getLettreRelancePdf: (factureId) => api.get(`/ventes/factures/${factureId}/lettre-relance-pdf/`, { responseType: 'blob' }),
  // Lettre de relance PREMIUM (langage visuel du devis) — niveau 1/2/3.
  getLettreRelancePremiumPdf: (factureId, niveau = 1) =>
    api.get(`/ventes/factures/${factureId}/lettre-relance-premium/`, {
      params: { niveau }, responseType: 'blob',
    }),
  // Fiche de remise / garantie après-vente PREMIUM pour un chantier.
  getFicheRemisePremiumPdf: (chantierId) =>
    api.get(`/ventes/chantiers/${chantierId}/fiche-remise-premium/`, { responseType: 'blob' }),
  getNiveauxRelance: () => api.get('/ventes/niveaux-relance/'),
  saveNiveauRelance: (id, data) => id
    ? api.patch(`/ventes/niveaux-relance/${id}/`, data)
    : api.post('/ventes/niveaux-relance/', data),
  deleteNiveauRelance: (id) => api.delete(`/ventes/niveaux-relance/${id}/`),

  // Lignes de facture
  getLignesFacture: (params) => api.get('/ventes/factures-lignes/', { params }),
  createLigneFacture: (data) => api.post('/ventes/factures-lignes/', data),
  updateLigneFacture: (id, data) => api.put(`/ventes/factures-lignes/${id}/`, data),
  deleteLigneFacture: (id) => api.delete(`/ventes/factures-lignes/${id}/`),
}

export default ventesApi
