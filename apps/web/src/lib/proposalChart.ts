/**
 * P2 — Graphe « production estimée vs consommation » de la PROPOSITION client.
 *
 * Constructeur PUR de chaîne SVG (aucun DOM, aucun réseau, aucune dépendance) qui
 * reprend le LANGAGE VISUEL des graphes de l'estimateur pro-11
 * (`roofPro11/graphs.renderYearGraph`) : 12 barres mensuelles, ligne de base fine,
 * étiquettes de mois courtes, `<title>` au survol. Ici on COMPARE deux séries —
 * la production solaire estimée (barres LAITON `--color-brass-400`) et la
 * consommation électrique du client (barres AZUR `--color-azur-*`) — côte à côte
 * par mois.
 *
 * Discipline « zéro chiffre inventé » : on ne dessine QUE les valeurs reçues du
 * backend (les tableaux Q6 `monthly_production` / `monthly_consumption`). Une série
 * vide/absente est simplement omise ; les deux vides → on n'émet aucune barre.
 *
 * Volontairement SELF-CONTAINED (pas d'import de `productionWindow`) pour ne pas
 * tirer toute la chaîne de l'estimateur (productionEngine/estimatorBrainV2/roof…)
 * dans la page de proposition : la géométrie de barres et le format kWh sont
 * triviaux et reproduits ici à l'identique du langage pro-11.
 */

/** Étiquettes mensuelles courtes FR (index 0 = janvier) — alignées sur pro-11. */
export const MONTH_LABELS_FR = [
  'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
  'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
];

/**
 * WJ80 — Étiquettes mensuelles courtes EN/AR (mêmes index 0 = janvier). Le
 * graphe le plus persuasif de la page restait français-only jusqu'ici, même
 * en mode anglais/arabe — ces paires couvrent le même contrat que `data-i18n`
 * ailleurs sur la page (jamais un repli français sous un bouton EN/AR actif).
 */
export const MONTH_LABELS_EN = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];
export const MONTH_LABELS_AR = [
  'ينا', 'فبر', 'مار', 'أبر', 'ماي', 'يون',
  'يول', 'غشت', 'شتن', 'أكت', 'نون', 'دجن',
];

export type ChartLang = 'fr' | 'en' | 'ar';

/** WJ80 — Choisit le jeu d'étiquettes de mois selon la langue courante. */
export function monthLabelsFor(lang: ChartLang): string[] {
  if (lang === 'ar') return MONTH_LABELS_AR;
  if (lang === 'en') return MONTH_LABELS_EN;
  return MONTH_LABELS_FR;
}

/** Format kWh entier FR (séparateur de milliers = espace fine) — « 1 240 kWh ». */
export function fmtKwh(n: number, lang: ChartLang = 'fr'): string {
  const v = Number.isFinite(n) && n > 0 ? n : 0;
  const grouped = Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  // WJ80 — même séparateur de milliers dans les trois langues (convention
  // numérique déjà utilisée ailleurs sur la page en EN/AR) ; seule l'unité
  // reste "kWh" partout (unité SI, non traduite).
  void lang;
  return `${grouped} kWh`;
}

