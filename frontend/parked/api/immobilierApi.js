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
  // WIR263 — historique d'escalade des relances de loyer. LECTURE SEULE côté
  // API (`RelanceLoyerViewSet.http_method_names = ['get','head','options']`) :
  // une relance naît TOUJOURS de `echeancesLoyer.relancer(id)`. Le filtre par
  // échéance existe déjà côté serveur (`get_queryset` lit `?echeance_loyer=`),
  // donc `list({ echeance_loyer: <id> })` suffit — aucun filterset à ajouter.
  // Forme de la réponse : contrat committé
  // `apps/immobilier/contract_samples/relances_loyer_par_echeance.json`.
  relancesLoyer: crud('relances-loyer'),
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
