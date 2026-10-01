/**
 * QJR664 — « Une journée type » du tunnel /devis/mon-toit, partagé par les
 * trois pages (fr / en / ar). Décision fondateur 01/10/2026 : le graphe est
 * montré dans les trois langues (avant : copie inline FR seulement).
 *
 * Production (doré #eda100, fond 18 %) vs consommation (bleu #2a78d6,
 * pointillé [6,3]) sur 24 h, 4 petits multiples (janvier/avril/juillet/
 * novembre). `hasJourTypeData()` (lib/jourTypeData.ts) reste la garde « zéro
 * chiffre inventé » : faux → la section est masquée ENTIÈREMENT.
 *
 * Le graphe montre la journée d'un foyer REPRÉSENTATIF, pas la consommation du
 * visiteur — la note du bloc (propre à chaque page) le dit.
 */
import {
  JOUR_TYPE_DATA,
  JOUR_TYPE_MONTH_IDS,
  JOUR_TYPE_MONTH_LABELS,
  hasJourTypeData,
} from '../../lib/jourTypeData';

export type JourTypeLang = 'fr' | 'en' | 'ar';

interface JourTypeCopy {
  aria: string;
  prod: string;
  conso: string;
  captionConso: string;
  captionProd: string;
  captionAuto: string;
  captionSurplus: string;
  kwh: string;
}

const COPY: Record<JourTypeLang, JourTypeCopy> = {
  fr: {
    aria: 'Production (doré) et consommation (bleu pointillé) sur 24 h, en kW',
    prod: 'Production (kW)',
    conso: 'Consommation (kW)',
    captionConso: 'Conso',
    captionProd: 'Prod',
    captionAuto: 'Autoconso',
    captionSurplus: 'Surplus',
    kwh: 'kWh',
  },
  en: {
    aria: 'Production (gold) and consumption (dashed blue) over 24 h, in kW',
    prod: 'Production (kW)',
    conso: 'Consumption (kW)',
    captionConso: 'Usage',
    captionProd: 'Output',
    captionAuto: 'Self-consumed',
    captionSurplus: 'Surplus',
    kwh: 'kWh',
  },
  ar: {
    aria: 'الإنتاج (ذهبي) والاستهلاك (أزرق متقطع) على مدى 24 ساعة، بالكيلوواط',
    prod: 'الإنتاج (كيلوواط)',
    conso: 'الاستهلاك (كيلوواط)',
    captionConso: 'الاستهلاك',
    captionProd: 'الإنتاج',
    captionAuto: 'الاستهلاك الذاتي',
    captionSurplus: 'الفائض',
    kwh: 'ك.و.س',
  },
};

export function jourTypeChartSvg(
  prodKw: number[],
  consoKw: number[],
  w: number,
  h: number,
  pad: number,
  lang: JourTypeLang = 'fr',
): string {
  const c = COPY[lang];
  const max = Math.max(0.001, ...prodKw, ...consoKw);
  const x = (i: number) => pad + (i / (prodKw.length - 1)) * (w - 2 * pad);
  const y = (v: number) => pad + (1 - v / max) * (h - 2 * pad);
  const lineOf = (arr: number[]) => `M${arr.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' L')}`;
  const prodLine = lineOf(prodKw);
  const prodArea = `${prodLine} L${x(prodKw.length - 1).toFixed(1)},${(h - pad).toFixed(1)} L${x(0).toFixed(1)},${(h - pad).toFixed(1)} Z`;
  const consoLine = lineOf(consoKw);
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="120" preserveAspectRatio="none" role="img" aria-label="${c.aria}">` +
    `<path d="${prodArea}" fill="rgba(237,161,0,0.18)" stroke="none"></path>` +
    `<path d="${prodLine}" fill="none" stroke="#eda100" stroke-width="2"><title>${c.prod}</title></path>` +
    `<path d="${consoLine}" fill="none" stroke="#2a78d6" stroke-width="2" stroke-dasharray="6,3"><title>${c.conso}</title></path>` +
    `</svg>`;
}

/** Rend le bloc `#mt-jourtype-wrap` / `#mt-jourtype-grid` dans la langue donnée. */
export function renderJourType(lang: JourTypeLang, doc: Document = document): void {
  const wrap = doc.getElementById('mt-jourtype-wrap');
  const grid = doc.getElementById('mt-jourtype-grid');
  if (!wrap || !grid) return;
  if (!hasJourTypeData()) {
    wrap.hidden = true;
    return;
  }
  const c = COPY[lang];
  const n = (v: number) => `${v.toFixed(2)}&nbsp;${c.kwh}`;
  let markup = '';
  for (const m of JOUR_TYPE_MONTH_IDS) {
    const d = JOUR_TYPE_DATA[m];
    if (!d) continue;
    const label = JOUR_TYPE_MONTH_LABELS[m][lang];
    markup += `<div class="border border-white/10 bg-white/5 p-2">` +
      `<p class="text-xs font-semibold text-white">${label}</p>` +
      jourTypeChartSvg(d.prodKw, d.consoKw, 280, 120, 6, lang) +
      `<p class="mt-1 text-[11px] text-lune-faint">${c.captionConso} ${n(d.consoJourKwh)} · ${c.captionProd} ${n(d.prodJourKwh)} · ${c.captionAuto} ${n(d.autoconsommeKwh)} · ${c.captionSurplus} ${n(d.surplusKwh)}</p>` +
      `</div>`;
  }
  grid.innerHTML = markup;
  wrap.hidden = false;
}
