/**
 * SOURCE UNIQUE DE VÉRITÉ des durées et seuils de GARANTIE publiés sur
 * taqinor.ma (même discipline que `STAGES.py` côté ERP pour les stages, ou
 * `fiches.ts` pour les fiches techniques).
 *
 * POURQUOI CE FICHIER : la valeur « 84,8 % / 25 ans » (ancien barème PERC) s'est
 * propagée dans 25+ fichiers précisément parce qu'aucune constante n'existait.
 * Toute page/composant/fiche qui affiche une garantie DOIT dériver sa valeur
 * d'ici plutôt que de re-coder un littéral, pour qu'une correction se fasse en
 * un seul endroit.
 *
 * ADJUDICATION DES CHIFFRES (2026-07-04, vérifiée contre les fiches PDF liées) :
 *
 *  PANNEAUX (les deux modules N-type TOPCon réellement liés dans `fiches.ts`) :
 *   - Garantie PRODUIT : 12 ans.
 *   - Garantie de PERFORMANCE : LINÉAIRE sur 30 ans, ≥ 87,4 % de la puissance
 *     initiale à 30 ans (année 1 ≤ 1 %, puis ≤ 0,4 %/an → ≥ 89,4 % à 25 ans).
 *   Sources :
 *   - Canadian Solar TOPBiHiKu7 CS7N-TB-AG, datasheet v1.62C3 (N-type TOPCon,
 *     garantie linéaire 30 ans / ≥ 87,4 % à 30 ans).
 *   - Jinko Tiger Neo JKM710-735N-66HL5-BDV (N-type TOPCon, garantie linéaire
 *     30 ans / ≥ 87,4 % à 30 ans).
 *   L'ancien « ≥ 84,8 % / 25 ans » est le barème PERC : il n'apparaît sur
 *   AUCUNE des fiches liées et ne doit plus être affiché.
 *
 *  ONDULEURS : 10 ans (Deye SUN-…-SG05LP, Huawei SUN2000).
 *   O1 (2026-08-20) — sourcé contre les documents officiels constructeur :
 *   - Huawei : datasheet SUN2000-5/8/10KTL-M0/M1 (le lien `datasheet` de la
 *     fiche `onduleur-huawei-reseau`) — garantie constructeur 120 mois.
 *   - Deye : « SUN Series Hybrid inverter 10-Year Limited Warranty for
 *     Installation in Europe » (deyeinverter.com) — couvre TOUTE la gamme
 *     SUN Series Hybrid, 10 ans SI le site d'installation est en Europe ; la
 *     datasheet technique SG05LP3/SG05LP1 elle-même écrit « 5 Years/10 Years
 *     — the Warranty Period Depends the Final Installation Site ». Le Maroc
 *     n'étant pas couvert nommément, 10 ans reste la valeur affichée (celle
 *     du document constructeur le plus favorable et déjà utilisée partout),
 *     mais le terme exact pour une installation marocaine reste À CONFIRMER
 *     contre le certificat du distributeur (cf. la note structurée de la
 *     fiche `onduleur-deye-hybride` dans fiches.ts, qui porte cette réserve).
 *
 *  BATTERIE : 10 ans, ≥ 70 % de capacité (Dyness DL5.0C LFP).
 *   NB (WA13, sourcé O1 2026-08-20) : la garantie Dyness DL5.0C est VERSIONNÉE
 *   par région — documents officiels dyness.com trouvés : version Europe
 *   « DL5.0C ESS System » = 10 ans ; version Amériques « DL5.0C Pro ESS
 *   System » (WarrantyTermsDL5.0CPro…pdf, V2-202502) = 7 ans avec rétention
 *   ≥ 70 % de l'énergie utilisable à 7 ans ; version Asie-Pacifique propose
 *   les DEUX (7 ans ou 10 ans selon le palier acheté). Aucun document n'est
 *   spécifique au Maroc : 10 ans reste la valeur affichée (comme l'onduleur
 *   ci-dessus), 7 ans documenté comme variante régionale possible. Le seuil
 *   ≥ 70 % vient du document Amériques (70 % de l'Usable Energy à 7 ans) —
 *   c'est la seule valeur de seuil trouvée dans un document officiel Dyness,
 *   appliquée ici par défaut faute d'un seuil publié pour la version 10 ans.
 *
 *  STRUCTURE (acier galvanisé) : 20 ans.
 *  POSE / main-d'œuvre Taqinor : 2 ans.
 */

/** Garantie PRODUIT des panneaux (défauts de fabrication), en années. */
export const PANEL_PRODUCT_WARRANTY_YEARS = 12;

/** Durée de la garantie de PERFORMANCE (linéaire) des panneaux, en années. */
export const PANEL_PERFORMANCE_WARRANTY_YEARS = 30;

/** Seuil de puissance garanti au terme de la garantie de performance (30 ans). */
export const PANEL_PERFORMANCE_FLOOR_PCT = 87.4;

/** Perte de puissance garantie la première année (plafond), en %. */
export const PANEL_FIRST_YEAR_DEGRADATION_PCT = 1;

/** Perte de puissance garantie par an après la 1ʳᵉ année (plafond), en %/an. */
export const PANEL_ANNUAL_DEGRADATION_PCT = 0.4;

/**
 * Seuil de puissance garanti DÉRIVÉ à 25 ans, à partir du barème
 * ≤ 1 % (an 1) puis ≤ 0,4 %/an : 100 − 1 − 0,4×24 = 89,4 %.
 */
export const PANEL_PERFORMANCE_FLOOR_25Y_PCT = 89.4;

/** Garantie onduleur, en années — Deye/Huawei, source en tête de fichier (O1). */
export const INVERTER_WARRANTY_YEARS = 10;

/** Garantie batterie (durée), en années. */
export const BATTERY_WARRANTY_YEARS = 10;

/** Seuil de capacité garanti de la batterie au terme, en %. */
export const BATTERY_CAPACITY_FLOOR_PCT = 70;

/** Garantie structure (acier galvanisé), en années. */
export const STRUCTURE_WARRANTY_YEARS = 20;

/** Garantie pose / main-d'œuvre Taqinor, en années. */
export const INSTALL_WARRANTY_YEARS = 2;

/**
 * Formatage des seuils de % à la française (virgule décimale) — pour l'affichage
 * FR/AR ; l'anglais utilise le point (voir `pctEn`).
 */
export function pctFr(value: number): string {
  return String(value).replace('.', ',');
}

/** Formatage des seuils de % à l'anglaise (point décimal). */
export function pctEn(value: number): string {
  return String(value).replace(',', '.');
}

/** Libellé FR de la performance panneau, ex. « ≥ 87,4 % ». */
export const PANEL_PERFORMANCE_FLOOR_FR = `≥ ${pctFr(PANEL_PERFORMANCE_FLOOR_PCT)} %`;

/** Libellé EN de la performance panneau, ex. « ≥ 87.4 % ». */
export const PANEL_PERFORMANCE_FLOOR_EN = `≥ ${pctEn(PANEL_PERFORMANCE_FLOOR_PCT)} %`;
