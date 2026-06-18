/**
 * Logique PURE de la FENÊTRE « Production estimée » (W50) — l'écran Année / Mois / Jour
 * de l'estimateur toiture pro-11. Tout ici est testable HORS DOM et HORS réseau : la
 * sélection de série selon le scope, le cyclage mois/jour, la mise à l'échelle par le
 * nombre de panneaux (kWc), le plafonnement honnête des économies, le formatage FR, et
 * la GÉOMÉTRIE des graphes (barres mensuelles, courbe horaire 24 h, barres journalières).
 *
 * Le moteur de DONNÉES (W49, productionEngine.ts) est CONSOMMÉ tel quel : on reçoit une
 * `ScaledProduction` (annuel + 12 mensuels + jours types + totaux journaliers) déjà mise
 * à l'échelle par le serveur, et un éventuel `SpecificDateProfile` (date précise). Le
 * rescale CLIENT (édition du nombre de panneaux) est PUREMENT linéaire en kWc (la
 * production PVGIS est linéaire) → aucun appel serveur supplémentaire pour un simple
 * changement de comptage.
 *
 * AUCUN chiffre d'économies n'est inventé : on réutilise le modèle d'autoconsommation
 * plafonné (annualSavingsMad d'estimatorBrainV2) — jamais production × tarif non plafonné.
 */
import {
  DAYS_IN_MONTH,
  MONTH_LABELS_FR,
  scaleByKwc,
  scaleDateProfile,
  type ScaledProduction,
  type SpecificDateProfile,
  type PerKwcProduction,
} from './productionEngine';
import { annualSavingsMad } from './estimatorBrainV2';

export type ProductionScope = 'year' | 'month' | 'day';

/** Source de production telle que renvoyée par /api/roof-production. */
export type ProductionSource = 'pvgis' | 'pvgis-monthly' | 'estimate';

/** Étiquettes longues FR des mois (pour les titres « Production de mars »). */
export const MONTH_NAMES_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** Étiquettes mensuelles courtes (réexport pour le rendu — index 0 = janvier). */
export { MONTH_LABELS_FR, DAYS_IN_MONTH };

// — Formatage FR (espace fine comme séparateur de milliers, unité après) ——————

const NF0 = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
const NF1 = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });

/** Entier formaté FR (séparateur de milliers = espace). */
export function fmtInt(n: number): string {
  return NF0.format(Number.isFinite(n) ? Math.round(n) : 0);
}

/** kWh affichés : entier + unité (« 12 480 kWh »). « ~ » optionnel pour le côté indicatif. */
export function fmtKwh(n: number, approx = false): string {
  const v = Number.isFinite(n) && n > 0 ? n : 0;
  return `${approx ? '~' : ''}${fmtInt(v)} kWh`;
}

/** kWc affichés (1 décimale, « 8,6 kWc »). */
export function fmtKwc(n: number): string {
  const v = Number.isFinite(n) && n > 0 ? n : 0;
  return `${NF1.format(v)} kWc`;
}

/** Fourchette d'économies MAD/an, plafonnée (« 9 200 – 11 800 MAD »). */
export function fmtSavings(low: number, high: number): string {
  return `${fmtInt(low)} – ${fmtInt(high)} MAD`;
}

/** Étiquette de source pour l'UI : « PVGIS » fiable vs « estimé » (PVGIS injoignable). */
export function sourceLabel(source: ProductionSource): string {
  if (source === 'pvgis') return 'PVGIS · GPS exact';
  if (source === 'pvgis-monthly') return 'PVGIS (mensuel) · GPS exact';
  return 'estimé · PVGIS indisponible';
}

/** Vrai si la production est un repli interne (figures à étiqueter « estimé »). */
export function isEstimate(source: ProductionSource): boolean {
  return source === 'estimate';
}

// — Cyclage mois / jour ————————————————————————————————————————————————

/** Index de mois suivant/précédent, wrap circulaire 0↔11. `dir` = +1 ou −1. */
export function cycleMonth(month: number, dir: number): number {
  const m = ((Math.trunc(month) % 12) + 12) % 12;
  return ((m + Math.sign(dir) + 12) % 12);
}

/** Nombre de jours d'un mois (index 0 = janvier), borné. */
export function daysInMonth(monthIndex: number): number {
  const m = ((Math.trunc(monthIndex) % 12) + 12) % 12;
  return DAYS_IN_MONTH[m];
}

/**
 * Jour suivant/précédent À L'INTÉRIEUR du mois courant (wrap 1↔derniersJour). Le mois ne
 * change pas : la fenêtre Jour cycle les jours du mois sélectionné. `day` 1-based.
 */
export function cycleDay(monthIndex: number, day: number, dir: number): number {
  const last = daysInMonth(monthIndex);
  const d0 = (Math.trunc(day) - 1 + last) % last; // 0-based, borné
  const next = (d0 + Math.sign(dir) + last) % last;
  return next + 1; // re-1-based
}

