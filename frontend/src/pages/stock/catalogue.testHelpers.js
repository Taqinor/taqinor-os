/* Fixtures partagées des tests Catalogue/Stock (ENF19). */

/** Champs communs d'un produit de test ; chaque test y ajoute sa catégorie. */
export const produitStockBase = {
  id: 1,
  nom: 'Panneau 550 Wc',
  sku: 'PAN-550',
  marque: 'JA Solar',
  prix_vente: '1000',
  prix_achat: '700',
  tva: 20,
  quantite_stock: 12,
  quantite_reservee: 0,
  quantite_disponible: 12,
  seuil_alerte: 5,
  is_low_stock: false,
  is_archived: false,
}

const noop = () => {}

/** Props de base de <CatalogueTable> (droits d'écriture + gestionnaires inertes). */
export const propsCatalogueBase = {
  loading: false,
  canWrite: true,
  canDelete: true,
  onEdit: noop,
  onDelete: noop,
  onHistorique: noop,
  onReapprovisionner: noop,
}
