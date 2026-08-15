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
  sites: {
    ...crud('sites'),
    rentabilite: (id, params) =>
      api.get(`/immobilier/sites/${id}/rentabilite/`, { params }),
  },
  batiments: {
    ...crud('batiments'),
    rentabilite: (id, params) =>
      api.get(`/immobilier/batiments/${id}/rentabilite/`, { params }),
    repartitionCharges: (id, params) =>
      api.get(`/immobilier/batiments/${id}/repartition-charges/`, { params }),
    genererRegularisation: (id, data) =>
      api.post(`/immobilier/batiments/${id}/generer-regularisation/`, data),
  },
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
    impayees: () => api.get('/immobilier/echeances-loyer/impayees/'),
    relancer: (id, data) =>
      api.post(`/immobilier/echeances-loyer/${id}/relancer/`, data),
  },
  // NTPRO8 / WIR263 — historique des relances d'impayé. LECTURE SEULE : une
  // relance naît uniquement de `echeances-loyer/<id>/relancer/`. L'escalade
  // niveau 1 → 2 → 3 a une portée JURIDIQUE (le niveau 3 vaut mise en
  // demeure), d'où l'affichage du niveau atteint AVANT tout nouveau clic.
  relancesLoyer: {
    ...crud('relances-loyer'),
    parEcheance: (echeanceId) =>
      api.get('/immobilier/relances-loyer/',
        { params: { echeance_loyer: echeanceId } }),
  },
  budgetsCharges: {
    ...crud('budgets-charges'),
    consommation: (id) =>
      api.get(`/immobilier/budgets-charges/${id}/consommation/`),
  },
  depensesCharges: crud('depenses-charges'),
  regularisationsCharges: {
    ...crud('regularisations-charges'),
    emettre: (id) =>
      api.post(`/immobilier/regularisations-charges/${id}/emettre/`),
  },
}

export default immobilierApi