// — Rescale CLIENT par nombre de panneaux (linéaire, sans appel serveur) ————————

/**
 * Met une production PAR 1 kWc (gardée côté client à partir de la réponse serveur) à
 * l'échelle d'un nouveau nombre de panneaux. PUREMENT linéaire (scaleByKwc). Sert quand
 * l'utilisateur édite le comptage : on ne refait PAS d'appel /api/roof-production.
 */
export function rescaleByPanels(perKwc: PerKwcProduction, panels: number, panelKwc: number): ScaledProduction {
  const kwc = Math.max(0, (Number.isFinite(panels) ? panels : 0) * panelKwc);
  return scaleByKwc(perKwc, kwc);
}

/** Rescale d'un profil de date précise par un nouveau nombre de panneaux (linéaire). */
export function rescaleDateByPanels(
  perKwcDate: SpecificDateProfile,
  panels: number,
  panelKwc: number,
): SpecificDateProfile {
  const kwc = Math.max(0, (Number.isFinite(panels) ? panels : 0) * panelKwc);
  return scaleDateProfile(perKwcDate, kwc);
}

// — Sélection de série selon le scope ————————————————————————————————————

/** Une barre nommée (label + valeur kWh) pour un graphe à barres. */
export interface NamedBar {
  label: string;
  kwh: number;
}

/**
 * Année : 12 barres mensuelles (kWh/mois) + total annuel. Le total RENVOYÉ est
 * `annualKwh` (l'ancre PVcalc), pas la somme des barres — les deux coïncident par
 * construction du moteur, mais on garde l'ancre pour la cohérence d'affichage.
 */
export function yearSeries(prod: ScaledProduction): { bars: NamedBar[]; totalKwh: number } {
  const bars = prod.monthlyKwh.map((kwh, i) => ({ label: MONTH_LABELS_FR[i], kwh: Math.max(0, kwh) }));
  return { bars, totalKwh: Math.max(0, prod.annualKwh) };
}

/**
 * Mois : ~N barres journalières (chaque jour du mois = même total journalier moyen, le
 * jour-type est une moyenne) + total mensuel. Le total journalier moyen × jours du mois
 * = total mensuel (cohérence garantie par le moteur). Les barres sont étiquetées 1..N.
 */
export function monthSeries(prod: ScaledProduction, monthIndex: number): { bars: NamedBar[]; totalKwh: number } {
  const m = ((Math.trunc(monthIndex) % 12) + 12) % 12;
  const days = DAYS_IN_MONTH[m];
  const dailyAvg = Math.max(0, prod.dailyKwhByMonth[m]);
  const bars: NamedBar[] = Array.from({ length: days }, (_, i) => ({ label: String(i + 1), kwh: dailyAvg }));
  return { bars, totalKwh: Math.max(0, prod.monthlyKwh[m]) };
}

/** Un point horaire (heure 0–23 + puissance kW). */
export interface HourPoint {
  hour: number;
  kw: number;
}

/**
 * Jour : 24 points de PUISSANCE (kW) + total journalier (kWh). Source du profil :
 *  - une DATE précise fournie (SpecificDateProfile) → ce profil ;
 *  - sinon le JOUR-TYPE du mois sélectionné (moyenne du mois).
 * L'énergie (kWh) = somme des puissances horaires (pas horaire 1 h).
 */
export function daySeries(
  prod: ScaledProduction,
  monthIndex: number,
  specificDate: SpecificDateProfile | null,
): { points: HourPoint[]; totalKwh: number; isTypical: boolean } {
  if (specificDate && Array.isArray(specificDate.hourlyKw) && specificDate.hourlyKw.length === 24) {
    const points = specificDate.hourlyKw.map((kw, h) => ({ hour: h, kw: Math.max(0, kw) }));
    return { points, totalKwh: Math.max(0, specificDate.dailyKwh), isTypical: false };
  }
  const m = ((Math.trunc(monthIndex) % 12) + 12) % 12;
  const profile = prod.typicalDayByMonth[m] ?? new Array<number>(24).fill(0);
  const points = profile.map((kw, h) => ({ hour: h, kw: Math.max(0, kw) }));
  const totalKwh = points.reduce((a, p) => a + p.kw, 0);
  return { points, totalKwh: Math.max(0, totalKwh), isTypical: true };
}

// — Économies honnêtes plafonnées (réutilise le modèle existant) ————————————

/**
 * Économies MENSUELLES plafonnées (MAD) pour un mois donné : on dérive la conso mensuelle
 * de la cible annuelle (target/12 ×) et on plafonne via annualSavingsMad sur 1/12 d'année.
 * JAMAIS production × tarif non plafonné — l'autoconsommation alignée borne l'économie.
 */
