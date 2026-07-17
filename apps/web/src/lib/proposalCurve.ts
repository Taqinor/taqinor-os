/**
 * WJ16 — Courbe « production solaire vs consommation » sur une JOURNÉE type
 * (lever → coucher du soleil), rendue en SVG PUR (aucun DOM, aucun réseau, aucune
 * dépendance). C'est le visuel le plus persuasif de la proposition : il montre la
 * cloche de production solaire (du lever au coucher) recouvrant la consommation
 * du foyer.
 *
 * DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » :
 *  - L'amplitude de la cloche est CALÉE sur la production journalière moyenne RÉELLE
 *    (`prod_kwh` annuel backend / 365) quand elle est fournie : l'axe porte alors
 *    des kWh réels.
 *  - Sans production annuelle, on dessine une cloche NORMALISÉE clairement libellée
 *    « profil — année type » (forme illustrative, AUCUN chiffre d'axe) — le visuel
 *    le plus persuasif ne disparaît jamais, mais ne ment pas non plus.
 *  - WJ119 — la forme horaire de consommation N'EST PLUS une double-gaussienne
 *    générique : elle porte `BASELINE_SHAPE` (applianceConsumption.ts, la même
 *    silhouette marocaine soirée-dominante que l'outil « Affiner ma consommation »,
 *    pic 19h-21h ≈26 % de l'énergie), avec des variantes été/Ramadan et des
 *    profils dédiés par MODE (industriel équipes, commercial, agricole pompage).
 *    Reste un PROFIL normalisé à 1, jamais une donnée chiffrée affichée — le
 *    libellé « profil type au Maroc, ajusté à votre facture » (page) le dit
 *    explicitement, jamais « mesuré ».
 *
 * Mouvement : l'animation (tracé de la courbe + soleil qui se lève) est gérée 100 %
 * en CSS dans la page et GATÉE derrière `prefers-reduced-motion: no-preference` —
 * ce module n'émet que la géométrie statique (zéro CLS, lisible sans JS ni motion).
 */
import { BASELINE_SHAPE } from './applianceConsumption';

/** Heures représentées (5 h → 21 h), pas horaire. */
const HOUR_START = 5;
const HOUR_END = 21;
const HOURS = HOUR_END - HOUR_START; // 16

/**
 * Profil de production solaire normalisé (cloche centrée midi solaire ≈ 13 h).
 * Valeur ∈ [0,1] par heure ; 0 avant le lever / après le coucher. Forme standard
 * (sinus carré sur la fenêtre de jour), pas une donnée mesurée.
 */
export function solarProfile(hour: number): number {
  const sunrise = 6.5;
  const sunset = 19.5;
  if (hour <= sunrise || hour >= sunset) return 0;
  const t = (hour - sunrise) / (sunset - sunrise); // 0..1
  const s = Math.sin(Math.PI * t);
  return s * s; // cloche douce, pic à midi solaire
}

// ════════════════════════════════════════════════════════════════════════════
// WJ119 — Silhouette de consommation RÉELLEMENT marocaine, par MODE (résidentiel/
// industriel/commercial/agricole) + variante (normale/été/Ramadan). Chaque forme
// est un tableau de 24 poids (heure 0-23), jamais une donnée chiffrée : normalisée
// à son propre maximum (∈ [0,1]) juste avant l'échantillonnage, exactement comme
// l'ancienne double-gaussienne qu'elle remplace.
// ════════════════════════════════════════════════════════════════════════════

/** Les 4 marchés reconnus par le générateur de devis (residentiel par défaut). */
export type ProposalCurveMode = 'residentiel' | 'industriel' | 'commercial' | 'agricole';

/** Variante saisonnière/religieuse — n'a de sens que pour résidentiel/commercial. */
export type ProposalCurveVariant = 'normal' | 'ete' | 'ramadan';

