/**
 * WJ120 — Simulateur « et avec N batteries ? » de la proposition client.
 *
 * MOTEUR HORAIRE GLOUTON, PUR et testable (aucun DOM, aucun réseau, aucune
 * dépendance) : il oppose, heure par heure, une courbe de CONSOMMATION (silhouette
 * de `proposalCurve.consumptionProfile`, mise à l'échelle du kWh journalier RÉEL du
 * client) à une courbe de PRODUCTION solaire (`proposalCurve.solarProfile`, mise à
 * l'échelle de la production estimée du système), et répartit chaque kWh :
 *   • DIRECT  = min(prod, conso) : le solaire couvre d'abord ce qui est consommé
 *               à cet instant (jamais du stockage inutile).
 *   • SURPLUS (prod > conso) → charge la batterie (rendement one-way ≈0,96), le
 *               reste est exporté/perdu (valorisé à ZÉRO — pas de net-billing BT
 *               clair au Maroc, conservateur, cohérent avec applianceConsumption).
 *   • DÉFICIT (conso > prod) ← batterie d'abord (décharge, rendement one-way), puis
 *               réseau pour le reste.
 *
 * « JOUR 2 SIMULÉ POUR ÉVITER LE BIAIS DE SoC INITIAL » : on déroule la boucle 24 h
 * DEUX fois en reportant l'état de charge (SoC) du jour 1 dans le jour 2, et on ne
 * rapporte QUE le jour 2 (régime permanent). Sinon un jour 1 démarrant batterie vide
 * sous-estimerait l'autoconsommation du matin (aucune énergie stockée la veille).
 *
 * DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » : ce module ne fabrique AUCUN prix. Les seules
 * constantes chiffrées sont des CONSTANTES PHYSIQUES documentées (rendement, DoD,
 * capacité catalogue) — chacune porte un commentaire de source. La capacité par
 * unité vient STRICTEMENT des références catalogue Deyness 5/10 kWh (jamais d'une
 * valeur inventée). Le prix batterie est lu du devis par la page, jamais ici.
 */
import type { ProposalItem } from './proposition';

/** 24 heures dans une journée — taille de toutes les courbes horaires. */
export const HOURS_PER_DAY = 24;

// ── Constantes physiques (chacune SOURCÉE) ───────────────────────────────────

/**
 * Rendement ONE-WAY d'une batterie LFP (lithium fer phosphate) ≈ 0,96 : appliqué
 * UNE fois à la charge et UNE fois à la décharge → rendement ALLER-RETOUR ≈ 0,92
 * (0,96² ≈ 0,9216), l'ordre de grandeur publié pour un pack LFP + onduleur-chargeur
 * moderne (systèmes résidentiels Deye/Deyness). Conservateur : les pertes réelles
 * dépendent du courant et de la température. Réglable ici.
 */
export const BATTERY_ONE_WAY_EFFICIENCY = 0.96;

/**
 * Profondeur de décharge (DoD) LFP retenue = 0,90. Le lithium LFP tolère 90-95 % de
 * DoD sans dégradation notable (contre ~50 % au plomb) ; on retient 0,90 (borne
 * BASSE de la fourchette 90-95 %) — choix PRUDENT : la capacité utile affichée est
 * plutôt sous-estimée que sur-promise. Réglable ici.
 */
export const BATTERY_DEPTH_OF_DISCHARGE = 0.9;

/**
 * Capacité catalogue par UNITÉ (kWh) — RÉFÉRENCES RÉELLES du catalogue Deyness :
 *   BAT-DEY-5  → 5 kWh   ·   BAT-DEY-10 → 10 kWh.
 *
 * ⚠ NE JAMAIS confondre avec `applianceConsumption.BATTERY_KWH_PER_DAY` (= 6) :
 *   ce dernier est une CONSOMMATION journalière couvrable (kWh/JOUR décalés du
 *   surplus vers le soir), PAS une capacité de STOCKAGE (kWh). Ce sont deux
 *   grandeurs physiques DIFFÉRENTES — la capacité par unité vient TOUJOURS des réfs
 *   5/10 ci-dessus, JAMAIS du 6. (Le `?? 5.0` de frontend solar.js:503 est encore
 *   une AUTRE chose — une capacité/unité par défaut côté générateur — à ne pas
 *   « réconcilier » avec ce 6 non plus.)
 */
