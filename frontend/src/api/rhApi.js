import api from './axios'
import { makeResourceFactory } from './resource'

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

/**
 * ARC50 — pilote de typage : le schéma OpenAPI généré (YAPIC5 +
 * `npm run gen:api-types`) documente la forme réelle de `Employe`. Ceci ne
 * change AUCUN comportement runtime (JSDoc pur, ce repo n'exécute pas tsc) —
 * uniquement de la documentation typée pour l'éditeur.
 * @typedef {import('./types/schema').components['schemas']['Employe']} Employe
 */

// ARC44 — Fabrique partagée (`api/resource.js`) : réservée aux DEUX groupes de
// ce module dont le quintet complet (list/get/create/update/remove) tombe sur
// un seul chemin REST plat. Le reste de rhApi garde des fonctions nommées à
// plat (contrat historique, souvent des @actions sans CRUD complet) — migrer
// ces dernières changerait l'API exportée pour aucun gain réel.
const resource = makeResourceFactory(api, '/rh')
// ARC50 — ressource `employes` typée `Employe` (voir le typedef ci-dessus).
const employesResource = resource('employes')
const quizFormationResource = resource('quiz-formation')

const rhApi = {
  // ── UX21 — Cockpit RH & tableaux de bord ──
  getCockpit: () => api.get('/rh/cockpit/'),
  getEcheances: (params) => api.get('/rh/echeances/', { params }),
  getTableauBordHse: (params) => api.get('/rh/tableau-bord-hse/', { params }),

  // ── UX22 — Dossiers employés (ARC44 — sur la factory partagée) ──
  getEmployes: (params) => employesResource.list(params),
  getEmploye: (id) => employesResource.get(id),
  createEmploye: (data) => employesResource.create(data),
  updateEmploye: (id, data) => employesResource.update(id, data),
  deleteEmploye: (id) => employesResource.remove(id),
  // @actions dossier
  getCddAEcheance: (params) => api.get('/rh/employes/cdd-a-echeance/', { params }),
  verifierHabilitation: (id, params) =>
    api.get(`/rh/employes/${id}/verifier-habilitation/`, { params }),
  getRegistreFormation: (id) =>
    api.get(`/rh/employes/${id}/registre-formation/`),

  // ── YHIRE2 / ZRH12 — Offboarding (sortie) ──
  sortirEmploye: (id, data) => api.post(`/rh/employes/${id}/sortir/`, data ?? {}),
  getComptesActifsSortis: () => api.get('/rh/employes/comptes-actifs-sortis/'),
  // Certificat de travail (ZRH12) — PDF authentifié (cookie), récupéré en blob.
  getCertificatTravail: (id) =>
    api.get(`/rh/employes/${id}/certificat-travail/`, { responseType: 'blob' }),
  getElementsSortie: (params) => api.get('/rh/elements-sortie/', { params }),
  updateElementSortie: (id, data) => api.patch(`/rh/elements-sortie/${id}/`, data),

  // ── XRH1 / XRH4 / XRH5 / XRH6 — Onboarding, essai, CNSS, chatter ──
  getHistoriqueEmploye: (id) => api.get(`/rh/employes/${id}/historique/`),
  noterEmploye: (id, data) => api.post(`/rh/employes/${id}/noter/`, data ?? {}),
  getIntegration: (id) => api.get(`/rh/employes/${id}/integration/`),
  instancierIntegration: (id, data) =>
    api.post(`/rh/employes/${id}/instancier-integration/`, data ?? {}),
  updateElementIntegrationEmploye: (id, data) =>
    api.patch(`/rh/elements-integration-employe/${id}/`, data),
  confirmerEssai: (id) => api.post(`/rh/employes/${id}/confirmer-essai/`, {}),
  getADeclarer: (params) => api.get('/rh/employes/a-declarer/', { params }),
  marquerDeclare: (id) => api.post(`/rh/employes/${id}/marquer-declare/`, {}),

  // ── XRH15/16 — Écart compétences, compa-ratio, candidats internes ──
  getEcartCompetences: (id) =>
    api.get(`/rh/employes/${id}/ecart-competences/`),
  creerBesoinDepuisEcart: (id, data) =>
    api.post(`/rh/employes/${id}/ecart-competences-creer-besoin-formation/`, data ?? {}),
  getCompaRatio: (id) => api.get(`/rh/employes/${id}/compa-ratio/`),
  getCandidatsInternes: (posteId) =>
    api.get(`/rh/postes/${posteId}/candidats-internes/`),
  getRisqueAttrition: (id) => api.get(`/rh/employes/${id}/risque-attrition/`),
  getTopRisqueAttrition: (params) =>
    api.get('/rh/cockpit/top-risque-attrition/', { params }),

  // ── ZRH14-17 — Badges, carrière, localisation, recherche compétences ──
  getAttributionsBadge: (params) =>
    api.get('/rh/attributions-badge/', { params }),
  getBadgesReconnaissance: (params) =>
    api.get('/rh/badges-reconnaissance/', { params }),
  attribuerBadge: (data) => api.post('/rh/attributions-badge/', data),
  getLocalisationDuJour: (params) =>
    api.get('/rh/employes/localisation-du-jour/', { params }),
  getRapportTurnover: (params) =>
    api.get('/rh/employes/rapport-turnover/', { params }),
  // ── ZRH3/6/18 — rapports congés, absences non justifiées et présence ──
  getRapportConges: (params) =>
    api.get('/rh/demandes-conge/rapport/', { params }),
  getAbsentsNonJustifies: (params) =>
    api.get('/rh/pointages/absents-non-justifies/', { params }),
  genererIncidentAbsence: (data) =>
    api.post('/rh/pointages/generer-incident-absence/', data ?? {}),
  getRapportPresence: (params) =>
    api.get('/rh/pointages/rapport/', { params }),

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
  // PACT24 — pas de fonction ``soumettreDemandeConge`` : le modèle
  // ``DemandeConge`` n'a pas d'état brouillon, une demande est créée déjà
  // ``soumise`` (statut par défaut) ; aucun appelant frontend n'existait pour
  // l'ancien `.../soumettre/`, qui n'a jamais été une route du ViewSet.
  createDemandeConge: (data) => api.post('/rh/demandes-conge/', data),
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
  // PACT19 — DEUX 404 statués, tous deux de type (b) « désaccord de nom » :
  // les actions EXISTENT, mais sur un AUTRE ViewSet que `pointages`.
  //   * `calendrier-equipe` vit sur `DemandeCongeViewSet`
  //     (apps/rh/views.py:1160) → `/rh/demandes-conge/calendrier-equipe/`,
  //     déjà appelé correctement par `getCalendrierConges` ci-dessus.
  //     L'ancien `getCalendrierPointages` pointait sur `/rh/pointages/…`,
  //     n'avait AUCUN appelant, et doublait `getCalendrierConges` : retiré
  //     plutôt que redirigé — deux noms pour une seule route, c'est le
  //     prochain défaut.
  //   * `export-paie` vit sur `HeuresSuppViewSet` (apps/rh/views.py:1437,
  //     `selectors.heures_supp_pour_paie`) → `/rh/heures-supp/export-paie/`.
  //     C'est bien un export de PAIE d'heures supplémentaires, pas de
  //     pointages : le nom de la fonction le dit désormais.
  exportPaieHeuresSupp: (params) =>
    api.get('/rh/heures-supp/export-paie/', { params }),
  getFeuillesTemps: (params) => api.get('/rh/feuilles-temps/', { params }),
  getHeuresSupp: (params) => api.get('/rh/heures-supp/', { params }),
  getRoster: (params) => api.get('/rh/roster/', { params }),
  getPresencesChantier: (params) => api.get('/rh/presences-chantier/', { params }),
  getIncidentsPresence: (params) => api.get('/rh/incidents-presence/', { params }),
  // XRH11 — correction d'un pointage (motif obligatoire) + audit immuable.
  updatePointage: (id, data) => api.patch(`/rh/pointages/${id}/`, data),
  getCorrectionsPointage: (id) =>
    api.get(`/rh/pointages/${id}/corrections/`),
  // XRH13 — import CSV pointeuse externe (multipart).
  importPointageCsv: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/rh/pointages/importer/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  getDevicesEmployeMap: (params) =>
    api.get('/rh/devices-employe-map/', { params }),
  createDeviceEmployeMap: (data) =>
    api.post('/rh/devices-employe-map/', data),
  // XRH10 — devices kiosque (admin).
  getDevicesKiosque: (params) => api.get('/rh/devices-kiosque/', { params }),
  emettreDeviceKiosque: (data) =>
    api.post('/rh/devices-kiosque/emettre/', data ?? {}),
  revoquerDeviceKiosque: (id) =>
    api.post(`/rh/devices-kiosque/${id}/revoquer/`, {}),
  definirCodePointage: (id, data) =>
    api.post(`/rh/employes/${id}/definir-code-pointage/`, data ?? {}),
  // XRH10 — guichet kiosque (device-token X-Kiosque-Token, AllowAny serveur).
  kiosquePointer: (pin, token) =>
    api.post('/rh/pointages/kiosque/', { pin },
      { headers: { 'X-Kiosque-Token': token } }),

  // ── UX25 — Compétences, habilitations & formation ──
  getCompetences: (params) => api.get('/rh/competences/', { params }),
  // WIR36 — wrapper d'écriture manquant (ViewSet full CRUD, aucun appelant).
  createCompetence: (data) => api.post('/rh/competences/', data),
  getCompetencesEmploye: (params) =>
    api.get('/rh/competences-employe/', { params }),
  // WIR36 — idem : évaluation de compétence d'un employé (matrice).
  createCompetenceEmploye: (data) => api.post('/rh/competences-employe/', data),
  getHabilitations: (params) => api.get('/rh/habilitations/', { params }),
  // WIR36 — idem : habilitation électrique par employé.
  createHabilitation: (data) => api.post('/rh/habilitations/', data),
  getCertifications: (params) => api.get('/rh/certifications/', { params }),
  // WIR36 — idem : certification spécifique par employé.
  createCertification: (data) => api.post('/rh/certifications/', data),
  getVisitesMedicales: (params) => api.get('/rh/visites-medicales/', { params }),
  // WIR36 — idem : visite médicale du travail (aptitude).
  createVisiteMedicale: (data) => api.post('/rh/visites-medicales/', data),
  getSessionsFormation: (params) => api.get('/rh/sessions-formation/', { params }),
  marquerSessionRealisee: (id, data) =>
    api.post(`/rh/sessions-formation/${id}/marquer-realisee/`, data ?? {}),
  getBesoinsFormation: (params) => api.get('/rh/besoins-formation/', { params }),
  // ── XRH34 — Quiz builder (gestion RH — porte les bonnes réponses ; ARC44) ──
  getQuizFormation: (params) => quizFormationResource.list(params),
  createQuizFormation: (data) => quizFormationResource.create(data),
  updateQuizFormation: (id, data) => quizFormationResource.update(id, data),
  deleteQuizFormation: (id) => quizFormationResource.remove(id),
  getTentativesQuiz: (params) => api.get('/rh/tentatives-quiz/', { params }),
  // ── XRH27 — Organigramme (arbre des départements) ──
  getArbreDepartements: () => api.get('/rh/departements/arbre/'),
  getDepartements: (params) => api.get('/rh/departements/', { params }),
  // FG160 — référentiel des postes (utilisé par les gabarits d'intégration
  // et les grilles salariales, PACT85/PACT88).
  getPostes: (params) => api.get('/rh/postes/', { params }),
  // ── XRH15 — Analyse d'écarts / évolution de compétences ──
  getCompetencesRequises: (params) =>
    api.get('/rh/competences-requises/', { params }),
  getEvolutionCompetences: (params) =>
    api.get('/rh/competences/evolution/', { params }),
  // ── XRH29 — Ayants droit & avantages sociaux ──
  getAyantsDroit: (params) => api.get('/rh/ayants-droit/', { params }),
  getAvantagesSociaux: (params) =>
    api.get('/rh/avantages-sociaux/', { params }),

  // ── UX26 — EPI, recrutement & évaluations ──
  getEpiCatalogue: (params) => api.get('/rh/epi-catalogue/', { params }),
  getDotationsEpi: (params) => api.get('/rh/dotations-epi/', { params }),
  getOuverturesPoste: (params) => api.get('/rh/ouvertures-poste/', { params }),
  createOuverturePoste: (data) => api.post('/rh/ouvertures-poste/', data),
  getCandidatures: (params) => api.get('/rh/candidatures/', { params }),
  createCandidature: (data) => api.post('/rh/candidatures/', data),
  updateCandidature: (id, data) => api.patch(`/rh/candidatures/${id}/`, data),
  embaucherCandidat: (id, data) =>
    api.post(`/rh/candidatures/${id}/embaucher/`, data ?? {}),

  // ── XRH17-23 / ZRH7-9 — ATS complet (recrutement) ──
  // Entretiens de recrutement (XRH17) + notation par évaluateur.
  getEntretiensRecrutement: (params) =>
    api.get('/rh/entretiens-recrutement/', { params }),
  createEntretienRecrutement: (data) =>
    api.post('/rh/entretiens-recrutement/', data),
  noterEntretienRecrutement: (id, data) =>
    api.post(`/rh/entretiens-recrutement/${id}/noter/`, data ?? {}),
  // Gabarits d'email par étape (XRH19).
  getGabaritsEmailRecrutement: (params) =>
    api.get('/rh/gabarits-email-recrutement/', { params }),
  createGabaritEmailRecrutement: (data) =>
    api.post('/rh/gabarits-email-recrutement/', data),
  updateGabaritEmailRecrutement: (id, data) =>
    api.patch(`/rh/gabarits-email-recrutement/${id}/`, data),
  deleteGabaritEmailRecrutement: (id) =>
    api.delete(`/rh/gabarits-email-recrutement/${id}/`),
  // Promesses d'embauche / lettres d'offre (XRH20).
  getPromessesEmbauche: (params) =>
    api.get('/rh/promesses-embauche/', { params }),
  createPromesseEmbauche: (data) =>
    api.post('/rh/promesses-embauche/', data),
  promessePdfUrl: (id) => `/rh/promesses-embauche/${id}/pdf/`,
  // Vivier / talent pool (XRH21).
  getVivier: (params) => api.get('/rh/candidatures/vivier/', { params }),
  mettreAuVivier: (id, data) =>
    api.post(`/rh/candidatures/${id}/mettre-au-vivier/`, data ?? {}),
  rattacherDepuisVivier: (id, data) =>
    api.post(`/rh/candidatures/${id}/rattacher/`, data ?? {}),
  // CV parsing (XRH23) + comparatif candidats (XRH17).
  parserCv: (id) => api.post(`/rh/candidatures/${id}/parser-cv/`, {}),
  getComparatifCandidats: (id) =>
    api.get(`/rh/candidatures/${id}/comparatif/`),
  getHistoriqueCandidature: (id) =>
    api.get(`/rh/candidatures/${id}/historique/`),
  noterCandidature: (id, data) =>
    api.post(`/rh/candidatures/${id}/noter/`, data ?? {}),
  // Statistiques recrutement (XRH22).
  getRecrutementStatistiques: (params) =>
    api.get('/rh/recrutement/statistiques/', { params }),
  // Modèles d'évaluation (ZRH7) + feedback 360° (ZRH9).
  getModelesEvaluation: (params) =>
    api.get('/rh/modeles-evaluation/', { params }),
  createModeleEvaluation: (data) =>
    api.post('/rh/modeles-evaluation/', data),
  updateModeleEvaluation: (id, data) =>
    api.patch(`/rh/modeles-evaluation/${id}/`, data),
  deleteModeleEvaluation: (id) =>
    api.delete(`/rh/modeles-evaluation/${id}/`),
  getRetoursFeedback360: (params) =>
    api.get('/rh/retours-feedback360/', { params }),
  createRetourFeedback360: (data) =>
    api.post('/rh/retours-feedback360/', data),
  getSyntheseFeedback360: (params) =>
    api.get('/rh/retours-feedback360/synthese/', { params }),
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
  // WIR36 — wrapper d'écriture manquant (ViewSet full CRUD, aucun appelant).
  createAccidentTravail: (data) => api.post('/rh/accidents-travail/', data),
  getPresquAccidents: (params) => api.get('/rh/presqu-accidents/', { params }),
  // WIR36 — idem : presqu'accident (near-miss).
  createPresquAccident: (data) => api.post('/rh/presqu-accidents/', data),
  getCauseriesSecurite: (params) => api.get('/rh/causeries-securite/', { params }),
  // WIR36 — idem : causerie de sécurité (toolbox talk).
  createCauserieSecurite: (data) => api.post('/rh/causeries-securite/', data),
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
  // ── ZRH13 — Allocations self-service ──
  getMesAllocations: () => api.get('/rh/portail/mes-allocations/'),
  demanderAllocation: (data) =>
    api.post('/rh/portail/mes-allocations/', data),
  // ── XRH9 — Demandes RH / attestations self-service ──
  getMesDemandes: () => api.get('/rh/portail/mes-demandes/'),
  demanderAttestation: (data) =>
    api.post('/rh/portail/demander-attestation/', data),
  telechargerDemandeUrl: (id) =>
    `/rh/portail/${id}/mes-demandes-telecharger/`,
  // ── XRH28 — Annuaire interne (tous rôles) ──
  getAnnuaire: (params) => api.get('/rh/employes/annuaire/', { params }),
  // ── XRH34 — Quiz self-service ──
  getQuizDisponibles: () => api.get('/rh/portail/quiz-disponibles/'),
  passerQuiz: (id, data) => api.post(`/rh/portail/${id}/passer-quiz/`, data),
  getMesTentativesQuiz: () => api.get('/rh/portail/mes-tentatives-quiz/'),
  attestationQuizUrl: (id) => `/rh/tentatives-quiz/${id}/attestation/`,
  // ── XRH26 — Auto-évaluation self-service ──
  getMesEvaluations: () => api.get('/rh/portail/mes-evaluations/'),
  saisirAutoEvaluation: (id, data) =>
    api.patch(`/rh/portail/${id}/mon-auto-evaluation/`, data),
  // ── ZRH9 — Feedback 360° self-service ──
  getMesFeedback360: () => api.get('/rh/portail/mes-feedback360/'),
  saisirMonFeedback360: (id, data) =>
    api.patch(`/rh/portail/${id}/mon-feedback360/`, data),
  // ── XRH32 — Pulse eNPS ──
  getCampagnesPulse: (params) => api.get('/rh/campagnes-pulse/', { params }),
  repondrePulse: (id, data) =>
    api.post(`/rh/campagnes-pulse/${id}/repondre/`, data),
  getResultatsPulse: (id) => api.get(`/rh/campagnes-pulse/${id}/resultats/`),
  // Ordres de mission / avances (portail : lecture des siens via ?employe côté
  // serveur ; les viewsets scopent au dossier de l'appelant).
  getOrdresMission: (params) => api.get('/rh/ordres-mission/', { params }),
  getNotesFrais: (params) => api.get('/rh/notes-frais/', { params }),
  getAvancesSalaire: (params) => api.get('/rh/avances-salaire/', { params }),

  // ── PACT81 — Permis de conduire (FG197) & affectations véhicule (FG198) ──
  getPermisConduire: (params) => api.get('/rh/permis-conduire/', { params }),
  createPermisConduire: (data) => api.post('/rh/permis-conduire/', data),
  getAffectationsVehicule: (params) =>
    api.get('/rh/affectations-vehicule/', { params }),
  createAffectationVehicule: (data) =>
    api.post('/rh/affectations-vehicule/', data),
  terminerAffectationVehicule: (id) =>
    api.post(`/rh/affectations-vehicule/${id}/terminer/`, {}),

  // ── PACT82 — Dépôt des bulletins de paie (FG196) ──
  getBulletinsPaie: (params) => api.get('/rh/bulletins-paie/', { params }),
  uploadBulletinPaie: ({ employe, file, annee, mois, note }) => {
    const fd = new FormData()
    fd.append('employe', employe)
    fd.append('file', file)
    fd.append('annee', annee)
    fd.append('mois', mois)
    if (note) fd.append('note', note)
    return api.post('/rh/bulletins-paie/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ── PACT83 — Guichet des demandes d'allocation (ZRH13, côté traitant) ──
  getDemandesAllocation: (params) =>
    api.get('/rh/demandes-allocation/', { params }),
  validerDemandeAllocation: (id) =>
    api.post(`/rh/demandes-allocation/${id}/valider/`, {}),
  refuserDemandeAllocation: (id) =>
    api.post(`/rh/demandes-allocation/${id}/refuser/`, {}),

  // ── PACT84 — Guichet des demandes RH / attestations (XRH9, côté traitant) ──
  getDemandesRh: (params) => api.get('/rh/demandes-rh/', { params }),
  traiterDemandeRh: (id) => api.post(`/rh/demandes-rh/${id}/traiter/`, {}),
  refuserDemandeRh: (id, data) =>
    api.post(`/rh/demandes-rh/${id}/refuser/`, data ?? {}),

  // ── PACT85 — Modèles d'intégration / onboarding (XRH4, gabarits) ──
  getModelesIntegration: (params) =>
    api.get('/rh/modeles-integration/', { params }),
  createModeleIntegration: (data) =>
    api.post('/rh/modeles-integration/', data),
  updateModeleIntegration: (id, data) =>
    api.patch(`/rh/modeles-integration/${id}/`, data),
  getElementsIntegration: (params) =>
    api.get('/rh/elements-integration/', { params }),
  createElementIntegration: (data) =>
    api.post('/rh/elements-integration/', data),
  updateElementIntegration: (id, data) =>
    api.patch(`/rh/elements-integration/${id}/`, data),
  deleteElementIntegration: (id) =>
    api.delete(`/rh/elements-integration/${id}/`),

  // ── PACT86 — Éléments variables de paie (FG192, bordereau externe) ──
  getElementsVariablesPaie: (params) =>
    api.get('/rh/elements-variables-paie/', { params }),
  createElementVariablePaie: (data) =>
    api.post('/rh/elements-variables-paie/', data),
  updateElementVariablePaie: (id, data) =>
    api.patch(`/rh/elements-variables-paie/${id}/`, data),
  marquerExporteElementVariablePaie: (id) =>
    api.post(`/rh/elements-variables-paie/${id}/marquer-exporte/`, {}),

  // ── PACT87 — Entretiens de sortie (XRH25) ──
  getEntretiensSortie: (params) =>
    api.get('/rh/entretiens-sortie/', { params }),
  createEntretienSortie: (data) => api.post('/rh/entretiens-sortie/', data),

  // ── PACT88 — Grilles salariales (XRH16, SENSIBLE — salaires_voir) ──
  getGrillesSalariales: (params) =>
    api.get('/rh/grilles-salariales/', { params }),
  createGrilleSalariale: (data) => api.post('/rh/grilles-salariales/', data),
  updateGrilleSalariale: (id, data) =>
    api.patch(`/rh/grilles-salariales/${id}/`, data),
  deleteGrilleSalariale: (id) =>
    api.delete(`/rh/grilles-salariales/${id}/`),

  // ── PACT89 — Horaires de travail (XRH8) ──
  getHorairesTravail: (params) => api.get('/rh/horaires-travail/', { params }),
  createHoraireTravail: (data) => api.post('/rh/horaires-travail/', data),
  updateHoraireTravail: (id, data) =>
    api.patch(`/rh/horaires-travail/${id}/`, data),

  // ── PACT90 — Jours bloqués (congés) (ZRH4) ──
  getJoursBloquesConge: (params) =>
    api.get('/rh/jours-bloques-conge/', { params }),
  createJourBloqueConge: (data) =>
    api.post('/rh/jours-bloques-conge/', data),
  deleteJourBloqueConge: (id) =>
    api.delete(`/rh/jours-bloques-conge/${id}/`),

  // ── PACT91 — Parcours (timeline) des employés (ZRH15) ──
  getTypesLigneParcours: (params) =>
    api.get('/rh/types-ligne-parcours/', { params }),
  createTypeLigneParcours: (data) =>
    api.post('/rh/types-ligne-parcours/', data),
  getLignesParcours: (params) => api.get('/rh/lignes-parcours/', { params }),
  createLigneParcours: (data) => api.post('/rh/lignes-parcours/', data),

  // ── PACT92 — Fermetures collectives (XRH14) ──
  getPeriodesFermeture: (params) =>
    api.get('/rh/periodes-fermeture/', { params }),
  createPeriodeFermeture: (data) =>
    api.post('/rh/periodes-fermeture/', data),
  appliquerPeriodeFermeture: (id) =>
    api.post(`/rh/periodes-fermeture/${id}/appliquer/`, {}),

  // ── PACT93 — Primes & indemnités (FG193) ──
  getTypesPrime: (params) => api.get('/rh/types-prime/', { params }),
  createTypePrime: (data) => api.post('/rh/types-prime/', data),
  updateTypePrime: (id, data) => api.patch(`/rh/types-prime/${id}/`, data),
  getPrimesAttribuees: (params) =>
    api.get('/rh/primes-attribuees/', { params }),
  createPrimeAttribuee: (data) => api.post('/rh/primes-attribuees/', data),
  updatePrimeAttribuee: (id, data) =>
    api.patch(`/rh/primes-attribuees/${id}/`, data),
  validerPrimeAttribuee: (id) =>
    api.post(`/rh/primes-attribuees/${id}/valider/`, {}),

  // ── PACT94 — Réglages RH (XRH12/XRH24, singleton société) ──
  getMonReglageRh: () => api.get('/rh/reglages/mon-reglage/'),
  updateMonReglageRh: (data) =>
    api.patch('/rh/reglages/mon-reglage/', data),
}

export default rhApi
