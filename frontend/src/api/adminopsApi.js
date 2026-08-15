import api from './axios'

/**
 * Client HTTP du module Administration (apps.adminops).
 *
 * NTADM22/32 — sessions d'impersonation sous consentement : le support DEMANDE,
 * l'Administrateur du tenant AUTORISE. Aucun appel ici n'ouvre de session par
 * lui-même : le serveur reste la seule autorité (sans consentement, `demarrer`
 * répond 403).
 */
const adminopsApi = {
  // ── Impersonation (NTADM22 / NTADM32) ────────────────────────────────────
  listImpersonations: () => api.get('/adminops/impersonation/'),
  ciblesImpersonation: (params) =>
    api.get('/adminops/impersonation/cibles/', { params }),
  demanderImpersonation: (data) => api.post('/adminops/impersonation/', data),
  impersonationsEnAttente: () =>
    api.get('/adminops/impersonation/en-attente/'),
  sessionImpersonationActive: () =>
    api.get('/adminops/impersonation/session-active/'),
  consentirImpersonation: (id) =>
    api.post(`/adminops/impersonation/${id}/consentir/`),
  refuserImpersonation: (id) =>
    api.post(`/adminops/impersonation/${id}/refuser/`),
  demarrerImpersonation: (id) =>
    api.post(`/adminops/impersonation/${id}/demarrer/`),
  terminerImpersonation: (id) =>
    api.post(`/adminops/impersonation/${id}/terminer/`),

  // ── Annonces produit (NTADM18 / NTADM19) ─────────────────────────────────
  // `suppressErrorToast` : ces deux appels vivent dans la CLOCHE, montée sur
  // toute la coquille. Un échec réseau ne doit jamais y faire surgir un toast
  // d'erreur global — l'onglet se contente d'être vide.
  listAnnonces: () =>
    api.get('/adminops/annonces/', { suppressErrorToast: true }),
  marquerAnnonceLue: (id) =>
    api.post(`/adminops/annonces/${id}/marquer-lu/`, null,
      { suppressErrorToast: true }),

  // ── WIR267 — Registre de facturation de licence (N100(e), fondateur) ────
  // Strictement superuser côté serveur — jamais une surface tenant.
  listFacturationLicences: (params) =>
    api.get('/adminops/facturation-licences/', { params }),
  marquerLicencePayee: (id, data) =>
    api.post(`/adminops/facturation-licences/${id}/marquer-payee/`, data),
  exporterFacturationLicencesCsv: () =>
    api.get('/adminops/facturation-licences/export-csv/', { responseType: 'blob' }),
}

export default adminopsApi