export function monthlySavings(monthlyKwh: number, annualTargetKwh: number): { low: number; high: number } {
  // annualSavingsMad raisonne en annuel ; pour un mois on lui passe ×12 puis on /12.
  const yr = annualSavingsMad(Math.max(0, monthlyKwh) * 12, Math.max(0, annualTargetKwh));
  return { low: yr.low / 12, high: yr.high / 12 };
}

/**
 * Économies JOURNALIÈRES plafonnées (MAD) : même principe, ramené à l'échelle d'un jour
 * (×365 puis /365). Plafond d'autoconsommation conservé — jamais de chiffre inventé.
 */
export function dailySavings(dailyKwh: number, annualTargetKwh: number): { low: number; high: number } {
  const yr = annualSavingsMad(Math.max(0, dailyKwh) * 365, Math.max(0, annualTargetKwh));
  return { low: yr.low / 365, high: yr.high / 365 };
}

/** Économies ANNUELLES plafonnées (MAD) — passe-plat direct vers le modèle existant. */
export function annualSavings(annualKwh: number, annualTargetKwh: number): { low: number; high: number } {
  return annualSavingsMad(Math.max(0, annualKwh), Math.max(0, annualTargetKwh));
}

// — Géométrie des graphes (SVG inline, hand-built, sans librairie) ————————————

export interface SvgBox {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}

const DEFAULT_BOX: SvgBox = { width: 320, height: 140, padLeft: 6, padRight: 6, padTop: 8, padBottom: 18 };

/** Rectangle d'une barre (coordonnées SVG) dans un graphe à barres. */
export interface BarRect {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  kwh: number;
}

/**
 * Géométrie de barres uniformément réparties dans la zone de tracé. La barre la plus haute
 * occupe toute la hauteur utile ; les autres sont proportionnelles. `gapRatio` = part de
 * l'espacement entre barres (0–0.9). Toutes les valeurs ≤ 0 → barres de hauteur 0 (pas de
 * NaN). Déterministe → testable au pixel.
 */
export function barGeometry(bars: NamedBar[], box: SvgBox = DEFAULT_BOX, gapRatio = 0.2): BarRect[] {
  const n = bars.length;
  if (n <= 0) return [];
  const plotW = box.width - box.padLeft - box.padRight;
  const plotH = box.height - box.padTop - box.padBottom;
  const max = bars.reduce((m, b) => Math.max(m, b.kwh), 0);
  const slot = plotW / n;
  const g = Math.max(0, Math.min(0.9, gapRatio));
  const barW = slot * (1 - g);
  return bars.map((b, i) => {
    const h = max > 0 ? (Math.max(0, b.kwh) / max) * plotH : 0;
    const x = box.padLeft + i * slot + (slot - barW) / 2;
    const y = box.padTop + (plotH - h);
    return { x, y, width: barW, height: h, label: b.label, kwh: b.kwh };
  });
}

/**
 * Chemin SVG (« M … L … ») d'une courbe horaire 24 points sur la largeur du graphe.
 * L'axe X couvre 0–23 h, l'axe Y la puissance (0 = bas). Pic à 0 → ligne plate en bas.
 * Renvoie une chaîne vide si la série n'a pas 24 points (garde défensive).
 */
export function dayCurvePath(points: HourPoint[], box: SvgBox = DEFAULT_BOX): string {
  if (!Array.isArray(points) || points.length !== 24) return '';
  const plotW = box.width - box.padLeft - box.padRight;
  const plotH = box.height - box.padTop - box.padBottom;
  const max = points.reduce((m, p) => Math.max(m, p.kw), 0);
  const xAt = (h: number) => box.padLeft + (h / 23) * plotW;
  const yAt = (kw: number) => box.padTop + (plotH - (max > 0 ? (kw / max) * plotH : 0));
  let d = '';
  points.forEach((p, i) => {
    d += `${i === 0 ? 'M' : 'L'}${xAt(p.hour).toFixed(2)} ${yAt(p.kw).toFixed(2)}`;
    if (i < points.length - 1) d += ' ';
  });
  return d;
}

/** Aire remplie sous la courbe horaire (ferme le chemin sur la ligne de base). */
export function dayAreaPath(points: HourPoint[], box: SvgBox = DEFAULT_BOX): string {
  const line = dayCurvePath(points, box);
  if (!line) return '';
  const plotW = box.width - box.padLeft - box.padRight;
  const baseY = box.height - box.padBottom;
  const rightX = box.padLeft + plotW;
  return `${line} L${rightX.toFixed(2)} ${baseY.toFixed(2)} L${box.padLeft.toFixed(2)} ${baseY.toFixed(2)} Z`;
}

export { DEFAULT_BOX as DEFAULT_GRAPH_BOX };
