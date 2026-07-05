import api from './axios'

/* XPOS2 — Écran caisse (vente rapide, /pos).
   ----------------------------------------------------------------------------
   Aucun endpoint POS dédié n'existe côté backend : ce client compose sur les
   endpoints EXISTANTS déjà consommés ailleurs dans l'appli — jamais de code
   backend ajouté depuis cette lane (frontend-only).

   - Recherche produit + stock dispo (N14 `quantite_disponible`) : réutilise
     GET /stock/produits/ (stockApi.getProduits) — voir features/pos/pos.js.
   - Client optionnel + quick-create : POST /crm/clients/ (pattern QG3/QC1,
     cf. ClientQuickCreateModal + companyLookup).
   - Encaissement : une vente comptoir devient une Facture (client requis côté
     modèle, apps/ventes/models.py Facture.client) —
       1) POST /ventes/factures/            (en-tête : client, taux_tva…)
       2) POST /ventes/factures-lignes/     (une par ligne du panier)
       3) POST /ventes/factures/<id>/enregistrer-paiement/  (mode + montant)
       4) POST /ventes/factures/<id>/emettre/               (pose officiellement)
   GAP notée : il n'existe pas de endpoint POS "one-shot" (facture + lignes +
   paiement en un seul appel) — cette lane enchaîne les 4 appels ci-dessus côté
   client. Un futur XPOS backend pourrait les fusionner serveur-side.
   - Impression du ticket (XPOS3) : PAS ENCORE CONSTRUITE — bouton "Imprimer"
     stubé sur window.print() (voir CaisseScreen), à remplacer par le futur
     rendu de ticket dédié quand XPOS3 arrive. */
const posApi = {
  // Recherche produit instantanée (nom/SKU/référence) + stock dispo. On
  // réutilise l'endpoint catalogue existant ; le filtrage texte se fait
  // côté client (features/pos/pos.js:searchCatalogueForPos), le même
  // découpage que ProduitPicker (features/stock/catalogue.js).
  getProduits: (params) => api.get('/stock/produits/', { params }),

  // Client optionnel : recherche (autocomplete QC1) + création rapide (QG3).
  searchClients: (q) => api.get('/crm/clients/search/', { params: { q } }),
  createClient: (data) => api.post('/crm/clients/', data),

  // Encaissement — enchaîne Facture (en-tête) → lignes → paiement → émission.
  createFacture: (data) => api.post('/ventes/factures/', data),
  createLigneFacture: (data) => api.post('/ventes/factures-lignes/', data),
  enregistrerPaiement: (factureId, data) =>
    api.post(`/ventes/factures/${factureId}/enregistrer-paiement/`, data),
  emettreFacture: (factureId) =>
    api.post(`/ventes/factures/${factureId}/emettre/`),
  getFacture: (factureId) => api.get(`/ventes/factures/${factureId}/`),
}

export default posApi
