import api from './axios'

/* ============================================================================
   FLOTTE (UX15–UX20) — client API du module Flotte (parc de véhicules & engins).
   ----------------------------------------------------------------------------
   Miroir FIN des ViewSets DRF de `apps/flotte` (préfixe `/flotte/`). Toutes les
   URLs sont relatives : l'intercepteur axios préfixe `/api/django`. Les listes
   acceptent des `params` de filtre (statut, énergie, vehicule, conducteur…),
   transmis tels quels au backend. Aucune donnée « prix d'achat / marge » n'est
   demandée ni rendue côté client.
   ========================================================================== */

// Fabrique CRUD standard pour un ViewSet DRF simple (list/get/create/update/del).
function crud(prefix) {
  return {
    list: (params) => api.get(`/flotte/${prefix}/`, { params }),
    get: (id) => api.get(`/flotte/${prefix}/${id}/`),
    create: (data) => api.post(`/flotte/${prefix}/`, data),
    update: (id, data) => api.patch(`/flotte/${prefix}/${id}/`, data),
    remove: (id) => api.delete(`/flotte/${prefix}/${id}/`),
  }
}

const flotteApi = {
  // ── Parc : véhicules, engins, référentiels, actifs unifiés ──
  vehicules: crud('vehicules'),
  engins: crud('engins'),
  referentiels: crud('referentiels'),
  actifs: crud('actifs'),

  // Cockpit (FLOTTE35) — synthèse société (dispo / échéances / coûts / conso).
  tableauBord: () => api.get('/flotte/vehicules/tableau-bord/'),
  // Fiches véhicule (detail=True, lecture seule) — jamais de prix d'achat.
  vehiculeTco: (id, params) => api.get(`/flotte/vehicules/${id}/tco/`, { params }),
  vehiculeTsav: (id, params) => api.get(`/flotte/vehicules/${id}/tsav/`, { params }),
  vehiculeEcoConduite: (id, params) =>
    api.get(`/flotte/vehicules/${id}/eco-conduite/`, { params }),
  vehiculeAmortissement: (id, params) =>
    api.get(`/flotte/vehicules/${id}/amortissement/`, { params }),

  // ── Conducteurs & mobilité ──
  conducteurs: crud('conducteurs'),
  affectations: crud('affectations'),
  reservations: crud('reservations'),
  demandesVehicule: crud('demandes-vehicule'),
  etatsDesLieux: crud('etats-des-lieux'),

  // ── Entretien ──
  plansEntretien: crud('plans-entretien'),
  echeancesEntretien: crud('echeances-entretien'),
  garages: crud('garages'),
  ordresReparation: crud('ordres-reparation'),
  pneumatiques: crud('pneumatiques'),
  pieces: crud('pieces'),

  // ── Conformité réglementaire ──
  echeancesReglementaires: crud('echeances-reglementaires'),
  assurances: crud('assurances'),
  visitesTechniques: crud('visites-techniques'),
  cartesGrises: crud('cartes-grises'),
  baremesVignette: crud('baremes-vignette'),
  // FLOTTE24 — moteur unifié d'alertes réglementaires (echu / j7 / j15 / j30).
  alertesEcheances: () =>
    api.get('/flotte/echeances-reglementaires/alertes-echeances/'),

  // ── Carburant, cartes, sinistres, infractions, télématique ──
  pleins: crud('pleins'),
  cartes: crud('cartes'),
  sinistres: crud('sinistres'),
  infractions: crud('infractions'),
  relevesTelematiques: crud('releves-telematiques'),
  trajetsTelematiques: crud('trajets-telematiques'),
  trajetsChantier: crud('trajets-chantier'),
}

export default flotteApi
