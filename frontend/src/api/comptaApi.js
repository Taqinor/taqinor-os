import api from './axios'

/* ============================================================================
   Comptabilité (apps/compta) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /compta/... ».
   Un seul point d'import pour tous les écrans du module (UX2–UX9).
   Aucune donnée sensible (prix d'achat / marge) n'est demandée ni rendue.
   ========================================================================== */

// Déclenche le téléchargement d'un blob (export fichier) côté navigateur.
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// Fabrique générique de CRUD REST sur une ressource du routeur compta.
function resource(path) {
  return {
    list: (params) => api.get(`/compta/${path}/`, { params }),
    get: (id) => api.get(`/compta/${path}/${id}/`),
    create: (data) => api.post(`/compta/${path}/`, data),
    update: (id, data) => api.patch(`/compta/${path}/${id}/`, data),
    remove: (id) => api.delete(`/compta/${path}/${id}/`),
  }
}

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
  caisses: resource('caisses'),
  virements: resource('virements'),
  previsionnel: resource('previsionnel'),

  // ── UX7 — Fiscalité & déclarations ──
  declarationsTva: resource('declarations-tva'),
  retenuesSource: resource('retenues-source'),
  timbresFiscaux: resource('timbres-fiscaux'),

  // ── UX8 — Immobilisations ──
  immobilisations: {
    ...resource('immobilisations'),
    planAmortissement: (id) =>
      api.get(`/compta/immobilisations/${id}/plan-amortissement/`),
    genererPlanAmortissement: (id, data) =>
      api.post(`/compta/immobilisations/${id}/plan-amortissement/`, data),
    ceder: (id, data) => api.post(`/compta/immobilisations/${id}/ceder/`, data),
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
}

export default comptaApi
