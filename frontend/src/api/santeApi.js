import api from './axios'

/* ============================================================================
   Santé (apps/sante) — client API.
   ----------------------------------------------------------------------------
   axios préfixe déjà « /api/django » : on appelle donc « /sante/... ».
   Basenames DRF confirmés côté backend : praticiens / salles / patients /
   rendezvous. Le calendrier `rendezvous` accepte les filtres
   ?praticien=&salle=&date_debut=&date_fin= (NTSAN4).
   ========================================================================== */

const santeApi = {
  // ── Praticiens ──
  praticiens: {
    list: (params) => api.get('/sante/praticiens/', { params }),
  },

  // ── Salles ──
  salles: {
    list: (params) => api.get('/sante/salles/', { params }),
  },

  // ── Patients ──
  // `q` (NTSAN18 — écran Réception) cherche par nom/prénom/CIN/téléphone.
  patients: {
    list: (params) => api.get('/sante/patients/', { params }),
    get: (id) => api.get(`/sante/patients/${id}/`),
    create: (data) => api.post('/sante/patients/', data),
    update: (id, data) => api.patch(`/sante/patients/${id}/`, data),
  },

  // ── Rendez-vous (agenda) ──
  rendezvous: {
    list: (params) => api.get('/sante/rendezvous/', { params }),
    create: (data) => api.post('/sante/rendezvous/', data),
    update: (id, data) => api.patch(`/sante/rendezvous/${id}/`, data),
    remove: (id) => api.delete(`/sante/rendezvous/${id}/`),
    // NTSAN18 — bouton « Patient arrivé » de l'écran Réception : bascule le
    // statut en salle d'attente (le serveur reste source de vérité).
    checkin: (id) => api.patch(`/sante/rendezvous/${id}/`, { statut: 'arrive' }),
    // WIR53 — NTSAN37 : annulation (délai + pénalité calculés côté serveur,
    // jamais de facturation auto). `annule_par` attendu : 'patient'|'clinique'.
    // Réponse : le RDV mis à jour + `penalite_applicable` (bool).
    annuler: (id, annule_par) =>
      api.post(`/sante/rendezvous/${id}/annuler/`, { annule_par }),
  },

  // ── Nomenclature des actes (NTSAN7 — paramétrage clinique) ──
  // `actif` est en lecture seule côté API : le soft-disable passe par les
  // actions dédiées (jamais un DELETE physique une fois l'acte utilisé).
  actesMedicaux: {
    list: (params) => api.get('/sante/actes-medicaux/', { params }),
    create: (data) => api.post('/sante/actes-medicaux/', data),
    update: (id, data) => api.patch(`/sante/actes-medicaux/${id}/`, data),
    desactiver: (id) => api.post(`/sante/actes-medicaux/${id}/desactiver/`),
    activer: (id) => api.post(`/sante/actes-medicaux/${id}/activer/`),
  },

  // ── Prises en charge / entente préalable (NTSAN12) ── WIR53(b) : la
  // notification `sante.alertes_prise_en_charge_expirant` pointe vers
  // `/sante/prises-en-charge?id=<pk>` — `PrisesEnChargePage` lit ce `?id=`.
  prisesEnCharge: {
    list: (params) => api.get('/sante/prises-en-charge/', { params }),
    get: (id) => api.get(`/sante/prises-en-charge/${id}/`),
  },

  // ── Conventions (NTSAN9) ── noms utilisés pour l'affichage des PEC.
  conventions: {
    list: (params) => api.get('/sante/conventions/', { params }),
    create: (data) => api.post('/sante/conventions/', data),
  },

  // ── Grilles tarifaires (NTSAN8) — tarifs par convention/acte. ──
  grillesTarifaires: {
    list: (params) => api.get('/sante/grilles-tarifaires/', { params }),
    create: (data) => api.post('/sante/grilles-tarifaires/', data),
  },

  // ── Admissions (NTSAN6 — WIR142) — ouvrir/clôturer un séjour patient. ──
  admissions: {
    list: (params) => api.get('/sante/admissions/', { params }),
    create: (data) => api.post('/sante/admissions/', data),
    cloturer: (id) => api.post(`/sante/admissions/${id}/cloturer/`),
  },

  // ── Actes réalisés (NTSAN10 — WIR142) — `tarif_applique_ttc` est TOUJOURS
  // calculé côté serveur, jamais envoyé par le client. ──
  actesRealises: {
    list: (params) => api.get('/sante/actes-realises/', { params }),
    create: (data) => api.post('/sante/actes-realises/', data),
  },

  // ── Factures santé (NTSAN13 — WIR142) — `POST` agrège des ActeRealise
  // existants non facturés : {admission, actes_realises: [...], convention?,
  // remise_ttc?}. Split tiers payant/patient calculé côté serveur. ──
  facturesSante: {
    list: (params) => api.get('/sante/factures-sante/', { params }),
    get: (id) => api.get(`/sante/factures-sante/${id}/`),
    create: (data) => api.post('/sante/factures-sante/', data),
    // WIR273 — NTSAN28 : actes les plus facturés (volume + CA) + répartition
    // du CA par convention. Filtres optionnels `date_debut`/`date_fin`.
    statistiques: (params) => api.get('/sante/factures-sante/statistiques/', { params }),
  },

  // ── Encaissement (NTSAN15 — WIR142) — `encaisse_par` posé côté serveur. ──
  paiementsSante: {
    list: (params) => api.get('/sante/paiements-sante/', { params }),
    create: (data) => api.post('/sante/paiements-sante/', data),
  },

  // ── Configuration agenda (WIR142) — horaires/indisponibilités/motifs/
  // sites du praticien. ──
  horairesOuverturePraticien: {
    list: (params) => api.get('/sante/horaires-ouverture-praticien/', { params }),
    create: (data) => api.post('/sante/horaires-ouverture-praticien/', data),
  },
  indisponibilitesPraticien: {
    list: (params) => api.get('/sante/indisponibilites-praticien/', { params }),
    create: (data) => api.post('/sante/indisponibilites-praticien/', data),
  },
  motifsConsultation: {
    list: (params) => api.get('/sante/motifs-consultation/', { params }),
    create: (data) => api.post('/sante/motifs-consultation/', data),
  },
  sitesPraticien: {
    list: (params) => api.get('/sante/sites-praticien/', { params }),
    create: (data) => api.post('/sante/sites-praticien/', data),
  },
}

export default santeApi