/** Régime d'équipes d'un site industriel — 1x8 par défaut (aucun champ backend
 *  ne le porte encore aujourd'hui, cf. resolveProposalCurveMode). */
export type IndustrialShift = '1x8' | '2x8' | '3x8';

export interface ConsumptionShapeOptions {
  mode?: ProposalCurveMode;
  variant?: ProposalCurveVariant;
  industrialShift?: IndustrialShift;
}

/**
 * WJ119 — Normalise le champ backend `ProposalQuote.inst_type` (valeurs
 * OBSERVÉES aujourd'hui : "Résidentielle" / "Industrielle / Commerciale" /
 * "Agricole" — builder.py `inst_type = {...}.get(mode, "Résidentielle")") ou une
 * future clé machine minuscule (residentiel/industriel/commercial/agricole/
 * professionnel — ce dernier étant le nom interne du mode "industriel" côté
 * simulateur, mon-toit.astro MODE_LABEL) en l'un des 4 modes de courbe reconnus.
 * Absent/inconnu → 'residentiel' (repli honnête, jamais un mode fabriqué). Le
 * backend NE DISTINGUE PAS ENCORE industriel de commercial (une seule catégorie
 * combinée "Industrielle / Commerciale" — la table d'archétypes par catégorie
 * QX44 n'est pas construite) : le combiné retombe sur 'industriel', son mode
 * interne réel, tant qu'aucun champ ne permet de séparer les deux.
 */
export function resolveProposalCurveMode(instType: string | null | undefined): ProposalCurveMode {
  const s = (instType ?? '').trim().toLowerCase();
  if (!s) return 'residentiel';
  if (s.includes('agricole') || s.includes('pompage')) return 'agricole';
  if (s.includes('commercial') && !s.includes('industriel')) return 'commercial';
  if (s.includes('industriel') || s.includes('professionnel')) return 'industriel';
  return 'residentiel';
}

/** Normalise une forme brute (poids quelconques ≥ 0) à son propre maximum (∈ [0,1]). */
function normalizeShape(shape: readonly number[]): number[] {
  let max = 0;
  for (const w of shape) if (Number.isFinite(w) && w > max) max = w;
  if (max <= 0) return shape.map(() => 0);
  return shape.map((w) => (Number.isFinite(w) && w > 0 ? w / max : 0));
}

/** Échantillonne une forme normalisée de 24 poids (heure 0-23) à une heure
 *  QUELCONQUE (interpolation linéaire entre les deux heures entières voisines,
 *  circulaire — minuit suit 23 h). */
function sampleShape(shape: readonly number[], hour: number): number {
  const h = ((hour % 24) + 24) % 24;
  const h0 = Math.floor(h);
  const h1 = (h0 + 1) % 24;
  const frac = h - h0;
  const v0 = shape[h0] ?? 0;
  const v1 = shape[h1] ?? 0;
  return v0 + (v1 - v0) * frac;
}

/** WJ119 — été/intérieur : +40-60 % 13h-18h (climatisation) — ESTIMATION (multi-
 *  plicateur médian retenu, à confirmer/affiner avec des factures d'été réelles,
 *  APPLIANCES_NOTES.md). Ne s'applique qu'au résidentiel/commercial (toggle page). */
const SUMMER_BOOST_HOURS: readonly number[] = [13, 14, 15, 16, 17, 18];
const SUMMER_BOOST_MULT = 1.5;

/** WJ119 — Ramadan : journée de jeûne −30 à −40 % (retenu −35 %, ESTIMATION),
 *  pic iftar au coucher du soleil (retenu 19 h, ×1.8) et bosse suhoor 3h-5h
 *  (repas avant l'aube, retenu ×2.5) — ordres de grandeur documentés, jamais un
 *  chiffre mesuré. */
