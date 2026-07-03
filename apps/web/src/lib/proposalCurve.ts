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
 *  - La forme horaire (cloche solaire + double-bosse de conso matin/soir) est un
 *    PROFIL physique standard normalisé à 1, jamais une donnée chiffrée affichée.
 *
 * Mouvement : l'animation (tracé de la courbe + soleil qui se lève) est gérée 100 %
 * en CSS dans la page et GATÉE derrière `prefers-reduced-motion: no-preference` —
 * ce module n'émet que la géométrie statique (zéro CLS, lisible sans JS ni motion).
 */

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

/**
 * Profil de consommation domestique normalisé (double bosse matin + soirée).
 * Valeur ∈ [0,1] par heure. Profil de charge résidentiel standard, illustratif.
 */
export function consumptionProfile(hour: number): number {
  const morning = Math.exp(-Math.pow((hour - 7.5) / 2.0, 2)); // pic matin
  const evening = Math.exp(-Math.pow((hour - 20) / 2.2, 2)) * 1.15; // pic soirée
  const base = 0.18; // veille permanente
  const v = base + 0.7 * morning + 0.85 * evening;
  return Math.min(1, v);
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
 */
export function renderYearCurve(
  annualProdKwh: number | null | undefined,
  box: CurveBox = DEFAULT_CURVE_BOX,
  lang: CurveLang = 'fr',
): DailyCurve {
  const annual = typeof annualProdKwh === 'number' && Number.isFinite(annualProdKwh) && annualProdKwh > 0
    ? annualProdKwh : null;
  const hasRealScale = annual !== null;

  const solar = pathFromProfile(solarProfile, box, true);
  const cons = pathFromProfile(consumptionProfile, box, false);

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