export const DEYNESS_CAPACITY_KWH: Readonly<Record<string, number>> = {
  'BAT-DEY-5': 5,
  'BAT-DEY-10': 10,
};

/** Capacité par défaut du curseur quand l'offre ne porte pas de batterie : l'unité
 *  de base Deyness (BAT-DEY-5 = 5 kWh). Toujours une réf catalogue, jamais inventée. */
export const DEFAULT_UNIT_CAPACITY_KWH = DEYNESS_CAPACITY_KWH['BAT-DEY-5'];

/**
 * Puissance MOYENNE des CHARGES ESSENTIELLES (W) — utilisée UNIQUEMENT pour estimer
 * les « heures de secours » (autonomie sur coupure réseau). C'est une ESTIMATION
 * d'un SOUS-ENSEMBLE essentiel documenté, JAMAIS toute la maison :
 *   • réfrigérateur : ≈ 60 W en MOYENNE (compresseur cyclé ~25-30 % d'une plaque
 *     signalétique ~200 W — cf. applianceConsumption `frigo`)
 *   • éclairage LED essentiel (quelques points) : ≈ 100 W
 *   • box internet / routeur : ≈ 20-40 W
 * Somme ≈ 180-200 W ; on retient 200 W (marge PRUDENTE → heures de secours plutôt
 * SOUS-estimées que sur-promises). À confirmer, APPLIANCES_NOTES.md. Réglable ici.
 */
export const ESSENTIAL_LOAD_W = 200;

// ── Types ────────────────────────────────────────────────────────────────────

/** Le bilan énergétique d'UNE journée (kWh), côté conso ET côté production. */
export interface DailyEnergy {
  /** kWh consommés couverts DIRECTEMENT par le solaire (min(prod, conso) horaire). */
  directKwh: number;
  /** kWh consommés couverts par la BATTERIE (décharge). */
  fromBatteryKwh: number;
  /** kWh consommés importés du RÉSEAU (déficit non couvert). */
  fromGridKwh: number;
  /** kWh de production EXPORTÉS/perdus (surplus non stocké). */
  exportedKwh: number;
  /** kWh de production prélevés du surplus pour CHARGER la batterie (avant pertes). */
  solarToBatteryKwh: number;
  /** Total consommé sur la journée (kWh). */
  consumptionKwh: number;
  /** Total produit sur la journée (kWh). */
  productionKwh: number;
}

/** Découpage HORAIRE (24 valeurs) de la consommation servie — pour l'aire empilée. */
export interface HourlySplit {
  direct: number[];
  battery: number[];
  grid: number[];
}

export interface BatterySimInput {
  /** Silhouette horaire de consommation (24 poids ≥ 0, échelle libre). */
  consumptionShape: number[];
  /** Silhouette horaire de production solaire (24 poids ≥ 0, échelle libre). */
  productionShape: number[];
  /** Consommation journalière RÉELLE du client (kWh/jour) — met à l'échelle la conso. */
  dailyConsumptionKwh: number;
  /** Production journalière estimée du système (kWh/jour) — met à l'échelle le solaire. */
  dailyProductionKwh: number;
  /** Capacité par unité (kWh) — RÉF catalogue (5 ou 10), jamais inventée. */
  capacityKwhPerUnit: number;
  /** Nombre d'unités batterie (le curseur : 0, 1, 2, 3…). */
  units: number;
  /** Rendement one-way (défaut BATTERY_ONE_WAY_EFFICIENCY). */
  oneWayEfficiency?: number;
  /** Profondeur de décharge (défaut BATTERY_DEPTH_OF_DISCHARGE). */
  depthOfDischarge?: number;
  /** Puissance des charges essentielles (W, défaut ESSENTIAL_LOAD_W). */
  essentialLoadW?: number;
}

