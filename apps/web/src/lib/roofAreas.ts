/**
 * Agrégation PURE de plusieurs « zones de panneaux » de toiture.
 *
 * L'estimateur 3D pro-11 laisse l'utilisateur tracer plusieurs zones (chaque pan
 * de toit ou portion utile) ; chacune est dimensionnée par l'optimiseur existant
 * (best-fit), puis ajustable au panneau près. Ce module ne fait que sommer les
 * résultats par zone — aucune dépendance au DOM, à Three.js ni à la carte.
 *
 * Les TOTAUX additionnent panels/kwc/annualKwh simplement sur toutes les zones non
 * nulles. Les ÉCONOMIES ne sont PAS sommées zone par zone : chaque zone résout
 * indépendamment contre la MÊME facture globale (pas une part par zone), donc son
 * `savingsLow/High` est DÉJÀ plafonné au coût évitable de TOUTE la facture — sommer
 * N zones peut afficher jusqu'à N× l'économie maximale réelle (WB20). On calcule
 * donc UNE seule fois l'économie plafonnée à partir du kWh produit TOTAL et de la
 * cible annuelle (facture) globale, via `savingsFn` injecté par l'appelant (garde ce
 * module pur — aucune dépendance directe à estimatorBrainV2).
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
 * Somme panels/kwc/annualKwh sur toutes les zones non nulles. Les `null` (zone vide
 * / non calculée) sont ignorés ; une liste vide ou tout-null renvoie un résultat à
 * zéro.
 *
 * Les économies ne sont JAMAIS sommées zone par zone (WB20) : chaque zone plafonne
 * déjà sa propre économie contre TOUTE la facture (même cible globale, dupliquée par
 * zone), donc l'addition sur-compte jusqu'à N× sur un toit à N zones. On recalcule
 * ici UNE seule économie plafonnée à partir de la production TOTALE et de
 * `targetAnnualKwh` (kWh/an de la facture globale, ex. `Recommendation.targetAnnualKwh`
 * / `PitchedRecommendation.targetAnnualKwh`), via `savingsFn` (typiquement
 * `annualSavingsMad` de `estimatorBrainV2` — injecté pour garder ce module pur, sans
 * dépendance directe).
 *
 * Si `targetAnnualKwh`/`savingsFn` sont omis (cible pas encore connue), on retombe
 * sur la somme brute — mêmes limites qu'avant, mais l'appelant courant (zones.ts)
 * fournit toujours la cible dès qu'une zone a un résultat.
 */
export function aggregateAreas(
  results: (AreaResult | null)[],
  targetAnnualKwh?: number,
  savingsFn?: (productionKwhYr: number, consumptionKwhYr: number) => { low: number; high: number },
): AreaResult {
  const total = emptyResult();
  for (const r of results) {
    if (!r) continue;
    total.panels += r.panels;
    total.kwc += r.kwc;
    total.annualKwh += r.annualKwh;
    total.savingsLow += r.savingsLow;
    total.savingsHigh += r.savingsHigh;
  }
  if (targetAnnualKwh != null && targetAnnualKwh > 0 && savingsFn) {
    const savings = savingsFn(total.annualKwh, targetAnnualKwh);
    total.savingsLow = savings.low;
    total.savingsHigh = savings.high;
  }
  return total;
}

/** Libellé d'affichage d'une zone (0-based) : « Zone 1 », « Zone 2 », … */
export function areaLabel(index: number): string {
  return `Zone ${index + 1}`;
}
