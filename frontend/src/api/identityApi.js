import api from './axios'

/* ============================================================================
   WIR134 — Client API de la fondation « Identité & accès » (apps/identity).
   ----------------------------------------------------------------------------
   Miroir fin de `apps/identity/urls.py` (préfixe `/identity/`). Toutes les
   écritures sont gouvernées `IsAdminRole` côté serveur ; `company` est TOUJOURS
   forcée côté serveur (jamais lue du corps). `api` préfixe déjà `/api/django`.
   ========================================================================== */

const identityApi = {
  // NTSEC11 — politique réseau (une par société) + plages CIDR autorisées.
  networkPolicies: {
    list: () => api.get('/identity/network-policies/'),
    create: (data) => api.post('/identity/network-policies/', data),
    update: (id, data) => api.patch(`/identity/network-policies/${id}/`, data),
    remove: (id) => api.delete(`/identity/network-policies/${id}/`),
  },
  ipRules: {
    list: () => api.get('/identity/ip-allow-rules/'),
    create: (data) => api.post('/identity/ip-allow-rules/', data),
    remove: (id) => api.delete(`/identity/ip-allow-rules/${id}/`),
  },

  // NTSEC14 — appareils de confiance de l'utilisateur (liste + « oublier »,
  // révocation douce qui reforce la MFA sur cet appareil).
  trustedDevices: {
    list: () => api.get('/identity/trusted-devices/'),
    forget: (id) => api.delete(`/identity/trusted-devices/${id}/`),
  },

  // NTSEC1 — fournisseurs d'identité SSO (SAML/OIDC).
  providers: {
    list: () => api.get('/identity/providers/'),
    create: (data) => api.post('/identity/providers/', data),
    update: (id, data) => api.patch(`/identity/providers/${id}/`, data),
    remove: (id) => api.delete(`/identity/providers/${id}/`),
  },

  // NTSEC24 — comptes de service (jetons machine-à-machine).
  serviceAccounts: {
    list: () => api.get('/identity/service-accounts/'),
    create: (data) => api.post('/identity/service-accounts/', data),
    remove: (id) => api.delete(`/identity/service-accounts/${id}/`),
  },

  // NTSEC27 — posture de sécurité consolidée (score + items faibles).
  posture: () => api.get('/identity/posture/'),

  // NTSEC22 — accès break-glass : liste + octroi (Directeur only, MFA requise).
  breakGlass: {
    list: () => api.get('/identity/break-glass/'),
    grant: (data) => api.post('/identity/break-glass/', data),
  },

  // NTSEC28 — bannière légale de connexion (pré-auth). `get` renvoie le texte
  // à afficher ; `acknowledge` journalise l'accusé (best-effort).
  loginBanner: {
    get: (username) =>
      api.get('/identity/login-banner/', { params: { username } }),
    acknowledge: (username) =>
      api.post('/identity/login-banner/', { username }),
  },
}

export default identityApi
