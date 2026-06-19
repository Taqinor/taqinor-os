/**
 * W68 — LOGIQUE PURE de la VARIABILITÉ de consommation (« Affiner ma consommation »)
 * de l'estimateur toiture pro-11. Tout ici est testable HORS DOM et HORS réseau : la
 * construction d'une courbe horaire (24 valeurs kWh), la répartition de l'énergie d'un
 * appareil sur son créneau, le calcul des watts d'une climatisation (BTU ÷ EER) et d'un
 * chargeur de voiture électrique (kW × h, ou km/jour × conso), la fusion « sur ma
 * facture » (ajout au-dessus du socle) vs « déjà compris » (reshape à total constant),
 * le recalage sur la facture, l'autoconsommation (surplus valorisé à zéro) plafonnée par
 * le modèle billMAD existant, et le dimensionnement batterie (taille-au-besoin,
 * 6 kWh/jour par batterie).
 *
 * AUCUN chiffre inventé : les économies réutilisent `annualSavingsMad` (estimatorBrainV2,
 * plafond billMAD — JAMAIS un nouveau tarif), la production horaire vient de PVGIS (la
 * courbe `typicalDayByMonth` du moteur de production), et les TYPIQUES d'appareils sont
 * des fourchettes publiées documentées dans `apps/web/APPLIANCES_NOTES.md`, TOUJOURS
 * surchargeables par le client (sa plaque signalétique prime). Rien n'est asserté comme
 * un fait.
 */
import { annualSavingsMad, type TariffGrid, REGIE_TARIFF } from './estimatorBrainV2';

/** Nombre d'heures dans une journée (taille de toutes les courbes horaires). */
export const HOURS_PER_DAY = 24;

/** Capacité utile retenue par batterie (kWh/jour couvrable) — constante opérateur.
 *  Dimensionnement « taille-au-besoin » : autant de batteries que de tranches de
 *  6 kWh/jour à décaler du surplus solaire vers le soir. Réglable ici. */
export const BATTERY_KWH_PER_DAY = 6;

/** Une courbe horaire = 24 valeurs d'ÉNERGIE (kWh) indexées par l'heure 0–23. */
export type HourlyCurve = number[];

/** Crée une courbe horaire à zéro (24 valeurs). */
export function emptyCurve(): HourlyCurve {
  return new Array<number>(HOURS_PER_DAY).fill(0);
}

/** Somme d'une courbe (total journalier kWh), bornée ≥ 0 et finie. */
export function curveTotal(curve: HourlyCurve): number {
  let s = 0;
  for (const v of curve) s += Number.isFinite(v) && v > 0 ? v : 0;
  return s;
}

/** Normalise une heure quelconque dans [0,23] (wrap circulaire). */
export function normHour(h: number): number {
  const n = Math.trunc(Number.isFinite(h) ? h : 0);
  return ((n % HOURS_PER_DAY) + HOURS_PER_DAY) % HOURS_PER_DAY;
}

/**
 * Liste des heures couvertes par un créneau [startHour, endHour) qui peut traverser
 * minuit (ex. 22→6 = soir + nuit). `endHour === startHour` ou un créneau de 24 h → toute
 * la journée. Durée minimale 1 h (un appareil « 0 h » occupe quand même son heure de
 * départ pour ne jamais diviser par zéro).
 */
export function windowHours(startHour: number, endHour: number): number[] {
  const s = normHour(startHour);
  let len = Math.trunc(endHour) - Math.trunc(startHour);
  // Normalise la longueur dans [1, 24].
  len = ((len % HOURS_PER_DAY) + HOURS_PER_DAY) % HOURS_PER_DAY;
  if (len === 0) len = HOURS_PER_DAY; // un créneau « plein » couvre 24 h
  const out: number[] = [];
  for (let i = 0; i < len; i++) out.push((s + i) % HOURS_PER_DAY);
  return out;
}

/**
 * Profil journalier de base à partir d'un total journalier (kWh) : une silhouette
 * résidentielle marocaine plausible (creux la nuit, petite bosse matin, pic du soir).
 * Les poids sont une FORME (normalisée à 1) — ce ne sont PAS des chiffres de
 * consommation : le total réel vient TOUJOURS de la facture (billToAnnualKwh ÷ 365).
 * Le client peut ensuite tout éditer à la main. Poids documentés dans APPLIANCES_NOTES.md.
 */
