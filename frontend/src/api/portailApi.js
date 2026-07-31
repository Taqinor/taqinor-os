import api from './axios'

/* ============================================================================
   NTPRT10/NTPRT11 — API du portail CLIENT authentifié.
   ----------------------------------------------------------------------------
   Toutes les routes vivent sous `/api/django/portail/…` et sont gardées côté
   serveur par `roles.IsPortalClientUser` (portée EXACTE `portail_client` +
   rattachement non nul). Aucun id de client n'est envoyé par le client : le
   scope est déduit du compte connecté côté serveur — un paramètre client_id
   dans l'URL serait exactement le trou qu'on évite.

   Le PDF du devis passe par l'UNIQUE chemin canonique `/proposal`
   (CLAUDE.md règle #4), jamais par un rendu spécifique au portail.
   ========================================================================== */

const portailApi = {
  // NTPRT19 — marque du portail pour le domaine appelant. PUBLIC (sans
  // session) : la page de login doit pouvoir se brander avant toute auth. La
  // société est résolue côté serveur par l'en-tête Host — on n'envoie AUCUN
  // identifiant de société (ce serait un énumérateur de tenants).
  themePublic: () => api.get('/public/portail/theme/'),
  devis: {
    liste: () => api.get('/portail/mes-devis/'),
    detail: (id) => api.get(`/portail/mes-devis/${id}/`),
    accepter: (id, payload) =>
      api.post(`/portail/mes-devis/${id}/accepter/`, payload),
    // Règle #4 — chemin canonique du PDF client, ouvert au propriétaire.
    pdfUrl: (id) => `/api/django/ventes/devis/${id}/proposal/`,
  },
  factures: {
    liste: () => api.get('/portail/mes-factures/'),
    detail: (id) => api.get(`/portail/mes-factures/${id}/`),
    payer: (id) => api.post(`/portail/mes-factures/${id}/payer/`, {}),
  },
}

export default portailApi
