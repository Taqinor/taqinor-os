/**
 * Source unique de vérité des MARQUES tier-1 réellement utilisées / distribuées
 * par Taqinor (liste confirmée par le fondateur). INTÉGRITÉ : noms + catégorie
 * de marque uniquement — aucun numéro de modèle, référence ou spec n'est
 * inventé ici.
 *
 * `logo` pointe vers un fichier sous `/public/` (ex. '/brands/jinko.svg') ou
 * vaut `null` tant qu'aucun fichier logo n'existe. Les logos officiels seront
 * déposés dans `public/brands/` plus tard ; jusque-là, des word-marks stylisés
 * sont rendus à la place.
 */

export interface Brand {
  name: string;
  category: string;
  logo: string | null;
}

export const BRANDS: Brand[] = [
  { name: 'Canadian Solar', category: 'Panneaux', logo: null },
  { name: 'JA Solar', category: 'Panneaux', logo: null },
  { name: 'Jinko', category: 'Panneaux', logo: null },
  { name: 'Deye', category: 'Onduleurs', logo: null },
  { name: 'Huawei', category: 'Onduleurs', logo: null },
  { name: 'Dyness', category: 'Batteries', logo: null },
  { name: 'Nexans', category: 'Câbles', logo: null },
];
