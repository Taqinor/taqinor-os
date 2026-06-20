/**
 * Agrégation PURE de plusieurs « zones de panneaux » de toiture.
 *
 * L'estimateur 3D pro-11 laisse l'utilisateur tracer plusieurs zones (chaque pan
 * de toit ou portion utile) ; chacune est dimensionnée par l'optimiseur existant
 * (best-fit), puis ajustable au panneau près. Ce module ne fait que sommer les
 * résultats par zone — aucune dépendance au DOM, à Three.js ni à la carte.
 *
 * Les TOTAUX additionnent simplement chaque champ sur toutes les zones non nulles.
 * Les économies sont SOMMÉES (jamais re-plafonnées globalement) : chaque zone porte
 * déjà ses économies plafonnées à sa propre part de facture, et l'addition reflète
 * fidèlement « toutes les zones ensemble » telle que l'utilisateur les a posées.
 *
 * Pur → entièrement testé (tests/roofAreas.test.ts).
 */

/** Résultat chiffré d'UNE zone (instantané du gagnant de l'optimiseur). */
export interface AreaResult {
  panels: number;
  kwc: number;
  annualKwh: number;
  savingsLow: number;
  savingsHigh: number;
}

/** Résultat vide (zéro partout) — zone non encore calculée. */
export function emptyResult(): AreaResult {
  return { panels: 0, kwc: 0, annualKwh: 0, savingsLow: 0, savingsHigh: 0 };
}

/**
 * Somme chaque champ sur toutes les zones non nulles. Les `null` (zone vide / non
 * calculée) sont ignorés ; une liste vide ou tout-null renvoie un résultat à zéro.
 */
export function aggregateAreas(results: (AreaResult | null)[]): AreaResult {
  const total = emptyResult();
  for (const r of results) {
    if (!r) continue;
    total.panels += r.panels;
    total.kwc += r.kwc;
    total.annualKwh += r.annualKwh;
    total.savingsLow += r.savingsLow;
    total.savingsHigh += r.savingsHigh;
  }
  return total;
}

/** Libellé d'affichage d'une zone (0-based) : « Zone 1 », « Zone 2 », … */
export function areaLabel(index: number): string {
  return `Zone ${index + 1}`;
}
