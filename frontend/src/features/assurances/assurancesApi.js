import api from '../../api/axios'

/* ============================================================================
   API du module Assurances d'entreprise (Groupe NTASS) — préfixe
   `/assurances/`. Fine couche autour d'axios : chaque fonction renvoie la
   promesse axios (`res.data` côté appelant). Les basenames/@actions reflètent
   exactement `apps/assurances/urls.py`. La société est TOUJOURS posée côté
   serveur (jamais dans le corps). Aucun prix d'achat / marge n'est exposé.
   ========================================================================== */

const assurancesApi = {
  // ── Polices (NTASS2) ──
  getPolices: (params) => api.get('/assurances/polices/', { params }),
  getPolice: (id) => api.get(`/assurances/polices/${id}/`),
  createPolice: (data) => api.post('/assurances/polices/', data),
  updatePolice: (id, data) => api.patch(`/assurances/polices/${id}/`, data),
  deletePolice: (id) => api.delete(`/assurances/polices/${id}/`),
  getPolicesExpirantes: (within = 30) =>
    api.get('/assurances/polices/expirantes/', { params: { within } }),
  // NTASS3 — chatter police.
  getPoliceHistorique: (id) =>
    api.get(`/assurances/polices/${id}/historique/`),
  noterPolice: (id, body) =>
    api.post(`/assurances/polices/${id}/noter/`, { body }),
  // NTASS5 — échéancier de primes.
  genererEcheancier: (id, periodicite) =>
    api.post(`/assurances/polices/${id}/generer-echeancier/`, { periodicite }),
  // NTASS9 — renouvellement.
  renouvelerPolice: (id, data = {}) =>
    api.post(`/assurances/polices/${id}/renouveler/`, data),

  // ── Assureurs / courtiers (NTASS1) ──
  getAssureurs: (params) => api.get('/assurances/assureurs/', { params }),
  createAssureur: (data) => api.post('/assurances/assureurs/', data),
  getCourtiers: (params) => api.get('/assurances/courtiers/', { params }),
  createCourtier: (data) => api.post('/assurances/courtiers/', data),

  // ── Garanties (NTASS4) ──
  getGaranties: (policeId) =>
    api.get('/assurances/garanties-police/', { params: { police: policeId } }),
  createGarantie: (data) => api.post('/assurances/garanties-police/', data),

  // ── Actifs couverts (NTASS7) ──
  getActifsCouverts: (policeId) =>
    api.get('/assurances/actifs-couverts/', { params: { police: policeId } }),
  createActifCouvert: (data) => api.post('/assurances/actifs-couverts/', data),

  // ── Échéances de prime (NTASS5/6) ──
  getEcheancesPrime: (policeId) =>
    api.get('/assurances/echeances-prime/', { params: { police: policeId } }),
  marquerEcheancePayee: (id) =>
    api.post(`/assurances/echeances-prime/${id}/marquer-payee/`),
  proposerEcriturePrime: (id) =>
    api.post(`/assurances/echeances-prime/${id}/proposer-ecriture/`),

  // ── Attestations (NTASS17/18) ──
  getAttestations: (policeId) =>
    api.get('/assurances/attestations/', { params: { police: policeId } }),
  createAttestation: (data) => api.post('/assurances/attestations/', data),
  getAttestationsExpirantes: (within = 30) =>
    api.get('/assurances/attestations/expirantes/', { params: { within } }),

  // ── Sinistres (NTASS10-16) ──
  getSinistres: (params) =>
    api.get('/assurances/declarations-sinistre/', { params }),
  getSinistre: (id) => api.get(`/assurances/declarations-sinistre/${id}/`),
  createSinistre: (data) =>
    api.post('/assurances/declarations-sinistre/', data),
  updateSinistre: (id, data) =>
    api.patch(`/assurances/declarations-sinistre/${id}/`, data),
  getSinistreHistorique: (id) =>
    api.get(`/assurances/declarations-sinistre/${id}/historique/`),
  noterSinistre: (id, body) =>
    api.post(`/assurances/declarations-sinistre/${id}/noter/`, { body }),
  enregistrerIndemnisation: (id, data) =>
    api.post(
      `/assurances/declarations-sinistre/${id}/enregistrer-indemnisation/`,
      data),
  proposerEcritureIndemnisation: (id) =>
    api.post(
      `/assurances/declarations-sinistre/${id}/proposer-ecriture-indemnisation/`),
  marquerSinistreConteste: (id) =>
    api.post(`/assurances/declarations-sinistre/${id}/marquer-conteste/`),

  // ── Transverse (NTASS20/21) ──
  getCouvertureActif: (typeActif, actifRef) =>
    api.get('/assurances/couverture-actif/', {
      params: { type_actif: typeActif, actif_ref: actifRef },
    }),
  getTableauBord: () => api.get('/assurances/tableau-bord/'),

  // ── WIR145 — exigences d'assurance par marché + vérification conformité ──
  getExigencesMarche: (params) =>
    api.get('/assurances/exigences-assurance-marche/', { params }),
  createExigenceMarche: (data) =>
    api.post('/assurances/exigences-assurance-marche/', data),
  deleteExigenceMarche: (id) =>
    api.delete(`/assurances/exigences-assurance-marche/${id}/`),
  verifierExigenceMarche: (id) =>
    api.post(`/assurances/exigences-assurance-marche/${id}/verifier/`),
}

export default assurancesApi
