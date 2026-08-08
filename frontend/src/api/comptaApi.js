import api from './axios'
import { makeResourceFactory } from './resource'
import { downloadBlobInGesture } from '../utils/downloadBlob'

/* ============================================================================
   Comptabilité (apps/compta) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /compta/... ».
   Un seul point d'import pour tous les écrans du module (UX2–UX9).
   Aucune donnée sensible (prix d'achat / marge) n'est demandée ni rendue.
   ========================================================================== */

// Déclenche le téléchargement d'un blob (export fichier) côté navigateur.
// VX172 — appelé avec le blob déjà résolu (post-`await` de l'appelant) : pas
// de fenêtre pré-ouverte possible d'ici, mais `downloadBlobInGesture()`
// tente quand même l'onglet visible en iOS/standalone (repli `a.download`
// automatique si bloqué) au lieu du téléchargement invisible d'avant.
export function downloadBlob(blob, filename) {
  downloadBlobInGesture().deliver(blob instanceof Blob ? blob : new Blob([blob]), filename)
}

// ARC44 — Fabrique générique de CRUD REST sur une ressource du routeur compta
// (factory partagée `frontend/src/api/resource.js`, forme/URLs inchangées).
const resource = makeResourceFactory(api, '/compta')

const comptaApi = {
  downloadBlob,

  // ── UX2 — Pilotage / cockpit financier ──
  cockpit: (params) => api.get('/compta/pilotage/cockpit/', { params }),

  // ── UX3 — Plan comptable, comptes CGNC & journaux ──
  plans: resource('plans'),
  comptes: resource('comptes'),
  journaux: resource('journaux'),

  // ── UX4 — Écritures comptables ──
  ecritures: {
    ...resource('ecritures'),
    valider: (id) => api.post(`/compta/ecritures/${id}/valider/`),
    extourner: (id) => api.post(`/compta/ecritures/${id}/extourner/`),
  },

  // ── UX5 — États comptables CGNC (blob quand export fichier) ──
  etats: {
    // PACT18 — SOULIGNÉ, pas tiret : `def grand_livre` (apps/compta/views.py)
    // est la SEULE @action de ce ViewSet sans `url_path=` explicite, et le
    // `url_path` par défaut d'une @action DRF est le NOM DE LA MÉTHODE, tel
    // quel, souligné compris (rest_framework/decorators.py : `func.url_path =
    // url_path if url_path else func.__name__`). Un tiret ici a rendu l'onglet
    // « Comptabilité → États → Grand-livre » muet, sans le moindre message.
    // Ne pas « harmoniser » avec ses voisines tant que le serveur ne déclare
    // pas `url_path='grand-livre'` : ce serait rouvrir le trou.
    grandLivre: (params) => api.get('/compta/etats/grand_livre/', { params }),
    balance: (params) => api.get('/compta/etats/balance/', { params }),
    cpc: (params) => api.get('/compta/etats/cpc/', { params }),
    bilan: (params) => api.get('/compta/etats/bilan/', { params }),
    esg: (params) => api.get('/compta/etats/esg/', { params }),
    etic: (params) => api.get('/compta/etats/etic/', { params }),
    positionTresorerie: (params) =>
      api.get('/compta/etats/position-tresorerie/', { params }),
    previsionnelTresorerie: (params) =>
      api.get('/compta/etats/previsionnel-tresorerie/', { params }),
    balanceAgeeFournisseurs: (params) =>
      api.get('/compta/etats/balance-agee-fournisseurs/', { params }),
    releveFournisseur: (tiersId, params) =>
      api.get(`/compta/etats/releve-fournisseur/${tiersId}/`, { params }),
    tableauFlux: (params) => api.get('/compta/etats/tableau-flux/', { params }),
    tableauImmobilisations: (params) =>
      api.get('/compta/etats/tableau-immobilisations/', { params }),
    journalItems: (params) => api.get('/compta/etats/journal-items/', { params }),
    continuiteSequences: (params) =>
      api.get('/compta/etats/continuite-sequences/', { params }),
    controleIce: (params) => api.get('/compta/etats/controle-ice/', { params }),
    dossierCloture: (params) =>
      api.get('/compta/etats/dossier-cloture/',
        { params: { export: 'xlsx', ...params }, responseType: 'blob' }),

    // ── UX7 — Exports fichiers ──
    // Le backend renvoie un fichier UNIQUEMENT avec « ?export=... » (jamais
    // « ?format= », réservé par DRF). Sans « export », ces routes renvoient du
    // JSON. On force donc `export` et `responseType:'blob'` pour télécharger.
    exportFec: (params) =>
      api.get('/compta/etats/export-fec/',
        { params: { export: 'fec', ...params }, responseType: 'blob' }),
    liasseFiscale: (params) =>
      api.get('/compta/etats/liasse-fiscale/',
        { params: { export: 'csv', ...params }, responseType: 'blob' }),
    exportFiduciaire: (params) =>
      api.get('/compta/etats/export-fiduciaire/',
        { params: { export: 'csv', ...params }, responseType: 'blob' }),
    releveDeductionsTva: (params) =>
      api.get('/compta/etats/releve-deductions-tva/',
        { params: { export: 'csv', ...params }, responseType: 'blob' }),
    declarationHonoraires: (params) =>
      api.get('/compta/etats/declaration-honoraires/',
        { params: { export: 'csv', ...params }, responseType: 'blob' }),
    aideIs: (params) =>
      api.get('/compta/etats/aide-is/',
        { params: { export: 'csv', ...params }, responseType: 'blob' }),
  },

  // ── UX6 — Trésorerie & prévisionnel ──
  tresorerie: resource('tresorerie'),
  caisses: {
    ...resource('caisses'),
    mouvementList: (id, params) =>
      api.get(`/compta/caisses/${id}/mouvement/`, { params }),
    mouvementCreer: (id, data) =>
      api.post(`/compta/caisses/${id}/mouvement/`, data),
    posterMouvement: (id, data) =>
      api.post(`/compta/caisses/${id}/poster-mouvement/`, data),
    resume: (id, params) =>
      api.get(`/compta/caisses/${id}/resume/`, { params }),
    clotureList: (id) => api.get(`/compta/caisses/${id}/cloturer/`),
    cloturer: (id, data) => api.post(`/compta/caisses/${id}/cloturer/`, data),
  },
  virements: resource('virements'),
  previsionnel: resource('previsionnel'),

  // ── UX7 — Fiscalité & déclarations ──
  declarationsTva: {
    ...resource('declarations-tva'),
    preparer: (data) => api.post('/compta/declarations-tva/preparer/', data),
    export: (id) => api.get(
      `/compta/declarations-tva/${id}/export/`, { responseType: 'blob' }),
    deposer: (id) => api.post(`/compta/declarations-tva/${id}/deposer/`),
    comparatif: (id, params) =>
      api.get(`/compta/declarations-tva/${id}/comparatif/`, { params }),
    bordereauPdf: (id) =>
      api.get(`/compta/declarations-tva/${id}/bordereau-pdf/`,
        { responseType: 'blob' }),
  },
  retenuesSource: {
    ...resource('retenues-source'),
    verser: (id) => api.post(`/compta/retenues-source/${id}/verser/`),
    bordereau: (params) =>
      api.get('/compta/retenues-source/bordereau/', { params }),
    attestation: (id) =>
      api.get(`/compta/retenues-source/${id}/attestation/`,
        { responseType: 'blob' }),
    attestationAnnuelle: (params) =>
      api.get('/compta/retenues-source/attestation-annuelle/',
        { params, responseType: 'blob' }),
  },
  timbresFiscaux: {
    ...resource('timbres-fiscaux'),
    verser: (id) => api.post(`/compta/timbres-fiscaux/${id}/verser/`),
  },

  // ── XACC9 — Calendrier des obligations fiscales ──
  obligationsFiscales: {
    ...resource('obligations-fiscales'),
    generer: (data) => api.post('/compta/obligations-fiscales/generer/', data),
    rappels: () => api.post('/compta/obligations-fiscales/rappels/'),
  },

  // ── UX8 — Immobilisations ──
  immobilisations: {
    ...resource('immobilisations'),
    planAmortissement: (id) =>
      api.get(`/compta/immobilisations/${id}/plan-amortissement/`),
    genererPlanAmortissement: (id, data) =>
      api.post(`/compta/immobilisations/${id}/plan-amortissement/`, data),
    ceder: (id, data) => api.post(`/compta/immobilisations/${id}/ceder/`, data),
    depuisFactureFournisseur: (data) =>
      api.post('/compta/immobilisations/depuis-facture-fournisseur/', data),
    // PACT163 / XACC16 — plan fiscal parallèle (amortissement dérogatoire).
    planFiscal: (id) => api.get(`/compta/immobilisations/${id}/plan-fiscal/`),
    genererPlanFiscal: (id, data) =>
      api.post(`/compta/immobilisations/${id}/plan-fiscal/`, data),
  },
  dotations: {
    ...resource('dotations'),
    poster: (id) => api.post(`/compta/dotations/${id}/poster/`),
  },
  cessions: {
    ...resource('cessions'),
    poster: (id) => api.post(`/compta/cessions/${id}/poster/`),
  },
  // ── PACT163 / XACC15 — Charges constatées d'avance (étalement) ──
  chargesAvance: {
    ...resource('charges-avance'),
  },

  // ── UX9 — Rapprochements, budgets & clôtures ──
  rapprochements: {
    ...resource('rapprochements'),
    lignesGl: (id) => api.get(`/compta/rapprochements/${id}/lignes-gl/`),
    resume: (id) => api.get(`/compta/rapprochements/${id}/resume/`),
    ajouterLigneReleve: (id, data) =>
      api.post(`/compta/rapprochements/${id}/ligne-releve/`, data),
    pointer: (id, data) =>
      api.post(`/compta/rapprochements/${id}/pointer/`, data),
    suggestions: (id) => api.get(`/compta/rapprochements/${id}/suggestions/`),
    accepterSuggestions: (id) =>
      api.post(`/compta/rapprochements/${id}/accepter-suggestions/`),
    cloturer: (id) => api.post(`/compta/rapprochements/${id}/cloturer/`),
  },
  modelesRapprochement: {
    ...resource('modeles-rapprochement'),
    appliquer: (id, data) =>
      api.post(`/compta/modeles-rapprochement/${id}/appliquer/`, data),
  },
  rapprochements3voies: {
    ...resource('rapprochements-3voies'),
    evaluer: (id) => api.post(`/compta/rapprochements-3voies/${id}/evaluer/`),
    valider: (id, data) =>
      api.post(`/compta/rapprochements-3voies/${id}/valider/`, data),
  },
  budgets: {
    ...resource('budgets'),
    // PACT163 / XACC22 — génère une ligne par courbe de répartition (au lieu
    // d'une saisie manuelle des 12 mois).
    genererLigneRepartie: (id, data) =>
      api.post(`/compta/budgets/${id}/generer-ligne-repartie/`, data),
  },
  centresCout: resource('centres-cout'),
  provisionsCreances: resource('provisions-creances'),
  comptesAuxiliaires: resource('comptes-auxiliaires'),
  mappingsCompte: resource('mappings-compte'),
  piecesJustificatives: resource('pieces-justificatives'),
  exercices: {
    ...resource('exercices'),
    cloturer: (id) => api.post(`/compta/exercices/${id}/cloturer/`),
    rouvrir: (id) => api.post(`/compta/exercices/${id}/rouvrir/`),
  },
  periodes: {
    ...resource('periodes'),
    cloturer: (id) => api.post(`/compta/periodes/${id}/cloturer/`),
    rouvrir: (id) => api.post(`/compta/periodes/${id}/rouvrir/`),
  },

  // ── FG127/128 — Effets à recevoir/payer ──
  effets: {
    ...resource('effets'),
    encaisser: (id, data) => api.post(`/compta/effets/${id}/encaisser/`, data),
    payer: (id, data) => api.post(`/compta/effets/${id}/payer/`, data),
    rejeter: (id, data) => api.post(`/compta/effets/${id}/rejeter/`, data),
    escompter: (id, data) => api.post(`/compta/effets/${id}/escompter/`, data),
    apurerEscompte: (id, data) =>
      api.post(`/compta/effets/${id}/apurer-escompte/`, data),
    endosser: (id, data) => api.post(`/compta/effets/${id}/endosser/`, data),
  },
  // ── FG129 — Bordereaux de remise en banque ──
  bordereaux: {
    ...resource('bordereaux'),
    poster: (id) => api.post(`/compta/bordereaux/${id}/poster/`),
  },
  // ── FG133/134 — Campagnes de règlement fournisseurs ──
  paymentRuns: {
    ...resource('payment-runs'),
    proposer: (id, data) => api.post(`/compta/payment-runs/${id}/proposer/`, data),
    figer: (id) => api.post(`/compta/payment-runs/${id}/figer/`),
    poster: (id) => api.post(`/compta/payment-runs/${id}/poster/`),
    fichierVirement: (id) =>
      api.get(`/compta/payment-runs/${id}/fichier-virement/`,
        { responseType: 'blob' }),
  },

  // ── FG135 — Notes de frais (écran validation/comptable, distinct RH) ──
  notesFrais: {
    ...resource('notes-frais'),
    refacturables: (params) =>
      api.get('/compta/notes-frais/refacturables/', { params }),
    refacturer: (data) => api.post('/compta/notes-frais/refacturer/', data),
    ocr: (formData) => api.post('/compta/notes-frais/ocr/', formData),
    soumettre: (id) => api.post(`/compta/notes-frais/${id}/soumettre/`),
    valider: (id, data) => api.post(`/compta/notes-frais/${id}/valider/`, data),
    rejeter: (id, data) => api.post(`/compta/notes-frais/${id}/rejeter/`, data),
    rembourser: (id, data) =>
      api.post(`/compta/notes-frais/${id}/rembourser/`, data),
    recuPdf: (id) =>
      api.get(`/compta/notes-frais/${id}/recu-pdf/`, { responseType: 'blob' }),
    analyse: (params) => api.get('/compta/notes-frais/analyse/', { params }),
  },
  rapportsNotesFrais: {
    ...resource('rapports-notes-frais'),
    soumettre: (id) => api.post(`/compta/rapports-notes-frais/${id}/soumettre/`),
    valider: (id) => api.post(`/compta/rapports-notes-frais/${id}/valider/`),
    rembourser: (id, data) =>
      api.post(`/compta/rapports-notes-frais/${id}/rembourser/`, data),
    recuPdf: (id) =>
      api.get(`/compta/rapports-notes-frais/${id}/recu-pdf/`,
        { responseType: 'blob' }),
  },
  plafondsNotesFrais: resource('plafonds-notes-frais'),
  baremesIndemnite: resource('baremes-indemnite'),
  indemnitesChantier: {
    ...resource('indemnites-chantier'),
    soumettre: (id) => api.post(`/compta/indemnites-chantier/${id}/soumettre/`),
    valider: (id, data) =>
      api.post(`/compta/indemnites-chantier/${id}/valider/`, data),
    rejeter: (id, data) =>
      api.post(`/compta/indemnites-chantier/${id}/rejeter/`, data),
    rembourser: (id, data) =>
      api.post(`/compta/indemnites-chantier/${id}/rembourser/`, data),
  },

  // ── FG145 — Retenue de garantie & cautions bancaires ──
  retenuesGarantie: {
    ...resource('retenues-garantie'),
    liberer: (id, data) =>
      api.post(`/compta/retenues-garantie/${id}/liberer/`, data),
    echeances: (params) =>
      api.get('/compta/retenues-garantie/echeances/', { params }),
  },
  cautionsBancaires: {
    ...resource('cautions-bancaires'),
    mainlevee: (id, data) =>
      api.post(`/compta/cautions-bancaires/${id}/mainlevee/`, data),
    echeances: (params) =>
      api.get('/compta/cautions-bancaires/echeances/', { params }),
  },

  // ── FG146 — Contrats à l'avancement (revenue-recognition/WIP) ──
  contratsAvancement: {
    ...resource('contrats-avancement'),
    constater: (id, data) =>
      api.post(`/compta/contrats-avancement/${id}/constater/`, data),
    avancement: (id) =>
      api.get(`/compta/contrats-avancement/${id}/avancement/`),
  },
  // ── FG147 — Travaux en cours (PCA/WIP cut-off) ──
  travauxEnCours: {
    ...resource('travaux-en-cours'),
    reprendre: (id, data) =>
      api.post(`/compta/travaux-en-cours/${id}/reprendre/`, data),
  },
  // ── FG148 — Campagnes de versement de commissions ──
  commissionPayoutRuns: {
    ...resource('commission-payout-runs'),
    valider: (id) => api.post(`/compta/commission-payout-runs/${id}/valider/`),
    poster: (id) => api.post(`/compta/commission-payout-runs/${id}/poster/`),
  },

  // ── XFAC14 — Compensation AR/AP (netting) ──
  compensations: {
    ...resource('compensations'),
    valider: (id) => api.post(`/compta/compensations/${id}/valider/`),
  },

  // ── PACT160 / XACC24 — Approbation des changements de RIB fournisseur ──
  approbationsRib: {
    ...resource('approbations-rib'),
    approuver: (id, data) =>
      api.post(`/compta/approbations-rib/${id}/approuver/`, data || {}),
    refuser: (id, data) =>
      api.post(`/compta/approbations-rib/${id}/refuser/`, data || {}),
  },

  // ── XACC26 — Provisions FNP/FAE de fin de période ──
  provisionsPeriode: {
    genererFnp: (data) =>
      api.post('/compta/provisions-periode/generer-fnp/', data),
    genererFae: (data) =>
      api.post('/compta/provisions-periode/generer-fae/', data),
    rapport: (params) =>
      api.get('/compta/provisions-periode/rapport/', { params }),
    exportCsv: (params) =>
      api.get('/compta/provisions-periode/export-csv/',
        { params, responseType: 'blob' }),
  },

  // ── COMPTA39 — Piste d'audit comptable (hash-chaînée, admin) ──
  pistesAudit: {
    list: (params) => api.get('/compta/pistes-audit/', { params }),
    get: (id) => api.get(`/compta/pistes-audit/${id}/`),
    verifier: () => api.get('/compta/pistes-audit/verifier/'),
    sceller: (data) => api.post('/compta/pistes-audit/sceller/', data),
  },

  // PACT26 — `campagnes` (FG201/XMKT10/XMKT34) est retiré d'ici : le double
  // montage `/compta/campagnes/...` a été supprimé, `CampagnesScreen.jsx`
  // consomme désormais `marketingApi.campagnes` (`/marketing/campagnes/...`).

  // ── XMKT30 / WIR65 — Calendrier marketing unifié ──
  // Agrège les 5 sources company-scoped servies par CalendrierMarketingView
  // (apps/compta/views.py) : campagnes (planifiee_le, XMKT7), posts sociaux
  // (XMKT35), étapes de séquences dues, événements (XMKT28) et relances de
  // devis abandonnés (FG203). Fenêtre ?from=&to= (AAAA-MM-JJ), filtre optionnel
  // ?channel= (appliqué côté client).
  calendrierMarketing: {
    get: (params) => api.get('/compta/calendrier-marketing/', { params }),
    reschedule: (payload) =>
      api.post('/compta/calendrier-marketing/reschedule/', payload),
  },

  /* ══ WIR107 — Sous-ensembles comptables avancés (NTFIN + XACC8) ══════════
     Ces routes existaient côté REST (apps/compta/urls.py) sans aucun client
     ici : elles étaient donc INATTEIGNABLES depuis l'ERP. Deux écrans réels
     les pilotent désormais (« Clôture » et « Écritures récurrentes ») ; les
     autres familles (consolidation, IFRS 15, analytique) sont exposées ici en
     API-only jusqu'à demande d'écran, pour ne pas dupliquer un client ad hoc
     dans chaque page future. */

  // ── NTFIN26-34 — Cockpit de clôture (checklist, accruals, variations) ──
  modelesCloture: {
    ...resource('modeles-cloture'),
    seed: () => api.post('/compta/modeles-cloture/seed/'),
  },
  tachesClotureModele: resource('taches-cloture-modele'),
  instancesCloture: {
    ...resource('instances-cloture'),
    instancier: (data) => api.post('/compta/instances-cloture/instancier/', data),
  },
  tachesCloture: {
    ...resource('taches-cloture'),
    cocher: (id, data) => api.post(`/compta/taches-cloture/${id}/cocher/`, data),
    genererOd: (id, data) =>
      api.post(`/compta/taches-cloture/${id}/generer-od/`, data),
  },
  accrualsCloture: {
    ...resource('accruals-cloture'),
    poster: (id) => api.post(`/compta/accruals-cloture/${id}/poster/`),
  },
  justificationsVariation: resource('justifications-variation'),

  // ── XACC8 / WIR107 — Modèles d'écriture & écritures récurrentes ──
  modelesEcriture: {
    ...resource('modeles-ecriture'),
    generer: (id, data) => api.post(`/compta/modeles-ecriture/${id}/generer/`, data),
  },
  lignesModeleEcriture: resource('lignes-modele-ecriture'),
  abonnementsEcriture: {
    ...resource('abonnements-ecriture'),
    genererDues: (data) =>
      api.post('/compta/abonnements-ecriture/generer-dues/', data || {}),
  },

  // ── NTFIN1-12 / 50-56 — Consolidation groupe (API-only pour l'instant) ──
  cyclesConsolidation: {
    ...resource('cycles-consolidation'),
    ouvrir: (id) => api.post(`/compta/cycles-consolidation/${id}/ouvrir/`),
    verrouiller: (id) => api.post(`/compta/cycles-consolidation/${id}/verrouiller/`),
    collecter: (id, data) => api.post(`/compta/cycles-consolidation/${id}/collecter/`, data || {}),
    controlesCollecte: (id) => api.get(`/compta/cycles-consolidation/${id}/controles-collecte/`),
    intercos: (id) => api.get(`/compta/cycles-consolidation/${id}/intercos/`),
    apparier: (id, data) => api.post(`/compta/cycles-consolidation/${id}/apparier/`, data || {}),
    eliminations: (id) => api.get(`/compta/cycles-consolidation/${id}/eliminations/`),
    genererReciproques: (id) =>
      api.post(`/compta/cycles-consolidation/${id}/generer-reciproques/`),
    interetsMinoritaires: (id, data) =>
      api.post(`/compta/cycles-consolidation/${id}/interets-minoritaires/`, data || {}),
    etatsConsolides: (id, params) =>
      api.get(`/compta/cycles-consolidation/${id}/etats-consolides/`, { params }),
    moniteur: (id) => api.get(`/compta/cycles-consolidation/${id}/moniteur/`),
    tableauFlux: (id, params) =>
      api.get(`/compta/cycles-consolidation/${id}/tableau-flux/`, { params }),
    variationCapitaux: (id) =>
      api.get(`/compta/cycles-consolidation/${id}/variation-capitaux/`),
    annexes: (id) => api.get(`/compta/cycles-consolidation/${id}/annexes/`),
    comparatif: (id) => api.get(`/compta/cycles-consolidation/${id}/comparatif/`),
    etapesAudit: (id) => api.get(`/compta/cycles-consolidation/${id}/etapes-audit/`),
    simuler: (id, data) => api.post(`/compta/cycles-consolidation/${id}/simuler/`, data || {}),
    exportLiasse: (id, params) =>
      api.get(`/compta/cycles-consolidation/${id}/export-liasse/`,
        { params: { export: 'xlsx', ...(params || {}) }, responseType: 'blob' }),
  },
  liassesRemontee: resource('liasses-remontee'),
  mappingsConsolidation: resource('mappings-consolidation'),
  operationsInterco: resource('operations-interco'),
  margesInternesStock: {
    ...resource('marges-internes-stock'),
    eliminer: (id) => api.post(`/compta/marges-internes-stock/${id}/eliminer/`),
  },
  eliminationsTitres: {
    ...resource('eliminations-titres'),
    eliminer: (id) => api.post(`/compta/eliminations-titres/${id}/eliminer/`),
  },

  // ── NTFIN — Multi-référentiel, analytique & clés de répartition (API-only) ──
  referentielsComptables: {
    ...resource('referentiels-comptables'),
    seed: () => api.post('/compta/referentiels-comptables/seed/'),
  },
  ajustementsGaap: {
    ...resource('ajustements-gaap'),
    poster: (data) => api.post('/compta/ajustements-gaap/poster/', data),
  },
  axesAnalytiques: resource('axes-analytiques'),
  imputationsAxes: resource('imputations-axes'),
  clesRepartition: {
    ...resource('cles-repartition'),
    valider: (id) => api.get(`/compta/cles-repartition/${id}/valider/`),
  },
  lignesCleRepartition: resource('lignes-cle-repartition'),
  allocations: {
    ...resource('allocations'),
    executer: (data) => api.post('/compta/allocations/executer/', data),
    reverser: (id) => api.post(`/compta/allocations/${id}/reverser/`),
  },
  allocationsRecurrentes: resource('allocations-recurrentes'),

  // ── NTFIN47-48 — Reconnaissance du revenu IFRS 15 (API-only) ──
  contratsRevenu: {
    ...resource('contrats-revenu'),
    allouer: (id) => api.post(`/compta/contrats-revenu/${id}/allouer/`),
  },
  obligationsPerformance: {
    ...resource('obligations-performance'),
    genererEcheancier: (id, data) =>
      api.post(`/compta/obligations-performance/${id}/generer-echeancier/`, data || {}),
  },
  echeancesReconnaissance: {
    ...resource('echeances-reconnaissance'),
    reconnaitre: (id) => api.post(`/compta/echeances-reconnaissance/${id}/reconnaitre/`),
  },
}

export default comptaApi
