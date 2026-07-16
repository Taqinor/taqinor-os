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
    grandLivre: (params) => api.get('/compta/etats/grand-livre/', { params }),
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
  },
  dotations: {
    ...resource('dotations'),
    poster: (id) => api.post(`/compta/dotations/${id}/poster/`),
  },
  cessions: {
    ...resource('cessions'),
    poster: (id) => api.post(`/compta/cessions/${id}/poster/`),
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
  budgets: resource('budgets'),
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

  // ── FG201/XMKT10/XMKT34 — Campagnes marketing (email/SMS/WhatsApp) ──
  // La génération IA (XMKT34) est key-gated : `genererIaDisponible` sonde la
  // config (aucun appel LLM) — sans clé, le bouton « Générer avec l'IA » est
  // entièrement masqué ; `genererIa` renvoie une SUGGESTION éditable
  // (objet/corps), jamais auto-appliquée à la campagne.
  campagnes: {
    ...resource('campagnes'),
    envoyer: (id, data) => api.post(`/compta/campagnes/${id}/envoyer/`, data),
    genererIaDisponible: () =>
      api.get('/compta/campagnes/generer-ia-disponible/'),
    genererIa: (payload) =>
      api.post('/compta/campagnes/generer-ia/', payload),
  },

  // ── XMKT30 — Calendrier marketing unifié ──
  // Agrège 4 sources company-scoped : campagnes (planifiee_le, XMKT7), étapes
  // de séquences dues, événements (XMKT28) et relances (FG31). Fenêtre
  // ?from=&to= (AAAA-MM-JJ), filtre optionnel ?channel=.
  // NOTE (XMKT30, lane frontend/marketing) : endpoint agrégé pas encore
  // construit côté backend (aucune route `calendrier-marketing` ni vue
  // équivalente dans apps/compta/urls.py|views.py à ce jour) — câblé sur
  // l'URL conventionnelle ci-dessous, prêt à s'activer dès que
  // apps/compta/views.py expose l'agrégation (tâche BLOQUÉE côté backend).
  calendrierMarketing: {
    get: (params) => api.get('/compta/calendrier-marketing/', { params }),
    reschedule: (payload) =>
      api.post('/compta/calendrier-marketing/reschedule/', payload),
  },
}

export default comptaApi
