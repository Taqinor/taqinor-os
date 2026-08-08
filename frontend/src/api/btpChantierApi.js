import api from './axios'

/* ============================================================================
   BTP / Chantier (apps.btp_chantier, Groupe NTCON) — client API.
   ----------------------------------------------------------------------------
   Groupe PACT §E2 — le backend (7 ressources : réserves de chantier, RFI,
   visas de documents techniques, journal de chantier, avenants, DGD,
   diffusion de plans) était COMPLET et testé mais l'app n'avait AUCUN fichier
   client : ses ressources étaient toutes invisibles. Ce fichier grandit tâche
   par tâche (PACT62-68), une section par ressource — les chemins reprennent
   EXACTEMENT `apps/btp_chantier/urls.py` (préfixe `/btp-chantier/`, monté
   dans `erp_agentique/urls.py`), jamais un endpoint réinventé.
   ========================================================================== */

const btpChantierApi = {
  // ── PACT62 — Réserves de chantier (punch-list géo-localisée) — NTCON1/2 ──
  reserves: {
    // `params` : { lot, statut, gravite, chantier } — tous optionnels.
    list: (params) => api.get('/btp-chantier/reserves-chantier/', { params }),
    get: (id) => api.get(`/btp-chantier/reserves-chantier/${id}/`),
    // `data` : { chantier, lot?, localisation_plan:{document_ged_id,x,y},
    // description, gravite, responsable_leve?, date_limite? }.
    create: (data) => api.post('/btp-chantier/reserves-chantier/', data),
    photos: (id) => api.get(`/btp-chantier/reserves-chantier/${id}/photos/`),
    // Requiert côté serveur : une photo `records.Attachment` phase=apres déjà
    // déposée, et `signataire_nom` (loi 53-05) — sinon 400 avec le motif exact.
    lever: (id, signataireNom) =>
      api.post(`/btp-chantier/reserves-chantier/${id}/lever/`, {
        signataire_nom: signataireNom,
      }),
    contester: (id, motif) =>
      api.post(`/btp-chantier/reserves-chantier/${id}/contester/`, { motif }),
  },

  // ── PACT63 — Demandes d'information technique (RFI) — NTCON3/4 ──────────
  rfi: {
    // `params` : { chantier, statut } — tous optionnels.
    list: (params) => api.get('/btp-chantier/rfi/', { params }),
    // `data` : { chantier, question, destinataire_texte?, destinataire_user?,
    // delai_jours?, impact_cout?, impact_delai_jours? } — `numero` et
    // `date_limite_reponse` posés côté serveur (jours OUVRÉS).
    create: (data) => api.post('/btp-chantier/rfi/', data),
    repondre: (id, texte) => api.post(`/btp-chantier/rfi/${id}/repondre/`, { texte }),
    clore: (id) => api.post(`/btp-chantier/rfi/${id}/clore/`),
  },

  // ── PACT64 — Visas de documents techniques — NTCON5 ──────────────────────
  visas: {
    // `params` : { chantier, statut } — tous optionnels.
    list: (params) => api.get('/btp-chantier/visas/', { params }),
    // `data` : { chantier, document_ged_id, type_visa, delai_revue_jours? } —
    // `reference` (préfixe VIS) posée côté serveur.
    create: (data) => api.post('/btp-chantier/visas/', data),
    soumettreObservations: (id, observations) =>
      api.post(`/btp-chantier/visas/${id}/soumettre-observations/`, { observations }),
    approuver: (id, { avecObservations = false, observations = '' } = {}) =>
      api.post(`/btp-chantier/visas/${id}/approuver/`, {
        avec_observations: avecObservations, observations,
      }),
    refuser: (id, observations) =>
      api.post(`/btp-chantier/visas/${id}/refuser/`, { observations }),
  },

  // ── PACT65 — Journal de chantier quotidien — NTCON6 ──────────────────────
  journal: {
    // `params` : { chantier, du, au } — tous optionnels.
    list: (params) => api.get('/btp-chantier/journal-chantier/', { params }),
    // `data` : { chantier, date, meteo?, effectif_interne?,
    // effectif_sous_traitant?, materiel_present?, evenements?, visiteurs? } —
    // une entrée par jour/chantier (contrainte serveur, 400 sur doublon).
    create: (data) => api.post('/btp-chantier/journal-chantier/', data),
    // `params` : { chantier (requis), du?, au? } — PDF interne WeasyPrint.
    exportPdf: (params) =>
      api.get('/btp-chantier/journal-chantier/export-pdf/', {
        params, responseType: 'blob',
      }),
  },

  // ── PACT66 — Avenants de chantier (chiffrage + approbation) — NTCON7/8 ──
  avenants: {
    // `params` : { chantier, statut } — tous optionnels.
    list: (params) => api.get('/btp-chantier/avenants-chantier/', { params }),
    // `data` : { chantier, description, montant_ht, impact_delai_jours?,
    // impact_budget?, avenant_contrat_id?, lignes? } — `reference` (préfixe
    // AVC) posée côté serveur.
    create: (data) => api.post('/btp-chantier/avenants-chantier/', data),
    // Passe en « soumis au client » + (re)génère le lien public tokenisé.
    faireApprouver: (id) =>
      api.post(`/btp-chantier/avenants-chantier/${id}/faire-approuver/`),
    // Décision INTERNE (sans passer par le lien public).
    approuver: (id) => api.post(`/btp-chantier/avenants-chantier/${id}/approuver/`),
    refuser: (id, motif) =>
      api.post(`/btp-chantier/avenants-chantier/${id}/refuser/`, { motif }),
  },
}

export default btpChantierApi