export const BASELINE_SHAPE: readonly number[] = [
  // 0h   1h   2h   3h   4h   5h    6h    7h    8h    9h   10h   11h
  0.6, 0.5, 0.45, 0.4, 0.4, 0.5, 0.9, 1.3, 1.2, 1.0, 0.9, 0.9,
  // 12h  13h  14h  15h  16h  17h   18h   19h   20h   21h   22h   23h
  1.0, 1.0, 0.9, 0.9, 1.0, 1.3, 1.8, 2.2, 2.4, 2.0, 1.4, 0.9,
];

/** Construit une courbe horaire (kWh) qui SOMME EXACTEMENT à `dailyKwh`, suivant la
 *  silhouette de base. dailyKwh ≤ 0 → courbe nulle. */
export function baselineCurve(dailyKwh: number): HourlyCurve {
  const total = Number.isFinite(dailyKwh) && dailyKwh > 0 ? dailyKwh : 0;
  if (total <= 0) return emptyCurve();
  const wTotal = BASELINE_SHAPE.reduce((a, b) => a + b, 0);
  return BASELINE_SHAPE.map((w) => (total * w) / wTotal);
}

// ════════════════════════ Appareils ════════════════════════

/** Mode de prise en compte d'un appareil dans la facture. */
export type ApplianceBilling =
  /** Pas encore reflété dans la facture (clim ou voiture neuve) : AJOUTE au total. */
  | 'onTop'
  /** Déjà dans la facture : sert UNIQUEMENT à reshaper la distribution (total fixe). */
  | 'inBill';

/** Un appareil paramétré par le client (toutes les valeurs sont éditables). */
export interface Appliance {
  /** Identifiant de type (pour l'UI / les typiques). */
  kind: string;
  /** Libellé affiché. */
  label: string;
  /** Énergie journalière de l'appareil (kWh/jour). Calculée à partir de ses réglages. */
  dailyKwh: number;
  /** Heure de début du créneau (0–23). */
  startHour: number;
  /** Heure de fin du créneau (exclusive ; peut traverser minuit). */
  endHour: number;
  /** Prise en compte : ajout au socle, ou simple reshape. */
  billing: ApplianceBilling;
}

/**
 * Watts ÉLECTRIQUES d'une climatisation à partir de sa puissance frigorifique (BTU/h) et
 * de son coefficient d'efficacité EER : W = BTU/h ÷ EER. EER par défaut ≈ 9 (non-inverter)
 * ou ≈ 12 (inverter), tous deux éditables. Entrées invalides → 0 (jamais NaN).
 * Source des défauts : APPLIANCES_NOTES.md.
 */
export function acWattsFromBtu(btuPerHour: number, eer: number): number {
  const btu = Number.isFinite(btuPerHour) && btuPerHour > 0 ? btuPerHour : 0;
  const e = Number.isFinite(eer) && eer > 0 ? eer : 0;
  if (btu <= 0 || e <= 0) return 0;
  return btu / e;
}

/** kWh = W × h ÷ 1000 (énergie d'un appareil de puissance constante sur `hours`). */
export function kwhFromWattsHours(watts: number, hours: number): number {
  const w = Number.isFinite(watts) && watts > 0 ? watts : 0;
  const h = Number.isFinite(hours) && hours > 0 ? hours : 0;
  return (w * h) / 1000;
}

/**
 * Énergie journalière (kWh) d'une recharge de voiture électrique par DISTANCE :
 * km/jour × (conso kWh/100 km) ÷ 100. Conso par défaut ≈ 17 kWh/100 km, éditable.
 * Source : APPLIANCES_NOTES.md.
 */
export function evKwhFromDistance(kmPerDay: number, kwhPer100km: number): number {
  const km = Number.isFinite(kmPerDay) && kmPerDay > 0 ? kmPerDay : 0;
  const c = Number.isFinite(kwhPer100km) && kwhPer100km > 0 ? kwhPer100km : 0;
  return (km * c) / 100;
}

