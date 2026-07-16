import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   IMMOBILIER (Groupe NTPRO) — client API du module Immobilier & facilities.
   ----------------------------------------------------------------------------
   Miroir FIN des ViewSets DRF de `apps/immobilier` (préfixe `/immobilier/`).
   Toutes les URLs sont relatives : l'intercepteur axios préfixe `/api/django`.
   ========================================================================== */

const crud = makeResourceFactory(api, '/immobilier')

const immobilierApi = {
  sites: crud('sites'),
  batiments: crud('batiments'),
  niveaux: crud('niveaux'),
  locaux: crud('locaux'),
  locataires: {
    ...crud('locataires'),
    resolveClient: (id) => api.post(`/immobilier/locataires/${id}/resolve-client/`),
  },
  baux: {
    ...crud('baux'),
    reviser: (id, data) => api.post(`/immobilier/baux/${id}/reviser/`, data),
    encaisserDepot: (id, data) =>
      api.post(`/immobilier/baux/${id}/encaisser-depot/`, data),
    restituerDepot: (id, data) =>
      api.post(`/immobilier/baux/${id}/restituer-depot/`, data),
    genererEcheancier: (id) =>
      api.post(`/immobilier/baux/${id}/generer-echeancier/`),
  },
  echeancesLoyer: {
    ...crud('echeances-loyer'),
    emettreQuittance: (id) =>
      api.post(`/immobilier/echeances-loyer/${id}/emettre-quittance/`),
    quittancePdfUrl: (id) => `/immobilier/echeances-loyer/${id}/quittance-pdf/`,
  },
}

export default immobilierApi