export interface BatterySimResult extends DailyEnergy {
  /**
   * TAUX D'AUTOCONSOMMATION (%) = part de la PRODUCTION solaire réellement utilisée
   * sur place (directement OU stockée pour plus tard) plutôt qu'exportée :
   *   selfConsommation = (direct + solaire→batterie) / production = 1 − exporté/production.
   * Grandeur côté PRODUCTION (« combien de ce que je PRODUIS je garde »).
   */
  selfConsumptionPct: number;
  /**
   * TAUX D'AUTOSUFFISANCE (%) = part de la CONSOMMATION couverte par le solaire
   * (directement OU via la batterie) plutôt que par le réseau :
   *   autosuffisance = (direct + batterie) / consommation.
   * Grandeur côté CONSOMMATION (« combien de ce que je CONSOMME vient du solaire »).
   * DISTINCTE de l'autoconsommation ci-dessus — libellés et formules différents.
   */
  selfSufficiencyPct: number;
  /** Heures d'autonomie sur charges ESSENTIELLES (frigo + éclairage + box), batterie pleine. */
  backupHours: number;
  /** Capacité UTILE totale du parc (kWh) = units × capacité/unité × DoD. */
  usableCapacityKwh: number;
  /** Découpage horaire du JOUR 2 (régime permanent) — pour l'aire empilée. */
  hourly: HourlySplit;
  /** Bilan du JOUR 1 (démarré batterie VIDE) — exposé pour prouver le biais de SoC. */
  day1: DailyEnergy;
}

// ── Mise à l'échelle des silhouettes ─────────────────────────────────────────

/**
 * Met une silhouette de 24 poids (échelle libre ≥ 0) à l'échelle d'un total
 * journalier (kWh) : renvoie 24 valeurs kWh sommant EXACTEMENT à `dailyKwh`. Une
 * silhouette de somme nulle, un total ≤ 0 ou une taille ≠ 24 → 24 zéros (jamais NaN,
 * jamais d'énergie fabriquée).
 */
export function scaleShapeToDaily(shape: number[], dailyKwh: number): number[] {
  const out = new Array<number>(HOURS_PER_DAY).fill(0);
  if (!Array.isArray(shape) || shape.length !== HOURS_PER_DAY) return out;
  const total = Number.isFinite(dailyKwh) && dailyKwh > 0 ? dailyKwh : 0;
  if (total <= 0) return out;
  let sum = 0;
  for (const w of shape) sum += Number.isFinite(w) && w > 0 ? w : 0;
  if (sum <= 0) return out;
  for (let h = 0; h < HOURS_PER_DAY; h++) {
    const w = Number.isFinite(shape[h]) && shape[h] > 0 ? shape[h] : 0;
    out[h] = (total * w) / sum;
  }
  return out;
}

// ── Moteur horaire glouton ───────────────────────────────────────────────────

interface DayRun {
  energy: DailyEnergy;
  hourly: HourlySplit;
  socEnd: number;
}

/**
 * Déroule UNE journée de 24 h à partir d'un état de charge initial `socStart` (kWh
 * DANS les cellules). Renvoie le bilan énergétique de la journée, le découpage
 * horaire de la conso servie, et le SoC de fin (à reporter au lendemain).
 */
function runDay(
  consKwh: number[],
  prodKwh: number[],
  usableCap: number,
  etaCharge: number,
  etaDischarge: number,
  socStart: number,
): DayRun {
  let soc = Math.max(0, Math.min(usableCap, socStart));
  let directKwh = 0;
  let fromBatteryKwh = 0;
  let fromGridKwh = 0;
  let exportedKwh = 0;
  let solarToBatteryKwh = 0;
  let consumptionKwh = 0;
  let productionKwh = 0;
  const hDirect = new Array<number>(HOURS_PER_DAY).fill(0);
  const hBattery = new Array<number>(HOURS_PER_DAY).fill(0);
  const hGrid = new Array<number>(HOURS_PER_DAY).fill(0);

  for (let h = 0; h < HOURS_PER_DAY; h++) {
    const c = Number.isFinite(consKwh[h]) && consKwh[h] > 0 ? consKwh[h] : 0;
    const p = Number.isFinite(prodKwh[h]) && prodKwh[h] > 0 ? prodKwh[h] : 0;
    consumptionKwh += c;
    productionKwh += p;

    const direct = Math.min(c, p);
    directKwh += direct;
    let surplus = p - direct; // ≥ 0
    let deficit = c - direct; // ≥ 0

    // CHARGE depuis le surplus (rendement à la charge ; borné par la place restante).
    if (surplus > 0 && soc < usableCap) {
      const room = usableCap - soc;
      const intoCells = Math.min(surplus * etaCharge, room);
      soc += intoCells;
      const drawnFromSurplus = intoCells / etaCharge; // solaire réellement prélevé
      solarToBatteryKwh += drawnFromSurplus;
      surplus -= drawnFromSurplus;
    }
    exportedKwh += surplus; // reste du surplus = exporté/perdu

    // DÉCHARGE vers le déficit (rendement à la décharge ; borné par le SoC).
    let served = 0;
    if (deficit > 0 && soc > 0) {
      const deliverable = Math.min(deficit, soc * etaDischarge);
      served = deliverable;
      soc -= deliverable / etaDischarge; // énergie retirée des cellules
      deficit -= deliverable;
    }
    fromBatteryKwh += served;
    fromGridKwh += deficit; // reste du déficit = réseau

    hDirect[h] = direct;
    hBattery[h] = served;
    hGrid[h] = deficit;
  }

  return {
    energy: {
      directKwh,
      fromBatteryKwh,
      fromGridKwh,
      exportedKwh,
      solarToBatteryKwh,
      consumptionKwh,
      productionKwh,
    },
    hourly: { direct: hDirect, battery: hBattery, grid: hGrid },
    socEnd: soc,
  };
}