/**
 * Répartit l'énergie journalière d'un appareil UNIFORMÉMENT sur les heures de son
 * créneau, et l'ajoute à la courbe fournie (qui est modifiée et renvoyée). La somme des
 * ajouts == dailyKwh exactement (par construction : dailyKwh ÷ nbHeures × nbHeures).
 */
export function distributeAppliance(curve: HourlyCurve, appliance: Appliance): HourlyCurve {
  const total = Number.isFinite(appliance.dailyKwh) && appliance.dailyKwh > 0 ? appliance.dailyKwh : 0;
  if (total <= 0) return curve;
  const hours = windowHours(appliance.startHour, appliance.endHour);
  const per = total / hours.length;
  for (const h of hours) curve[h] += per;
  return curve;
}

/**
 * Courbe horaire d'un appareil seul (24 valeurs sommant à son dailyKwh) — utile pour
 * tester la répartition d'un appareil isolément.
 */
export function applianceCurve(appliance: Appliance): HourlyCurve {
  return distributeAppliance(emptyCurve(), appliance);
}

/**
 * Compose la courbe de consommation finale à partir :
 *  - d'une courbe DE BASE (le socle issu de la facture, ou une courbe éditée à la main) ;
 *  - d'une liste d'appareils.
 * Règle de prise en compte :
 *  - « onTop » : l'énergie de l'appareil s'AJOUTE par-dessus le socle → le total monte
 *    (un appareil neuf pas encore dans la facture augmente le besoin et le dimensionnement) ;
 *  - « inBill » : l'appareil ne fait que RESHAPER la distribution — on l'ajoute d'abord
 *    puis on RE-NORMALISE l'ensemble au total du socle, de sorte que le total reste FIXE.
 *
 * Concrètement : on part du socle, on ajoute tous les « inBill », on re-normalise au total
 * du socle (reshape à total constant), PUIS on ajoute tous les « onTop » (qui montent le
 * total). Le total final = total socle + Σ(onTop) ; le total des « inBill » reste compris.
 */
export function composeConsumption(base: HourlyCurve, appliances: Appliance[]): HourlyCurve {
  const baseTotal = curveTotal(base);
  // 1) Socle + appareils « déjà compris ».
  const reshaped = base.slice();
  let hasInBill = false;
  for (const a of appliances) {
    if (a.billing === 'inBill') {
      distributeAppliance(reshaped, a);
      hasInBill = true;
    }
  }
  // 2) Re-normalisation au total du socle (les « inBill » ne changent QUE la forme).
  //    Socle nul → un « inBill » n'a aucun total à reshaper : il ne fabrique PAS d'énergie
  //    (on repart du socle nul). Sinon on ramène la courbe reshapée au total du socle.
  let out = reshaped;
  if (hasInBill) {
    if (baseTotal <= 0) {
      out = base.slice(); // rien à reshaper → on garde le socle (nul)
    } else {
      const reshapedTotal = curveTotal(reshaped);
      if (reshapedTotal > 0) {
        const k = baseTotal / reshapedTotal;
        out = reshaped.map((v) => v * k);
      }
    }
  }
  // 3) Ajout des appareils « sur ma facture » (montent le total).
  for (const a of appliances) {
    if (a.billing === 'onTop') distributeAppliance(out, a);
  }
  return out;
}

/**
 * Recale une courbe ÉDITÉE À LA MAIN pour que son total journalier égale `targetDailyKwh`
 * (le kWh/jour dérivé de la facture). Reshape pur : on multiplie chaque heure par le
 * facteur d'échelle. Courbe nulle ou cible ≤ 0 → renvoyée telle quelle (rien à recaler).
 */
export function rescaleToDaily(curve: HourlyCurve, targetDailyKwh: number): HourlyCurve {
  const target = Number.isFinite(targetDailyKwh) && targetDailyKwh > 0 ? targetDailyKwh : 0;
  const total = curveTotal(curve);
  if (target <= 0 || total <= 0) return curve.slice();
  const k = target / total;
  return curve.map((v) => (Number.isFinite(v) && v > 0 ? v * k : 0));
}

// ════════════════════════ Autoconsommation + économies ════════════════════════

