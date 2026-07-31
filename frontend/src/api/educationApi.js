import api from './axios'

/* ============================================================================
   Éducation (apps/education) — client API.
   ----------------------------------------------------------------------------
   WIR143 — le backend est complet et testé (structure année/niveau/classe,
   familles/élèves + inscriptions, workflow validation/liste d'attente
   FIFO/promotion, scolarité, présences bulk + notif absence, notes, emploi du
   temps, cantine, discipline, portail parents, certificats/exports) mais
   AUCUN client frontend n'existait avant ce lot. axios préfixe déjà
   « /api/django » : on appelle donc « /education/... ».
   ========================================================================== */

const educationApi = {
  // ── Structure (années scolaires / niveaux / classes) — NTEDU1 ──
  anneesScolaires: {
    list: (params) => api.get('/education/annees-scolaires/', { params }),
    create: (data) => api.post('/education/annees-scolaires/', data),
    update: (id, data) => api.patch(`/education/annees-scolaires/${id}/`, data),
  },
  niveaux: {
    list: (params) => api.get('/education/niveaux/', { params }),
    create: (data) => api.post('/education/niveaux/', data),
  },
  classes: {
    list: (params) => api.get('/education/classes/', { params }),
    create: (data) => api.post('/education/classes/', data),
    update: (id, data) => api.patch(`/education/classes/${id}/`, data),
    // NTEDU37 — export liste de classe (contacts parents), ?type=pdf|xlsx.
    export: (id, type = 'xlsx') =>
      api.get(`/education/classes/${id}/export/`, {
        params: { type }, responseType: 'blob',
      }),
    trombinoscope: (id) => api.get(`/education/classes/${id}/trombinoscope/`),
  },

  // ── Familles / élèves — NTEDU2 ──
  familles: {
    list: (params) => api.get('/education/familles/', { params }),
    get: (id) => api.get(`/education/familles/${id}/`),
    create: (data) => api.post('/education/familles/', data),
    update: (id, data) => api.patch(`/education/familles/${id}/`, data),
  },
  eleves: {
    list: (params) => api.get('/education/eleves/', { params }),
    get: (id) => api.get(`/education/eleves/${id}/`),
    create: (data) => api.post('/education/eleves/', data),
    update: (id, data) => api.patch(`/education/eleves/${id}/`, data),
    // NTEDU18 — certificat de scolarité PDF (numéroté côté serveur).
    certificatScolarite: (id, anneeScolaireId) =>
      api.get(`/education/eleves/${id}/certificat-scolarite/`, {
        params: anneeScolaireId ? { annee_scolaire: anneeScolaireId } : {},
        responseType: 'blob',
      }),
  },

  // ── Inscriptions — NTEDU3/4/5 ──
  inscriptions: {
    list: (params) => api.get('/education/inscriptions/', { params }),
    create: (data) => api.post('/education/inscriptions/', data),
    valider: (id) => api.post(`/education/inscriptions/${id}/valider/`),
    refuser: (id) => api.post(`/education/inscriptions/${id}/refuser/`),
    affecterClasse: (id, classeId) =>
      api.post(`/education/inscriptions/${id}/affecter-classe/`, { classe: classeId }),
    listeAttente: (classeId) =>
      api.get('/education/inscriptions/liste-attente/', { params: { classe: classeId } }),
    desinscrire: (id) => api.post(`/education/inscriptions/${id}/desinscrire/`),
    promouvoir: (classeId) =>
      api.post('/education/inscriptions/promouvoir/', { classe: classeId }),
    reinscriptionMasse: (anneeSourceId, anneeCibleId) =>
      api.post('/education/inscriptions/reinscription-masse/', {
        annee_source: anneeSourceId, annee_cible: anneeCibleId,
      }),
  },

  // ── Scolarité (grilles tarifaires / remises / échéancier) — NTEDU6/8 ──
  grillesTarifaires: {
    list: (params) => api.get('/education/grilles-tarifaires/', { params }),
    create: (data) => api.post('/education/grilles-tarifaires/', data),
  },
  remises: {
    list: (params) => api.get('/education/remises/', { params }),
    create: (data) => api.post('/education/remises/', data),
    approuver: (id) => api.post(`/education/remises/${id}/approuver/`),
    rejeter: (id) => api.post(`/education/remises/${id}/rejeter/`),
  },
  // Échéancier : LECTURE SEULE (généré exclusivement à la validation d'une
  // inscription — jamais créé/modifié directement).
  echeanciers: {
    list: (params) => api.get('/education/echeanciers/', { params }),
    get: (id) => api.get(`/education/echeanciers/${id}/`),
  },

  // ── Présences (bulk par séance) — NTEDU12 ──
  seances: {
    list: (params) => api.get('/education/seances/', { params }),
    create: (data) => api.post('/education/seances/', data),
  },
  presences: {
    list: (params) => api.get('/education/presences/', { params }),
    // NTEDU12 — {seance, presences: [{eleve, statut, justificatif?}, ...]},
    // upsert (create/update) par (seance, eleve) — jamais un appel/élève.
    bulkSaisie: (seanceId, presences) =>
      api.post('/education/presences/bulk-saisie/', { seance: seanceId, presences }),
  },

  // ── Matières / évaluations / notes (bulk) — NTEDU14/15 ──
  matieres: {
    list: (params) => api.get('/education/matieres/', { params }),
    create: (data) => api.post('/education/matieres/', data),
  },
  matieresClasse: {
    list: (params) => api.get('/education/matieres-classe/', { params }),
    create: (data) => api.post('/education/matieres-classe/', data),
  },
  evaluations: {
    list: (params) => api.get('/education/evaluations/', { params }),
    create: (data) => api.post('/education/evaluations/', data),
  },
  notes: {
    list: (params) => api.get('/education/notes/', { params }),
    // NTEDU15 — {evaluation, notes: [{eleve, valeur, appreciation?}, ...]}.
    bulkSaisie: (evaluationId, notes) =>
      api.post('/education/notes/bulk-saisie/', { evaluation: evaluationId, notes }),
  },

  // ── Emploi du temps (créneaux hebdo par classe) — NTEDU21 ──
  emploiDuTemps: {
    list: (params) => api.get('/education/emploi-du-temps/', { params }),
    create: (data) => api.post('/education/emploi-du-temps/', data),
    update: (id, data) => api.patch(`/education/emploi-du-temps/${id}/`, data),
    remove: (id) => api.delete(`/education/emploi-du-temps/${id}/`),
  },

  // ── Cantine (menus + inscriptions) — NTEDU25 ──
  menusCantine: {
    list: (params) => api.get('/education/menus-cantine/', { params }),
    create: (data) => api.post('/education/menus-cantine/', data),
    jour: (date) => api.get('/education/menus-cantine/jour/', { params: date ? { date } : {} }),
  },
  inscriptionsCantine: {
    list: (params) => api.get('/education/inscriptions-cantine/', { params }),
    create: (data) => api.post('/education/inscriptions-cantine/', data),
  },

  // ── Discipline (incidents) — NTEDU27 ──
  incidents: {
    list: (params) => api.get('/education/incidents/', { params }),
    create: (data) => api.post('/education/incidents/', data),
    demarrerTraitement: (id) => api.post(`/education/incidents/${id}/demarrer-traitement/`),
    cloturer: (id) => api.post(`/education/incidents/${id}/cloturer/`),
  },

  // ── Paramètres établissement (singleton par société) — NTEDU19 ──
  parametres: {
    get: () => api.get('/education/parametres/'),
    save: (data) => api.post('/education/parametres/', data),
  },
}

export default educationApi