/**
 * WJ120 — Simule le parc de `units` batteries face à la journée type (conso ×
 * production). Déroule DEUX jours en reportant le SoC (jour 2 = régime permanent,
 * rapporté ; jour 1 exposé séparément pour prouver le biais de SoC initial).
 * Déterministe et pur.
 */
export function simulateBattery(input: BatterySimInput): BatterySimResult {
  const etaOneWay = clamp01(input.oneWayEfficiency ?? BATTERY_ONE_WAY_EFFICIENCY, 0.5, 1);
  const dod = clamp01(input.depthOfDischarge ?? BATTERY_DEPTH_OF_DISCHARGE, 0.1, 1);
  const essentialW = Number.isFinite(input.essentialLoadW) && (input.essentialLoadW ?? 0) > 0
    ? (input.essentialLoadW as number)
    : ESSENTIAL_LOAD_W;
  const units = Number.isFinite(input.units) && input.units > 0 ? Math.trunc(input.units) : 0;
  const capPerUnit = Number.isFinite(input.capacityKwhPerUnit) && input.capacityKwhPerUnit > 0
    ? input.capacityKwhPerUnit
    : 0;
  const usableCap = units * capPerUnit * dod;

  const consKwh = scaleShapeToDaily(input.consumptionShape, input.dailyConsumptionKwh);
  const prodKwh = scaleShapeToDaily(input.productionShape, input.dailyProductionKwh);

  const d1 = runDay(consKwh, prodKwh, usableCap, etaOneWay, etaOneWay, 0);
  const d2 = runDay(consKwh, prodKwh, usableCap, etaOneWay, etaOneWay, d1.socEnd);

  const e = d2.energy;
  const selfConsumptionPct = e.productionKwh > 0
    ? ((e.directKwh + e.solarToBatteryKwh) / e.productionKwh) * 100
    : 0;
  const selfSufficiencyPct = e.consumptionKwh > 0
    ? ((e.directKwh + e.fromBatteryKwh) / e.consumptionKwh) * 100
    : 0;

  // Heures de secours = énergie livrable batterie pleine ÷ charge essentielle.
  // Livrable = capacité utile × rendement décharge (kWh) ; charge en kW = W/1000.
  const backupHours = essentialW > 0 ? (usableCap * etaOneWay) / (essentialW / 1000) : 0;

  return {
    ...e,
    selfConsumptionPct,
    selfSufficiencyPct,
    backupHours,
    usableCapacityKwh: usableCap,
    hourly: d2.hourly,
    day1: d1.energy,
  };
}

function clamp01(v: number, lo: number, hi: number): number {
  if (!Number.isFinite(v)) return hi;
  return Math.max(lo, Math.min(hi, v));
}

// ── Détection de la ligne batterie du devis (capacité + unités offertes) ──────

