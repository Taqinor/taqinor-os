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
    // AUDV25 (DRAFT165-6) — gravité BLOQUANTE + statut OUVERTE/EN_COURS
    // combinés en un seul appel (un `?statut=` à valeur unique ne peut pas
    // l'exprimer). `chantierId` optionnel — toute la société sinon.
    bloquantes: (chantierId) =>
      api.get('/btp-chantier/reserves-chantier/bloquantes/', {
        params: { chantier: chantierId || undefined },
      }),
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

  // ── PACT67 — Décompte général et définitif (DGD) — NTCON9/10/11 ─────────
  decomptes: {
    // `params` : { chantier } — optionnel.
    list: (params) => api.get('/btp-chantier/decomptes-generaux/', { params }),
    // `data` : { chantier, montant_marche_initial_ht?, situations_incluses?,
    // retenue_garantie_id? } — `reference` (préfixe DGD) + totaux recalculés
    // côté serveur à la création.
    create: (data) => api.post('/btp-chantier/decomptes-generaux/', data),
    notifier: (id) => api.post(`/btp-chantier/decomptes-generaux/${id}/notifier/`),
    contester: (id, motif, montantConteste) =>
      api.post(`/btp-chantier/decomptes-generaux/${id}/contester/`, {
        motif, montant_conteste: montantConteste,
      }),
    finaliser: (id) => api.post(`/btp-chantier/decomptes-generaux/${id}/finaliser/`),
    // Réservé admin (403 serveur sinon) — DGD verrouillé (statut définitif).
    deverrouiller: (id, motif) =>
      api.post(`/btp-chantier/decomptes-generaux/${id}/deverrouiller/`, { motif }),
    exportPdf: (id) =>
      api.get(`/btp-chantier/decomptes-generaux/${id}/export-pdf/`, {
        responseType: 'blob',
      }),
  },
  // NTCON11 — comparatif déboursé sec vs facturé (admin/responsable only —
  // jamais un coût dans une sortie client). Route hors du routeur DRF du
  // module (vue fonction dédiée par chantier).
  debourseVsFacture: (chantierId) =>
    api.get(`/btp-chantier/chantiers/${chantierId}/debourse-vs-facture/`),

  // ── NTCON14 — Lots du planning tous-corps-d'état (TCE) ──────────────────
  lots: {
    // `params` : { chantier, statut, jalon } — tous optionnels.
    list: (params) => api.get('/btp-chantier/lots/', { params }),
    // `data` : { chantier, nom, ordre?, couleur?, interne?, sous_traitant?,
    // date_debut_prevue?, date_fin_prevue?, jalon_contractuel?, montant_ht?,
    // taux_penalite_retard_pmil?, plafond_penalite_pct? }.
    create: (data) => api.post('/btp-chantier/lots/', data),
    update: (id, data) => api.patch(`/btp-chantier/lots/${id}/`, data),
    remove: (id) => api.delete(`/btp-chantier/lots/${id}/`),
    // Tâches `gestion_projet.Tache` rattachées au lot (lecture).
    taches: (id) => api.get(`/btp-chantier/lots/${id}/taches/`),
    // Remplace l'ensemble des tâches rattachées (`tacheIds` = liste d'IDs).
    definirTaches: (id, tacheIds) =>
      api.post(`/btp-chantier/lots/${id}/taches/`, { taches: tacheIds }),
    // NTCON19 — checklist de RÉCEPTION du lot (distincte de la checklist
    // d'exécution du chantier). `etapes` absente = modèle par défaut.
    checklist: (id) => api.get(`/btp-chantier/lots/${id}/checklist/`),
    definirChecklist: (id, etapes) =>
      api.post(`/btp-chantier/lots/${id}/checklist/`, { etapes }),
    cocher: (id, cle, fait = true) =>
      api.post(`/btp-chantier/lots/${id}/cocher/`, { cle, fait }),
    // Réception du lot : refusée (400) tant qu'une étape obligatoire reste
    // à cocher, selon le réglage `guard_checklist_lot_bloquant`.
    terminer: (id) => api.post(`/btp-chantier/lots/${id}/terminer/`),
  },
  // NTCON14 — Gantt du chantier GROUPÉ PAR LOT (avec code couleur).
  planningLots: (chantierId) =>
    api.get(`/btp-chantier/chantiers/${chantierId}/planning-lots/`),
  // NTCON15 — exposition aux pénalités de retard, LOT PAR LOT (donnée
  // INTERNE : le serveur exige `btp_gerer` même en lecture, 403 sinon).
  penalitesParLot: (chantierId) =>
    api.get(`/btp-chantier/chantiers/${chantierId}/penalites-par-lot/`),

  // ── NTCON18 — Opt-in au photo-rapport hebdomadaire (par chantier) ───────
  // Aucun envoi tant qu'aucune ligne `actif` n'existe pour le chantier.
  abonnementsRapportPhoto: {
    list: (params) =>
      api.get('/btp-chantier/abonnements-rapport-photo/', { params }),
    // `data` : { chantier, actif?, destinataires? (emails client/MOE) }.
    create: (data) => api.post('/btp-chantier/abonnements-rapport-photo/', data),
    update: (id, data) =>
      api.patch(`/btp-chantier/abonnements-rapport-photo/${id}/`, data),
  },

  // NTCON22 — PDF INTERNE d'avancement sur une période (`{ du, au }`) :
  // jamais un devis client, jamais servi par `/proposal`, aucun coût d'achat.
  rapportAvancement: (chantierId, params) =>
    api.get(`/btp-chantier/chantiers/${chantierId}/rapport-avancement/`, {
      params, responseType: 'blob',
    }),

  // ── NTCON25 — Réglages BTP de la société (singleton par tenant) ─────────
  // Lecture tout rôle BTP ; écriture réservée aux ADMIN (403 serveur sinon).
  parametres: {
    get: () => api.get('/btp-chantier/parametres/'),
    enregistrer: (data) => api.patch('/btp-chantier/parametres/', data),
  },

  // NTCON24 — assistant de clôture : GET = pré-requis (liste EXPLICITE de ce
  // qui bloque), POST = enchaîne vérification → DGD → notification et renvoie
  // l'URL d'export du dossier consolidé.
  cloture: {
    prerequis: (chantierId) =>
      api.get(`/btp-chantier/chantiers/${chantierId}/cloture-btp/`),
    cloturer: (chantierId, data) =>
      api.post(`/btp-chantier/chantiers/${chantierId}/cloture-btp/`, data),
  },

  // NTCON20 — ZIP « dossier chantier » consolidé (archivage légal/litige) :
  // journal, réserves levées + preuves, visas approuvés, DGD, PPSPS signés.
  exportDossierBtp: (chantierId) =>
    api.get(`/btp-chantier/chantiers/${chantierId}/export-dossier-btp/`, {
      responseType: 'blob',
    }),

  // NTCON17 — registre des intervenants (coordination SPS/CISSCT) : lecture
  // seule, agrège sous-traitants actifs + attestations + PPSPS + effectifs.
  intervenants: (chantierId) =>
    api.get(`/btp-chantier/chantiers/${chantierId}/intervenants/`),

  // ── NTCON16 — PPSPS de chantier (plan de prévention) ────────────────────
  ppsps: {
    // `params` : { chantier } — optionnel.
    list: (params) => api.get('/btp-chantier/ppsps/', { params }),
    // `data` : { chantier, titre?, document_ged_id?, lots_couverts? }.
    create: (data) => api.post('/btp-chantier/ppsps/', data),
    // Rend le plan opposable (`date_validation`/`valide_par` posés serveur).
    valider: (id) => api.post(`/btp-chantier/ppsps/${id}/valider/`),
    // Signature d'un sous-traitant (e-sign typée, loi 53-05).
    signer: (id, sousTraitantId, signataireNom) =>
      api.post(`/btp-chantier/ppsps/${id}/signer/`, {
        sous_traitant: sousTraitantId, signataire_nom: signataireNom,
      }),
  },

  // ── PACT68 — Diffusion contrôlée de plans — NTCON12/13 ───────────────────
  diffusions: {
    // `params` : { chantier, document } — tous optionnels.
    list: (params) => api.get('/btp-chantier/diffusions-plan/', { params }),
    // `data` : { chantier, document_ged_id, version_diffusee,
    // destinataires_internes?, destinataires_externes? } — `partage_ged_id`/
    // `date_diffusion`/`accuse_reception` posés côté serveur.
    create: (data) => api.post('/btp-chantier/diffusions-plan/', data),
    // Crée le partage GED externe (si destinataires externes) + notifie les
    // internes ; pose `date_diffusion` côté serveur.
    diffuser: (id) => api.post(`/btp-chantier/diffusions-plan/${id}/diffuser/`),
    // NTCON13 — alerte « plan périmé encore consulté » pour un chantier.
    plansPerimes: (chantierId) =>
      api.get('/btp-chantier/diffusions-plan/plans-perimes/', {
        params: { chantier: chantierId },
      }),
  },
}

export default btpChantierApi
