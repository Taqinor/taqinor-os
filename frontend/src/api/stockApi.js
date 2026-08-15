import api from './axios'

const stockApi = {
  // Produits
  // VX163 — `config` (ex. `{signal}`) transmis pour l'annulation en vol.
  getProduits: (params, config) => api.get('/stock/produits/', { params, ...config }),
  getProduit: (id) => api.get(`/stock/produits/${id}/`),
  createProduit: (data) => api.post('/stock/produits/', data),
  updateProduit: (id, data) => api.patch(`/stock/produits/${id}/`, data),
  patchProduit: (id, data) => api.patch(`/stock/produits/${id}/`, data),
  deleteProduit: (id) => api.delete(`/stock/produits/${id}/`),
  getProduitsArchived: () => api.get('/stock/produits/', { params: { show_archived: 'true' } }),
  // NTP2P3 — catalogue interne d'achat (lecture seule) : n'expose JAMAIS
  // `prix_vente`, donc aucune marge n'est visible du demandeur.
  getCatalogueAchat: (params, config) =>
    api.get('/stock/catalogue-achat/', { params, ...config }),
  // NTP2P22 — favoris du demandeur (épinglés + 5 derniers demandés).
  getFavorisCatalogueAchat: () => api.get('/stock/catalogue-achat/favoris/'),
  setFavorisCatalogueAchat: (produitIds) =>
    api.put('/stock/catalogue-achat/favoris/', { produit_ids: produitIds }),
  // NTP2P23 — simulateur d'impact budgétaire (LECTURE SEULE : n'engage rien).
  simulerBudgetDisponible: (montant, config) =>
    api.get('/stock/budgets-departement/disponible/',
      { params: { montant }, ...config }),
  unarchiveProduit: (id) => api.patch(`/stock/produits/${id}/unarchive/`),
  forceDeleteProduit: (id) => api.delete(`/stock/produits/${id}/force-delete/`),
  // QP2 — clone serveur (nouveau nom, SKU frais, prix d'achat copié côté
  // serveur) ; réservé Directeur + Commercial responsable (QG4).
  dupliquerProduit: (id, nom) => api.post(`/stock/produits/${id}/dupliquer/`, { nom }),
  // APX18 — photo produit. UN seul aller-retour : le serveur téléverse dans
  // MinIO (primitive plateforme `records.Attachment`, ARC26) ET rattache la
  // pièce jointe au produit dans la même transaction — jamais de pièce jointe
  // orpheline. `file = null` retire la photo. Les écrans lisent ensuite
  // `produit.image_url` (endpoint plateforme, même origine, cookie httpOnly).
  // INTERNE : la photo n'entre dans aucun PDF ni sortie client-facing.
  uploadProduitImage: (id, file) => {
    if (!file) return api.delete(`/stock/produits/${id}/photo/`)
    const fd = new FormData()
    fd.append('file', file)
    return api.post(`/stock/produits/${id}/photo/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // Catégories
  getCategories: (params) => api.get('/stock/categories/', { params }),
  createCategorie: (data) => api.post('/stock/categories/', data),
  updateCategorie: (id, data) => api.put(`/stock/categories/${id}/`, data),
  patchCategorie: (id, data) => api.patch(`/stock/categories/${id}/`, data),
  deleteCategorie: (id) => api.delete(`/stock/categories/${id}/`),

  // Fournisseurs
  getFournisseurs: (params) => api.get('/stock/fournisseurs/', { params }),
  createFournisseur: (data) => api.post('/stock/fournisseurs/', data),
  updateFournisseur: (id, data) => api.put(`/stock/fournisseurs/${id}/`, data),
  deleteFournisseur: (id) => api.delete(`/stock/fournisseurs/${id}/`),
  // WIR190 — archivage fournisseur : `destroy` REPLIE sur un archivage quand
  // une FK PROTECT (prix d'achat négociés…) retient la fiche — il renvoie
  // alors 200 `{archived:true, detail, bloquants}` au lieu de 204. Ces trois
  // wrappers reprennent EXACTEMENT le patron produit (`show_archived`,
  // `unarchive`, `force-delete` qui refuse en 409 en nommant les bloquants) :
  // sans eux un fournisseur archivé était invisible ET irrécupérable.
  getFournisseursArchived: (params) =>
    api.get('/stock/fournisseurs/', { params: { ...params, show_archived: 'true' } }),
  unarchiveFournisseur: (id) => api.patch(`/stock/fournisseurs/${id}/unarchive/`),
  forceDeleteFournisseur: (id) => api.delete(`/stock/fournisseurs/${id}/force-delete/`),

  // Mouvements
  getMouvements: (params) => api.get('/stock/mouvements/', { params }),
  createMouvement: (data) => api.post('/stock/mouvements/', data),

  // Édition en masse du catalogue (T8) + export Excel d'une sélection.
  bulkProduits: (payload) => api.post('/stock/produits/bulk/', payload),
  // N16 — inventaire physique : comptage par produit → ajustement de stock.
  inventaire: (payload) => api.post('/stock/produits/inventaire/', payload),
  // N18 — valorisation du stock par emplacement (coût moyen, INTERNE/admin).
  valorisation: () => api.get('/stock/produits/valorisation/'),
  exportProduitsXlsx: (ids) =>
    api.post('/stock/produits/export-xlsx/', { ids }, { responseType: 'blob' }),
  // N15 — Stock multi-emplacements (dépôt principal + camionnette …).
  // Le total produit reste inchangé ; un transfert ne fait que ventiler.
  getEmplacements: () => api.get('/stock/emplacements/'),
  saveEmplacement: (id, data) => id
    ? api.patch(`/stock/emplacements/${id}/`, data)
    : api.post('/stock/emplacements/', data),
  deleteEmplacement: (id) => api.delete(`/stock/emplacements/${id}/`),
  getProduitEmplacements: (id) => api.get(`/stock/produits/${id}/emplacements/`),
  getTransferts: (params) => api.get('/stock/transferts/', { params }),
  createTransfert: (data) => api.post('/stock/transferts/', data),

  // N17 — listes de prix multi-fournisseurs par SKU (INTERNE, jamais client).
  getProduitPrixFournisseurs: (id) =>
    api.get(`/stock/produits/${id}/prix-fournisseurs/`),
  createPrixFournisseur: (data) => api.post('/stock/prix-fournisseurs/', data),
  updatePrixFournisseur: (id, data) =>
    api.patch(`/stock/prix-fournisseurs/${id}/`, data),
  deletePrixFournisseur: (id) => api.delete(`/stock/prix-fournisseurs/${id}/`),

  // Marques gérées (Paramètres → Stock). Une marque utilisée n'est pas supprimable.
  getMarques: () => api.get('/stock/marques/'),
  saveMarque: (id, data) => id
    ? api.patch(`/stock/marques/${id}/`, data) : api.post('/stock/marques/', data),
  deleteMarque: (id) => api.delete(`/stock/marques/${id}/`),

  // Bons de commande FOURNISSEUR (achats — N11). Les prix d'achat sont INTERNES.
  getBonsCommandeFournisseur: (params) =>
    api.get('/stock/bons-commande-fournisseur/', { params }),
  getBonCommandeFournisseur: (id) =>
    api.get(`/stock/bons-commande-fournisseur/${id}/`),
  createBonCommandeFournisseur: (data) =>
    api.post('/stock/bons-commande-fournisseur/', data),
  updateBonCommandeFournisseur: (id, data) =>
    api.patch(`/stock/bons-commande-fournisseur/${id}/`, data),
  deleteBonCommandeFournisseur: (id) =>
    api.delete(`/stock/bons-commande-fournisseur/${id}/`),
  envoyerBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/envoyer/`),
  // QS4/QS3 — envois fournisseur : WhatsApp (lien wa.me prêt à envoyer +
  // marque le BCF « envoyé ») et email (PDF joint + EmailLog). Le lien/PDF
  // montrent les prix d'achat au FOURNISSEUR (légitime), jamais côté client.
  whatsappBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/whatsapp/`),
  envoyerEmailBcf: (id, payload) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/envoyer-email/`, payload ?? {}),
  recevoirBcf: (id, receptions) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/recevoir/`, { receptions }),
  // ZPUR11 — motif OBLIGATOIRE (le backend refuse un motif vide) ; `rouvrir`
  // repasse un BCF ANNULE en brouillon (refusé si des réceptions confirmées existent).
  annulerBcf: (id, motifAnnulation) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/annuler/`,
      { motif_annulation: motifAnnulation }),
  rouvrirBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/rouvrir/`),
  // XPUR18 / WIR191 — SEUL chemin de modification d'un BCF déjà ENVOYE/RECU
  // (l'update direct est refusé en 400 à ces statuts) : journalise chaque
  // changement, incrémente `revision` et renvoie `reapprobation_requise`.
  // Corps : {lignes:[{id, quantite, prix_achat_unitaire, designation}],
  // date_commande, date_livraison_prevue, note}.
  reviserBcf: (id, data) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/reviser/`, data ?? {}),
  // ZPUR4 — clone en nouveau BROUILLON (quantités reçues à zéro).
  dupliquerBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/dupliquer/`),
  // ZPUR6 — fusionne plusieurs BCF BROUILLON du même fournisseur.
  fusionnerBcf: (ids) =>
    api.post('/stock/bons-commande-fournisseur/fusionner/', { bons_commande: ids }),
  // ZPUR1 — facture directement les lignes « sur commande » (sans réception préalable).
  facturerBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/facturer/`),
  bcfPdf: (id) =>
    api.get(`/stock/bons-commande-fournisseur/${id}/pdf/`, { responseType: 'blob' }),

  // ZPUR3 — modèles de BCF réutilisables (« purchase templates »).
  getModelesBcf: (params) => api.get('/stock/modeles-bcf/', { params }),
  getModeleBcf: (id) => api.get(`/stock/modeles-bcf/${id}/`),
  createModeleBcf: (data) => api.post('/stock/modeles-bcf/', data),
  updateModeleBcf: (id, data) => api.patch(`/stock/modeles-bcf/${id}/`, data),
  deleteModeleBcf: (id) => api.delete(`/stock/modeles-bcf/${id}/`),
  genererModeleBcf: (id, fournisseurId) =>
    api.post(`/stock/modeles-bcf/${id}/generer/`,
      fournisseurId ? { fournisseur: fournisseurId } : {}),

  // N20 — Étiquettes QR/CODE128 imprimables pour une sélection de SKU
  // (jeton stable PRODUIT:<id>, jamais de prix d'achat) + résolveur de scan.
  etiquettesProduits: (ids, { symbology = 'qr', sortie = 'pdf' } = {}) =>
    api.get('/stock/produits/etiquettes/', {
      params: { ids, symbology, sortie },
      paramsSerializer: { indexes: null },
      responseType: 'blob',
    }),
  resolveCode: (code) =>
    api.get('/stock/produits/resolve/', { params: { code } }),

  // N19 — retours fournisseur (articles défectueux/erronés). La validation
  // décrémente le stock. Usage INTERNE (prix d'achat jamais client-facing).
  getRetoursFournisseur: (params) =>
    api.get('/stock/retours-fournisseur/', { params }),
  getRetourFournisseur: (id) =>
    api.get(`/stock/retours-fournisseur/${id}/`),
  createRetourFournisseur: (data) =>
    api.post('/stock/retours-fournisseur/', data),
  validerRetourFournisseur: (id) =>
    api.post(`/stock/retours-fournisseur/${id}/valider/`),
  annulerRetourFournisseur: (id) =>
    api.post(`/stock/retours-fournisseur/${id}/annuler/`),

  // G5 — Réceptions fournisseur (goods-in). La confirmation incrémente le
  // stock (ENTREE) + avance le statut du BCF. Usage INTERNE.
  getReceptionsFournisseur: (params) =>
    api.get('/stock/receptions-fournisseur/', { params }),
  getReceptionFournisseur: (id) =>
    api.get(`/stock/receptions-fournisseur/${id}/`),
  createReceptionFournisseur: (data) =>
    api.post('/stock/receptions-fournisseur/', data),
  confirmerReceptionFournisseur: (id) =>
    api.post(`/stock/receptions-fournisseur/${id}/confirmer/`),
  annulerReceptionFournisseur: (id) =>
    api.post(`/stock/receptions-fournisseur/${id}/annuler/`),
  // XSTK4/XSTK5 — décompose un code GS1-128/DataMatrix scanné et résout le
  // produit + série/lot/péremption préremplis pour la réception scan-first.
  scanGs1ReceptionFournisseur: (code) =>
    api.get('/stock/receptions-fournisseur/scan-gs1/', { params: { code } }),

  // G5 — Factures fournisseur / comptes à payer (AP). Solde dû = TTC − Σ
  // paiements ; statut recalculé à chaque paiement. Usage INTERNE.
  getFacturesFournisseur: (params) =>
    api.get('/stock/factures-fournisseur/', { params }),
  getFactureFournisseur: (id) =>
    api.get(`/stock/factures-fournisseur/${id}/`),
  createFactureFournisseur: (data) =>
    api.post('/stock/factures-fournisseur/', data),
  updateFactureFournisseur: (id, data) =>
    api.patch(`/stock/factures-fournisseur/${id}/`, data),
  deleteFactureFournisseur: (id) =>
    api.delete(`/stock/factures-fournisseur/${id}/`),
  getComptesAPayer: (params) =>
    api.get('/stock/factures-fournisseur/comptes-a-payer/', { params }),
  ajouterPaiementFournisseur: (factureId, data) =>
    api.post(`/stock/factures-fournisseur/${factureId}/paiements/`, data),
  // XACC36 — SINK OCR → brouillon de facture d'achat. `file` optionnel (le
  // scan d'origine, rattaché en pièce jointe côté serveur).
  factureFournisseurDepuisOcr: ({ fields, file }) => {
    const formData = new FormData()
    formData.append('fields', JSON.stringify(fields ?? {}))
    if (file) formData.append('file', file)
    return api.post('/stock/factures-fournisseur/depuis-ocr/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // WR3 — Pilotage stock (analytics INTERNES ; les valeurs au prix d'achat
  // ne sortent jamais vers un document client).
  produitsAReapprovisionner: () =>
    api.get('/stock/produits/a-reapprovisionner/'),
  genererBcfReappro: (fournisseurId) =>
    api.post('/stock/produits/generer-bcf-reappro/',
      fournisseurId ? { fournisseur_id: fournisseurId } : {}),
  previsionsReappro: (nbMois) =>
    api.get('/stock/produits/previsions-reappro/',
      { params: nbMois ? { nb_mois: nbMois } : {} }),
  rotationStock: (jours) =>
    api.get('/stock/produits/rotation/', { params: jours ? { jours } : {} }),
  expirantBientot: (jours) =>
    api.get('/stock/produits/expirant-bientot/',
      { params: jours ? { jours } : {} }),

  // WR4 — Achats & fournisseurs (INTERNES ; prix d'achat jamais client-facing).
  // FG58 — comparaison des prix multi-fournisseurs d'un produit (admin).
  comparerFournisseurs: (produitId) =>
    api.get(`/stock/produits/${produitId}/comparer-fournisseurs/`),
  // FG59 — scorecard performance d'un fournisseur (admin).
  performanceFournisseur: (fournisseurId) =>
    api.get(`/stock/fournisseurs/${fournisseurId}/performance/`),
  // XPUR25 / WIR27 — fiche fournisseur 360 : agrégat BCF ouverts/en retard,
  // réceptions attendues, factures ouvertes/solde total dû, retours/avoirs,
  // score de performance (OTD), conformité (XPUR1), accords de prix actifs
  // (paliers XPUR14). `fournisseurs/{id}/vue-360/` — action construite côté
  // serveur (voir apps/stock/views/fournisseur.py `FournisseurViewSet.
  // vue_360`).
  getFournisseur360: (id) => api.get(`/stock/fournisseurs/${id}/vue-360/`),
  // NTP2P8 — score de risque fournisseur (0-100, 100 = risque nul) + facteurs.
  getScoreRisqueFournisseur: (id) =>
    api.get(`/stock/fournisseurs/${id}/score-risque/`),
  // NTP2P7 — dossier d'onboarding (pièces légales) d'un fournisseur.
  getOnboardingFournisseur: (id) =>
    api.get(`/stock/fournisseurs/${id}/onboarding/`),
  createDossierOnboarding: (data) =>
    api.post('/stock/dossiers-onboarding-fournisseur/', data),
  validerDossierOnboarding: (id, data) =>
    api.post(`/stock/dossiers-onboarding-fournisseur/${id}/valider-dossier/`, data),
  createDocumentFournisseur: (data) =>
    api.post('/stock/documents-fournisseur/', data),
  televerserDocumentFournisseur: (id, formData) =>
    api.post(`/stock/documents-fournisseur/${id}/televerser/`, formData),
  // Onglets détaillés — réutilisent les endpoints EXISTANTS déjà câblés
  // ailleurs (WR4/FG55/FG56/FG58/FG59, XPUR1, XPUR9), filtrés par fournisseur
  // côté frontend quand l'API ne filtre pas déjà nativement.
  getFacturesFournisseurDe: (fournisseurId, params) =>
    api.get('/stock/factures-fournisseur/', { params: { ...params, fournisseur: fournisseurId } }),
  getRetoursFournisseurDe: (fournisseurId, params) =>
    api.get('/stock/retours-fournisseur/', { params }).then((r) => ({
      ...r,
      data: Array.isArray(r.data?.results)
        ? { ...r.data, results: r.data.results.filter((x) => x.fournisseur === fournisseurId) }
        : (r.data ?? []).filter((x) => x.fournisseur === fournisseurId),
    })),
  getBonsCommandeFournisseurDe: (fournisseurId, params) =>
    api.get('/stock/bons-commande-fournisseur/', { params }).then((r) => ({
      ...r,
      data: Array.isArray(r.data?.results)
        ? { ...r.data, results: r.data.results.filter((x) => x.fournisseur === fournisseurId) }
        : (r.data ?? []).filter((x) => x.fournisseur === fournisseurId),
    })),
  // XPUR1 — documents de conformité, filtrés serveur par ?fournisseur=.
  getDocumentsConformiteFournisseur: (fournisseurId) =>
    api.get('/stock/documents-conformite-fournisseur/', { params: { fournisseur: fournisseurId } }),
  // WIR26 — Paramètres → Achats (singleton par société). GET crée le réglage
  // si besoin (`AchatsParametres.for_company`) ; PATCH exige un `id` (route
  // détail du ViewSet), obtenu via le GET précédent.
  getAchatsParametres: () => api.get('/stock/achats-parametres/'),
  updateAchatsParametres: (id, data) =>
    api.patch(`/stock/achats-parametres/${id}/`, data),
  // FG55 — PDF d'une facture fournisseur (blob, interne).
  factureFournisseurPdf: (id) =>
    api.get(`/stock/factures-fournisseur/${id}/pdf/`, { responseType: 'blob' }),
  // FG56 — facturer une réception confirmée → crée une facture fournisseur.
  facturerReception: (id) =>
    api.post(`/stock/receptions-fournisseur/${id}/facturer/`),
  // FG60 — export Excel de la liste (filtrée) des mouvements de stock (blob).
  exportMouvementsXlsx: (params) =>
    api.post('/stock/mouvements/export-xlsx/', null,
      { params, responseType: 'blob' }),
  // FG62 — suggestions de réapprovisionnement par emplacement (admin).
  suggestionsReapproEmplacement: () =>
    api.get('/stock/emplacements/suggestions-reappro/'),
  // ZSTK3 — rapport prévisionnel produit (disponible + entrées/sorties
  // attendues → solde projeté daté). INTERNE, lecture seule.
  produitPrevisionnel: (produitId) =>
    api.get(`/stock/produits/${produitId}/previsionnel/`),
  // ZSTK7 — « Vue groupée / pivot » : quantités entrées/sorties/nettes
  // agrégées par produit/type/mois/emplacement.
  mouvementsAgregation: (params) =>
    api.get('/stock/mouvements/agregation/', { params }),
  mouvementsAgregationXlsx: (params) =>
    api.get('/stock/mouvements/agregation/',
      { params: { ...params, export: 'xlsx' }, responseType: 'blob' }),
  // ZSTK6 — planche d'étiquettes lot/série depuis une réception confirmée.
  receptionEtiquettes: (id, { symbology = 'qr' } = {}) =>
    api.get(`/stock/receptions-fournisseur/${id}/etiquettes/`,
      { params: { symbology, sortie: 'pdf' }, responseType: 'blob' }),
  // ZPUR9 — rapport imprimable « analyse d'achats » (PDF, admin/responsable).
  analyseAchatsPdf: (params) =>
    api.get('/stock/produits/analyse-achats/pdf/',
      { params, responseType: 'blob' }),
  analyseAchatsXlsx: (params) =>
    api.get('/stock/produits/analyse-achats/export-xlsx/',
      { params, responseType: 'blob' }),

  // ZSTK12 — nomenclatures de code-barres (Paramètres) + leurs règles.
  getNomenclaturesCodeBarres: () => api.get('/stock/nomenclatures-code-barres/'),
  createNomenclatureCodeBarres: (data) =>
    api.post('/stock/nomenclatures-code-barres/', data),
  updateNomenclatureCodeBarres: (id, data) =>
    api.patch(`/stock/nomenclatures-code-barres/${id}/`, data),
  deleteNomenclatureCodeBarres: (id) =>
    api.delete(`/stock/nomenclatures-code-barres/${id}/`),
  createRegleCodeBarres: (data) => api.post('/stock/regles-code-barres/', data),
  updateRegleCodeBarres: (id, data) =>
    api.patch(`/stock/regles-code-barres/${id}/`, data),
  deleteRegleCodeBarres: (id) => api.delete(`/stock/regles-code-barres/${id}/`),

  // WR5 — Opérations stock (admin/INTERNE).
  // FG63 — sessions d'inventaire physique (brouillon → valider / annuler).
  getInventaireSessions: (params) =>
    api.get('/stock/inventaire-sessions/', { params }),
  getInventaireSession: (id) =>
    api.get(`/stock/inventaire-sessions/${id}/`),
  createInventaireSession: (data) =>
    api.post('/stock/inventaire-sessions/', data),
  validerInventaireSession: (id) =>
    api.post(`/stock/inventaire-sessions/${id}/valider/`),
  annulerInventaireSession: (id) =>
    api.post(`/stock/inventaire-sessions/${id}/annuler/`),

  // FG66 / DC36 — kits (nomenclatures) : liste + explosion en lignes composant.
  getKits: (params) => api.get('/stock/kits/', { params }),
  exploserKit: (id, quantite) =>
    api.get(`/stock/kits/${id}/exploser/`,
      { params: quantite ? { quantite } : {} }),
  // XMFG19 — remplacement de masse d'un composant (préview dry_run → confirmer).
  remplacerComposantKits: (data) =>
    api.post('/stock/kits/remplacer-composant/', data),
  // ZMFG9 — disponibilité multi-niveaux du kit (kits assemblables + goulots).
  getKitDisponibilite: (id) =>
    api.get(`/stock/kits/${id}/disponibilite/`),

  // DC35 / FG254 — fiches techniques (datasheets) rattachées aux produits.
  getFichesTechniques: (produitId) =>
    api.get('/stock/fiches-techniques/',
      { params: produitId ? { produit: produitId } : {} }),
  createFicheTechnique: (data) =>
    api.post('/stock/fiches-techniques/', data),
  updateFicheTechnique: (id, data) =>
    api.patch(`/stock/fiches-techniques/${id}/`, data),
  deleteFicheTechnique: (id) =>
    api.delete(`/stock/fiches-techniques/${id}/`),
  // PV7 — PDF constructeur (FileField `pdf`), envoyé séparément en multipart.
  uploadFicheTechniquePdf: (id, file) => {
    const fd = new FormData()
    fd.append('pdf', file)
    return api.patch(`/stock/fiches-techniques/${id}/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // ── WIR108 — fiche fournisseur : acomptes, avoirs, contacts, catégories ──

  // XPUR5 — catégories fournisseur (référentiel léger, comme Marque). CRUD.
  getCategoriesFournisseur: (params) =>
    api.get('/stock/categories-fournisseur/', { params }),
  createCategorieFournisseur: (data) =>
    api.post('/stock/categories-fournisseur/', data),
  updateCategorieFournisseur: (id, data) =>
    api.patch(`/stock/categories-fournisseur/${id}/`, data),
  deleteCategorieFournisseur: (id) =>
    api.delete(`/stock/categories-fournisseur/${id}/`),

  // XPUR5 — contacts secondaires du fournisseur (N par fournisseur), déjà
  // filtrés serveur par ?fournisseur=. `Fournisseur.contact_personne` reste
  // le contact principal (champ libre, inchangé).
  getContactsFournisseurDe: (fournisseurId) =>
    api.get('/stock/contacts-fournisseur/', { params: { fournisseur: fournisseurId } }),
  createContactFournisseur: (data) =>
    api.post('/stock/contacts-fournisseur/', data),
  updateContactFournisseur: (id, data) =>
    api.patch(`/stock/contacts-fournisseur/${id}/`, data),
  deleteContactFournisseur: (id) =>
    api.delete(`/stock/contacts-fournisseur/${id}/`),

  // XPUR8 — acomptes/avances fournisseur sur BCF. L'endpoint filtre
  // uniquement par ?bon_commande= (pas de FK directe vers le fournisseur) :
  // on récupère d'abord les BCF du fournisseur (déjà câblé,
  // getBonsCommandeFournisseurDe) puis on agrège leurs acomptes.
  getAcomptesFournisseur: (params) =>
    api.get('/stock/acomptes-fournisseur/', { params }),
  getAcomptesFournisseurDe: async (fournisseurId) => {
    const bcfRes = await stockApi.getBonsCommandeFournisseurDe(fournisseurId)
    const bcfs = Array.isArray(bcfRes.data?.results)
      ? bcfRes.data.results : (bcfRes.data ?? [])
    const parBcf = await Promise.all(
      bcfs.map((b) => api.get('/stock/acomptes-fournisseur/', { params: { bon_commande: b.id } })))
    return parBcf.flatMap((r) => (Array.isArray(r.data?.results) ? r.data.results : (r.data ?? [])))
  },
  createAcompteFournisseur: (data) =>
    api.post('/stock/acomptes-fournisseur/', data),
  updateAcompteFournisseur: (id, data) =>
    api.patch(`/stock/acomptes-fournisseur/${id}/`, data),
  deleteAcompteFournisseur: (id) =>
    api.delete(`/stock/acomptes-fournisseur/${id}/`),

  // XPUR9 — avoirs fournisseur (notes de crédit AP), filtrés serveur par
  // ?fournisseur=. `imputer` réduit le solde dû d'une facture du même
  // fournisseur ; `valider` fait passer brouillon → validé.
  getAvoirsFournisseurDe: (fournisseurId) =>
    api.get('/stock/avoirs-fournisseur/', { params: { fournisseur: fournisseurId } }),
  createAvoirFournisseur: (data) =>
    api.post('/stock/avoirs-fournisseur/', data),
  validerAvoirFournisseur: (id) =>
    api.post(`/stock/avoirs-fournisseur/${id}/valider/`),
  imputerAvoirFournisseur: (id, data) =>
    api.post(`/stock/avoirs-fournisseur/${id}/imputer/`, data),

  // ── WIR109 — inventaire/stock avancé : lots FEFO, inventaire annuel,
  // revalorisations, conditionnements ──────────────────────────────────────

  // XSTK6 — lots en entrepôt (LECTURE SEULE, alimenté à la réception).
  // `sortir` décrémente un lot (garde périmé, contournable avec motif tracé).
  getLotsEntrepot: (params) => api.get('/stock/lots-entrepot/', { params }),
  getLotFefo: (produitId, quantite) =>
    api.get('/stock/lots-entrepot/fefo/', { params: { produit: produitId, quantite } }),
  sortirLotEntrepot: (id, data) =>
    api.post(`/stock/lots-entrepot/${id}/sortir/`, data),

  // XSTK13 — inventaire annuel légal FIGÉ (CGNC, LECTURE SEULE ; `figer`
  // crée le snapshot immuable de l'exercice, jamais réécrit ensuite).
  getInventairesAnnuels: (params) => api.get('/stock/inventaires-annuels/', { params }),
  figerInventaireAnnuel: (data) =>
    api.post('/stock/inventaires-annuels/figer/', data),
  exportInventaireAnnuelXlsx: (id) =>
    api.get(`/stock/inventaires-annuels/${id}/export-xlsx/`, { responseType: 'blob' }),

  // XSTK14 — revalorisation manuelle du stock (document tracé, admin-only).
  // `valider` verrouille le document (devient la nouvelle couche de coût moyen).
  getRevalorisationsStock: (params) => api.get('/stock/revalorisations-stock/', { params }),
  createRevalorisationStock: (data) =>
    api.post('/stock/revalorisations-stock/', data),
  deleteRevalorisationStock: (id) =>
    api.delete(`/stock/revalorisations-stock/${id}/`),
  validerRevalorisationStock: (id) =>
    api.post(`/stock/revalorisations-stock/${id}/valider/`),

  // XSTK15 — conditionnements d'achat d'un produit (Touret/Carton…), CRUD.
  getConditionnementsProduit: (params) => api.get('/stock/conditionnements/', { params }),
  createConditionnementProduit: (data) =>
    api.post('/stock/conditionnements/', data),
  updateConditionnementProduit: (id, data) =>
    api.patch(`/stock/conditionnements/${id}/`, data),
  deleteConditionnementProduit: (id) =>
    api.delete(`/stock/conditionnements/${id}/`),

  // NTWMS29/33/42 — pilotage d'entrepôt (lecture seule).
  getEntrepotCockpit: (params) => api.get('/stock/entrepot/cockpit/', { params }),
  simulerCapacite: (params) => api.get('/stock/simuler-capacite/', { params }),
  getZonesSurcapacite: (params) =>
    api.get('/stock/entrepot/alertes-surcapacite/', { params }),

  // NTSCM26 — TCO par fournisseur (prix nu + coût du retard + coût qualité).
  // INTERNE : réservé responsable/admin, jamais un document client.
  comparerTcoFournisseurs: (produitId, params) =>
    api.get(`/stock/produits/${produitId}/comparer-tco/`, { params }),
}

export default stockApi