export interface OfferBattery {
  /** Vrai si l'offre (avec_items) porte une ligne batterie identifiable. */
  present: boolean;
  /** Capacité par unité (kWh) issue de la réf catalogue (5/10), ou null si indéterminée. */
  capacityKwhPerUnit: number | null;
  /** Nombre d'unités offertes (quantité de la ligne batterie). */
  units: number;
  /** Désignation de la ligne détectée (pour affichage/debug). */
  designation: string;
}

const BATTERY_KEYWORDS = /batter|deyness|\blfp\b|lithium|bat-dey/i;

/**
 * WJ120 — Détecte, dans les lignes d'une option (typiquement `avec_items`), la ligne
 * BATTERIE : capacité par unité (STRICTEMENT depuis les réfs catalogue Deyness
 * BAT-DEY-5 → 5 kWh / BAT-DEY-10 → 10 kWh, sinon un « N kWh » explicite dans la
 * désignation), et le nombre d'unités offertes (quantité). Aucune capacité inventée :
 * une ligne batterie sans capacité lisible renvoie `capacityKwhPerUnit: null` (la
 * page retombera alors sur l'unité de base catalogue). Renvoie la PREMIÈRE ligne
 * batterie rencontrée.
 */
export function resolveOfferBattery(items: ProposalItem[] | null | undefined): OfferBattery {
  const empty: OfferBattery = { present: false, capacityKwhPerUnit: null, units: 0, designation: '' };
  if (!Array.isArray(items)) return empty;
  for (const it of items) {
    const desig = typeof it?.designation === 'string' ? it.designation : '';
    if (!desig || !BATTERY_KEYWORDS.test(desig)) continue;
    const lower = desig.toLowerCase();
    let capacity: number | null = null;
    if (lower.includes('bat-dey-10')) capacity = DEYNESS_CAPACITY_KWH['BAT-DEY-10'];
    else if (lower.includes('bat-dey-5')) capacity = DEYNESS_CAPACITY_KWH['BAT-DEY-5'];
    else {
      // Repli : un « N kWh » explicite dans la désignation d'une ligne batterie.
      const m = /(\d+(?:[.,]\d+)?)\s*kwh/i.exec(lower);
      if (m) {
        const parsed = parseFloat(m[1].replace(',', '.'));
        if (Number.isFinite(parsed) && parsed > 0) capacity = parsed;
      }
    }
    const qty = Number.isFinite(it?.quantite) && it.quantite > 0 ? Math.trunc(it.quantite) : 1;
    return { present: true, capacityKwhPerUnit: capacity, units: qty, designation: desig };
  }
  return empty;
}

// ── Aire empilée « direct / batterie / réseau » (style SolarEdge) ─────────────

export type SplitChartLang = 'fr' | 'en' | 'ar';

export interface SplitChartBox {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}

export const DEFAULT_SPLIT_BOX: SplitChartBox = {
  width: 360,
  height: 150,
  padLeft: 8,
  padRight: 8,
  padTop: 10,
  padBottom: 20,
};

