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
}

export default adminopsApi
