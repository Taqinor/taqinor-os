import api from './axios'

// N21–N24 — Générateurs de PDF après-vente (régénérés à la demande).
// Chaque appel renvoie un blob PDF ; aucun prix d'achat n'y figure.
const documentsApi = {
  pvReception: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/pv-reception/`, { responseType: 'blob' }),
  bonLivraison: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/bon-livraison/`, { responseType: 'blob' }),
  dossierRemise: (chantierId) =>
    api.get(`/documents/chantiers/${chantierId}/dossier-remise/`, { responseType: 'blob' }),
  attestation: (chantierId, type = 'installation') =>
    api.get(`/documents/chantiers/${chantierId}/attestation/`, {
      params: { type }, responseType: 'blob',
    }),
}

export default documentsApi