/**
 * AUTOCONSOMMATION journalière (kWh) : pour chaque heure, min(conso, production) — le
 * solaire ne couvre que ce qui est consommé À CETTE HEURE ; le surplus (production >
 * conso) est valorisé à ZÉRO (pas de net-billing BT clair au Maroc — conservateur).
 * `productionHourlyKw` = profil de PUISSANCE (kW) du jour-type ; le pas étant 1 h,
 * l'énergie (kWh) = la puissance (kW). Les deux tableaux sont alignés sur 24 heures.
 */
export function selfConsumptionDailyKwh(consumption: HourlyCurve, productionHourlyKw: HourlyCurve): number {
  let self = 0;
  for (let h = 0; h < HOURS_PER_DAY; h++) {
    const c = Number.isFinite(consumption[h]) && consumption[h] > 0 ? consumption[h] : 0;
    const p = Number.isFinite(productionHourlyKw[h]) && productionHourlyKw[h] > 0 ? productionHourlyKw[h] : 0;
    self += Math.min(c, p);
  }
  return self;
}

/** Surplus journalier (kWh) exporté/perdu = production − autoconsommation (≥ 0). */
export function surplusDailyKwh(consumption: HourlyCurve, productionHourlyKw: HourlyCurve): number {
  let prod = 0;
  for (let h = 0; h < HOURS_PER_DAY; h++) {
    prod += Number.isFinite(productionHourlyKw[h]) && productionHourlyKw[h] > 0 ? productionHourlyKw[h] : 0;
  }
  return Math.max(0, prod - selfConsumptionDailyKwh(consumption, productionHourlyKw));
}

/** Taux d'autoconsommation (0–1) = autoconsommé ÷ produit (0 si production nulle). */
export function selfConsumptionRate(consumption: HourlyCurve, productionHourlyKw: HourlyCurve): number {
  let prod = 0;
  for (const p of productionHourlyKw) prod += Number.isFinite(p) && p > 0 ? p : 0;
  if (prod <= 0) return 0;
  return selfConsumptionDailyKwh(consumption, productionHourlyKw) / prod;
}

/**
 * ÉCONOMIES annuelles (MAD) à partir de l'autoconsommation horaire réellement alignée.
 * On dérive l'autoconsommation journalière de la courbe horaire (surplus à zéro), on la
 * passe en annuel (×365) et on plafonne par le modèle existant `annualSavingsMad`
 * (plafond billMAD — JAMAIS un nouveau tarif). La cible de conso (`annualConsumptionKwh`)
 * borne aussi l'économie. Fourchette d'alignement temporel conservée par le modèle.
 */
export function savingsFromHourly(
  consumption: HourlyCurve,
  productionHourlyKw: HourlyCurve,
  annualConsumptionKwh: number,
  tariff: TariffGrid = REGIE_TARIFF,
): { low: number; high: number; selfDailyKwh: number; selfAnnualKwh: number } {
  const selfDaily = selfConsumptionDailyKwh(consumption, productionHourlyKw);
  const selfAnnual = selfDaily * 365;
  // L'économie = facture évitée par l'autoconsommation, plafonnée billMAD. On passe la
  // PRODUCTION effective = l'autoconsommation alignée (le surplus valant zéro), et la
  // CONSO = la cible annuelle ; annualSavingsMad plafonne au coût évitable.
  const yr = annualSavingsMad(selfAnnual, Math.max(0, annualConsumptionKwh), tariff);
  return { low: yr.low, high: yr.high, selfDailyKwh: selfDaily, selfAnnualKwh: selfAnnual };
}

// ════════════════════════ Dimensionnement (besoin + batterie) ════════════════════════

/**
 * Besoin de PRODUCTION dérivé de la consommation journalière courante (kWh/jour → kWh/an).
 * Un appareil « sur ma facture » fait monter ce besoin annuel, donc le nombre de panneaux
 * recommandé et la batterie. PUR : c'est juste dailyKwh × 365.
 */
export function annualConsumptionFromDaily(dailyKwh: number): number {
  return Math.max(0, Number.isFinite(dailyKwh) ? dailyKwh : 0) * 365;
}

