import api from './axios'

const installationsApi = {
  // Chantiers
  getInstallations: (params) => api.get('/installations/chantiers/', { params }),
  getInstallation: (id) => api.get(`/installations/chantiers/${id}/`),
  createInstallation: (data) => api.post('/installations/chantiers/', data),
  updateInstallation: (id, data) => api.patch(`/installations/chantiers/${id}/`, data),
  deleteInstallation: (id) => api.delete(`/installations/chantiers/${id}/`),
  createFromDevis: (devisId) =>
    api.post('/installations/chantiers/creer-depuis-devis/', { devis: devisId }),
  getHistorique: (id) => api.get(`/installations/chantiers/${id}/historique/`),
  noter: (id, body) => api.post(`/installations/chantiers/${id}/noter/`, { body }),
  miseEnService: (id, data) =>
    api.post(`/installations/chantiers/${id}/mise-en-service/`, data),
  annuler: (id, motif) => api.post(`/installations/chantiers/${id}/annuler/`, { motif }),
  reactiver: (id) => api.post(`/installations/chantiers/${id}/reactiver/`),
  // N4/N9 — checklist d'exécution + saisie de n° de série.
  getChecklist: (id) => api.get(`/installations/chantiers/${id}/checklist/`),
  cocherChecklist: (id, payload) =>
    api.post(`/installations/chantiers/${id}/cocher-checklist/`, payload),
  // NTMOB11 — métadonnées (étape + géoloc/horodatage) d'une photo de
  // checklist déjà uploadée via recordsApi.uploadAttachment.
  ajouterChecklistPhotoMeta: (id, payload) =>
    api.post(`/installations/chantiers/${id}/checklist-photo/`, payload),
  // NTMOB16 — signature client tracée sur le bon de livraison chantier
  // (distinct de installationsApi.signerClient, réservé aux interventions).
  signerClientChantier: (id, { signature_client, signataire_nom }) =>
    api.post(`/installations/chantiers/${id}/signer-client/`,
      { signature_client, signataire_nom }),
  // N4 — étapes modèle de checklist (Paramètres → Chantiers).
  getChecklistEtapes: (templateId) =>
    api.get('/installations/checklist-etapes/',
      templateId ? { params: { template: templateId } } : undefined),
  saveChecklistEtape: (id, data) => id
    ? api.patch(`/installations/checklist-etapes/${id}/`, data)
    : api.post('/installations/checklist-etapes/', data),
  deleteChecklistEtape: (id) => api.delete(`/installations/checklist-etapes/${id}/`),

  // N74 — modèles nommés de checklist, auto-sélectionnés par type d'installation.
  getChecklistTemplates: () => api.get('/installations/checklist-templates/'),
  saveChecklistTemplate: (id, data) => id
    ? api.patch(`/installations/checklist-templates/${id}/`, data)
    : api.post('/installations/checklist-templates/', data),
  deleteChecklistTemplate: (id) => api.delete(`/installations/checklist-templates/${id}/`),

  // CH1/CH5 — étapes/gates configurables du cycle de vie chantier (Directeur).
  getStagesChantier: () => api.get('/installations/etapes-chantier/'),
  saveStageChantier: (id, data) => id
    ? api.patch(`/installations/etapes-chantier/${id}/`, data)
    : api.post('/installations/etapes-chantier/', data),
  deleteStageChantier: (id) => api.delete(`/installations/etapes-chantier/${id}/`),

  // CH2 — parcours d'étapes du chantier + état de gate par étape (timeline).
  getEtapesChantier: (id) => api.get(`/installations/chantiers/${id}/etapes/`),
  // CH2 — avance à l'étape `cle` donnée, ou à la suivante si omise. Rejet 400
  // avec `{detail, raisons[]}` si un gate bloquant n'est pas satisfait.
  avancerEtape: (id, cle) =>
    api.post(`/installations/chantiers/${id}/avancer-etape/`,
      cle ? { etape: cle } : {}),

  // CH3 — fiche de recette IEC 62446-1 (mise en service structurée).
  getRecette: (id) => api.get(`/installations/chantiers/${id}/recette/`),
  ouvrirRecette: (id) => api.post(`/installations/chantiers/${id}/recette/`, {}),
  // WIR202/CH3 — la fiche se créait VIDE et bloquait le gate « Mise en
  // service » à jamais : rien ne permettait de la remplir. Ces trois wrappers
  // adressent le CommissioningRecord lui-même (contrôles documentaires,
  // visuels, électriques, sécurité) et ses relevés I-V par string.
  getRecetteRecord: (recordId) =>
    api.get(`/installations/recettes-commissioning/${recordId}/`),
  updateRecette: (recordId, data) =>
    api.patch(`/installations/recettes-commissioning/${recordId}/`, data),
  ajouterReleveIv: (recordId, data) =>
    api.post(`/installations/recettes-commissioning/${recordId}/ajouter-iv/`, data),

  // CH4 — pack de remise client (handover). GET aperçoit à blanc si absent.
  getPackRemise: (id) => api.get(`/installations/chantiers/${id}/pack-remise/`),
  genererPackRemise: (id) =>
    api.post(`/installations/chantiers/${id}/pack-remise/`, {}),

  // Rapport de production énergétique ESTIMÉE (PDF client-facing).
  // `params` : nb_mois, date_debut, date_fin, production_annuelle_kwh,
  // rendement, tarif, co2. Réponse en blob PDF.
  rapportEnergie: (id, params) =>
    api.get(`/installations/chantiers/${id}/rapport-energie/`,
      { params, responseType: 'blob' }),

  // N13 — besoin matériel (lecture seule) + création d'un BCF brouillon.
  besoinMateriel: (id) => api.get(`/installations/chantiers/${id}/besoin-materiel/`),
  commanderBesoin: (id, fournisseurId) =>
    api.post(`/installations/chantiers/${id}/commander-besoin/`,
      fournisseurId ? { fournisseur: fournisseurId } : {}),

  // FG74 — Gantt multi-chantier (lecture seule, jalons par chantier actif).
  getGanttChantiers: () => api.get('/installations/chantiers/gantt/'),

  // N43 — régime loi 82-21 suggéré pour une puissance (kWc) donnée.
  getRegimeSuggestion: (kwc) =>
    api.get('/installations/chantiers/regime-suggestion/', { params: { kwc } }),

  // FG79 — matérialise la chaîne d'interventions standard du chantier (idempotent).
  creerInterventionsStandard: (id) =>
    api.post(`/installations/chantiers/${id}/creer-interventions-standard/`, {}),

  // FG71 — synthèse coût / marge du chantier. STRICTEMENT INTERNE (admin) : ne
  // jamais afficher hors écran admin, jamais sur un document client.
  getChantierCout: (id, tarifJour) =>
    api.get(`/installations/chantiers/${id}/cout/`,
      { params: tarifJour ? { tarif_jour: tarifJour } : undefined }),

  // Interventions (sorties chantier) — F3/F4
  getInterventions: (params) => api.get('/installations/interventions/', { params }),
  createIntervention: (data) => api.post('/installations/interventions/', data),
  updateIntervention: (id, data) => api.patch(`/installations/interventions/${id}/`, data),
  deleteIntervention: (id) => api.delete(`/installations/interventions/${id}/`),
  getInterventionHistorique: (id) =>
    api.get(`/installations/interventions/${id}/historique/`),
  noterIntervention: (id, body) =>
    api.post(`/installations/interventions/${id}/noter/`, { body }),

  // F5 — Liste de préparation (matériel du chantier + outils du kit).
  getPreparation: (id) => api.get(`/installations/interventions/${id}/preparation/`),
  choisirKit: (id, kit) =>
    api.post(`/installations/interventions/${id}/choisir-kit/`, { kit }),
  cocherMateriel: (id, ligne, charge) =>
    api.post(`/installations/interventions/${id}/cocher-materiel/`, { ligne, charge }),
  cocherOutil: (id, ligne, coche) =>
    api.post(`/installations/interventions/${id}/cocher-outil/`, { ligne, coche }),
  confirmerCharge: (id) =>
    api.post(`/installations/interventions/${id}/confirmer-charge/`, {}),
  commanderManques: (id, fournisseur) =>
    api.post(`/installations/interventions/${id}/commander-manques/`,
      fournisseur ? { fournisseur } : {}),

  // F6 — Trajet & check-in GPS (géolocalisation navigateur, aucun service externe).
  departDepot: (id) => api.post(`/installations/interventions/${id}/depart-depot/`, {}),
  checkin: (id, lat, lng) =>
    api.post(`/installations/interventions/${id}/checkin/`, { lat, lng }),
  retourDepot: (id) => api.post(`/installations/interventions/${id}/retour/`, {}),

  // F7/F8 — Photos guidées par shot list (stockage objet générique).
  getPhotos: (id) => api.get(`/installations/interventions/${id}/photos/`),
  ajouterPhoto: (id, file, slot, phase) => {
    const fd = new FormData()
    fd.append('file', file)
    if (slot) fd.append('slot', slot)
    if (phase) fd.append('phase', phase)
    return api.post(`/installations/interventions/${id}/ajouter-photo/`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  supprimerPhoto: (id, photo) =>
    api.post(`/installations/interventions/${id}/supprimer-photo/`, { photo }),

  // F7/F8 — Créneaux de shot list (Paramètres → Documentation terrain).
  getShotlistSlots: () => api.get('/installations/shotlist-slots/'),
  saveShotlistSlot: (id, data) => id
    ? api.patch(`/installations/shotlist-slots/${id}/`, data)
    : api.post('/installations/shotlist-slots/', data),
  deleteShotlistSlot: (id) => api.delete(`/installations/shotlist-slots/${id}/`),

  // Types d'intervention gérés (Paramètres → Chantiers). Types système protégés.
  getTypesIntervention: () => api.get('/installations/types-intervention/'),
  saveTypeIntervention: (id, data) => id
    ? api.patch(`/installations/types-intervention/${id}/`, data)
    : api.post('/installations/types-intervention/', data),
  deleteTypeIntervention: (id) => api.delete(`/installations/types-intervention/${id}/`),

  // ── F9 — N° de série par composant (+ OCR swappable no-op) ──
  getSerials: (id) => api.get(`/installations/interventions/${id}/serials/`),
  ajouterSerial: (id, { produit, designation, slot, numero_serie, file }) => {
    const fd = new FormData()
    if (produit) fd.append('produit', produit)
    if (designation) fd.append('designation', designation)
    if (slot) fd.append('slot', slot)
    if (numero_serie != null) fd.append('numero_serie', numero_serie)
    if (file) fd.append('file', file)
    return api.post(`/installations/interventions/${id}/ajouter-serial/`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  modifierSerial: (id, payload) =>
    api.post(`/installations/interventions/${id}/modifier-serial/`, payload),
  supprimerSerial: (id, serial) =>
    api.post(`/installations/interventions/${id}/supprimer-serial/`, { serial }),

  // ── F10 — Annotation d'une photo (dessin + légende) ──
  annoterPhoto: (id, payload) =>
    api.post(`/installations/interventions/${id}/annoter-photo/`, payload),

  // ── F11/F12 — Réconciliation du matériel consommé ──
  getConsommation: (id) =>
    api.get(`/installations/interventions/${id}/consommation/`),
  ajouterLigneConsommation: (id, payload) =>
    api.post(`/installations/interventions/${id}/ajouter-ligne-consommation/`, payload),
  modifierLigneConsommation: (id, payload) =>
    api.post(`/installations/interventions/${id}/modifier-ligne-consommation/`, payload),
  supprimerLigneConsommation: (id, ligne) =>
    api.post(`/installations/interventions/${id}/supprimer-ligne-consommation/`, { ligne }),
  validerConsommation: (id) =>
    api.post(`/installations/interventions/${id}/valider-consommation/`, {}),
  overageReview: () =>
    api.get('/installations/interventions/overage-review/'),

  // ── F13/F14 — Mémos vocaux (+ transcription swappable no-op) ──
  getMemos: (id) => api.get(`/installations/interventions/${id}/memos/`),
  ajouterMemo: (id, file, cible) => {
    const fd = new FormData()
    fd.append('file', file)
    if (cible) fd.append('cible', cible)
    return api.post(`/installations/interventions/${id}/ajouter-memo/`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  modifierMemo: (id, memo, transcript) =>
    api.post(`/installations/interventions/${id}/modifier-memo/`, { memo, transcript }),
  supprimerMemo: (id, memo) =>
    api.post(`/installations/interventions/${id}/supprimer-memo/`, { memo }),

  // ── F15 — Temps d'équipe ──
  getCrewTime: (id) => api.get(`/installations/interventions/${id}/crew-time/`),

  // ── F16 — Réserves (punch-list) ──
  getReserves: (id) => api.get(`/installations/interventions/${id}/reserves/`),
  ajouterReserve: (id, payload) =>
    api.post(`/installations/interventions/${id}/ajouter-reserve/`, payload),
  modifierReserve: (id, payload) =>
    api.post(`/installations/interventions/${id}/modifier-reserve/`, payload),
  resoudreReserve: (id, payload) =>
    api.post(`/installations/interventions/${id}/resoudre-reserve/`, payload),

  // ── F17 — Retour d'outillage ──
  getToolReturn: (id) => api.get(`/installations/interventions/${id}/tool-return/`),
  cocherToolReturn: (id, payload) =>
    api.post(`/installations/interventions/${id}/cocher-tool-return/`, payload),
  confirmerToolReturn: (id) =>
    api.post(`/installations/interventions/${id}/confirmer-tool-return/`, {}),

  // ── F18 — Consignes de sécurité (sign-off) ──
  getSafety: (id) => api.get(`/installations/interventions/${id}/safety/`),
  cocherSafety: (id, cle, coche) =>
    api.post(`/installations/interventions/${id}/cocher-safety/`, { cle, coche }),
  signerSafety: (id) =>
    api.post(`/installations/interventions/${id}/signer-safety/`, {}),
  // ── FG69 — signature client sur le compte-rendu d'intervention ──
  signerClient: (id, { signature_client, signataire_nom }) =>
    api.post(`/installations/interventions/${id}/signer-client/`,
      { signature_client, signataire_nom }),
  getConsignesSecurite: () => api.get('/installations/consignes-securite/'),
  saveConsigneSecurite: (id, data) => id
    ? api.patch(`/installations/consignes-securite/${id}/`, data)
    : api.post('/installations/consignes-securite/', data),
  deleteConsigneSecurite: (id) => api.delete(`/installations/consignes-securite/${id}/`),

  // ── F19 — Compte-rendu PDF (client-facing) ──
  compteRenduUrl: (id) =>
    `/api/django/installations/interventions/${id}/compte-rendu/`,

  // ── F20 — Contrôle qualité IA des photos (vision swappable, no-op) ──
  getPhotoQa: (id) => api.get(`/installations/interventions/${id}/photo-qa/`),

  // ── F23 — Code/QR de l'intervention ──
  getCode: (id) => api.get(`/installations/interventions/${id}/code/`),

  // ── FG68 — Calendrier dispatch techniciens (groupé par technicien) ──
  getCalendrierInterventions: (dateFrom, dateTo) =>
    api.get('/installations/interventions/calendrier/',
      { params: { date_from: dateFrom, date_to: dateTo } }),

  // ── FG73 — « Ma tournée » : interventions du jour du technicien, ordonnées
  // géographiquement (plus proche voisin) avec lien Itinéraire Google Maps. ──
  // NTMOB21 — météo terrain du jour au point GPS (cache serveur 1 h).
  // Erreur silencieuse : le widget est informatif, jamais bloquant.
  getMeteoTerrain: (lat, lon) =>
    api.get('/installations/meteo/', {
      params: { lat, lon }, suppressErrorToast: true,
    }),
  getMaTournee: (date, config) =>
    api.get('/installations/interventions/ma-tournee/',
      { params: date ? { date } : undefined, ...config }),

  // ── FG299 — Plan de charge des équipes (capacité vs affecté) ──
  getPlanDeCharge: (params) =>
    api.get('/installations/interventions/plan-de-charge/', { params }),

  // ── FG300 — Conflits d'affectation (double-booking technicien/camionnette) ──
  getConflitsAffectation: (params) =>
    api.get('/installations/interventions/conflits-affectation/', { params }),

  // ── FG301 — Nivellement de charge (proposition de rééquilibrage, lecture seule) ──
  getNivellementCharge: (params) =>
    api.get('/installations/interventions/nivellement-charge/', { params }),

  // ── FG303 — Planning des camionnettes (capacité véhicule) ──
  getPlanningCamionnettes: (params) =>
    api.get('/installations/interventions/planning-camionnettes/', { params }),

  // ── N91/F21 — Synchro idempotente de la capture terrain hors-ligne ──
  // `ops` : [{ client_op_id, op_type, payload }]. Sûr à rejouer en entier
  // (la même clé est un no-op côté serveur). suppressErrorToast : le flush se
  // fait en arrière-plan, on ne veut pas spammer l'utilisateur si le réseau
  // retombe pendant l'envoi (l'outbox réessaiera).
  syncField: (ops) =>
    api.post('/installations/sync/', { ops }, { suppressErrorToast: true }),

  // ── XSTK1 — Magasin : casiers, put-away, pick-lists, colisage ──

  // FG319 — casiers de rangement (zone/allée/casier) sous un emplacement.
  getBinLocations: (params) => api.get('/installations/bin-locations/', { params }),
  getBinLocation: (id) => api.get(`/installations/bin-locations/${id}/`),
  createBinLocation: (data) => api.post('/installations/bin-locations/', data),
  updateBinLocation: (id, data) => api.patch(`/installations/bin-locations/${id}/`, data),
  deleteBinLocation: (id) => api.delete(`/installations/bin-locations/${id}/`),

  // FG319 — affectation produit ↔ casier (quantité indicative).
  getBinAffectations: (params) => api.get('/installations/bin-affectations/', { params }),
  createBinAffectation: (data) => api.post('/installations/bin-affectations/', data),
  updateBinAffectation: (id, data) => api.patch(`/installations/bin-affectations/${id}/`, data),
  deleteBinAffectation: (id) => api.delete(`/installations/bin-affectations/${id}/`),

  // FG320 — rangement guidé (put-away). `bin_suggere` calculé serveur à la
  // création ; `ranger(id, bin)` confirme (bin optionnel = casier suggéré).
  getPutAways: (params) => api.get('/installations/putaways/', { params }),
  getPutAway: (id) => api.get(`/installations/putaways/${id}/`),
  createPutAway: (data) => api.post('/installations/putaways/', data),
  rangerPutAway: (id, binId) =>
    api.post(`/installations/putaways/${id}/ranger/`, binId ? { bin: binId } : {}),

  // FG321 — bons de prélèvement par chantier. Les lignes sont générées
  // serveur depuis les réservations actives du chantier à la création.
  getPickLists: (params) => api.get('/installations/pick-lists/', { params }),
  getPickList: (id) => api.get(`/installations/pick-lists/${id}/`),
  createPickList: (data) => api.post('/installations/pick-lists/', data),
  demarrerPickList: (id) => api.post(`/installations/pick-lists/${id}/demarrer/`, {}),
  terminerPickList: (id) => api.post(`/installations/pick-lists/${id}/terminer/`, {}),

  // FG321 — lignes de prélèvement (cocher `preleve` / `quantite_prelevee`).
  getPickListLignes: (params) => api.get('/installations/pick-list-lignes/', { params }),
  updatePickListLigne: (id, data) => api.patch(`/installations/pick-list-lignes/${id}/`, data),

  // FG322 — colis de préparation (référence anti-collision posée serveur).
  getColisList: (params) => api.get('/installations/colis/', { params }),
  getColis: (id) => api.get(`/installations/colis/${id}/`),
  createColis: (data) => api.post('/installations/colis/', data),
  updateColis: (id, data) => api.patch(`/installations/colis/${id}/`, data),
  controlerColis: (id) => api.post(`/installations/colis/${id}/controler/`, {}),
  expedierColis: (id) => api.post(`/installations/colis/${id}/expedier/`, {}),

  // FG322 — lignes de colis (articles emballés + `controle_ok`).
  getColisLignes: (params) => api.get('/installations/colis-lignes/', { params }),
  createColisLigne: (data) => api.post('/installations/colis-lignes/', data),
  updateColisLigne: (id, data) => api.patch(`/installations/colis-lignes/${id}/`, data),
  deleteColisLigne: (id) => api.delete(`/installations/colis-lignes/${id}/`),

  // ── XSTK2 — Logistique : livraisons, transporteurs, tournée, POD,
  // comptages cycliques, demandes de transfert ──

  // FG329 — livraisons planifiées (dépôt/direct site → chantier). Cycle :
  // planifiée → en transit (`expedier`) → livrée (`livrer`) / annulée (`annuler`).
  getLivraisons: (params) => api.get('/installations/livraisons/', { params }),
  getLivraison: (id) => api.get(`/installations/livraisons/${id}/`),
  createLivraison: (data) => api.post('/installations/livraisons/', data),
  updateLivraison: (id, data) => api.patch(`/installations/livraisons/${id}/`, data),
  deleteLivraison: (id) => api.delete(`/installations/livraisons/${id}/`),
  expedierLivraison: (id) => api.post(`/installations/livraisons/${id}/expedier/`, {}),
  livrerLivraison: (id) => api.post(`/installations/livraisons/${id}/livrer/`, {}),
  annulerLivraison: (id) => api.post(`/installations/livraisons/${id}/annuler/`, {}),

  // FG329 — lignes de livraison (SKU + quantité).
  getLivraisonLignes: (params) => api.get('/installations/livraison-lignes/', { params }),
  createLivraisonLigne: (data) => api.post('/installations/livraison-lignes/', data),
  updateLivraisonLigne: (id, data) => api.patch(`/installations/livraison-lignes/${id}/`, data),
  deleteLivraisonLigne: (id) => api.delete(`/installations/livraison-lignes/${id}/`),

  // FG331 — transporteurs (interne/tiers) + tarif de base (INTERNE, jamais
  // affiché client). Filtrable par `active`.
  getTransporteurs: (params) => api.get('/installations/transporteurs/', { params }),
  createTransporteur: (data) => api.post('/installations/transporteurs/', data),
  updateTransporteur: (id, data) => api.patch(`/installations/transporteurs/${id}/`, data),
  deleteTransporteur: (id) => api.delete(`/installations/transporteurs/${id}/`),

  // FG332 — tournée de livraison proposée pour un jour (lecture seule,
  // consultative — n'exécute rien). `jour` = 'YYYY-MM-DD' requis.
  getTourneeLivraison: (jour, { departLat, departLng } = {}) =>
    api.get('/installations/tournee-livraison/', {
      params: {
        jour,
        ...(departLat != null ? { depart_lat: departLat } : {}),
        ...(departLng != null ? { depart_lng: departLng } : {}),
      },
    }),

  // FG330 — preuve de livraison (POD) : signature + photo + GPS horodaté.
  // Une seule preuve par livraison (OneToOne côté serveur). La signature est
  // une data-URL PNG (canvas) ; la photo passe par `recordsApi.uploadAttachment`
  // puis son id est posé sur `photo`.
  getPreuvesLivraison: (params) => api.get('/installations/preuves-livraison/', { params }),
  getPreuveLivraison: (id) => api.get(`/installations/preuves-livraison/${id}/`),
  createPreuveLivraison: (data) => api.post('/installations/preuves-livraison/', data),
  updatePreuveLivraison: (id, data) => api.patch(`/installations/preuves-livraison/${id}/`, data),

  // FG324 — sessions de comptage tournant (cycle count ABC), DISTINCTES des
  // `inventaire-sessions` one-shot (stockApi, câblées par WR5). Cycle :
  // planifié → en cours (`demarrer`) → terminé (`terminer`, poste l'écart
  // constaté en ajustement de stock, idempotent).
  getSessionsComptage: (params) => api.get('/installations/sessions-comptage/', { params }),
  getSessionComptage: (id) => api.get(`/installations/sessions-comptage/${id}/`),
  createSessionComptage: (data) => api.post('/installations/sessions-comptage/', data),
  updateSessionComptage: (id, data) => api.patch(`/installations/sessions-comptage/${id}/`, data),
  ajouterLigneComptage: (id, produitId) =>
    api.post(`/installations/sessions-comptage/${id}/ajouter-ligne/`, { produit: produitId }),
  demarrerComptage: (id) => api.post(`/installations/sessions-comptage/${id}/demarrer/`, {}),
  terminerComptage: (id) => api.post(`/installations/sessions-comptage/${id}/terminer/`, {}),

  // FG324 — lignes de comptage (saisie de `quantite_comptee` / `compte`).
  getComptageLignes: (params) => api.get('/installations/comptage-lignes/', { params }),
  updateComptageLigne: (id, data) => api.patch(`/installations/comptage-lignes/${id}/`, data),

  // FG325 — demandes de transfert inter-emplacements. Cycle : demandé →
  // approuvé (`approuver`) / refusé (`refuser`) → exécuté (`executer`, poste
  // RÉELLEMENT le mouvement de stock ; 409 si source insuffisante).
  getDemandesTransfert: (params) => api.get('/installations/demandes-transfert/', { params }),
  getDemandeTransfert: (id) => api.get(`/installations/demandes-transfert/${id}/`),
  createDemandeTransfert: (data) => api.post('/installations/demandes-transfert/', data),
  updateDemandeTransfert: (id, data) => api.patch(`/installations/demandes-transfert/${id}/`, data),
  approuverDemandeTransfert: (id) =>
    api.post(`/installations/demandes-transfert/${id}/approuver/`, {}),
  refuserDemandeTransfert: (id, motifRefus) =>
    api.post(`/installations/demandes-transfert/${id}/refuser/`,
      motifRefus ? { motif_refus: motifRefus } : {}),
  executerDemandeTransfert: (id) =>
    api.post(`/installations/demandes-transfert/${id}/executer/`, {}),

  // FG310 — demandes d'achat (réquisitions chantier) → approbation. Cycle :
  // brouillon → soumise (`soumettre`) → approuvée (`approuver`) / refusée
  // (`refuser`) → commandée (`marquer-commandee` / `generer-bcf`). Les lignes
  // ont leur propre endpoint (la réponse demande expose `lignes` en lecture
  // seule) ; référence/société/created_by sont posées côté serveur.
  getDemandesAchat: (params) => api.get('/installations/demandes-achat/', { params }),
  getDemandeAchat: (id) => api.get(`/installations/demandes-achat/${id}/`),
  createDemandeAchat: (data) => api.post('/installations/demandes-achat/', data),
  updateDemandeAchat: (id, data) => api.patch(`/installations/demandes-achat/${id}/`, data),
  deleteDemandeAchat: (id) => api.delete(`/installations/demandes-achat/${id}/`),
  soumettreDemandeAchat: (id) =>
    api.post(`/installations/demandes-achat/${id}/soumettre/`, {}),
  approuverDemandeAchat: (id) =>
    api.post(`/installations/demandes-achat/${id}/approuver/`, {}),
  refuserDemandeAchat: (id, motifRefus) =>
    api.post(`/installations/demandes-achat/${id}/refuser/`,
      motifRefus ? { motif_refus: motifRefus } : {}),
  createDemandeAchatLigne: (data) =>
    api.post('/installations/demandes-achat-lignes/', data),
  deleteDemandeAchatLigne: (id) =>
    api.delete(`/installations/demandes-achat-lignes/${id}/`),

  // ── XMFG1-16 — Atelier MRP-lite : ordres d'assemblage / démontage (kitting) ──

  // FG328 — ordres d'assemblage (kits → composite). Référence/société posées
  // serveur ; le statut avance via demarrer/terminer/annuler. Filtrable par
  // `statut`, `kit`, `responsable`, `date_prevue`.
  getOrdresAssemblage: (params) =>
    api.get('/installations/ordres-assemblage/', { params }),
  getOrdreAssemblage: (id) => api.get(`/installations/ordres-assemblage/${id}/`),
  createOrdreAssemblage: (data) =>
    api.post('/installations/ordres-assemblage/', data),
  updateOrdreAssemblage: (id, data) =>
    api.patch(`/installations/ordres-assemblage/${id}/`, data),
  deleteOrdreAssemblage: (id) =>
    api.delete(`/installations/ordres-assemblage/${id}/`),
  // XMFG2 — disponibilité par ligne de composant (réservation-aware).
  getDisponibiliteAssemblage: (id) =>
    api.get(`/installations/ordres-assemblage/${id}/disponibilite/`),
  // FG328/XMFG2 — passe l'ordre en cours (backflush différé à la clôture).
  demarrerAssemblage: (id) =>
    api.post(`/installations/ordres-assemblage/${id}/demarrer/`, {}),
  // FG328/XMFG1 — clôture + backflush stock. `quantite_produite`, emplacements,
  // forçage QC (`forcer`+`motif_forcage`) éditables au moment de la clôture.
  terminerAssemblage: (id, data) =>
    api.post(`/installations/ordres-assemblage/${id}/terminer/`, data ?? {}),
  // XMFG4 — annulation motivée (refusée si stock déjà mouvementé).
  annulerAssemblage: (id, motif) =>
    api.post(`/installations/ordres-assemblage/${id}/annuler/`,
      { motif_annulation: motif }),
  // XMFG4 — chatter de l'ordre (logs auto + notes).
  getHistoriqueAssemblage: (id) =>
    api.get(`/installations/ordres-assemblage/${id}/historique/`),
  noterAssemblage: (id, body) =>
    api.post(`/installations/ordres-assemblage/${id}/noter/`, { body }),
  // XMFG13 — checklist QC de l'ordre (gate de clôture).
  getControleQualiteAssemblage: (id) =>
    api.get(`/installations/ordres-assemblage/${id}/controle-qualite/`),
  enregistrerControleQualiteAssemblage: (id, itemModeleId, payload) =>
    api.post(
      `/installations/ordres-assemblage/${id}/controle-qualite/${itemModeleId}/`,
      payload),
  // XMFG14 — gamme d'exécution (étapes) de l'ordre.
  getEtapesAssemblage: (id) =>
    api.get(`/installations/ordres-assemblage/${id}/etapes/`),
  cocherEtapeAssemblage: (id, etapeModeleId, payload) =>
    api.post(
      `/installations/ordres-assemblage/${id}/etapes/${etapeModeleId}/cocher/`,
      payload),
  // ZMFG10 — bon d'assemblage PDF (worksheet atelier, aucun prix).
  bonAssemblageUrl: (id) =>
    `/api/django/installations/ordres-assemblage/${id}/bon-pdf/`,

  // XMFG6 — lignes de composant personnalisables (éditables tant que planifié).
  getLignesAssemblage: (ordreId) =>
    api.get('/installations/ordre-assemblage-lignes/', { params: { ordre: ordreId } }),
  createLigneAssemblage: (data) =>
    api.post('/installations/ordre-assemblage-lignes/', data),
  updateLigneAssemblage: (id, data) =>
    api.patch(`/installations/ordre-assemblage-lignes/${id}/`, data),
  deleteLigneAssemblage: (id) =>
    api.delete(`/installations/ordre-assemblage-lignes/${id}/`),

  // WIR248/XMFG11 — rebut de production rattaché à un ordre (SORTIE typée
  // REBUT, motivée) + mini-rapport agrégé par produit sur une période. Les
  // deux actions serveur existaient sans aucun consommateur.
  declarerRebutAssemblage: (id, data) =>
    api.post(`/installations/ordres-assemblage/${id}/declarer-rebut/`, data),
  getRapportRebuts: (params) =>
    api.get('/installations/ordres-assemblage/rapport-rebuts/', { params }),

  // XMFG12 — ordres de démontage (unbuild) : composite → composants.
  getOrdresDemontage: (params) =>
    api.get('/installations/ordres-demontage/', { params }),
  getOrdreDemontage: (id) => api.get(`/installations/ordres-demontage/${id}/`),
  createOrdreDemontage: (data) =>
    api.post('/installations/ordres-demontage/', data),
  updateOrdreDemontage: (id, data) =>
    api.patch(`/installations/ordres-demontage/${id}/`, data),
  deleteOrdreDemontage: (id) =>
    api.delete(`/installations/ordres-demontage/${id}/`),
  // XMFG12 — clôture : sort le composite, restocke les composants récupérés.
  terminerDemontage: (id) =>
    api.post(`/installations/ordres-demontage/${id}/terminer/`, {}),

  // XMFG12 — lignes de démontage (quantité récupérée éditable avant clôture).
  updateLigneDemontage: (id, data) =>
    api.patch(`/installations/ordre-demontage-lignes/${id}/`, data),

  // FG328 — kits d'assemblage (en-tête + nomenclature) : source des ordres.
  // Filtrable par `active`.
  getKitsAssemblage: (params) => api.get('/installations/kits/', { params }),

  // XMFG5 — nomenclature indentée + disponibilité d'un kit produit (stock app).
  getKitStructure: (kitId) => api.get(`/stock/kits/${kitId}/structure/`),

  // WIR110 — approvisionnement avancé (consultation lecture seule) : les 6
  // familles d'endpoints FG310-318 qui n'avaient aucun écran.
  getSeuilsApprobationBcf: (params) =>
    api.get('/installations/seuils-approbation-bcf/', { params }),
  getApprobationsBcf: (params) =>
    api.get('/installations/approbations-bcf/', { params }),
  getCommandesCadre: (params) =>
    api.get('/installations/commandes-cadre/', { params }),
  getAppelsCommande: (params) =>
    api.get('/installations/appels-commande/', { params }),
  getContratsPrixFournisseur: (params) =>
    api.get('/installations/contrats-prix-fournisseur/', { params }),
  getReceptionsNonFacturees: (params) =>
    api.get('/installations/receptions-non-facturees/', { params }),

  // WIR114 — astreintes (FG302), indisponibilités ressource (FG302) et
  // récurrences d'intervention (ZFSM3). Société/created_by posés serveur.
  getAstreintes: (params) => api.get('/installations/astreintes/', { params }),
  createAstreinte: (data) => api.post('/installations/astreintes/', data),
  deleteAstreinte: (id) => api.delete(`/installations/astreintes/${id}/`),
  getIndisponibilites: (params) =>
    api.get('/installations/indisponibilites-ressource/', { params }),
  createIndisponibilite: (data) =>
    api.post('/installations/indisponibilites-ressource/', data),
  deleteIndisponibilite: (id) =>
    api.delete(`/installations/indisponibilites-ressource/${id}/`),
  getRecurrencesIntervention: (params) =>
    api.get('/installations/recurrences-intervention/', { params }),
  createRecurrenceIntervention: (data) =>
    api.post('/installations/recurrences-intervention/', data),
  deleteRecurrenceIntervention: (id) =>
    api.delete(`/installations/recurrences-intervention/${id}/`),

  // WIR114 — ZFSM3 : modèles de fiche d'intervention + leurs champs (Paramètres).
  getFicheTemplates: (params) =>
    api.get('/installations/fiche-intervention-templates/', { params }),
  saveFicheTemplate: (id, data) => id
    ? api.patch(`/installations/fiche-intervention-templates/${id}/`, data)
    : api.post('/installations/fiche-intervention-templates/', data),
  deleteFicheTemplate: (id) =>
    api.delete(`/installations/fiche-intervention-templates/${id}/`),
  saveFicheChamp: (id, data) => id
    ? api.patch(`/installations/fiche-intervention-champs/${id}/`, data)
    : api.post('/installations/fiche-intervention-champs/', data),
  deleteFicheChamp: (id) =>
    api.delete(`/installations/fiche-intervention-champs/${id}/`),

  // WIR112 — équipes terrain canoniques (DC40). CRUD depuis Paramètres ;
  // `membres` (M2M utilisateurs) + `chef` optionnel. Société posée serveur.
  getEquipesTerrain: (params) => api.get('/installations/equipes/', { params }),
  saveEquipeTerrain: (id, data) => id
    ? api.patch(`/installations/equipes/${id}/`, data)
    : api.post('/installations/equipes/', data),
  deleteEquipeTerrain: (id) => api.delete(`/installations/equipes/${id}/`),

  // WIR113 — suivi GPS terrain (XFSM23), web-first. Consentement explicite
  // AVANT toute position : `positions-techniciens/ping/` refuse (403) sans
  // consentement actif. Les positions et les alertes de géofence sont en
  // LECTURE SEULE côté API (jamais de PATCH), leurs seules mutations passent
  // par les actions dédiées `revoquer` / `acquitter`.
  getGpsConsentements: (params) =>
    api.get('/installations/gps-consentements/', { params }),
  createGpsConsentement: (data) =>
    api.post('/installations/gps-consentements/', data),
  revoquerGpsConsentement: (id, reason) =>
    api.post(`/installations/gps-consentements/${id}/revoquer/`,
      reason ? { reason } : {}),
  getPositionsTechniciens: (params) =>
    api.get('/installations/positions-techniciens/', { params }),
  getCarteLivePositions: () =>
    api.get('/installations/positions-techniciens/carte-live/'),
  getGeofenceAlertes: (params) =>
    api.get('/installations/geofence-alertes/', { params }),
  acquitterGeofenceAlerte: (id) =>
    api.post(`/installations/geofence-alertes/${id}/acquitter/`, {}),

  // ── PACT55 — Sous-traitance chantier : annuaire (FG304), ordres de travaux
  // (FG305), factures/paiements en façade sur la chaîne AP standard (DC34,
  // FG306), attestations obligatoires (FG307), évaluations (FG308) et
  // retenues de garantie (FG309). Montants sous-traitant INTERNES uniquement.
  getSousTraitants: (params) => api.get('/installations/sous-traitants/', { params }),
  getSousTraitant: (id) => api.get(`/installations/sous-traitants/${id}/`),
  createSousTraitant: (data) => api.post('/installations/sous-traitants/', data),
  updateSousTraitant: (id, data) => api.patch(`/installations/sous-traitants/${id}/`, data),

  getOrdresSousTraitance: (params) =>
    api.get('/installations/ordres-sous-traitance/', { params }),
  createOrdreSousTraitance: (data) =>
    api.post('/installations/ordres-sous-traitance/', data),
  emettreOrdreSousTraitance: (id) =>
    api.post(`/installations/ordres-sous-traitance/${id}/emettre/`, {}),
  receptionnerOrdreSousTraitance: (id, montantRealise) =>
    api.post(`/installations/ordres-sous-traitance/${id}/receptionner/`,
      montantRealise != null && montantRealise !== ''
        ? { montant_realise: montantRealise } : {}),
  cloturerOrdreSousTraitance: (id) =>
    api.post(`/installations/ordres-sous-traitance/${id}/cloturer/`, {}),

  getFacturesSousTraitant: (params) =>
    api.get('/installations/factures-sous-traitant/', { params }),
  createFactureSousTraitant: (data) =>
    api.post('/installations/factures-sous-traitant/', data),
  annulerFactureSousTraitant: (id) =>
    api.post(`/installations/factures-sous-traitant/${id}/annuler/`, {}),

  getPaiementsSousTraitant: (params) =>
    api.get('/installations/paiements-sous-traitant/', { params }),
  createPaiementSousTraitant: (data) =>
    api.post('/installations/paiements-sous-traitant/', data),
  deletePaiementSousTraitant: (id) =>
    api.delete(`/installations/paiements-sous-traitant/${id}/`),

  getAttestationsSousTraitant: (params) =>
    api.get('/installations/attestations-sous-traitant/', { params }),
  createAttestationSousTraitant: (data) =>
    api.post('/installations/attestations-sous-traitant/', data),
  getAffectabiliteSousTraitant: (sousTraitantId, dateStr) =>
    api.get('/installations/attestations-sous-traitant/affectabilite/',
      { params: dateStr
        ? { sous_traitant: sousTraitantId, date: dateStr }
        : { sous_traitant: sousTraitantId } }),

  getEvaluationsSousTraitant: (params) =>
    api.get('/installations/evaluations-sous-traitant/', { params }),
  createEvaluationSousTraitant: (data) =>
    api.post('/installations/evaluations-sous-traitant/', data),
  getScorecardSousTraitant: (sousTraitantId) =>
    api.get('/installations/evaluations-sous-traitant/scorecard/',
      { params: { sous_traitant: sousTraitantId } }),

  getRetenuesGarantieSousTraitant: (params) =>
    api.get('/installations/retenues-garantie-sous-traitant/', { params }),
  createRetenueGarantieSousTraitant: (data) =>
    api.post('/installations/retenues-garantie-sous-traitant/', data),
  leverRetenueGarantieSousTraitant: (id) =>
    api.post(`/installations/retenues-garantie-sous-traitant/${id}/lever/`, {}),

  // ── PACT56 — Import et douane : dossiers d'import (FG315), frais et coût de
  // revient débarqué (FG316). Donnée interne, jamais montrée au client. ──
  getDossiersImport: (params) => api.get('/installations/dossiers-import/', { params }),
  getDossierImport: (id) => api.get(`/installations/dossiers-import/${id}/`),
  createDossierImport: (data) => api.post('/installations/dossiers-import/', data),
  updateDossierImport: (id, data) => api.patch(`/installations/dossiers-import/${id}/`, data),
  avancerDossierImport: (id, statutDouane) =>
    api.post(`/installations/dossiers-import/${id}/avancer/`,
      statutDouane ? { statut_douane: statutDouane } : {}),
  getLandedCostDossier: (id) =>
    api.get(`/installations/dossiers-import/${id}/landed-cost/`),
  appliquerCoutStockDossier: (id) =>
    api.post(`/installations/dossiers-import/${id}/appliquer-cout-stock/`, {}),

  getFraisImport: (params) => api.get('/installations/frais-import/', { params }),
  createFraisImport: (data) => api.post('/installations/frais-import/', data),
  deleteFraisImport: (id) => api.delete(`/installations/frais-import/${id}/`),

  getLandedCostLignes: (params) => api.get('/installations/landed-cost-lignes/', { params }),
  createLandedCostLigne: (data) => api.post('/installations/landed-cost-lignes/', data),
  deleteLandedCostLigne: (id) => api.delete(`/installations/landed-cost-lignes/${id}/`),

  // ── PACT57 — Prix négociés fournisseurs : écriture des commandes-cadres
  // (FG314) et contrats de prix (FG318) + leurs lignes. `getCommandesCadre`/
  // `getContratsPrixFournisseur` (lecture) existent déjà (WIR110). ──
  createCommandeCadre: (data) => api.post('/installations/commandes-cadre/', data),
  updateCommandeCadre: (id, data) => api.patch(`/installations/commandes-cadre/${id}/`, data),
  activerCommandeCadre: (id) => api.post(`/installations/commandes-cadre/${id}/activer/`, {}),
  cloturerCommandeCadre: (id) => api.post(`/installations/commandes-cadre/${id}/cloturer/`, {}),
  getCommandeCadreLignes: (params) =>
    api.get('/installations/commandes-cadre-lignes/', { params }),
  createCommandeCadreLigne: (data) =>
    api.post('/installations/commandes-cadre-lignes/', data),
  updateCommandeCadreLigne: (id, data) =>
    api.patch(`/installations/commandes-cadre-lignes/${id}/`, data),
  deleteCommandeCadreLigne: (id) =>
    api.delete(`/installations/commandes-cadre-lignes/${id}/`),

  createContratPrixFournisseur: (data) =>
    api.post('/installations/contrats-prix-fournisseur/', data),
  updateContratPrixFournisseur: (id, data) =>
    api.patch(`/installations/contrats-prix-fournisseur/${id}/`, data),
  activerContratPrixFournisseur: (id) =>
    api.post(`/installations/contrats-prix-fournisseur/${id}/activer/`, {}),
  expirerContratPrixFournisseur: (id) =>
    api.post(`/installations/contrats-prix-fournisseur/${id}/expirer/`, {}),
  getContratPrixLignes: (params) =>
    api.get('/installations/contrats-prix-lignes/', { params }),
  createContratPrixLigne: (data) =>
    api.post('/installations/contrats-prix-lignes/', data),
  updateContratPrixLigne: (id, data) =>
    api.patch(`/installations/contrats-prix-lignes/${id}/`, data),
  deleteContratPrixLigne: (id) =>
    api.delete(`/installations/contrats-prix-lignes/${id}/`),

  // ── PACT58 — Contrôle documentaire de projet : registre (FG297) et
  // révisions (indice/date/auteur/fichier) d'un document technique. ──
  getDocumentsProjet: (params) => api.get('/installations/documents-projet/', { params }),
  createDocumentProjet: (data) => api.post('/installations/documents-projet/', data),
  updateDocumentProjet: (id, data) => api.patch(`/installations/documents-projet/${id}/`, data),
  deleteDocumentProjet: (id) => api.delete(`/installations/documents-projet/${id}/`),

  getRevisionsDocument: (params) => api.get('/installations/revisions-document/', { params }),
  createRevisionDocument: (data) => api.post('/installations/revisions-document/', data),

  // ── PACT59 — Suivi projet du chantier : jalons (FG293), modèles de projet
  // (FG296) et comptes-rendus de réunion de chantier (FG298). ──
  getJalonsProjet: (params) => api.get('/installations/jalons-projet/', { params }),
  createJalonProjet: (data) => api.post('/installations/jalons-projet/', data),
  updateJalonProjet: (id, data) => api.patch(`/installations/jalons-projet/${id}/`, data),
  deleteJalonProjet: (id) => api.delete(`/installations/jalons-projet/${id}/`),

  getModelesProjet: (params) => api.get('/installations/modeles-projet/', { params }),
  createModeleProjet: (data) => api.post('/installations/modeles-projet/', data),
  instancierModeleProjet: (id, installationId) =>
    api.post(`/installations/modeles-projet/${id}/instancier/`,
      { installation: installationId }),

  getReunionsChantier: (params) => api.get('/installations/reunions-chantier/', { params }),
  createReunionChantier: (data) => api.post('/installations/reunions-chantier/', data),

  // ── PACT60 — Consultation fournisseurs et comparatif d'offres (FG311,
  // XPUR20/21). `offres`/`consultations`/`comparatif` sont imbriqués en
  // lecture dans chaque RFQ (aucun fetch séparé nécessaire pour comparer). ──
  getRFQs: (params) => api.get('/installations/rfq/', { params }),
  getRFQ: (id) => api.get(`/installations/rfq/${id}/`),
  createRFQ: (data) => api.post('/installations/rfq/', data),
  envoyerRFQ: (id) => api.post(`/installations/rfq/${id}/envoyer/`, {}),
  cloturerRFQ: (id) => api.post(`/installations/rfq/${id}/cloturer/`, {}),
  retenirOffreRFQ: (id, offreId) =>
    api.post(`/installations/rfq/${id}/retenir/`, { offre: offreId }),
  consulterFournisseurRFQ: (id, fournisseurId) =>
    api.post(`/installations/rfq/${id}/consulter/`, { fournisseur: fournisseurId }),
  envoyerConsultationsRFQ: (id, consultationIds) =>
    api.post(`/installations/rfq/${id}/envoyer-consultations/`,
      consultationIds ? { consultations: consultationIds } : {}),
  relancerNonRepondantsRFQ: (id) =>
    api.post(`/installations/rfq/${id}/relancer-non-repondants/`, {}),

  createRFQOffre: (data) => api.post('/installations/rfq-offres/', data),

  getRFQConsultations: (params) => api.get('/installations/rfq-consultations/', { params }),

  // ── PACT61 — Paramétrage des kits d'assemblage : le kit lui-même (FG328),
  // sa nomenclature (composants), sa gamme d'étapes (XMFG14) et son modèle
  // de contrôle qualité (XMFG13). L'Atelier existant ne fait que SÉLECTIONNER
  // un kit déjà créé — cette capacité manquait en amont. ──
  createKit: (data) => api.post('/installations/kits/', data),
  updateKit: (id, data) => api.patch(`/installations/kits/${id}/`, data),

  getKitComposants: (params) => api.get('/installations/kit-composants/', { params }),
  createKitComposant: (data) => api.post('/installations/kit-composants/', data),
  updateKitComposant: (id, data) => api.patch(`/installations/kit-composants/${id}/`, data),
  deleteKitComposant: (id) => api.delete(`/installations/kit-composants/${id}/`),

  // Gamme d'étapes du KIT (mode opératoire, XMFG14) — distinct de
  // `getEtapesAssemblage(ordreId)` qui lit la gamme INSTANCIÉE d'un ordre.
  getEtapesAssemblageKit: (params) => api.get('/installations/etapes-assemblage/', { params }),
  createEtapeAssemblageKit: (data) => api.post('/installations/etapes-assemblage/', data),
  updateEtapeAssemblageKit: (id, data) => api.patch(`/installations/etapes-assemblage/${id}/`, data),
  deleteEtapeAssemblageKit: (id) => api.delete(`/installations/etapes-assemblage/${id}/`),

  getControleQualiteModeles: (params) =>
    api.get('/installations/controle-qualite-modeles/', { params }),
  createControleQualiteModele: (data) =>
    api.post('/installations/controle-qualite-modeles/', data),
  updateControleQualiteModele: (id, data) =>
    api.patch(`/installations/controle-qualite-modeles/${id}/`, data),
}

/* ============================================================================
   WIR215/XPUR21 — Réponse fournisseur PUBLIQUE à une demande de prix (RFQ),
   sans login, résolue par le token de consultation. Le lien WhatsApp/email
   envoyé au fournisseur pointait jusqu'ici sur cet endpoint JSON : le
   fournisseur recevait un objet brut au lieu d'un formulaire.
   Le POST est IDEMPOTENT tant que la RFQ n'est pas clôturée (il crée l'offre
   puis la met à jour) ; un token invalide/expiré/révoqué renvoie 404 — jamais
   403, pour ne pas confirmer l'existence d'un token à un tiers.
   ========================================================================== */
export const rfqPublicApi = {
  get: (token) =>
    api.get(`/public/installations/rfq/${encodeURIComponent(token)}/`),
  repondre: (token, data) =>
    api.post(`/public/installations/rfq/${encodeURIComponent(token)}/`, data),
}

export default installationsApi
