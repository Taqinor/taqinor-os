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
  getMaTournee: (date) =>
    api.get('/installations/interventions/ma-tournee/',
      { params: date ? { date } : undefined }),

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
}

export default installationsApi
