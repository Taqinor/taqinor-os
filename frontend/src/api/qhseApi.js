import api from './axios'

/* ============================================================================
   UX29–UX33 — Client API du module QHSE (Qualité · Hygiène · Sécurité ·
   Environnement). Miroir fin du routeur DRF `apps/qhse` (préfixe `/qhse/`).
   Chaque ressource = un CRUD générique + ses @actions dédiées. Aucune logique
   métier ici : la vérité (statuts, calculs TF/TG, readiness ISO, échéances,
   gating clôture) vit côté serveur. `api` préfixe déjà `/api/django`.
   ========================================================================== */

// Fabrique un CRUD standard pour une ressource `/qhse/<slug>/`.
function crud(slug) {
  const base = `/qhse/${slug}/`
  return {
    list: (params) => api.get(base, { params }),
    get: (id) => api.get(`${base}${id}/`),
    create: (data) => api.post(base, data),
    update: (id, data) => api.patch(`${base}${id}/`, data),
    remove: (id) => api.delete(`${base}${id}/`),
  }
}

const qhseApi = {
  // ── Cockpit (UX29) ──────────────────────────────────────────────────────
  // Digest / calendrier unifié des échéances QHSE (inspections/permis/CNSS).
  calendrier: (params) => api.get('/qhse/calendrier/', { params }),
  // Tableau de bord « préparation ISO 9001:2015 » (score global + critères).
  iso9001Readiness: () => api.get('/qhse/iso9001-readiness/'),

  // ── UX30 — Non-conformités & CAPA ──────────────────────────────────────
  nonConformites: {
    ...crud('non-conformites'),
    // Chatter (Odoo-style) : historique (auto + notes) et ajout de note.
    historique: (id) => api.get(`/qhse/non-conformites/${id}/historique/`),
    noter: (id, body) => api.post(`/qhse/non-conformites/${id}/noter/`, { body }),
    // Crée une NCR depuis une réserve de chantier.
    depuisReserve: (data) =>
      api.post('/qhse/non-conformites/depuis-reserve/', data),
    // Clôture (conditionnée à l'efficacité des CAPA côté serveur).
    cloturer: (id) => api.post(`/qhse/non-conformites/${id}/cloturer/`),
  },
  capa: {
    ...crud('capa'),
    // CAPA en retard de la société (échéance passée, non résolue).
    enRetard: () => api.get('/qhse/capa/en-retard/'),
    // Relance en masse des CAPA en retard (notifications côté serveur).
    relancerRetards: () => api.post('/qhse/capa/relancer-retards/'),
    // Vérifie l'efficacité d'une CAPA réalisée.
    verifierEfficacite: (id, data) =>
      api.post(`/qhse/capa/${id}/verifier-efficacite/`, data),
  },

  // ── UX31 — Inspections & audits ─────────────────────────────────────────
  plansInspection: crud('plans-inspection'),
  pointsControle: crud('points-controle'),
  plansChantier: {
    ...crud('plans-chantier'),
    // Ouvre un plan chantier depuis un modèle ITP + un chantier_id.
    instancier: (data) => api.post('/qhse/plans-chantier/instancier/', data),
    holdPoints: (id) => api.get(`/qhse/plans-chantier/${id}/hold-points/`),
  },
  releves: {
    ...crud('releves'),
    photos: (id) => api.get(`/qhse/releves/${id}/photos/`),
  },
  courbesIv: crud('courbes-iv'),
  grillesAudit: crud('grilles-audit'),
  criteresAudit: crud('criteres-audit'),
  audits: {
    ...crud('audits'),
    calculerScore: (id) => api.post(`/qhse/audits/${id}/calculer-score/`),
    // Lève une NCR pour chaque réponse non conforme de l'audit.
    leverNcr: (id) => api.post(`/qhse/audits/${id}/lever-ncr/`),
  },
  reponsesCritere: crud('reponses-critere'),
  notationsFinChantier: {
    ...crud('notations-fin-chantier'),
    calculer: (id) => api.post(`/qhse/notations-fin-chantier/${id}/calculer/`),
    // Gate advisory : le chantier peut-il clôturer ? (`?chantier_id=`)
    peutCloturer: (params) =>
      api.get('/qhse/notations-fin-chantier/peut-cloturer/', { params }),
  },
  itemsNotation: crud('items-notation'),
  proceduresQualite: {
    ...crud('procedures-qualite'),
    activer: (id) => api.post(`/qhse/procedures-qualite/${id}/activer/`),
    courante: (params) =>
      api.get('/qhse/procedures-qualite/courante/', { params }),
    versions: (id) => api.get(`/qhse/procedures-qualite/${id}/versions/`),
  },
  retoursClient: {
    ...crud('retours-client'),
    moyenne: (params) => api.get('/qhse/retours-client/moyenne/', { params }),
  },

  // ── UX32 — Risques, permis & incidents ─────────────────────────────────
  evaluationsRisque: {
    ...crud('evaluations-risque'),
    criticite: (id) => api.get(`/qhse/evaluations-risque/${id}/criticite/`),
    documentUniqueStatut: (params) =>
      api.get('/qhse/evaluations-risque/document-unique-statut/', { params }),
  },
  lignesEvaluationRisque: crud('lignes-evaluation-risque'),
  permisTravail: {
    ...crud('permis-travail'),
    valider: (id) => api.post(`/qhse/permis-travail/${id}/valider/`),
    cloturer: (id) => api.post(`/qhse/permis-travail/${id}/cloturer/`),
    // Permis qui expirent bientôt ou sont déjà expirés.
    expirant: (params) => api.get('/qhse/permis-travail/expirant/', { params }),
  },
  consignationsLoto: {
    ...crud('consignations-loto'),
    deconsigner: (id) => api.post(`/qhse/consignations-loto/${id}/deconsigner/`),
  },
  inductionsSecurite: {
    ...crud('inductions-securite'),
    acquitter: (id, data) =>
      api.post(`/qhse/inductions-securite/${id}/acquitter/`, data),
  },
  plansUrgence: crud('plans-urgence'),
  contactsUrgence: crud('contacts-urgence'),
  secouristes: crud('secouristes'),
  incidents: {
    ...crud('incidents'),
    // Statistiques TF / TG des accidents du travail (QHSE34).
    statistiquesTfTg: (params) =>
      api.get('/qhse/incidents/statistiques-tf-tg/', { params }),
  },
  declarationsCnss: {
    ...crud('declarations-cnss'),
    aEcheance: (params) =>
      api.get('/qhse/declarations-cnss/a-echeance/', { params }),
  },
  analysesIncident: {
    ...crud('analyses-incident'),
    genererCapa: (id) => api.post(`/qhse/analyses-incident/${id}/generer-capa/`),
  },
  causesIncident: crud('causes-incident'),
  inspectionsSecurite: {
    ...crud('inspections-securite'),
    leverNcr: (id) => api.post(`/qhse/inspections-securite/${id}/lever-ncr/`),
  },

  // ── UX33 — Environnement & ESG ─────────────────────────────────────────
  dechets: crud('dechets'),
  bordereauxDechets: crud('bordereaux-dechets'),
  recyclageModules: crud('recyclage-modules'),
  conformitesEnvironnementales: {
    ...crud('conformites-environnementales'),
    aRelancer: (params) =>
      api.get('/qhse/conformites-environnementales/a-relancer/', { params }),
  },
  bilansCarbone: crud('bilans-carbone'),
  lignesBilanCarbone: crud('lignes-bilan-carbone'),
  indicateursEsg: crud('indicateurs-esg'),

  // ── XQHS2 — Dérogations & disposition NCR ──────────────────────────────
  derogations: crud('derogations'),

  // ── XQHS3 — Contrôle qualité à la réception fournisseur ────────────────
  plansControleReception: crud('plans-controle-reception'),
  pointsControleReception: crud('points-controle-reception'),
  controlesReception: {
    ...crud('controles-reception'),
    statuer: (id, data) =>
      api.post(`/qhse/controles-reception/${id}/statuer/`, data),
  },

  // ── XQHS4 — Codes de défaut & Pareto qualité ───────────────────────────
  codesDefaut: crud('codes-defaut'),
  paretoDefauts: (params) => api.get('/qhse/pareto-defauts/', { params }),

  // ── XQHS1 — Checklist des étapes légales AT/MP ─────────────────────────
  etapesDeclarationAt: {
    ...crud('etapes-declaration-at'),
    marquerFait: (id) =>
      api.post(`/qhse/etapes-declaration-at/${id}/marquer-fait/`),
  },

  // ── XQHS16 — Signalement QR public (chantier) ──────────────────────────
  liensSignalement: {
    ...crud('liens-signalement'),
    qr: (id) =>
      api.get(`/qhse/liens-signalement/${id}/qr/`, { responseType: 'blob' }),
  },
  signalementsPublics: crud('signalements-publics'),

  // ── XQHS17 — Observations sécurité comportementales (BBS) ──────────────
  observationsSecurite: {
    ...crud('observations-securite'),
    convertirCapa: (id, data) =>
      api.post(`/qhse/observations-securite/${id}/convertir-capa/`, data),
    convertirNcr: (id, data) =>
      api.post(`/qhse/observations-securite/${id}/convertir-ncr/`, data),
    compteurs: (params) =>
      api.get('/qhse/observations-securite/compteurs/', { params }),
  },

  // ── XQHS18 — Exercices d'urgence (drills) ──────────────────────────────
  exercicesUrgence: crud('exercices-urgence'),

  // ── XQHS20 — Registre des aspects & impacts environnementaux ───────────
  aspectsEnvironnementaux: {
    ...crud('aspects-environnementaux'),
    aRevoir: () => api.get('/qhse/aspects-environnementaux/a-revoir/'),
  },

  // ── XQHS21 — Relevés de consommation par site ──────────────────────────
  relevesConsommation: crud('releves-consommation'),

  // ── XQHS22 — Coût de la non-qualité (rollup, gated) ────────────────────
  coutNonQualite: (params) => api.get('/qhse/cout-non-qualite/', { params }),

  // ── XQHS23 — Pont SAV ↔ NCR ─────────────────────────────────────────────
  // (nonConformites.depuisTicketSav / creerIntervention / tauxDefaillance
  // ajoutés ci-dessous, en complément du bloc `nonConformites` UX30.)

  // ── XQHS24 — Gestion du changement (MOC léger) ─────────────────────────
  demandesChangement: {
    ...crud('demandes-changement'),
    transitionner: (id, data) =>
      api.post(`/qhse/demandes-changement/${id}/transitionner/`, data),
    creerCapa: (id, data) =>
      api.post(`/qhse/demandes-changement/${id}/creer-capa/`, data),
    aReverser: () => api.get('/qhse/demandes-changement/a-reverser/'),
    relancer: () => api.post('/qhse/demandes-changement/relancer/'),
  },

  // ── XQHS26 — Veille réglementaire ───────────────────────────────────────
  veillesReglementaires: {
    ...crud('veilles-reglementaires'),
    genererRevuesDues: () =>
      api.post('/qhse/veilles-reglementaires/generer-revues-dues/'),
  },
  revuesVeille: {
    ...crud('revues-veille'),
    conclure: (id, data) =>
      api.post(`/qhse/revues-veille/${id}/conclure/`, data),
  },

  // ── XQHS25 — Assistance IA QHSE (key-gated) ─────────────────────────────
  ia: {
    suggestionClassification: (data) =>
      api.post('/qhse/ia/suggestion-classification/', data),
    suggestionAnalyse: (data) =>
      api.post('/qhse/ia/suggestion-analyse/', data),
  },

  // ── XQHS27 — Documents terrain imprimables bilingues FR/AR ──────────────
  causerieSecuritePdf: (causerieId, params) =>
    api.get(`/qhse/causeries/${causerieId}/pdf/`, {
      params, responseType: 'blob',
    }),
}