function esc(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const SPLIT_COLORS = {
  direct: 'var(--color-brass-400, #e8b54a)', // solaire direct
  battery: 'var(--color-azur-300, #7fb4e8)', // stocké → restitué par la batterie
  grid: 'var(--color-lune-faint, #8d96b4)', // importé du réseau
  rule: 'var(--color-white, #fff)',
  faint: 'var(--color-lune-faint, #8d96b4)',
};

/** Construit le `d` d'une aire empilée entre une frontière basse et haute (24 pts). */
function bandPath(lowerY: number[], upperY: number[], xs: number[]): string {
  if (xs.length === 0) return '';
  let d = `M${xs[0].toFixed(2)} ${upperY[0].toFixed(2)}`;
  for (let i = 1; i < xs.length; i++) d += ` L${xs[i].toFixed(2)} ${upperY[i].toFixed(2)}`;
  for (let i = xs.length - 1; i >= 0; i--) d += ` L${xs[i].toFixed(2)} ${lowerY[i].toFixed(2)}`;
  return d + ' Z';
}

/**
 * WJ120 — SVG PUR (string) de l'aire empilée « direct / batterie / réseau » sur
 * 24 h : trois bandes cumulées (solaire direct en bas, batterie au milieu, réseau
 * en haut) dont la somme, à chaque heure, vaut la consommation de cette heure. Même
 * langage visuel que `proposalChart`/`proposalCurve` (viewBox 360×150, ligne de
 * base fine, role="img"). Déterministe, réutilisé côté serveur (rendu initial) ET
 * côté client (recalcul au curseur, sans réseau).
 */
export function renderBatterySplitSvg(
  hourly: HourlySplit,
  box: SplitChartBox = DEFAULT_SPLIT_BOX,
  lang: SplitChartLang = 'fr',
): string {
  const n = HOURS_PER_DAY;
  const plotW = box.width - box.padLeft - box.padRight;
  const plotH = box.height - box.padTop - box.padBottom;
  const baseY = box.padTop + plotH;

  const direct = hourly.direct ?? [];
  const battery = hourly.battery ?? [];
  const grid = hourly.grid ?? [];

  let max = 0;
  for (let h = 0; h < n; h++) {
    const total = safe(direct[h]) + safe(battery[h]) + safe(grid[h]);
    if (total > max) max = total;
  }

  const xs: number[] = [];
  for (let h = 0; h < n; h++) xs.push(box.padLeft + (h / (n - 1)) * plotW);
  const yFor = (v: number): number => (max > 0 ? baseY - (v / max) * plotH : baseY);

  // Frontières cumulées : direct [0 → d], batterie [d → d+b], réseau [d+b → d+b+g].
  const y0: number[] = []; // ligne de base
  const yd: number[] = []; // haut du direct
  const ydb: number[] = []; // haut du direct+batterie
  const ydbg: number[] = []; // haut du total (conso)
  for (let h = 0; h < n; h++) {
    const d = safe(direct[h]);
    const b = safe(battery[h]);
    const g = safe(grid[h]);
    y0.push(baseY);
    yd.push(yFor(d));
    ydb.push(yFor(d + b));
    ydbg.push(yFor(d + b + g));
  }

  const directBand = `<path d="${bandPath(y0, yd, xs)}" fill="${SPLIT_COLORS.direct}" fill-opacity="0.9" stroke="none"/>`;
  const batteryBand = `<path d="${bandPath(yd, ydb, xs)}" fill="${SPLIT_COLORS.battery}" fill-opacity="0.85" stroke="none"/>`;
  const gridBand = `<path d="${bandPath(ydb, ydbg, xs)}" fill="${SPLIT_COLORS.grid}" fill-opacity="0.55" stroke="none"/>`;

  const baseline = `<line x1="${box.padLeft}" y1="${baseY.toFixed(2)}" x2="${(box.width - box.padRight).toFixed(2)}" y2="${baseY.toFixed(2)}" stroke="${SPLIT_COLORS.rule}" stroke-opacity="0.12" stroke-width="1"/>`;

  // Repères horaires discrets (0h, 6h, 12h, 18h) — lecture neutre.
  const tickHours = [0, 6, 12, 18];
  const ticks = tickHours
    .map((h) => {
      const x = box.padLeft + (h / (n - 1)) * plotW;
      return `<text x="${x.toFixed(2)}" y="${(box.height - 6).toFixed(2)}" text-anchor="middle" font-size="9" fill="${SPLIT_COLORS.faint}">${h}h</text>`;
    })
    .join('');

  const titleByLang: Record<SplitChartLang, string> = {
    fr: 'Origine de votre électricité, heure par heure',
    en: 'Where your electricity comes from, hour by hour',
    ar: 'مصدر كهربائكم، ساعة بساعة',
  };
  const descByLang: Record<SplitChartLang, string> = {
    fr: 'Part de la consommation couverte par le solaire direct, la batterie et le réseau sur une journée type.',
    en: 'Share of consumption covered by direct solar, the battery and the grid over a typical day.',
    ar: 'حصة الاستهلاك المغطاة بالطاقة الشمسية المباشرة والبطارية والشبكة خلال يوم نموذجي.',
  };

  return (
    `<svg viewBox="0 0 ${box.width} ${box.height}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet" role="img" xmlns="http://www.w3.org/2000/svg">` +
    `<title>${esc(titleByLang[lang])}</title><desc>${esc(descByLang[lang])}</desc>` +
    baseline +
    directBand +
    batteryBand +
    gridBand +
    ticks +
    `</svg>`
  );
}

function safe(v: number | undefined): number {
  return Number.isFinite(v) && (v as number) > 0 ? (v as number) : 0;
}
