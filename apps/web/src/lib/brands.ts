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
 *
 * W183 — `heightMultiplier` : facteur optique pour égaliser la hauteur visuelle
 * des logos dans la bande (certains logos sont hauts et fins, d'autres larges et
 * bas). 1.0 = hauteur de référence (2rem). Absent = 1.0.
 * Valeurs calibrées à l'œil sur les word-marks actuels (taille de fonte 1.25rem–
 * 1.5rem) — à ajuster une fois les vrais SVG déposés.
 */

export interface Brand {
  name: string;
  category: string;
  logo: string | null;
  /** W183 — Multiplicateur de hauteur optique [0.7 – 1.4]. Défaut : 1. */
  heightMultiplier?: number;
}

export const BRANDS: Brand[] = [
  { name: 'Canadian Solar', category: 'Panneaux',   logo: null, heightMultiplier: 1.1 },
  { name: 'JA Solar',       category: 'Panneaux',   logo: null, heightMultiplier: 1.0 },
  { name: 'Jinko',          category: 'Panneaux',   logo: null, heightMultiplier: 0.9 },
  { name: 'Deye',           category: 'Onduleurs',  logo: null, heightMultiplier: 0.85 },
  { name: 'Huawei',         category: 'Onduleurs',  logo: null, heightMultiplier: 0.95 },
  { name: 'Dyness',         category: 'Batteries',  logo: null, heightMultiplier: 1.0 },
  { name: 'Nexans',         category: 'Câbles',     logo: null, heightMultiplier: 0.9 },
];