/** Échappe le texte injecté dans le SVG (`<title>` notamment). */
function esc(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Boîte SVG (mêmes proportions que le graphe ANNÉE de pro-11). */
export interface ChartBox {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}

export const DEFAULT_CHART_BOX: ChartBox = {
  width: 360,
  height: 150,
  padLeft: 8,
  padRight: 8,
  padTop: 10,
  padBottom: 20,
};

/** Normalise un tableau mensuel : exactement 12 valeurs finies ≥ 0, sinon `null`. */
function sanitizeMonthly(arr: unknown): number[] | null {
  if (!Array.isArray(arr) || arr.length !== 12) return null;
  let any = false;
  const out = arr.map((v) => {
    const n = typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : 0;
    if (n > 0) any = true;
    return n;
  });
  return any ? out : null;
}

/** Quelle(s) série(s) présenter, après nettoyage défensif. */
export interface ChartSeries {
  production: number[] | null;
  consumption: number[] | null;
  /** `comparison` (les deux), `production` (prod seule), `none` (rien à dessiner). */
  mode: 'comparison' | 'production' | 'none';
}

/**
 * Décide du mode d'affichage à partir des tableaux Q6 bruts :
 *  - production + consommation présentes → comparaison ;
 *  - production seule → production seule ;
 *  - production absente → rien (on n'affiche jamais une conso « solo » : sans
 *    production il n'y a pas d'histoire à raconter sur cette page).
 */
export function resolveSeries(
  monthlyProduction: unknown,
  monthlyConsumption: unknown,
): ChartSeries {
  const production = sanitizeMonthly(monthlyProduction);
  const consumption = sanitizeMonthly(monthlyConsumption);
  if (!production) return { production: null, consumption: null, mode: 'none' };
  if (consumption) return { production, consumption, mode: 'comparison' };
  return { production, consumption: null, mode: 'production' };
}

/** Rectangle d'une barre (coordonnées SVG). */
interface BarRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Géométrie de barres groupées par mois. Pour chaque mois on place 1 ou 2 barres
 * (production puis consommation) dans le « slot » du mois ; l'échelle Y est
 * COMMUNE aux deux séries (pic global = pleine hauteur) pour que la comparaison
 * soit honnête. Toute valeur ≤ 0 → hauteur 0 (jamais de NaN). Déterministe.
 */
export function barGroups(
  production: number[],
  consumption: number[] | null,
  box: ChartBox = DEFAULT_CHART_BOX,
): { prod: BarRect[]; cons: BarRect[] } {
  const plotW = box.width - box.padLeft - box.padRight;
  const plotH = box.height - box.padTop - box.padBottom;
  const baseY = box.padTop + plotH;
  const seriesCount = consumption ? 2 : 1;
  let max = 0;
  for (const v of production) max = Math.max(max, v);
  if (consumption) for (const v of consumption) max = Math.max(max, v);

  const slot = plotW / 12;
  const gap = slot * 0.22; // marge inter-mois
  const groupW = slot - gap;
  const barW = groupW / seriesCount;

  const rectFor = (value: number, monthIndex: number, seriesIndex: number): BarRect => {
    const h = max > 0 ? (Math.max(0, value) / max) * plotH : 0;
    const x = box.padLeft + monthIndex * slot + gap / 2 + seriesIndex * barW;
    const y = baseY - h;
    return { x, y, width: barW, height: h };
  };

  const prod = production.map((v, m) => rectFor(v, m, 0));
  const cons = consumption ? consumption.map((v, m) => rectFor(v, m, 1)) : [];
  return { prod, cons };
}

const BRASS = 'var(--color-brass-400, #e8b54a)';
const AZUR = 'var(--color-azur-300, #7fb4e8)';
const FAINT = 'var(--color-lune-faint, #8d96b4)';
const RULE = 'var(--color-white, #fff)';

/**
 * WJ80 — Chaque barre porte désormais, EN PLUS du `<title>` (survol souris,
 * invisible au tactile), des attributs `data-*` (mois/valeur/série déjà
 * formatés dans la langue courante) qu'un petit script de la page lit au
 * TAP pour afficher une légende « tap-to-reveal » sous le graphe — le tactile
 * (l'essentiel du trafic proposition) retrouve ainsi la même information que
 * la souris.
 */
function barsSvg(
  rects: BarRect[],
  fill: string,
  fillOpacity: number,
  kind: 'production' | 'consumption',
  monthLabels: string[],
  values: number[],
  lang: ChartLang,
): string {
  return rects
    .map((r, i) => {
      if (r.height <= 0) return '';
      const label = `${esc(monthLabels[i])} · ${esc(kindLabel(kind, lang))} ${esc(fmtKwh(values[i], lang))}`;
      return (
        `<rect x="${r.x.toFixed(2)}" y="${r.y.toFixed(2)}" width="${r.width.toFixed(2)}" height="${r.height.toFixed(2)}" rx="1.5" fill="${fill}" fill-opacity="${fillOpacity}" ` +
        `data-chart-bar data-kind="${kind}" data-month="${esc(monthLabels[i])}" data-value="${esc(fmtKwh(values[i], lang))}" tabindex="0" role="button" ` +
        `aria-label="${label}"><title>${label}</title></rect>`
      );
    })
    .join('');
}

/** WJ80 — Libellé de série (« production »/« consommation ») dans la langue courante. */
function kindLabel(kind: 'production' | 'consumption', lang: ChartLang): string {
  const labels: Record<ChartLang, { production: string; consumption: string }> = {
    fr: { production: 'production', consumption: 'consommation' },
    en: { production: 'production', consumption: 'consumption' },
    ar: { production: 'الإنتاج', consumption: 'الاستهلاك' },
  };
  return labels[lang][kind];
}

/**
 * WJ80 — Annotation visible du pic mensuel + total annuel de production,
 * directement dans le SVG (pas seulement dans le texte alentour de la page) :
 * lisible même quand le graphe est partagé/imprimé isolément. Calculée
 * UNIQUEMENT depuis les valeurs backend déjà dessinées — jamais un chiffre
 * inventé. Positionnée en haut-gauche de la zone de tracé, comme le repère
 * "pic ≈" de la courbe journalière (WJ16), pour un langage visuel cohérent.
 */
function peakAnnualLabel(production: number[], lang: ChartLang, box: ChartBox): string {
  const peak = Math.max(...production);
  const total = production.reduce((a, b) => a + b, 0);
  const texts: Record<ChartLang, { peak: string; total: string }> = {
    fr: { peak: `pic ≈ ${fmtKwh(peak, lang)}/mois`, total: `${fmtKwh(total, lang)}/an` },
    en: { peak: `peak ≈ ${fmtKwh(peak, lang)}/month`, total: `${fmtKwh(total, lang)}/year` },
    ar: { peak: `الذروة ≈ ${fmtKwh(peak, lang)}/شهر`, total: `${fmtKwh(total, lang)}/سنة` },
  };
  const t = texts[lang];
  return (
    `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 8).toFixed(2)}" font-size="9" fill="var(--color-brass-300, #f3cc66)">${esc(t.peak)}</text>` +
    `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 19).toFixed(2)}" font-size="8.5" fill="${FAINT}">${esc(t.total)}</text>`
  );
}

/**
 * Construit le SVG inline du graphe production-vs-consommation à partir des
 * tableaux Q6 (12 valeurs chacun ; vides/absents → série omise). Renvoie une
 * chaîne VIDE quand il n'y a rien d'honnête à dessiner (`mode === 'none'`) — la
 * page peut alors omettre tout le bloc graphe.
 *
 * Le SVG porte `role="img"` + un `<title>`/`<desc>` accessibles, un `viewBox`
 * responsive (largeur 100 %, hauteur réservée → zéro CLS), une ligne de base
 * fine et les étiquettes de mois courtes. Aucune transition (mouvement réduit).
 *
 * WJ80 — `lang` sélectionne les étiquettes de mois (FR/EN/AR) et l'annotation
 * pic/annuel ; la page appelle cette fonction une seconde fois (re-render, pas
 * de dual-node ici — le SVG est injecté via `set:html`) à chaque bascule de
 * langue. Les tailles de police (7→9/9.5) sont relevées pour rester lisibles
 * sur les petits écrans (l'essentiel du trafic de cette page).
 */
export function renderProposalChart(
  monthlyProduction: unknown,
  monthlyConsumption: unknown,
  box: ChartBox = DEFAULT_CHART_BOX,
  lang: ChartLang = 'fr',
): string {
  const series = resolveSeries(monthlyProduction, monthlyConsumption);
  if (series.mode === 'none' || !series.production) return '';

  const { prod, cons } = barGroups(series.production, series.consumption, box);
  const baseY = box.padTop + (box.height - box.padTop - box.padBottom);
  const monthLabels = monthLabelsFor(lang);

  const prodBars = barsSvg(prod, BRASS, 0.92, 'production', monthLabels, series.production, lang);
  const consBars = series.consumption
    ? barsSvg(cons, AZUR, 0.85, 'consumption', monthLabels, series.consumption, lang)
    : '';

  // Étiquettes de mois, centrées sous chaque slot. Taille relevée (7→9) pour
  // rester lisible sur les petits écrans — le graphe le plus consulté sur
  // mobile de toute la page (WJ80).
  const plotW = box.width - box.padLeft - box.padRight;
  const slot = plotW / 12;
  const labels = monthLabels.map((lbl, m) => {
    const cx = box.padLeft + m * slot + slot / 2;
    return `<text x="${cx.toFixed(2)}" y="${(box.height - 6).toFixed(2)}" text-anchor="middle" font-size="9" fill="${FAINT}">${esc(lbl)}</text>`;
  }).join('');

  const baseline = `<line x1="${box.padLeft}" y1="${baseY.toFixed(2)}" x2="${(box.width - box.padRight).toFixed(2)}" y2="${baseY.toFixed(2)}" stroke="${RULE}" stroke-opacity="0.12" stroke-width="1"/>`;

  const peakAnnual = peakAnnualLabel(series.production, lang, box);

  const descByLang: Record<ChartLang, { comparison: string; production: string; title: string }> = {
    fr: {
      comparison: 'Production solaire estimée comparée à la consommation électrique, par mois.',
      production: 'Production solaire estimée par mois.',
      title: 'Production vs consommation',
    },
    en: {
      comparison: 'Estimated solar production compared to electricity consumption, per month.',
      production: 'Estimated solar production per month.',
      title: 'Production vs consumption',
    },
    ar: {
      comparison: 'الإنتاج الشمسي المقدّر مقارنة بالاستهلاك الكهربائي، شهرياً.',
      production: 'الإنتاج الشمسي المقدّر شهرياً.',
      title: 'الإنتاج مقابل الاستهلاك',
    },
  };
  const d = descByLang[lang];
  const desc = series.mode === 'comparison' ? d.comparison : d.production;

  return `<svg viewBox="0 0 ${box.width} ${box.height}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet" role="img" xmlns="http://www.w3.org/2000/svg"><title>${esc(d.title)}</title><desc>${esc(desc)}</desc>${baseline}${prodBars}${consBars}${labels}${peakAnnual}</svg>`;
}
