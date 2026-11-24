import api from './axios'

// N21–N24 — Générateurs de PDF après-vente (régénérés à la demande).
// Chaque appel renvoie un blob PDF ; aucun prix d'achat n'y figure.
const documentsApi = {
  pvReception: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/pv-reception/`, { responseType: 'blob' }),
  // ACSV32 — PV de réception DÉFINITIVE (figé en GED, 409 tant que non prononcée).
  pvReceptionDefinitive: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/pv-reception/`, {
      params: { definitive: 1 }, responseType: 'blob' }),
  bonLivraison: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/bon-livraison/`, { responseType: 'blob' }),
  dossierRemise: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/dossier-remise/`, { responseType: 'blob' }),
  attestation: (chantierId, type = 'installation') =>
    api.get(`/documents/chantiers/${chantierId}/attestation/`, {
      params: { type }, responseType: 'blob',
    }),
  // Dossier contractuel du chantier (4 actes, 5 lignes) — contrat :
  // apps/documents/contract_samples/{dossier_contractuel,acte_contractuel}.json.
  // Un GET prépare le dossier s'il manque ; aucun montant n'est recalculé ici.
  dossierContrats: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/contrats/`),
  // `langue` : 'fr' (défaut) | 'ar' — l'arabe est la traduction qui accompagne l'acte.
  acte: (id, langue = 'fr') => api.get(`/documents/actes/${id}/`, { params: { langue } }),
  // `surcharges` : { <section>: valeur | null } — null remet le défaut.
  modifierActe: (id, surcharges, langue = 'fr') =>
    api.patch(`/documents/actes/${id}/`, { langue, surcharges }),
  pdfActe: (id, langue = 'fr') =>
    api.get(`/documents/actes/${id}/pdf/`, { params: { langue }, responseType: 'blob' }),
  emettreActe: (id) => api.post(`/documents/actes/${id}/emettre/`),
  rouvrirActe: (id) => api.post(`/documents/actes/${id}/rouvrir/`),
  // corps : { signature_client, signataire_nom, lieu }
  signerActe: (id, corps) => api.post(`/documents/actes/${id}/signer/`, corps),
  // corps : { signataire_nom, signe_le }
  marquerActeSigne: (id, corps) => api.post(`/documents/actes/${id}/marquer-signe/`, corps),
  enregistrerModeleActe: (id) => api.post(`/documents/actes/${id}/modele/`),
}

export default documentsApi