const RAMADAN_DAY_HOUR_START = 6;
const RAMADAN_DAY_HOUR_END = 18; // inclus
const RAMADAN_DAY_FACTOR = 0.65;
const RAMADAN_SUHOOR_HOURS: readonly number[] = [3, 4, 5];
const RAMADAN_SUHOOR_MULT = 2.5;
const RAMADAN_IFTAR_HOUR = 19;
const RAMADAN_IFTAR_MULT = 1.8;

/** Applique la variante été/Ramadan à une forme de base (résidentiel ou
 *  commercial) ; 'normal' renvoie la forme telle quelle. */
function applySeasonalVariant(base: readonly number[], variant: ProposalCurveVariant): number[] {
  const out = base.slice();
  if (variant === 'ete') {
    for (const h of SUMMER_BOOST_HOURS) out[h] *= SUMMER_BOOST_MULT;
  } else if (variant === 'ramadan') {
    for (let h = RAMADAN_DAY_HOUR_START; h <= RAMADAN_DAY_HOUR_END; h++) out[h] *= RAMADAN_DAY_FACTOR;
    for (const h of RAMADAN_SUHOOR_HOURS) out[h] *= RAMADAN_SUHOOR_MULT;
    out[RAMADAN_IFTAR_HOUR] *= RAMADAN_IFTAR_MULT;
  }
  return out;
}

/** WJ119 — Profil industriel par régime d'équipes. Poids plats : 1 = poste actif,
 *  `INDUSTRIAL_STANDBY_WEIGHT` = veille/éclairage de sécurité hors poste (jamais
 *  zéro : un site industriel garde toujours un socle hors production). Aucun champ
 *  backend ne porte le régime aujourd'hui → repli 1x8 (ESTIMATION documentée). */
const INDUSTRIAL_STANDBY_WEIGHT = 0.15;

function industrialShape(shift: IndustrialShift): number[] {
  if (shift === '3x8') return new Array(24).fill(1); // continu, trois équipes qui se relaient
  const out = new Array(24).fill(INDUSTRIAL_STANDBY_WEIGHT);
  // 1x8 : poste de jour unique (8h-16h) ; 2x8 : plateau 06h-22h (deux équipes).
  const [start, end] = shift === '2x8' ? [6, 22] : [8, 16];
  for (let h = start; h < end; h++) out[h] = 1;
  return out;
}

/** WJ119 — Archétype commercial GÉNÉRIQUE (horaires commerce courants 9h-19h) —
 *  UNE seule forme, pas de table par catégorie (QX44 pas encore construite) :
 *  ESTIMATION honnête, jamais présentée comme mesurée. */
const COMMERCIAL_OPEN_HOUR = 9;
const COMMERCIAL_CLOSE_HOUR = 19;
const COMMERCIAL_OFFHOURS_WEIGHT = 0.1;

function commercialShape(): number[] {
  const out = new Array(24).fill(COMMERCIAL_OFFHOURS_WEIGHT);
  for (let h = COMMERCIAL_OPEN_HOUR; h < COMMERCIAL_CLOSE_HOUR; h++) out[h] = 1;
  return out;
}

/** WJ119 — Fenêtre de pompage agricole = heures de JOUR (le pompage solaire
 *  tourne SUR le soleil, sans onduleur ni batterie — CLAUDE.md) : plate le jour,
 *  NULLE la nuit (aucune énergie stockée pour pomper après le coucher). */
const AGRICOLE_PUMP_START_HOUR = 7;
const AGRICOLE_PUMP_END_HOUR = 19;

function agricoleShape(): number[] {
  const out = new Array(24).fill(0);
  for (let h = AGRICOLE_PUMP_START_HOUR; h < AGRICOLE_PUMP_END_HOUR; h++) out[h] = 1;
  return out;
}