/**
 * Dimensionnement BATTERIE « taille-au-besoin » : le besoin de stockage journalier =
 * l'énergie consommée le SOIR/la NUIT qui pourrait être décalée depuis le surplus solaire,
 * borné par le surplus réellement disponible (on ne stocke pas ce qu'on n'a pas produit).
 * Nombre de batteries = plafond(besoin stockable ÷ 6 kWh/jour). Constante opérateur
 * BATTERY_KWH_PER_DAY ; aucun chiffre inventé. Renvoie aussi le besoin stockable retenu.
 *
 * `eveningStartHour` (défaut 18) : à partir de quelle heure la conso est « du soir » et
 * doit être servie par la batterie plutôt que par le solaire direct.
 */
export function batterySizing(
  consumption: HourlyCurve,
  productionHourlyKw: HourlyCurve,
  eveningStartHour = 18,
): { storableDailyKwh: number; batteries: number } {
  const start = normHour(eveningStartHour);
  // Conso hors fenêtre solaire directe : heures sans production (soir/nuit) à partir de
  // `start`, et tôt le matin avant le lever. On retient la conso aux heures où la
  // production est ≈ nulle (le solaire direct ne la couvre pas → candidate au stockage).
  let nightConsumption = 0;
  for (let h = 0; h < HOURS_PER_DAY; h++) {
    const c = Number.isFinite(consumption[h]) && consumption[h] > 0 ? consumption[h] : 0;
    const p = Number.isFinite(productionHourlyKw[h]) && productionHourlyKw[h] > 0 ? productionHourlyKw[h] : 0;
    const isEvening = h >= start || h < 6; // soir + nuit + petit matin
    if (isEvening && p <= 0) nightConsumption += c;
  }
  // On ne stocke que ce que le surplus solaire permet réellement de décaler.
  const surplus = surplusDailyKwh(consumption, productionHourlyKw);
  const storable = Math.max(0, Math.min(nightConsumption, surplus));
  const batteries = storable > 0 ? Math.ceil(storable / BATTERY_KWH_PER_DAY) : 0;
  return { storableDailyKwh: storable, batteries };
}

// ════════════════════════ Typiques d'appareils (défauts éditables) ════════════════════════

/** Un appareil du catalogue : défauts documentés (APPLIANCES_NOTES.md), TOUS éditables. */
export interface ApplianceTypical {
  kind: string;
  label: string;
  /** Puissance typique (W) — fourchette publiée, surchargée par la plaque du client. */
  watts: number;
  /** Heures d'usage par jour par défaut. */
  hoursPerDay: number;
  /** Créneau par défaut [start, end). */
  startHour: number;
  endHour: number;
  /** Prise en compte par défaut. */
  billing: ApplianceBilling;
  /** Note FR (ex. « beaucoup de foyers marocains sont au gaz »). */
  note?: string;
}

/**
 * Catalogue CURÉ d'appareils — fourchettes publiées (APPLIANCES_NOTES.md), TOUTES
 * éditables par le client (sa plaque signalétique prime, rien n'est asserté comme un
 * fait). La climatisation et la voiture ont leur propre saisie (BTU÷EER, kW×h ou km/jour)
 * dans l'UI ; on en donne ici une valeur de départ raisonnable.
 */
