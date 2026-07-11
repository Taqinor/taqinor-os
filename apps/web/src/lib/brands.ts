/**
 * Source unique de vérité des MARQUES tier-1 réellement utilisées / distribuées
 * par Taqinor (liste confirmée par le fondateur). INTÉGRITÉ : noms + catégorie
 * de marque uniquement — aucun numéro de modèle, référence ou spec n'est
 * inventé ici.
 *
 * `logo` pointe vers un fichier sous `/public/` (ex. '/brands/jinko.png') ou
 * vaut `null` tant qu'aucun fichier logo officiel n'est disponible ; dans ce
 * cas un word-mark stylisé est rendu à la place.
 *
 * W187 (2026-07-11) — logos officiels déposés dans `public/brands/`, sourcés
 * depuis les seuls hôtes d'assets atteignables (Wikimedia + raw.githubusercontent) :
 *   - Huawei / Nexans / JA Solar : SVG officiel (Wikimedia Commons)
 *   - Jinko : PNG domaine public (Wikimedia Commons)
 *   - Canadian Solar : PNG logo officiel (Wikipedia EN, usage nominatif)
 *   - Deye : PNG (Wikimedia Commons, CC BY-SA 4.0 — attribution dans
 *     `public/brands/CREDITS.md` ; identité confirmée : fichier utilisé sur
 *     l'article Deye de Wikipédia DE + Wikidata)
 * Seul **Dyness** n'a AUCUN asset atteignable : absent de Wikimedia / Wikidata /
 * GitHub ; ses seules sources (dyness.com, brandfetch) sont bloquées par la
 * liste blanche réseau de l'environnement. Il reste `null` / word-mark plutôt
 * qu'un logo fabriqué (règle « aucun contenu inventé »). Sources & licences :
 * voir `public/brands/CREDITS.md`.
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
  { name: 'Canadian Solar', category: 'Panneaux',   logo: '/brands/canadian-solar.png', heightMultiplier: 1.1 },
  { name: 'JA Solar',       category: 'Panneaux',   logo: '/brands/ja-solar.svg',       heightMultiplier: 1.0 },
  { name: 'Jinko',          category: 'Panneaux',   logo: '/brands/jinko.png',          heightMultiplier: 1.0 },
  { name: 'Deye',           category: 'Onduleurs',  logo: '/brands/deye.png',           heightMultiplier: 0.85 },
  { name: 'Huawei',         category: 'Onduleurs',  logo: '/brands/huawei.svg',         heightMultiplier: 0.95 },
  { name: 'Dyness',         category: 'Batteries',  logo: null,                         heightMultiplier: 1.0 },
  { name: 'Nexans',         category: 'Câbles',     logo: '/brands/nexans.svg',         heightMultiplier: 0.9 },
];