/** Construit la forme BRUTE (non normalisée) du mode/variante/régime demandé. */
function rawConsumptionShape(options: ConsumptionShapeOptions): number[] {
  const mode = options.mode ?? 'residentiel';
  const variant = options.variant ?? 'normal';
  switch (mode) {
    case 'industriel':
      return industrialShape(options.industrialShift ?? '1x8');
    case 'commercial':
      // Été/Ramadan restent pertinents pour un commerce (clim, horaires resserrés
      // pendant le jeûne) — même modulation que le résidentiel, appliquée à
      // l'archétype commercial plutôt qu'à BASELINE_SHAPE.
      return applySeasonalVariant(commercialShape(), variant);
    case 'agricole':
      return agricoleShape();
    case 'residentiel':
    default:
      return applySeasonalVariant(BASELINE_SHAPE, variant);
  }
}

/**
 * Profil de consommation normalisé (0-23h, interpolé pour une heure quelconque).
 * Résidentiel/normal (repli par défaut) = silhouette marocaine soirée-dominante
 * (BASELINE_SHAPE, applianceConsumption.ts — pic 19h-21h ≈26 % de l'énergie),
 * jamais une double-gaussienne générique. Valeur ∈ [0,1], jamais un chiffre
 * affiché — ce n'est qu'une FORME, illustrative par construction (WJ119).
 */
export function consumptionProfile(hour: number, options: ConsumptionShapeOptions = {}): number {
  const shape = normalizeShape(rawConsumptionShape(options));
  return sampleShape(shape, hour);
}

