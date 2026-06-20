import api from './axios'

const stockApi = {
  // Produits
  getProduits: (params) => api.get('/stock/produits/', { params }),
  getProduit: (id) => api.get(`/stock/produits/${id}/`),
  createProduit: (data) => api.post('/stock/produits/', data),
  updateProduit: (id, data) => api.patch(`/stock/produits/${id}/`, data),
  patchProduit: (id, data) => api.patch(`/stock/produits/${id}/`, data),
  deleteProduit: (id) => api.delete(`/stock/produits/${id}/`),
  getProduitsArchived: () => api.get('/stock/produits/', { params: { show_archived: 'true' } }),
  unarchiveProduit: (id) => api.patch(`/stock/produits/${id}/unarchive/`),
  forceDeleteProduit: (id) => api.delete(`/stock/produits/${id}/force-delete/`),

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
  recevoirBcf: (id, receptions) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/recevoir/`, { receptions }),
  annulerBcf: (id) =>
    api.post(`/stock/bons-commande-fournisseur/${id}/annuler/`),
  bcfPdf: (id) =>
    api.get(`/stock/bons-commande-fournisseur/${id}/pdf/`, { responseType: 'blob' }),

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
}

export default stockApi
