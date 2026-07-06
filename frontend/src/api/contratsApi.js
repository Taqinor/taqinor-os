import api from './axios'

/* ============================================================================
   API du module Gestion des contrats (CLM) — préfixe `/contrats/`.
   ----------------------------------------------------------------------------
   Fine couche autour d'axios : chaque fonction renvoie la promesse axios
   (`res.data` côté appelant). Les basenames, @actions et paramètres reflètent
   exactement `apps/contrats/urls.py` + les viewsets. La société est TOUJOURS
   posée côté serveur (jamais dans le corps). Aucun prix d'achat / marge n'est
   jamais demandé ni affiché — le module contrats n'en expose aucun.
   ========================================================================== */

const contratsApi = {
  /* ---------------- Contrats (UX34) — cycle de vie ---------------- */
  getContrats: (params) => api.get('/contrats/contrats/', { params }),
  getContrat: (id) => api.get(`/contrats/contrats/${id}/`),
  createContrat: (data) => api.post('/contrats/contrats/', data),
  updateContrat: (id, data) => api.patch(`/contrats/contrats/${id}/`, data),
  deleteContrat: (id) => api.delete(`/contrats/contrats/${id}/`),

  // Tableaux de bord / reporting (lecture seule).
  getTableauBord: (params) =>
    api.get('/contrats/contrats/tableau-de-bord/', { params }),
  getReporting: () => api.get('/contrats/contrats/reporting/'),

  // Analytique récurrente (MRR / rétention / campagne / CLV) — XCTR7-11.
  getMrrMouvements: (params) =>
    api.get('/contrats/contrats/mrr-mouvements/', { params }),
  getCohortesRetention: () =>
    api.get('/contrats/contrats/cohortes-retention/'),
  getClv: (params) => api.get('/contrats/contrats/clv/', { params }),
  campagneRevision: (data) =>
    api.post('/contrats/contrats/campagne-revision/', data),
  campagneRevisionRollback: (data) =>
    api.post('/contrats/contrats/campagne-revision-rollback/', data),

  // Échéances (préavis / renouvellement) — CONTRAT20/21.
  getPreavis: (params) => api.get('/contrats/contrats/preavis/', { params }),
  getARenouveler: (params) =>
    api.get('/contrats/contrats/a-renouveler/', { params }),

  // Machine d'états (transitions gardées) — CONTRAT12.
  getStatutsSuivants: (id) =>
    api.get(`/contrats/contrats/${id}/statuts-suivants/`),
  changerStatut: (id, statut) =>
    api.post(`/contrats/contrats/${id}/changer-statut/`, { statut }),

  // Chatter (historique + note) — CONTRAT15.
  getHistorique: (id) => api.get(`/contrats/contrats/${id}/historique/`),
  noter: (id, message) =>
    api.post(`/contrats/contrats/${id}/noter/`, { message }),

  // Rendu / liens.
  getLiens: (id) => api.get(`/contrats/contrats/${id}/liens/`),
  rendre: (id, gabarit) =>
    api.post(`/contrats/contrats/${id}/rendre/`, gabarit ? { gabarit } : {}),
  getPdfUrl: (id) => `/contrats/contrats/${id}/pdf/`,
  getPdf: (id) =>
    api.get(`/contrats/contrats/${id}/pdf/`, { responseType: 'blob' }),

  // Renouvellement / reconductions — CONTRAT23.
  renouveler: (id, data) =>
    api.post(`/contrats/contrats/${id}/renouveler/`, data),
  traiterReconductions: () =>
    api.post('/contrats/contrats/traiter-reconductions/'),

  // Signatures e-sign IN-APP — CONTRAT16.
  getSignatures: (id) => api.get(`/contrats/contrats/${id}/signatures/`),
  signer: (id, data) => api.post(`/contrats/contrats/${id}/signer/`, data),

  // Approbation interne — CONTRAT14.
  getEtapesApprobation: (id) =>
    api.get(`/contrats/contrats/${id}/etapes-approbation/`),
  lancerApprobation: (id) =>
    api.post(`/contrats/contrats/${id}/lancer-approbation/`),
  approuverEtape: (id, etape, commentaire) =>
    api.post(`/contrats/contrats/${id}/approuver-etape/`, { etape, commentaire }),
  rejeterEtape: (id, etape, commentaire) =>
    api.post(`/contrats/contrats/${id}/rejeter-etape/`, { etape, commentaire }),

  /* ---------------- Parties ---------------- */
  getParties: (params) => api.get('/contrats/parties/', { params }),
  createPartie: (data) => api.post('/contrats/parties/', data),
  updatePartie: (id, data) => api.patch(`/contrats/parties/${id}/`, data),
  deletePartie: (id) => api.delete(`/contrats/parties/${id}/`),

  /* ---------------- Liens contrat ---------------- */
  getContratLiens: (params) => api.get('/contrats/contrat-liens/', { params }),
  createContratLien: (data) => api.post('/contrats/contrat-liens/', data),
  deleteContratLien: (id) => api.delete(`/contrats/contrat-liens/${id}/`),

  /* ---------------- Modèles & clauses (UX35) ---------------- */
  getModeles: (params) => api.get('/contrats/modeles/', { params }),
  getModele: (id) => api.get(`/contrats/modeles/${id}/`),
  createModele: (data) => api.post('/contrats/modeles/', data),
  updateModele: (id, data) => api.patch(`/contrats/modeles/${id}/`, data),
  deleteModele: (id) => api.delete(`/contrats/modeles/${id}/`),
  instancierModele: (id, data) =>
    api.post(`/contrats/modeles/${id}/instancier/`, data ?? {}),

  getClauses: (params) => api.get('/contrats/clauses/', { params }),
  getClause: (id) => api.get(`/contrats/clauses/${id}/`),
  createClause: (data) => api.post('/contrats/clauses/', data),
  updateClause: (id, data) => api.patch(`/contrats/clauses/${id}/`, data),
  deleteClause: (id) => api.delete(`/contrats/clauses/${id}/`),

  // Liaisons modèle ↔ clause.
  getModeleClauses: (params) =>
    api.get('/contrats/modele-clauses/', { params }),
  createModeleClause: (data) => api.post('/contrats/modele-clauses/', data),
  deleteModeleClause: (id) => api.delete(`/contrats/modele-clauses/${id}/`),

  // Clauses résolues d'un contrat.
  getClausesContrat: (params) =>
    api.get('/contrats/clauses-contrat/', { params }),
  createClauseContrat: (data) => api.post('/contrats/clauses-contrat/', data),
  updateClauseContrat: (id, data) =>
    api.patch(`/contrats/clauses-contrat/${id}/`, data),
  deleteClauseContrat: (id) => api.delete(`/contrats/clauses-contrat/${id}/`),

  // Versions immuables — CONTRAT18 (lecture seule + création via action contrat).
  getVersions: (params) => api.get('/contrats/versions/', { params }),
  creerVersion: (id, data) =>
    api.post(`/contrats/contrats/${id}/creer-version/`, data ?? {}),

  // Avenants — CONTRAT24 (lecture seule + création via action contrat).
  getAvenants: (params) => api.get('/contrats/avenants/', { params }),
  creerAvenant: (id, data) =>
    api.post(`/contrats/contrats/${id}/creer-avenant/`, data),

  // Résiliations — CONTRAT25 (lecture seule + création via action contrat).
  getResiliations: (params) => api.get('/contrats/resiliations/', { params }),
  resilier: (id, data) =>
    api.post(`/contrats/contrats/${id}/resilier/`, data ?? {}),

  /* ---------------- Échéances & alertes (UX36) ---------------- */
  getAlertes: (params) => api.get('/contrats/alertes/', { params }),
  createAlerte: (data) => api.post('/contrats/alertes/', data),
  updateAlerte: (id, data) => api.patch(`/contrats/alertes/${id}/`, data),
  deleteAlerte: (id) => api.delete(`/contrats/alertes/${id}/`),
  declencherAlertes: () => api.post('/contrats/alertes/declencher/'),
  semerAlertes: (within) =>
    api.post('/contrats/alertes/semer-echeances/', { within }),

  getJalons: (params) => api.get('/contrats/jalons/', { params }),
  createJalon: (data) => api.post('/contrats/jalons/', data),
  updateJalon: (id, data) => api.patch(`/contrats/jalons/${id}/`, data),
  deleteJalon: (id) => api.delete(`/contrats/jalons/${id}/`),
  marquerJalonAtteint: (id) =>
    api.post(`/contrats/jalons/${id}/marquer-atteint/`),

  getObligations: (params) => api.get('/contrats/obligations/', { params }),
  createObligation: (data) => api.post('/contrats/obligations/', data),
  updateObligation: (id, data) => api.patch(`/contrats/obligations/${id}/`, data),
  deleteObligation: (id) => api.delete(`/contrats/obligations/${id}/`),
  marquerObligationFaite: (id) =>
    api.post(`/contrats/obligations/${id}/marquer-faite/`),

  getSla: (params) => api.get('/contrats/sla/', { params }),
  createSla: (data) => api.post('/contrats/sla/', data),
  updateSla: (id, data) => api.patch(`/contrats/sla/${id}/`, data),
  deleteSla: (id) => api.delete(`/contrats/sla/${id}/`),
  penaliteSla: (id, data) => api.post(`/contrats/sla/${id}/penalite/`, data ?? {}),

  getReglesApprobation: (params) =>
    api.get('/contrats/regles-approbation/', { params }),
  createRegleApprobation: (data) =>
    api.post('/contrats/regles-approbation/', data),
  updateRegleApprobation: (id, data) =>
    api.patch(`/contrats/regles-approbation/${id}/`, data),
  deleteRegleApprobation: (id) =>
    api.delete(`/contrats/regles-approbation/${id}/`),
  resoudreRegleApprobation: (params) =>
    api.get('/contrats/regles-approbation/resoudre/', { params }),

  /* ---------------- Finances de contrat (UX37) ---------------- */
  getRetenues: (params) => api.get('/contrats/retenues-garantie/', { params }),
  createRetenue: (data) => api.post('/contrats/retenues-garantie/', data),
  updateRetenue: (id, data) =>
    api.patch(`/contrats/retenues-garantie/${id}/`, data),
  deleteRetenue: (id) => api.delete(`/contrats/retenues-garantie/${id}/`),
  libererRetenue: (id) =>
    api.post(`/contrats/retenues-garantie/${id}/liberer/`),

  getCautions: (params) => api.get('/contrats/cautions/', { params }),
  createCaution: (data) => api.post('/contrats/cautions/', data),
  updateCaution: (id, data) => api.patch(`/contrats/cautions/${id}/`, data),
  deleteCaution: (id) => api.delete(`/contrats/cautions/${id}/`),

  getEcheanciers: (params) => api.get('/contrats/echeanciers/', { params }),
  getEcheancier: (id) => api.get(`/contrats/echeanciers/${id}/`),
  createEcheancier: (data) => api.post('/contrats/echeanciers/', data),
  updateEcheancier: (id, data) =>
    api.patch(`/contrats/echeanciers/${id}/`, data),
  deleteEcheancier: (id) => api.delete(`/contrats/echeanciers/${id}/`),
  ajouterLigneEcheance: (id, data) =>
    api.post(`/contrats/echeanciers/${id}/ajouter-ligne/`, data),

  getLignesEcheance: (params) =>
    api.get('/contrats/lignes-echeance/', { params }),
  pointerPaiement: (id) =>
    api.post(`/contrats/lignes-echeance/${id}/pointer-paiement/`),
  facturerLigne: (id) =>
    api.post(`/contrats/lignes-echeance/${id}/facturer/`),

  getIndexations: (params) => api.get('/contrats/indexations/', { params }),
  createIndexation: (data) => api.post('/contrats/indexations/', data),
  updateIndexation: (id, data) =>
    api.patch(`/contrats/indexations/${id}/`, data),
  deleteIndexation: (id) => api.delete(`/contrats/indexations/${id}/`),
  simulerIndexation: (id, data) =>
    api.post(`/contrats/indexations/${id}/simuler/`, data),
  appliquerIndexation: (id, data) =>
    api.post(`/contrats/indexations/${id}/appliquer/`, data),

  getPiecesConformite: (params) =>
    api.get('/contrats/pieces-conformite/', { params }),
  createPieceConformite: (data) =>
    api.post('/contrats/pieces-conformite/', data),
  updatePieceConformite: (id, data) =>
    api.patch(`/contrats/pieces-conformite/${id}/`, data),
  deletePieceConformite: (id) =>
    api.delete(`/contrats/pieces-conformite/${id}/`),
  marquerPieceFournie: (id, data) =>
    api.post(`/contrats/pieces-conformite/${id}/marquer-fournie/`, data ?? {}),

  /* ---------------- Cycles de facturation & exceptions — XCTR5 ---------------- */
  getCyclesFacturation: (params) =>
    api.get('/contrats/cycles-facturation/', { params }),
  getExceptionsFacturation: (params) =>
    api.get('/contrats/cycles-facturation/exceptions/', { params }),
  rejouerCycle: (id) =>
    api.post(`/contrats/cycles-facturation/${id}/rejouer/`),

  /* ---------------- Location de matériel (XCTR17-21) ---------------- */
  getOrdresLocation: (params) =>
    api.get('/contrats/ordres-location/', { params }),
  getOrdreLocation: (id) => api.get(`/contrats/ordres-location/${id}/`),
  createOrdreLocation: (data) =>
    api.post('/contrats/ordres-location/', data),
  updateOrdreLocation: (id, data) =>
    api.patch(`/contrats/ordres-location/${id}/`, data),
  deleteOrdreLocation: (id) => api.delete(`/contrats/ordres-location/${id}/`),
  disponibiliteLocation: (params) =>
    api.get('/contrats/ordres-location/disponibilite/', { params }),
  changerStatutOrdreLocation: (id, statut) =>
    api.post(`/contrats/ordres-location/${id}/changer-statut/`, { statut }),
  ordresLocationEnRetard: (params) =>
    api.get('/contrats/ordres-location/en-retard/', { params }),
  utilisationLocation: (params) =>
    api.get('/contrats/ordres-location/utilisation/', { params }),
  // Caution (dépôt de garantie) — XCTR18.
  cautionEncaisser: (id, montant) =>
    api.post(`/contrats/ordres-location/${id}/caution/encaisser/`, { montant }),
  cautionRestituer: (id) =>
    api.post(`/contrats/ordres-location/${id}/caution/restituer/`),
  cautionRetenir: (id, data) =>
    api.post(`/contrats/ordres-location/${id}/caution/retenir/`, data),
  // Retour / retards / inspection — XCTR19.
  cloturerOrdreLocation: (id) =>
    api.post(`/contrats/ordres-location/${id}/cloturer/`),
  inspecterOrdreLocation: (id, data) =>
    api.post(`/contrats/ordres-location/${id}/inspecter/`, data),
  // Longue durée : cycle récurrent + prolongation/écourtage — XCTR20.
  facturerCycleLocation: (id, data) =>
    api.post(`/contrats/ordres-location/${id}/facturer-cycle/`, data ?? {}),
  prolongerOrdreLocation: (id, data) =>
    api.post(`/contrats/ordres-location/${id}/prolonger/`, data),
  ecourterOrdreLocation: (id, data) =>
    api.post(`/contrats/ordres-location/${id}/ecourter/`, data),
  // Depuis un devis accepté — ZCTR6.
  ordresLocationDepuisDevis: (devisId, data) =>
    api.post(`/contrats/ordres-location/depuis-devis/${devisId}/`, data ?? {}),
  // Bons PDF — ZCTR5.
  getBonEnlevementUrl: (id) =>
    `/contrats/ordres-location/${id}/bon-enlevement/`,
  getBonEnlevement: (id) =>
    api.get(`/contrats/ordres-location/${id}/bon-enlevement/`, { responseType: 'blob' }),
  getBonRestitution: (id) =>
    api.get(`/contrats/ordres-location/${id}/bon-restitution/`, { responseType: 'blob' }),

  /* ---------------- Config location (ZCTR1/3/4) ---------------- */
  getPlansRecurrents: (params) =>
    api.get('/contrats/plans-recurrents/', { params }),
  createPlanRecurrent: (data) => api.post('/contrats/plans-recurrents/', data),
  updatePlanRecurrent: (id, data) =>
    api.patch(`/contrats/plans-recurrents/${id}/`, data),
  deletePlanRecurrent: (id) => api.delete(`/contrats/plans-recurrents/${id}/`),

  getMotifsResiliation: (params) =>
    api.get('/contrats/motifs-resiliation/', { params }),
  createMotifResiliation: (data) =>
    api.post('/contrats/motifs-resiliation/', data),
  updateMotifResiliation: (id, data) =>
    api.patch(`/contrats/motifs-resiliation/${id}/`, data),
  deleteMotifResiliation: (id) =>
    api.delete(`/contrats/motifs-resiliation/${id}/`),

  getParametresLocation: () =>
    api.get('/contrats/parametres-location/courant/'),
  updateParametresLocation: (data) =>
    api.patch('/contrats/parametres-location/courant/', data),

  // Génération d'un devis de renouvellement — CONTRAT23.
  genererDevisRenouvellement: (id, data) =>
    api.post(`/contrats/contrats/${id}/generer-devis-renouvellement/`, data ?? {}),
}

/* ============================================================================
   Portail client PUBLIC (sans login) — « Mes contrats » (XCTR14).
   Résolu par le token du portail self-service (compta.ComptePortailClient).
   Ne change JAMAIS le statut d'un contrat : la demande crée une activité côté
   ERP. Utilise l'axios NU (pas d'auth) sur le préfixe /public/.
   ========================================================================== */
export const contratsPortailApi = {
  mesContrats: (token) =>
    api.get(`/public/contrats/portail/${encodeURIComponent(token)}/`),
  demander: (token, contratId, data) =>
    api.post(
      `/public/contrats/portail/${encodeURIComponent(token)}/${contratId}/demande/`,
      data,
    ),
}

export default contratsApi
