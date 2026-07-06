import api from './axios'

/* ============================================================================
   Paie (paie marocaine) — client API.
   ----------------------------------------------------------------------------
   Toutes les routes sont scopées société côté serveur (palier
   Administrateur/Responsable), SAUF `mes-bulletins` (self-service, tout rôle,
   strictement scopé à l'utilisateur). Les fichiers générés (PDF bulletins,
   attestations) descendent en `responseType:'blob'`. Les états déclaratifs
   (CNSS/DAMANCOM/IR/livre) descendent en JSON.
   Basenames exacts : voir apps/paie/urls.py + views.py.
   ========================================================================== */
const paieApi = {
  // ── Périodes (run mensuel + cycle de statuts) ──
  getPeriodes: (params) => api.get('/paie/periodes/', { params }),
  getPeriode: (id) => api.get(`/paie/periodes/${id}/`),
  createPeriode: (data) => api.post('/paie/periodes/', data),
  updatePeriode: (id, data) => api.patch(`/paie/periodes/${id}/`, data),
  deletePeriode: (id) => api.delete(`/paie/periodes/${id}/`),
  changerStatutPeriode: (id, statut) =>
    api.post(`/paie/periodes/${id}/changer-statut/`, { statut }),
  cloturerPeriode: (id, validerBrouillons = true) =>
    api.post(`/paie/periodes/${id}/cloturer/`, {
      valider_brouillons: validerBrouillons,
    }),
  importerElementsRh: (id) =>
    api.post(`/paie/periodes/${id}/importer-elements-rh/`),
  // Calcul (sans persister) du bulletin d'un profil : ?profil=&personnes_a_charge=
  apercuBulletin: (id, params) =>
    api.get(`/paie/periodes/${id}/bulletin/`, { params }),
  // Déclarations (JSON) portées par la PÉRIODE.
  declarationCnss: (id) =>
    api.get(`/paie/periodes/${id}/declaration-cnss/`),
  fichierDamancom: (id) =>
    api.get(`/paie/periodes/${id}/fichier-damancom/`),
  etatIr: (id) => api.get(`/paie/periodes/${id}/etat-ir/`),
  livreDePaie: (id) => api.get(`/paie/periodes/${id}/livre-de-paie/`),
  journalDePaie: (id) => api.post(`/paie/periodes/${id}/journal-de-paie/`),
  journalVentile: (id) => api.post(`/paie/periodes/${id}/journal-ventile/`),
  etatIrAnnuel: (annee) =>
    api.get('/paie/periodes/etat-ir-annuel/', { params: { annee } }),
  etatIrAnnuelXml: (annee) =>
    api.get('/paie/periodes/etat-ir-annuel-xml/', { params: { annee } }),
  runGratification: (id, data) =>
    api.post(`/paie/periodes/${id}/run-gratification/`, data),
  reporterElements: (id) =>
    api.post(`/paie/periodes/${id}/reporter-elements/`),
  echeancesPeriode: (id) => api.get(`/paie/periodes/${id}/echeances/`),
  notifierEcheancesRetard: () =>
    api.post('/paie/periodes/notifier-echeances-retard/'),
  declarationCimr: (id) => api.get(`/paie/periodes/${id}/declaration-cimr/`),
  fichierCimr: (id) => api.get(`/paie/periodes/${id}/fichier-cimr/`),
  mouvementsCnss: (id) => api.get(`/paie/periodes/${id}/mouvements-cnss/`),
  affebdsRapprochement: (formData) =>
    api.post('/paie/periodes/affebds-rapprochement/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  fichierDamancomStrict: (id) =>
    api.get(`/paie/periodes/${id}/fichier-damancom-strict/`),
  deposerBds: (id, data) =>
    api.post(`/paie/periodes/${id}/deposer-bds/`, data),
  deposerBdsComplementaire: (id, data) =>
    api.post(`/paie/periodes/${id}/deposer-bds-complementaire/`, data),
  etatCharges: (id) => api.get(`/paie/periodes/${id}/etat-charges/`),
  rapprochementGl: (id) => api.get(`/paie/periodes/${id}/rapprochement-gl/`),
  coutGlobal: (id) => api.get(`/paie/periodes/${id}/cout-global/`),
  coutEmployeur: (id) => api.get(`/paie/periodes/${id}/cout-employeur/`),
  provisions: (id) => api.get(`/paie/periodes/${id}/provisions/`),
  horsVirement: (id) => api.get(`/paie/periodes/${id}/hors-virement/`),
  brutPourNet: (id, params) =>
    api.get(`/paie/periodes/${id}/brut-pour-net/`, { params }),
  controleEcarts: (id, params) =>
    api.get(`/paie/periodes/${id}/controle-ecarts/`, { params }),
  controleCompletude: (id) =>
    api.get(`/paie/periodes/${id}/controle-completude/`),
  avertissements: (id) => api.get(`/paie/periodes/${id}/avertissements/`),
  bulletinsPdf: (id) =>
    api.get(`/paie/periodes/${id}/bulletins-pdf/`, { responseType: 'blob' }),
  rattacherBulletins: (id, data) =>
    api.post(`/paie/periodes/${id}/rattacher-bulletins/`, data),

  // ── Bulletins (snapshot immuable, lecture seule + actions) ──
  getBulletins: (params) => api.get('/paie/bulletins/', { params }),
  getBulletin: (id) => api.get(`/paie/bulletins/${id}/`),
  genererBulletin: (data) => api.post('/paie/bulletins/generer/', data),
  validerBulletin: (id) => api.post(`/paie/bulletins/${id}/valider/`),
  marquerPayeBulletin: (id) => api.post(`/paie/bulletins/${id}/marquer-paye/`),
  rectifierBulletin: (id, data) =>
    api.post(`/paie/bulletins/${id}/rectifier/`, data),
  annulerBulletin: (id, data) =>
    api.post(`/paie/bulletins/${id}/annuler/`, data),
  bulletinPdf: (id) =>
    api.get(`/paie/bulletins/${id}/pdf/`, { responseType: 'blob' }),
  analysePaie: (params) => api.get('/paie/bulletins/analyse/', { params }),
  analysePaieCsv: (params) =>
    api.get('/paie/bulletins/analyse/',
      { params: { ...params, export: 'csv' }, responseType: 'blob' }),
  saisiesArretBulletin: (id) =>
    api.get(`/paie/bulletins/${id}/saisies-arret/`),

  // ── Paramètres sociaux versionnés ──
  getParametres: (params) => api.get('/paie/parametres/', { params }),
  saveParametre: (id, data) =>
    id ? api.patch(`/paie/parametres/${id}/`, data)
      : api.post('/paie/parametres/', data),
  deleteParametre: (id) => api.delete(`/paie/parametres/${id}/`),
  seedParametresDefaults: () =>
    api.post('/paie/parametres/seed-defaults/'),

  // ── Barème IR versionné (tranches imbriquées) ──
  getBaremes: (params) => api.get('/paie/baremes/', { params }),
  saveBareme: (id, data) =>
    id ? api.patch(`/paie/baremes/${id}/`, data)
      : api.post('/paie/baremes/', data),
  deleteBareme: (id) => api.delete(`/paie/baremes/${id}/`),

  // ── Rubriques (catalogue paramétrable) ──
  getRubriques: (params) => api.get('/paie/rubriques/', { params }),
  saveRubrique: (id, data) =>
    id ? api.patch(`/paie/rubriques/${id}/`, data)
      : api.post('/paie/rubriques/', data),
  deleteRubrique: (id) => api.delete(`/paie/rubriques/${id}/`),
  seedRubriquesDefaults: () =>
    api.post('/paie/rubriques/seed-defaults/'),
  seedRubriquesStandard: () =>
    api.post('/paie/rubriques/seed-standard/'),

  // ── Profils de paie par employé ──
  getProfils: (params) => api.get('/paie/profils/', { params }),
  getProfil: (id) => api.get(`/paie/profils/${id}/`),
  saveProfil: (id, data) =>
    id ? api.patch(`/paie/profils/${id}/`, data)
      : api.post('/paie/profils/', data),
  deleteProfil: (id) => api.delete(`/paie/profils/${id}/`),
  // Attestation PDF : ?type=salaire|travail|domiciliation (défaut travail).
  attestationPdf: (id, type) =>
    api.get(`/paie/profils/${id}/attestation/`, {
      responseType: 'blob', params: type ? { type } : {},
    }),
  expirerRegimesExoneration: () =>
    api.post('/paie/profils/expirer-regimes/'),
  synchroniserSalaireProfil: (id) =>
    api.post(`/paie/profils/${id}/synchroniser-salaire/`),
  // Solde de tout compte (STC, XPAI1) — corps : periode, motif,
  // mois_preavis, personnes_a_charge.
  stc: (id, data) => api.post(`/paie/profils/${id}/stc/`, data),
  stcPdf: (id) =>
    api.get(`/paie/profils/${id}/stc-pdf/`, { responseType: 'blob' }),
  simulationBulletin: (id, params) =>
    api.get(`/paie/profils/${id}/simulation/`, { params }),
  registreConges: (params) =>
    api.get('/paie/profils/registre-conges/', { params }),
  registreCongesFichier: (annee, format) =>
    api.get('/paie/profils/registre-conges/', {
      params: { annee, export: format }, responseType: 'blob',
    }),
  historiqueCarriere: (id) =>
    api.get(`/paie/profils/${id}/historique-carriere/`),
  historiqueCarrierePdf: (id) =>
    api.get(`/paie/profils/${id}/historique-carriere/`, {
      params: { export: 'pdf' }, responseType: 'blob',
    }),

  // ── Mutuelle / prévoyance (XPAI3) ──
  getRegimesMutuelle: (params) =>
    api.get('/paie/regimes-mutuelle/', { params }),
  saveRegimeMutuelle: (id, data) =>
    id ? api.patch(`/paie/regimes-mutuelle/${id}/`, data)
      : api.post('/paie/regimes-mutuelle/', data),
  deleteRegimeMutuelle: (id) => api.delete(`/paie/regimes-mutuelle/${id}/`),
  getAdhesionsMutuelle: (params) =>
    api.get('/paie/adhesions-mutuelle/', { params }),
  saveAdhesionMutuelle: (id, data) =>
    id ? api.patch(`/paie/adhesions-mutuelle/${id}/`, data)
      : api.post('/paie/adhesions-mutuelle/', data),
  deleteAdhesionMutuelle: (id) =>
    api.delete(`/paie/adhesions-mutuelle/${id}/`),

  // ── Structures de paie (gabarits, XPAI24) ──
  getStructures: (params) => api.get('/paie/structures/', { params }),
  saveStructure: (id, data) =>
    id ? api.patch(`/paie/structures/${id}/`, data)
      : api.post('/paie/structures/', data),
  deleteStructure: (id) => api.delete(`/paie/structures/${id}/`),
  ensureStructuresStandard: () =>
    api.post('/paie/structures/ensure-standard/'),
  appliquerStructure: (id, profilId) =>
    api.post(`/paie/structures/${id}/appliquer/`, { profil: profilId }),

  // ── Rubriques récurrentes par employé ──
  getRubriquesEmploye: (params) =>
    api.get('/paie/rubriques-employe/', { params }),
  saveRubriqueEmploye: (id, data) =>
    id ? api.patch(`/paie/rubriques-employe/${id}/`, data)
      : api.post('/paie/rubriques-employe/', data),
  deleteRubriqueEmploye: (id) =>
    api.delete(`/paie/rubriques-employe/${id}/`),

  // ── Éléments variables du mois ──
  getElementsVariables: (params) =>
    api.get('/paie/elements-variables/', { params }),
  saveElementVariable: (id, data) =>
    id ? api.patch(`/paie/elements-variables/${id}/`, data)
      : api.post('/paie/elements-variables/', data),
  deleteElementVariable: (id) =>
    api.delete(`/paie/elements-variables/${id}/`),

  // ── Ordres de virement des salaires ──
  getOrdresVirement: (params) =>
    api.get('/paie/ordres-virement/', { params }),
  getOrdreVirement: (id) => api.get(`/paie/ordres-virement/${id}/`),
  genererOrdreVirement: (data) =>
    api.post('/paie/ordres-virement/generer/', data),
  // "valider" côté UI = émettre l'ordre (fige) ; "rectifier" = régénérer.
  emettreOrdreVirement: (id) =>
    api.post(`/paie/ordres-virement/${id}/emettre/`),
  payerOrdreVirement: (id, compteTresorerieId, dateReglement) =>
    api.post(`/paie/ordres-virement/${id}/payer/`, {
      compte_tresorerie: compteTresorerieId,
      ...(dateReglement ? { date_reglement: dateReglement } : {}),
    }),
  // XPAI8 — ?format_banque=simt pour le format bancaire marocain SIMT.
  fichierVirement: (id, formatBanque) =>
    api.get(`/paie/ordres-virement/${id}/fichier/`, {
      params: formatBanque ? { format_banque: formatBanque } : {},
    }),
  // ── Lignes de virement — rejets/réémissions (XPAI9) ──
  getLignesVirement: (params) => api.get('/paie/lignes-virement/', { params }),
  rejeterLigneVirement: (id, motif) =>
    api.post(`/paie/lignes-virement/${id}/rejeter/`, { motif: motif || '' }),
  reemettreLigneVirement: (id, rib) =>
    api.post(`/paie/lignes-virement/${id}/reemettre/`, { rib }),

  // ── Avances / prêts salariés ──
  getAvances: (params) => api.get('/paie/avances/', { params }),
  saveAvance: (id, data) =>
    id ? api.patch(`/paie/avances/${id}/`, data)
      : api.post('/paie/avances/', data),
  deleteAvance: (id) => api.delete(`/paie/avances/${id}/`),

  // ── Saisies-arrêts / cessions ──
  getSaisies: (params) => api.get('/paie/saisies/', { params }),
  saveSaisie: (id, data) =>
    id ? api.patch(`/paie/saisies/${id}/`, data)
      : api.post('/paie/saisies/', data),
  deleteSaisie: (id) => api.delete(`/paie/saisies/${id}/`),
  annulerSaisie: (id, motif) =>
    api.post(`/paie/saisies/${id}/annuler/`, { motif: motif || '' }),
  creerLotSaisies: (data) => api.post('/paie/saisies/creer-lot/', data),

  // ── Cumuls annuels ──
  getCumulsAnnuels: (params) =>
    api.get('/paie/cumuls-annuels/', { params }),
  recalculerCumul: (data) =>
    api.post('/paie/cumuls-annuels/recalculer/', data),
  // XPAI22 — import de reprise des cumuls (go-live), multipart.
  repriseDryRun: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/paie/cumuls-annuels/reprise-dry-run/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  repriseCommit: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/paie/cumuls-annuels/reprise-commit/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ── Échéances déclaratives (XPAI6) ──
  getEcheancesDeclaratives: (params) =>
    api.get('/paie/echeances-declaratives/', { params }),
  updateEcheanceDeclarative: (id, data) =>
    api.patch(`/paie/echeances-declaratives/${id}/`, data),
  payerEcheance: (id, compteTresorerieId, dateReglement) =>
    api.post(`/paie/echeances-declaratives/${id}/payer/`, {
      compte_tresorerie: compteTresorerieId,
      ...(dateReglement ? { date_reglement: dateReglement } : {}),
    }),

  // ── Self-service employé (coffre-fort) — tout rôle, scopé utilisateur ──
  getMesBulletins: (params) => api.get('/paie/mes-bulletins/', { params }),
  mesBulletinPdf: (id) =>
    api.get(`/paie/mes-bulletins/${id}/pdf/`, { responseType: 'blob' }),
}

export default paieApi
