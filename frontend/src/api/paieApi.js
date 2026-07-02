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
  etatIrAnnuel: (annee) =>
    api.get('/paie/periodes/etat-ir-annuel/', { params: { annee } }),

  // ── Bulletins (snapshot immuable, lecture seule + actions) ──
  getBulletins: (params) => api.get('/paie/bulletins/', { params }),
  getBulletin: (id) => api.get(`/paie/bulletins/${id}/`),
  genererBulletin: (data) => api.post('/paie/bulletins/generer/', data),
  validerBulletin: (id) => api.post(`/paie/bulletins/${id}/valider/`),
  rectifierBulletin: (id, data) =>
    api.post(`/paie/bulletins/${id}/rectifier/`, data),
  bulletinPdf: (id) =>
    api.get(`/paie/bulletins/${id}/pdf/`, { responseType: 'blob' }),

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
  fichierVirement: (id) =>
    api.get(`/paie/ordres-virement/${id}/fichier/`),

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

  // ── Cumuls annuels ──
  getCumulsAnnuels: (params) =>
    api.get('/paie/cumuls-annuels/', { params }),
  recalculerCumul: (data) =>
    api.post('/paie/cumuls-annuels/recalculer/', data),

  // ── Self-service employé (coffre-fort) — tout rôle, scopé utilisateur ──
  getMesBulletins: (params) => api.get('/paie/mes-bulletins/', { params }),
  mesBulletinPdf: (id) =>
    api.get(`/paie/mes-bulletins/${id}/pdf/`, { responseType: 'blob' }),
}

export default paieApi