// ── XQHS2/XQHS23 — actions complémentaires sur `nonConformites` (UX30) ────
qhseApi.nonConformites.poserDisposition = (id, data) =>
  api.post(`/qhse/non-conformites/${id}/poser-disposition/`, data)
qhseApi.nonConformites.depuisTicketSav = (data) =>
  api.post('/qhse/non-conformites/depuis-ticket-sav/', data)
qhseApi.nonConformites.creerIntervention = (id, data) =>
  api.post(`/qhse/non-conformites/${id}/creer-intervention/`, data)
qhseApi.nonConformites.tauxDefaillanceProduit = () =>
  api.get('/qhse/non-conformites/taux-defaillance-produit/')

// ── WIR115 — Check-in sécurité (technicien seul sur site) ────────────────────
qhseApi.checkinsSecurite = {
  ...crud('checkins-securite'),
  // Enregistre le check-out réel (maintenant) — clôt le cycle.
  checkout: (id) => api.post(`/qhse/checkins-securite/${id}/checkout/`),
}

// ── WIR115 — SCAR : demande d'action corrective fournisseur ──────────────────
qhseApi.demandesActionFournisseur = {
  ...crud('demandes-action-fournisseur'),
  // Réponse fournisseur (émise → répondue) : cause racine + action.
  repondre: (id, data) =>
    api.post(`/qhse/demandes-action-fournisseur/${id}/repondre/`, data),
  // Vérification d'efficacité (répondue → vérifiée/close) : { efficace }.
  verifier: (id, data) =>
    api.post(`/qhse/demandes-action-fournisseur/${id}/verifier/`, data),
}

export default qhseApi