function esc(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** WJ80 — Langue courante de la page, thread à travers étiquettes + annotations. */
export type CurveLang = 'fr' | 'en' | 'ar';

export interface CurveBox {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}

export const DEFAULT_CURVE_BOX: CurveBox = {
  width: 360,
  height: 170,
  padLeft: 10,
  padRight: 10,
  padTop: 16,
  padBottom: 24,
};

/** Construit le `d` d'un path lissé (polyligne) à partir de points normalisés. */
function pathFromProfile(
  profile: (h: number) => number,
  box: CurveBox,
  close: boolean,
): { d: string; points: Array<{ x: number; y: number }> } {
  const plotW = box.width - box.padLeft - box.padRight;
  const plotH = box.height - box.padTop - box.padBottom;
  const baseY = box.padTop + plotH;
  const steps = HOURS * 2; // demi-heures pour un tracé fluide
  const points: Array<{ x: number; y: number }> = [];
  for (let i = 0; i <= steps; i++) {
    const hour = HOUR_START + (i / steps) * HOURS;
    const v = Math.max(0, Math.min(1, profile(hour)));
    const x = box.padLeft + (i / steps) * plotW;
    const y = baseY - v * plotH;
    points.push({ x, y });
  }
  let d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');
  if (close) {
    const last = points[points.length - 1];
    const first = points[0];
    d += ` L${last.x.toFixed(2)} ${baseY.toFixed(2)} L${first.x.toFixed(2)} ${baseY.toFixed(2)} Z`;
  }
  return { d, points };
}

export interface DailyCurve {
  /** SVG inline complet (string). */
  svg: string;
  /**
   * Vrai quand l'axe porte des kWh RÉELS (production annuelle backend fournie) ;
   * faux → mode « année type » (forme illustrative, aucun chiffre d'axe).
   */
  hasRealScale: boolean;
}

/** Format kWh court, virgule/point décimal selon la langue. */
function fmtKwh(n: number, lang: CurveLang = 'fr'): string {
  const v = Number.isFinite(n) && n > 0 ? n : 0;
  const rounded = (Math.round(v * 10) / 10).toString();
  // WJ80 — FR/AR gardent la virgule décimale (convention déjà utilisée
  // ailleurs sur la page en arabe) ; EN utilise le point décimal.
  const grouped = lang === 'en' ? rounded : rounded.replace('.', ',');
  return `${grouped} kWh`;
}

/** WJ80 — Libellés horaires (lever/midi/coucher) FR/EN/AR. */
const HOUR_TICK_LABELS: Record<CurveLang, { sunrise: string; noon: string; sunset: string }> = {
  fr: { sunrise: 'lever', noon: 'midi', sunset: 'coucher' },
  en: { sunrise: 'sunrise', noon: 'noon', sunset: 'sunset' },
  ar: { sunrise: 'الشروق', noon: 'الظهر', sunset: 'الغروب' },
};

/** WJ80 — Texte du repère d'échelle (pic + moyenne journalière ou repli « année type »). */
const SCALE_LABELS: Record<CurveLang, { peak: string; dailyAvg: string; typicalYear: string }> = {
  fr: { peak: 'pic ≈', dailyAvg: '/ jour en moyenne', typicalYear: 'profil — année type' },
  en: { peak: 'peak ≈', dailyAvg: '/ day on average', typicalYear: 'profile — typical year' },
  ar: { peak: 'الذروة ≈', dailyAvg: '/ يومياً في المتوسط', typicalYear: 'نمط — سنة نموذجية' },
};

/**
 * WJ16 — Construit le SVG de la courbe journalière production-vs-consommation.
 * `annualProdKwh` (backend `prod_kwh`) cale l'amplitude réelle ; absent/nul →
 * mode « année type » (forme normalisée, libellée). Aucune transition n'est
 * intégrée au SVG : l'animation vit dans la page, gatée reduced-motion.
 *
 * WJ80 — `lang` sélectionne les étiquettes horaires + le repère d'échelle
 * (FR/EN/AR) ; les tailles de police (7,5→8 → 9→9,5) sont relevées pour rester
 * lisibles sur petit écran, et le groupe de repère porte des `data-*` (déjà
 * formatés) qu'un petit script de la page lit au TAP (le survol/`<title>` est
 * invisible au tactile).
 *
 * WJ119 — `consumptionOptions` sélectionne le MODE (residentiel/industriel/
 * commercial/agricole) et la variante (normal/été/Ramadan) de la silhouette de
 * consommation — repli residentiel/normal (BASELINE_SHAPE), rétro-compatible :
 * un appelant qui n'en fournit pas obtient exactement le nouveau profil marocain
 * par défaut, jamais l'ancienne double-gaussienne.
 */
export function renderYearCurve(
  annualProdKwh: number | null | undefined,
  box: CurveBox = DEFAULT_CURVE_BOX,
  lang: CurveLang = 'fr',
  consumptionOptions: ConsumptionShapeOptions = {},
): DailyCurve {
  const annual = typeof annualProdKwh === 'number' && Number.isFinite(annualProdKwh) && annualProdKwh > 0
    ? annualProdKwh : null;
  const hasRealScale = annual !== null;

  const solar = pathFromProfile(solarProfile, box, true);
  const cons = pathFromProfile((h) => consumptionProfile(h, consumptionOptions), box, false);

  const plotH = box.height - box.padTop - box.padBottom;
  const baseY = box.padTop + plotH;

  // Étiquettes horaires (lever / midi / coucher) — repères de lecture neutres.
  const plotW = box.width - box.padLeft - box.padRight;
  const tickHours = [6, 13, 20] as const;
  const tickLabels = HOUR_TICK_LABELS[lang];
  const tickTexts = [tickLabels.sunrise, tickLabels.noon, tickLabels.sunset];
  const ticks = tickHours
    .map((h, i) => {
      const x = box.padLeft + ((h - HOUR_START) / HOURS) * plotW;
      return `<text x="${x.toFixed(2)}" y="${(box.height - 8).toFixed(2)}" text-anchor="middle" font-size="9" fill="var(--color-lune-faint, #8d96b4)">${esc(tickTexts[i])}</text>`;
    })
    .join('');

  const scale = SCALE_LABELS[lang];
  // Repère d'axe Y réel : production journalière moyenne (annuel / 365), libellée.
  let scaleLabel = '';
  if (hasRealScale) {
    const dailyAvg = annual! / 365;
    // Le pic horaire vaut env. dailyAvg / surface-sous-la-cloche (≈ 4,6 h équiv.).
    const peak = dailyAvg / 4.6;
    const peakFmt = fmtKwh(peak, lang);
    const avgFmt = fmtKwh(dailyAvg, lang);
    scaleLabel =
      `<g data-curve-scale data-peak="${esc(peakFmt)}" data-avg="${esc(avgFmt)}" tabindex="0" role="button" aria-label="${esc(scale.peak)} ${esc(peakFmt)}, ${esc(avgFmt)} ${esc(scale.dailyAvg)}">` +
      `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 8).toFixed(2)}" font-size="9" fill="var(--color-brass-300, #f3cc66)">${esc(scale.peak)} ${esc(peakFmt)}</text>` +
      `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 19).toFixed(2)}" font-size="8.5" fill="var(--color-lune-faint, #8d96b4)">${esc(avgFmt)} ${esc(scale.dailyAvg)}</text>` +
      `</g>`;
  } else {
    scaleLabel =
      `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 8).toFixed(2)}" font-size="9" fill="var(--color-lune-faint, #8d96b4)">${esc(scale.typicalYear)}</text>`;
  }

  const baseline = `<line x1="${box.padLeft}" y1="${baseY.toFixed(2)}" x2="${(box.width - box.padRight).toFixed(2)}" y2="${baseY.toFixed(2)}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>`;

  // Soleil décoratif (animé en CSS via la classe .curve-sun, statique sinon).
  const sunX = box.padLeft + plotW * ((13 - HOUR_START) / HOURS);
  const sunY = box.padTop + plotH * 0.18;
  const sun = `<circle class="curve-sun" cx="${sunX.toFixed(2)}" cy="${sunY.toFixed(2)}" r="6" fill="var(--color-brass-300, #f3cc66)" fill-opacity="0.9"/>`;

  // Longueur de tracé pour l'animation de dessin (dasharray en CSS).
  const descByLang: Record<CurveLang, string> = {
    fr: 'Production solaire estimée sur une journée type comparée à la consommation du foyer.',
    en: "Estimated solar production over a typical day compared to the household's consumption.",
    ar: 'الإنتاج الشمسي المقدّر خلال يوم نموذجي مقارنة باستهلاك المنزل.',
  };
  const titleByLang: Record<CurveLang, string> = {
    fr: 'Production vs consommation — journée type',
    en: 'Production vs consumption — typical day',
    ar: 'الإنتاج مقابل الاستهلاك — يوم نموذجي',
  };
  const desc = descByLang[lang];

  const svg =
    `<svg class="daily-curve" viewBox="0 0 ${box.width} ${box.height}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet" role="img" xmlns="http://www.w3.org/2000/svg">` +
    `<title>${esc(titleByLang[lang])}</title><desc>${esc(desc)}</desc>` +
    `<defs><linearGradient id="solarFill" x1="0" y1="0" x2="0" y2="1">` +
    `<stop offset="0%" stop-color="var(--color-brass-400, #e8b54a)" stop-opacity="0.42"/>` +
    `<stop offset="100%" stop-color="var(--color-brass-400, #e8b54a)" stop-opacity="0.04"/>` +
    `</linearGradient></defs>` +
    baseline +
    sun +
    `<path class="curve-solar-fill" d="${solar.d}" fill="url(#solarFill)" stroke="none"/>` +
    `<path class="curve-solar-line" d="${solar.d.replace(/ L[\d.]+ [\d.]+ L[\d.]+ [\d.]+ Z$/, '')}" fill="none" stroke="var(--color-brass-400, #e8b54a)" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<path class="curve-cons-line" d="${cons.d}" fill="none" stroke="var(--color-azur-300, #7fb4e8)" stroke-width="2" stroke-dasharray="4 3" stroke-linejoin="round" stroke-linecap="round"/>` +
    ticks +
    scaleLabel +
    `</svg>`;

  return { svg, hasRealScale };
}