export const APPLIANCE_TYPICALS: readonly ApplianceTypical[] = [
  { kind: 'clim', label: 'Climatisation', watts: 1340, hoursPerDay: 6, startHour: 13, endHour: 23, billing: 'onTop', note: 'Saisie par BTU ÷ EER (9 000 BTU ≈ 1 CV).' },
  { kind: 'ev', label: 'Recharge voiture électrique', watts: 7400, hoursPerDay: 3, startHour: 11, endHour: 15, billing: 'onTop', note: 'Recharger en plein soleil augmente fortement l’autoconsommation.' },
  { kind: 'cumulus', label: 'Chauffe-eau électrique (cumulus)', watts: 2000, hoursPerDay: 2.5, startHour: 6, endHour: 9, billing: 'inBill', note: 'Beaucoup de foyers marocains chauffent l’eau au gaz (butane) — optionnel.' },
  { kind: 'piscine', label: 'Pompe de piscine', watts: 1100, hoursPerDay: 6, startHour: 10, endHour: 16, billing: 'inBill' },
  { kind: 'four', label: 'Four électrique', watts: 2200, hoursPerDay: 1, startHour: 19, endHour: 20, billing: 'inBill' },
  { kind: 'plaque', label: 'Plaque / cuisinière électrique ou induction', watts: 2200, hoursPerDay: 1.5, startHour: 12, endHour: 21, billing: 'inBill', note: 'Le gaz reste courant au Maroc.' },
  { kind: 'lave-linge', label: 'Lave-linge', watts: 500, hoursPerDay: 1, startHour: 9, endHour: 12, billing: 'inBill', note: '≈ 1 kWh par cycle.' },
  { kind: 'lave-vaisselle', label: 'Lave-vaisselle', watts: 1800, hoursPerDay: 1, startHour: 20, endHour: 22, billing: 'inBill', note: '≈ 1 à 1,5 kWh par cycle.' },
  { kind: 'seche-linge', label: 'Sèche-linge', watts: 2400, hoursPerDay: 1, startHour: 10, endHour: 12, billing: 'inBill', note: '≈ 2 à 3 kWh par cycle.' },
  { kind: 'frigo', label: 'Réfrigérateur / congélateur', watts: 200, hoursPerDay: 24, startHour: 0, endHour: 24, billing: 'inBill', note: 'Socle permanent 24 h (≈ 1 à 2 kWh/jour).' },
  { kind: 'chauffage', label: 'Chauffage électrique / radiateur', watts: 1500, hoursPerDay: 4, startHour: 18, endHour: 23, billing: 'onTop', note: 'Surtout matins et soirs d’hiver.' },
  { kind: 'pompe-eau', label: 'Pompe à eau / forage', watts: 1100, hoursPerDay: 2, startHour: 8, endHour: 18, billing: 'inBill', note: 'Villas / rural, usage intermittent.' },
  { kind: 'fer', label: 'Fer à repasser', watts: 1400, hoursPerDay: 0.5, startHour: 18, endHour: 20, billing: 'inBill' },
  { kind: 'micro-ondes', label: 'Micro-ondes', watts: 900, hoursPerDay: 0.5, startHour: 12, endHour: 21, billing: 'inBill' },
  { kind: 'pac', label: 'Pompe à chaleur (chauffage / refroidissement)', watts: 2000, hoursPerDay: 5, startHour: 14, endHour: 22, billing: 'onTop', note: 'Configurable selon la saison.' },
  { kind: 'tv', label: 'Téléviseur + électronique', watts: 150, hoursPerDay: 5, startHour: 18, endHour: 23, billing: 'inBill', note: 'Petit socle agrégé.' },
  { kind: 'led', label: 'Éclairage LED', watts: 120, hoursPerDay: 5, startHour: 18, endHour: 23, billing: 'inBill', note: 'Petit socle agrégé.' },
];

/** Construit un Appliance à partir d'un typique (kWh = W × h ÷ 1000). */
export function applianceFromTypical(t: ApplianceTypical): Appliance {
  return {
    kind: t.kind,
    label: t.label,
    dailyKwh: kwhFromWattsHours(t.watts, t.hoursPerDay),
    startHour: t.startHour,
    endHour: t.endHour,
    billing: t.billing,
  };
}

/** Presets de climatisation (BTU) avec équivalent en chevaux (CV). Éditables côté UI. */
export const AC_BTU_PRESETS: readonly { btu: number; cv: number }[] = [
  { btu: 9000, cv: 1 },
  { btu: 12000, cv: 1.5 },
  { btu: 18000, cv: 2 },
  { btu: 24000, cv: 3 },
];

/** EER par défaut (éditables) : non-inverter ≈ 9, inverter ≈ 12 (APPLIANCES_NOTES.md). */
export const AC_EER_DEFAULT_NON_INVERTER = 9;
export const AC_EER_DEFAULT_INVERTER = 12;

/** Presets de puissance de chargeur VE (kW). 7,4 kW = wallbox monophasé courant. */
export const EV_CHARGER_KW_PRESETS: readonly number[] = [2.3, 3.7, 7.4, 11, 22];

/** Conso VE par défaut (kWh/100 km), éditable (APPLIANCES_NOTES.md). */
export const EV_KWH_PER_100KM_DEFAULT = 17;
