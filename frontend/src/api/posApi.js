import api from './axios'

/* XPOS — Client de l'app POS dédiée (`/api/django/pos/`).
   ----------------------------------------------------------------------------
   L'app backend `apps/pos` EXISTE et expose ses propres endpoints (montés à
   `/api/django/pos/` — voir apps/pos/urls.py + views.py) :

   - Ventes comptoir   : /pos/ventes/            (VenteComptoirViewSet)
       + POST /pos/ventes/                       créer une vente (brouillon)
       + POST /pos/ventes/<id>/lignes/           ajouter une ligne (produit + qté)
       + POST /pos/ventes/<id>/valider/          valider + paiements → Facture
       + GET  /pos/ventes/<id>/ticket-pdf/       PDF du ticket (vente validée)
       + POST /pos/ventes/<id>/ticket-escpos/    flux ESC/POS (imprimante réseau)
       + POST /pos/ventes/<id>/ticket-share-link/ lien public tokenisé du ticket
       + POST /pos/ventes/encaisser-facture/     encaisser une facture existante
       + GET  /pos/ventes/factures-recherche/    factures avec solde dû
       + GET  /pos/ventes/dashboard/             reporting ventes comptoir
       + GET  /pos/ventes/dashboard-export/      export xlsx du dashboard
   - Sessions caisse   : /pos/sessions/          (SessionCaisseViewSet)
       + POST /pos/sessions/                     ouvrir (fond de caisse)
       + POST /pos/sessions/<id>/cloturer/       clôturer (comptage espèces/TPE)
       + GET  /pos/sessions/<id>/rapport-z/      rapport Z de la session
   - Retraits (C&C)    : /pos/retraits/          (CommandeRetraitViewSet)
       + POST /pos/retraits/<id>/marquer-pret/   marquer prêt au retrait
       + POST /pos/retraits/<id>/remettre/       remettre (code de retrait)
   - Config matériel   : /pos/config-materiel/   (ConfigMaterielPOSViewSet)

   `axios` préfixe déjà `/api/django` : on n'écrit ici que `/pos/…`. */
const posApi = {
  // ── Catalogue + client (réutilise les endpoints transverses existants) ────
  // Recherche produit instantanée : filtrage texte côté client
  // (features/pos/pos.js:searchProduitsPos), sur le catalogue stock.
  getProduits: (params) => api.get('/stock/produits/', { params }),
  // Client optionnel : recherche (autocomplete QC1) + création rapide (QG3).
  searchClients: (q) => api.get('/crm/clients/search/', { params: { q } }),
  createClient: (data) => api.post('/crm/clients/', data),

  // ── Vente comptoir : brouillon → lignes → valider (paiements) ─────────────
  createVente: (data) => api.post('/pos/ventes/', data || {}),
  ajouterLigne: (venteId, data) =>
    api.post(`/pos/ventes/${venteId}/lignes/`, data),
  validerVente: (venteId, data) =>
    api.post(`/pos/ventes/${venteId}/valider/`, data),
  getVente: (venteId) => api.get(`/pos/ventes/${venteId}/`),

  // ── Ticket (XPOS7/9) : PDF, flux ESC/POS, lien public partageable ─────────
  ticketPdfUrl: (venteId) => `/pos/ventes/${venteId}/ticket-pdf/`,
  ticketEscpos: (venteId, params) =>
    api.post(`/pos/ventes/${venteId}/ticket-escpos/`, null, { params }),
  ticketShareLink: (venteId) =>
    api.post(`/pos/ventes/${venteId}/ticket-share-link/`),

  // ── Encaissement d'une facture existante (XPOS6) ──────────────────────────
  encaisserFacture: (data) =>
    api.post('/pos/ventes/encaisser-facture/', data),
  rechercheFactures: (q) =>
    api.get('/pos/ventes/factures-recherche/', { params: { q } }),

  // ── Dashboard ventes comptoir (XPOS11) ────────────────────────────────────
  getDashboard: (params) => api.get('/pos/ventes/dashboard/', { params }),
  exportDashboardUrl: () => '/pos/ventes/dashboard-export/',

  // ── Sessions de caisse (XPOS4) ────────────────────────────────────────────
  getSessions: (params) => api.get('/pos/sessions/', { params }),
  ouvrirSession: (data) => api.post('/pos/sessions/', data),
  cloturerSession: (sessionId, data) =>
    api.post(`/pos/sessions/${sessionId}/cloturer/`, data),
  rapportZ: (sessionId) => api.get(`/pos/sessions/${sessionId}/rapport-z/`),

  // ── Commandes de retrait / click-and-collect (XPOS15) ─────────────────────
  getRetraits: (params) => api.get('/pos/retraits/', { params }),
  marquerPret: (retraitId) =>
    api.post(`/pos/retraits/${retraitId}/marquer-pret/`),
  remettreRetrait: (retraitId, data) =>
    api.post(`/pos/retraits/${retraitId}/remettre/`, data),

  // ── Configuration matériel POS (XPOS18) ───────────────────────────────────
  getConfigMateriel: () => api.get('/pos/config-materiel/'),
  createConfigMateriel: (data) => api.post('/pos/config-materiel/', data),
  updateConfigMateriel: (id, data) =>
    api.patch(`/pos/config-materiel/${id}/`, data),
}

export default posApi
