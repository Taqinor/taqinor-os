import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   FLOTTE (UX15–UX20) — client API du module Flotte (parc de véhicules & engins).
   ----------------------------------------------------------------------------
   Miroir FIN des ViewSets DRF de `apps/flotte` (préfixe `/flotte/`). Toutes les
   URLs sont relatives : l'intercepteur axios préfixe `/api/django`. Les listes
   acceptent des `params` de filtre (statut, énergie, vehicule, conducteur…),
   transmis tels quels au backend. Aucune donnée « prix d'achat / marge » n'est
   demandée ni rendue côté client.
   ========================================================================== */

/**
 * ARC50 — pilote de typage : le schéma OpenAPI généré (YAPIC5 +
 * `npm run gen:api-types`) documente la forme réelle de `Vehicule`. Ceci ne
 * change AUCUN comportement runtime (JSDoc pur, ce repo n'exécute pas tsc) —
 * uniquement de la documentation typée pour l'éditeur.
 * @typedef {import('./types/schema').components['schemas']['Vehicule']} Vehicule
 */

// ARC44 — Fabrique CRUD standard (factory partagée `api/resource.js`), URLs
// et forme des réponses inchangées.
const crud = makeResourceFactory(api, '/flotte')

const flotteApi = {
  // ── Parc : véhicules, engins, référentiels, actifs unifiés ──
  // ARC50 — `crud('vehicules')` renvoie {list,get,create,update,remove} sur
  // des `Vehicule` (voir le typedef ci-dessus, généré depuis l'OpenAPI).
  vehicules: crud('vehicules'),
  modelesVehicule: crud('modeles-vehicule'),
  engins: crud('engins'),
  referentiels: crud('referentiels'),
  actifs: {
    ...crud('actifs'),
    // XFLT20 — détenteur courant de chaque accessoire de l'actif.
    detenteursCourants: (id) =>
      api.get(`/flotte/actifs/${id}/detenteurs-courants/`),
    documents: (id) => api.get(`/flotte/actifs/${id}/documents/`),
  },

  // Cockpit (FLOTTE35) — synthèse société (dispo / échéances / coûts / conso).
  tableauBord: () => api.get('/flotte/vehicules/tableau-bord/'),
  // Fiches véhicule (detail=True, lecture seule) — jamais de prix d'achat.
  vehiculeTco: (id, params) => api.get(`/flotte/vehicules/${id}/tco/`, { params }),
  vehiculeTsav: (id, params) => api.get(`/flotte/vehicules/${id}/tsav/`, { params }),
  vehiculeEcoConduite: (id, params) =>
    api.get(`/flotte/vehicules/${id}/eco-conduite/`, { params }),
  vehiculeAmortissement: (id, params) =>
    api.get(`/flotte/vehicules/${id}/amortissement/`, { params }),
  // XFLT3 — grand livre unifié des coûts du véhicule.
  vehiculeLedger: (id) => api.get(`/flotte/vehicules/${id}/ledger/`),
  // XFLT4 — historique des transitions de statut + journal d'audit.
  vehiculeHistorique: (id) => api.get(`/flotte/vehicules/${id}/historique/`),
  vehiculeActivites: (id) => api.get(`/flotte/vehicules/${id}/activites/`),
  // XFLT4 — changement de statut (gate checklist commande→actif côté serveur).
  changerStatut: (id, statut) =>
    api.post(`/flotte/vehicules/${id}/changer-statut/`, { statut }),
  // XFLT16 — cession (vente) du véhicule.
  ceder: (id, data) => api.post(`/flotte/vehicules/${id}/ceder/`, data),

  // ── Conducteurs & mobilité ──
  conducteurs: crud('conducteurs'),
  affectations: {
    ...crud('affectations'),
    // XFLT22 — réaffectation conducteur en masse.
    masse: (data) => api.post('/flotte/affectations/masse/', data),
  },
  reservations: crud('reservations'),
  demandesVehicule: crud('demandes-vehicule'),
  etatsDesLieux: {
    ...crud('etats-des-lieux'),
    // XFLT17 — e-signature (loi 53-05, nom saisi + horodatage serveur).
    signer: (id, data) => api.post(`/flotte/etats-des-lieux/${id}/signer/`, data),
  },
  // XFLT17 — charte véhicule versionnée + accusés de lecture.
  chartesVehicule: crud('chartes-vehicule'),
  accusesCharte: crud('accuses-charte'),

  // ── Entretien ──
  plansEntretien: {
    ...crud('plans-entretien'),
    echeances: (params) => api.get('/flotte/plans-entretien/echeances/', { params }),
    // XFLT22 — duplique un plan sur une sélection d'actifs.
    rollout: (id, actifFlotteIds) =>
      api.post(`/flotte/plans-entretien/${id}/rollout/`, {
        actif_flotte_ids: actifFlotteIds,
      }),
  },
  echeancesEntretien: {
    ...crud('echeances-entretien'),
    // WIR5/FLOTTE16 — déclenche la génération des échéances dues depuis les
    // plans actifs (miroir du beat quotidien `flotte.tasks`).
    generer: (params) => api.post('/flotte/echeances-entretien/generer/', null, { params }),
  },
  garages: crud('garages'),
  // XFLT14 — garanties véhicule & pièces.
  garanties: crud('garanties'),
  ordresReparation: {
    ...crud('ordres-reparation'),
    couts: (params) => api.get('/flotte/ordres-reparation/couts/', { params }),
    cloturer: (id, params) =>
      api.post(`/flotte/ordres-reparation/${id}/cloturer/`, null, { params }),
    // XFLT19 — approbation du devis de réparation.
    approuver: (id) => api.post(`/flotte/ordres-reparation/${id}/approuver/`),
  },
  pneumatiques: crud('pneumatiques'),
  pieces: crud('pieces'),
  // XFLT1 — contrats véhicule (leasing/LLD/location/entretien).
  contratsVehicule: {
    ...crud('contrats-vehicule'),
    expirants: (params) => api.get('/flotte/contrats-vehicule/expirants/', { params }),
  },
  // XFLT3 — coûts véhicule divers (péage, parking, lavage…).
  couts: crud('couts'),

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
  pleins: {
    ...crud('pleins'),
    // XFLT23 — OCR reçu de station (multipart, gated ZHIPU_API_KEY).
    ocr: (formData) => api.post('/flotte/pleins/ocr/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  },
  cartes: crud('cartes'),
  sinistres: crud('sinistres'),
  infractions: crud('infractions'),
  relevesTelematiques: crud('releves-telematiques'),
  trajetsTelematiques: crud('trajets-telematiques'),
  trajetsChantier: crud('trajets-chantier'),
  // XFLT24 — zones de géofencing + évaluation des relevés télématiques.
  zonesGeographiques: {
    ...crud('zones-geographiques'),
    evaluer: () => api.post('/flotte/zones-geographiques/evaluer/'),
  },
  // XFLT28 — rappels constructeur (recall) + rapprochement VIN.
  rappelsConstructeur: {
    ...crud('rappels-constructeur'),
    rapprocher: (id) => api.post(`/flotte/rappels-constructeur/${id}/rapprocher/`),
  },

  // ── XFLT5 — signalements d'anomalie (conducteur → OR) ──
  signalements: {
    ...crud('signalements'),
    convertirEnOr: (id) =>
      api.post(`/flotte/signalements/${id}/convertir-en-or/`),
  },

  // ── XFLT13 — inspections périodiques paramétrables (check-lists DVIR) ──
  modelesInspection: crud('modeles-inspection'),
  inspections: {
    ...crud('inspections'),
    tauxCompletion: (params) =>
      api.get('/flotte/inspections/taux-completion/', { params }),
  },

  // ── XFLT18 — budget flotte annuel vs réalisé ──
  budgets: crud('budgets'),

  // ── XFLT20 — registre de remise clés/carte/badge/tag ──
  remisesAccessoire: crud('remises-accessoire'),

  // ── Rapports (lecture seule, jamais de prix d'achat/marge) ──
  rapportCouts: (params) => api.get('/flotte/rapports/couts/', { params }),
  rapportRemplacement: () => api.get('/flotte/rapports/remplacement/'),
  rapportBudget: (params) => api.get('/flotte/rapports/budget/', { params }),
}

export default flotteApi
