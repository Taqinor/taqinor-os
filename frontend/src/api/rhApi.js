import api from './axios'

/* ============================================================================
   RH — Ressources humaines (apps.rh, préfixe API `/rh/`).
   ----------------------------------------------------------------------------
   Client HTTP fin pour le module RH : dossiers employés, congés & absences,
   temps & présence, compétences & habilitations, EPI/recrutement/évaluations,
   HSE, cockpit RH et portail self-service. `axios` préfixe automatiquement
   `/api/django`. Toutes les données sont scopées société côté serveur (jamais
   lues du corps de requête) ; le portail est isolé par utilisateur (le serveur
   résout le dossier lié au compte appelant).
   ========================================================================== */

const rhApi = {
  // ── UX21 — Cockpit RH & tableaux de bord ──
  getCockpit: () => api.get('/rh/cockpit/'),
  getEcheances: (params) => api.get('/rh/echeances/', { params }),
  getTableauBordHse: (params) => api.get('/rh/tableau-bord-hse/', { params }),

  // ── UX22 — Dossiers employés ──
  getEmployes: (params) => api.get('/rh/employes/', { params }),
  getEmploye: (id) => api.get(`/rh/employes/${id}/`),
  createEmploye: (data) => api.post('/rh/employes/', data),
  updateEmploye: (id, data) => api.patch(`/rh/employes/${id}/`, data),
  deleteEmploye: (id) => api.delete(`/rh/employes/${id}/`),
  // @actions dossier
  getCddAEcheance: (params) => api.get('/rh/employes/cdd-a-echeance/', { params }),
  verifierHabilitation: (id, params) =>
    api.get(`/rh/employes/${id}/verifier-habilitation/`, { params }),
  getRegistreFormation: (id) =>
    api.get(`/rh/employes/${id}/registre-formation/`),

  // Rémunérations (SENSIBLE — permission salaires_voir requise côté serveur).
  getRemunerations: (params) => api.get('/rh/remunerations/', { params }),
  createRemuneration: (data) => api.post('/rh/remunerations/', data),

  // Documents employé (multipart).
  getDocuments: (params) => api.get('/rh/documents/', { params }),
  getDocumentsExpirant: (params) =>
    api.get('/rh/documents/expirant-bientot/', { params }),
  uploadDocument: ({ employe, file, type_document, date_expiration }) => {
    const fd = new FormData()
    fd.append('employe', employe)
    fd.append('file', file)
    if (type_document) fd.append('type_document', type_document)
    if (date_expiration) fd.append('date_expiration', date_expiration)
    return api.post('/rh/documents/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteDocument: (id) => api.delete(`/rh/documents/${id}/`),

  // ── UX23 — Congés & absences ──
  getTypesAbsence: (params) => api.get('/rh/types-absence/', { params }),
  getSoldesConge: (params) => api.get('/rh/soldes-conge/', { params }),
  getDemandesConge: (params) => api.get('/rh/demandes-conge/', { params }),
  createDemandeConge: (data) => api.post('/rh/demandes-conge/', data),
  soumettreDemandeConge: (id, data) =>
    api.post(`/rh/demandes-conge/${id}/soumettre/`, data ?? {}),
  validerDemandeConge: (id, data) =>
    api.post(`/rh/demandes-conge/${id}/valider/`, data ?? {}),
  refuserDemandeConge: (id, data) =>
    api.post(`/rh/demandes-conge/${id}/refuser/`, data ?? {}),
  getCalendrierConges: (params) =>
    api.get('/rh/demandes-conge/calendrier-equipe/', { params }),

  // ── UX24 — Temps & présence ──
  getPointages: (params) => api.get('/rh/pointages/', { params }),
  createPointage: (data) => api.post('/rh/pointages/', data),
  pointagerArrivee: (data) => api.post('/rh/pointages/pointager-arrivee/', data ?? {}),
  pointagerDepart: (id, data) =>
    api.post(`/rh/pointages/${id}/pointager-depart/`, data ?? {}),
  getCalendrierPointages: (params) =>
    api.get('/rh/pointages/calendrier-equipe/', { params }),
  exportPaiePointages: (params) =>
    api.get('/rh/pointages/export-paie/', { params }),
  getFeuillesTemps: (params) => api.get('/rh/feuilles-temps/', { params }),
  getHeuresSupp: (params) => api.get('/rh/heures-supp/', { params }),
  getRoster: (params) => api.get('/rh/roster/', { params }),
  getPresencesChantier: (params) => api.get('/rh/presences-chantier/', { params }),
  getIncidentsPresence: (params) => api.get('/rh/incidents-presence/', { params }),

  // ── UX25 — Compétences, habilitations & formation ──
  getCompetences: (params) => api.get('/rh/competences/', { params }),
  getCompetencesEmploye: (params) =>
    api.get('/rh/competences-employe/', { params }),
  getHabilitations: (params) => api.get('/rh/habilitations/', { params }),
  getCertifications: (params) => api.get('/rh/certifications/', { params }),
  getVisitesMedicales: (params) => api.get('/rh/visites-medicales/', { params }),
  getSessionsFormation: (params) => api.get('/rh/sessions-formation/', { params }),
  marquerSessionRealisee: (id, data) =>
    api.post(`/rh/sessions-formation/${id}/marquer-realisee/`, data ?? {}),
  getBesoinsFormation: (params) => api.get('/rh/besoins-formation/', { params }),

  // ── UX26 — EPI, recrutement & évaluations ──
  getEpiCatalogue: (params) => api.get('/rh/epi-catalogue/', { params }),
  getDotationsEpi: (params) => api.get('/rh/dotations-epi/', { params }),
  getOuverturesPoste: (params) => api.get('/rh/ouvertures-poste/', { params }),
  getCandidatures: (params) => api.get('/rh/candidatures/', { params }),
  embaucherCandidat: (id, data) =>
    api.post(`/rh/candidatures/${id}/embaucher/`, data ?? {}),
  getCampagnesEvaluation: (params) =>
    api.get('/rh/campagnes-evaluation/', { params }),
  getEvaluationsEmploye: (params) =>
    api.get('/rh/evaluations-employe/', { params }),
  validerEvaluation: (id, data) =>
    api.post(`/rh/evaluations-employe/${id}/valider/`, data ?? {}),
  getSanctions: (params) => api.get('/rh/sanctions/', { params }),
  annulerSanction: (id, data) =>
    api.post(`/rh/sanctions/${id}/annuler/`, data ?? {}),

  // ── UX27 — HSE RH ──
  getAccidentsTravail: (params) => api.get('/rh/accidents-travail/', { params }),
  getPresquAccidents: (params) => api.get('/rh/presqu-accidents/', { params }),
  getCauseriesSecurite: (params) => api.get('/rh/causeries-securite/', { params }),
  getAnalysesRisques: (params) =>
    api.get('/rh/analyses-risques-chantier/', { params }),
  validerAnalyseRisques: (id, data) =>
    api.post(`/rh/analyses-risques-chantier/${id}/valider/`, data ?? {}),

  // ── UX28 — Portail self-service (isolé par utilisateur, tous rôles) ──
  getMesInfos: () => api.get('/rh/portail/mes-infos/'),
  updateMesInfos: (data) => api.patch('/rh/portail/mes-infos/', data),
  getMesSoldes: () => api.get('/rh/portail/mes-soldes/'),
  getMesConges: () => api.get('/rh/portail/mes-conges/'),
  demanderConge: (data) => api.post('/rh/portail/demander-conge/', data),
  getMesFrais: () => api.get('/rh/portail/mes-frais/'),
  declarerFrais: (data) => api.post('/rh/portail/declarer-frais/', data),
  getMesEpi: () => api.get('/rh/portail/mes-epi/'),
  getMesHabilitations: () => api.get('/rh/portail/mes-habilitations/'),
  getMesBulletins: () => api.get('/rh/portail/mes-bulletins/'),
  // Ordres de mission / avances (portail : lecture des siens via ?employe côté
  // serveur ; les viewsets scopent au dossier de l'appelant).
  getOrdresMission: (params) => api.get('/rh/ordres-mission/', { params }),
  getNotesFrais: (params) => api.get('/rh/notes-frais/', { params }),
  getAvancesSalaire: (params) => api.get('/rh/avances-salaire/', { params }),
}

export default rhApi
