/* Types d'équipement d'une catégorie / d'un produit — alignés sur
   stock.Categorie.TypeEquipement (backend). `__none` = sentinelle d'écran
   (« Non typée »), jamais envoyée telle quelle. Source unique des écrans
   Catégories et Produit (jamais recopiée). */
// source-choix: stock.Categorie.type_equipement +__none
export const TYPES_EQUIPEMENT = [
  { value: '__none', label: '— Non typée —' },
  { value: 'panneau', label: 'Panneau' },
  { value: 'onduleur', label: 'Onduleur' },
  { value: 'batterie', label: 'Batterie' },
  { value: 'structure', label: 'Structure' },
  { value: 'cable', label: 'Câble' },
  { value: 'protection', label: 'Protection' },
  { value: 'pompe', label: 'Pompe' },
  { value: 'variateur', label: 'Variateur' },
  { value: 'compteur', label: 'Compteur' },
  { value: 'accessoire', label: 'Accessoire' },
  // STKCAT2 — « Services & prestations » n'est pas un équipement : sans cette
  // valeur, la catégorie restait NULL (indistinguable d'une non typée).
  { value: 'service', label: 'Service' },
]
