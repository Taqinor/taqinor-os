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
  // NTPRT20/NTPRT27 — portails FOURNISSEUR et PARTENAIRE. Même principe que
  // ci-dessus : aucun identifiant d'entité n'est envoyé, le serveur borne au
  // rattachement du compte connecté.
  fournisseur: {
    tableauDeBord: () => api.get('/portail/fournisseur/tableau-de-bord/'),
  },
  partenaire: {
    tableauDeBord: () => api.get('/portail/partenaire/tableau-de-bord/'),
  },
  // PACT96-101 — administration ERP du portail (ComptePortailClient et son
  // provisioning, preuve d'acceptation de devis, rapprochement des paiements,
  // documents client, jalons de chantier, demandes de ticket SAV). Distinct
  // de la surface self-service CLIENT ci-dessus : ces ViewSets restent gardés
  // `IsResponsableOrAdmin` côté serveur (`IsAdminRole` en plus pour
  // `provisionner-acces`) — voir apps/portail/views.py + apps/compta/views.py.
  admin: {
    comptes: {
      liste: (params) => api.get('/portail/comptes-portail/', { params }),
      creer: (payload) => api.post('/portail/comptes-portail/', payload),
      patch: (id, payload) => api.patch(`/portail/comptes-portail/${id}/`, payload),
      provisionnerAcces: (id) =>
        api.post(`/portail/comptes-portail/${id}/provisionner-acces/`, {}),
    },
    acceptationsDevis: {
      liste: (params) => api.get('/portail/acceptations-devis-portail/', { params }),
    },
    paiementsFacture: {
      liste: (params) => api.get('/portail/paiements-facture-portail/', { params }),
      rapprocher: (id, payload) =>
        api.post(`/portail/paiements-facture-portail/${id}/rapprocher/`, payload ?? {}),
    },
    documentsClient: {
      liste: (params) => api.get('/portail/documents-client-portail/', { params }),
      marquerTraite: (id) =>
        api.post(`/portail/documents-client-portail/${id}/marquer_traite/`, {}),
    },
    jalonsChantier: {
      liste: (params) => api.get('/portail/jalons-chantier-portail/', { params }),
      creer: (payload) => api.post('/portail/jalons-chantier-portail/', payload),
      marquerAtteint: (id) =>
        api.post(`/portail/jalons-chantier-portail/${id}/marquer_atteint/`, {}),
    },
    demandesTicket: {
      liste: (params) => api.get('/portail/demandes-ticket-portail/', { params }),
      prendreEnCharge: (id, payload) =>
        api.post(`/portail/demandes-ticket-portail/${id}/prendre_en_charge/`, payload ?? {}),
    },
  },
}

export default portailApi
