// @vitest-environment jsdom
//
// PARCOURS UTILISATEUR COMPLET (jsdom) — la vérification « marche comme un vrai
// utilisateur » de bout en bout du constructeur de toiture 3D /preview/toiture-3d-pro-11.
// Là où les tests de moteur (V7/V8) prouvent les maths en PUR et où le harnais d'exécution
// (estimatorRuntimePro10Pro11) couvre chaque feature isolément, CE fichier MONTE le
// constructeur UNE fois et déroule une SESSION RÉSIDENTIELLE RÉELLE du début à la fin —
// facture → type de toit → tracé → recommandation → verrou d'axe → obstacle → édition de
// disposition → affinage de consommation → portées de production → multi-zones → handoff —
// en vérifiant à CHAQUE étape des INVARIANTS D'HONNÊTETÉ : aucun NaN/Infinity/undefined
// rendu, économies ≤ plafond facture (facture × 12), panneaux ≤ le besoin, couverture
// cohérente, et JAMAIS de POST de lead (/api/preview-lead ni /api/simulate).
//
// La scène 3D GPU ne peut pas rendre en jsdom (couverte ailleurs) — ici on se concentre
// sur les flux DONNÉES / DOM de l'utilisateur. Le harnais de montage (FakeMap mock, setupDom
// avec tous les ids rp9-*, initRoofToolPro8, le tracé par clics) est CALQUÉ sur
// estimatorRuntimePro10Pro11.test.ts (même convention de fichier auto-suffisant).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createRoofTypeSelect } from '../src/lib/roofTypeSelect';
import { zoomToFitRing } from '../src/lib/roof';
import { PITCH_VIEW } from '../src/scripts/roofPro11/constants';

// ── MapLibre mock : un faux Map qui capture les handlers et n'instancie AUCUN WebGL.
//    addLayer N'APPELLE PAS onAdd → le calque Three.js ne démarre jamais → sceneRoot reste
//    null → renderScene s'auto-annule. L'optimiseur + le DOM tournent quand même.
const fakeMaps: FakeMap[] = [];
class FakeMap {
  handlers: Record<string, ((e: unknown) => void)[]> = {};
  controls: unknown[] = [];
  flyToCalls: unknown[] = [];
  jumpToCalls: unknown[] = [];
  doubleClickZoom = { disable() {}, enable() {} };
  dragPan = { disable() {}, enable() {} };
  constructor() {
    fakeMaps.push(this);
  }
  on(ev: string, h: (e: unknown) => void) {
    (this.handlers[ev] ||= []).push(h);
    return this;
  }
  fire(ev: string, e: unknown) {
    (this.handlers[ev] || []).forEach((h) => h(e));
  }
  addControl(ctrl: unknown) { this.controls.push(ctrl); return this; }
  addLayer() { return this; }
  addSource() { return this; }
  sourceData: Record<string, unknown> = {};
  getSource(id?: string) {
    const self = this;
    return { setData(d: unknown) { if (id) self.sourceData[id] = d; } };
  }
  getLayer() { return null; }
  removeLayer() {}
  easeTo() { return this; }
  flyTo(opts: unknown) { this.flyToCalls.push(opts); return this; }
  jumpTo(opts: unknown) { this.jumpToCalls.push(opts); return this; }
  getBearing() { return 0; }
  getCanvas() { return { style: {} as Record<string, string>, width: 800, height: 600 }; }
  getContainer() { return document.getElementById('rp9-map'); }
  queryHits: Record<string, Array<{ properties: Record<string, unknown> }>> = {};
  queryRenderedFeatures(_pt: unknown, opts?: { layers?: string[] }) {
    const layer = opts?.layers?.[0];
    return (layer && this.queryHits[layer]) || [];
  }
  triggerRepaint() {}
  project() { return { x: 0, y: 0 }; }
  unproject() { return { lng: 0, lat: 0 }; }
  remove() {}
  setStyle() {}
}

vi.mock('maplibre-gl', () => {
  class NavigationControl {}
  class GeolocateControl {
    geoHandlers: Record<string, ((e: unknown) => void)[]> = {};
    on(ev: string, h: (e: unknown) => void) { (this.geoHandlers[ev] ||= []).push(h); return this; }
    fire(ev: string, e: unknown) { (this.geoHandlers[ev] || []).forEach((h) => h(e)); }
  }
  class Point {
    x: number; y: number;
    constructor(x: number, y: number) { this.x = x; this.y = y; }
  }
  const MercatorCoordinate = {
    fromLngLat: () => ({ x: 0, y: 0, z: 0, meterInMercatorCoordinateUnits: () => 1e-7 }),
  };
  // Acceptation ACAL490 — un document rouvert sur un pan actif VIDE porte désormais son épingle :
  // l'atelier y plante le repère du site (marqueur inerte, comme dans estimatorRuntimePro10Pro11).
  class Marker {
    setLngLat() { return this; }
    addTo() { return this; }
    remove() { return this; }
  }
  const api = { Map: FakeMap, NavigationControl, GeolocateControl, Marker, Point, MercatorCoordinate, GeoJSONSource: class {} };
  return { default: api, ...api };
});

// Un carré de `side` mètres autour d'un point — 4 coins lng/lat pour tracer un toit.
function squareCorners(side: number, lng0 = -7.62, lat0 = 33.59): [number, number][] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

const ID_INPUTS = ['rp9-bill', 'rp9-address', 'rp9-need-input', 'rp9-cible-kwh', 'rp9-obs-length', 'rp9-obs-width'];
const ID_RANGES = ['rp9-tilt-range', 'rp9-pitch-range'];
const ID_BUTTONS = [
  'rp9-finish', 'rp9-clear', 'rp9-undo-point', 'rp9-need-minus', 'rp9-need-plus', 'rp9-tilt-reco',
  'rp9-obstacle', 'rp9-obstacle-clear', 'rp9-obs-delete', 'rp9-obs-plus', 'rp9-obs-minus',
  'rp9-optimum', 'rp9-optimum-apply', 'rp9-cta',
  'rp9-prod-month-prev', 'rp9-prod-month-next',
  'rp9-prod-day-prev', 'rp9-prod-day-next', 'rp9-prod-day-reset',
  'rp9-add-area',
  // W68/W69 — affinage de consommation + édition de disposition.
  'rp9-cons-toggle', 'rp9-cons-recal', 'rp9-cons-reset', 'rp9-appl-add', 'rp9-cons-seasonal-toggle',
  'rp9-layout-toggle', 'rp9-layout-plus', 'rp9-layout-minus', 'rp9-layout-reset',
];
const ID_GENERIC = [
  'rp9-map', 'rp9-status', 'rp9-bill-kwh', 'rp9-config', 'rp9-azimuth-group', 'rp9-compass-arrow',
  'rp9-area-value', 'rp9-need-note', 'rp9-tilt-value', 'rp9-obs-edit', 'rp9-obs-dims',
  'rp9-optimum-note', 'rp9-optimum-card', 'rp9-optimum-label', 'rp9-optimum-source', 'rp9-optimum-kwc',
  'rp9-optimum-panels', 'rp9-optimum-prod', 'rp9-optimum-cover', 'rp9-optimum-why',
  'rp9-flat-controls', 'rp9-flat-only', 'rp9-pitched-controls', 'rp9-pitch-value', 'rp9-pitched-note', 'rp9-facing-note',
  'rp9-reco-title', 'rp9-reco-kwc', 'rp9-reco-panels', 'rp9-reco-prod', 'rp9-reco-cover',
  'rp9-reco-savings', 'rp9-reco-why', 'rp9-reco-bifacial', 'rp9-reco-band', 'rp9-results',
  'rp9-maxline', 'rp9-compare-wrap',
  'rp9-prod-window', 'rp9-prod-scope', 'rp9-prod-month-picker', 'rp9-prod-month-label',
  'rp9-prod-day-picker', 'rp9-prod-day-label', 'rp9-prod-headline', 'rp9-prod-sub',
  'rp9-prod-graph', 'rp9-prod-source', 'rp9-prod-savings',
  'rp9-areas-window', 'rp9-areas-list', 'rp9-areas-total-panels', 'rp9-areas-total-kwc',
  'rp9-areas-total-prod', 'rp9-areas-total-savings',
  // W68/W69 — conteneurs des fenêtres conso + disposition.
  'rp9-cons-window', 'rp9-cons-panel', 'rp9-cons-total', 'rp9-cons-self', 'rp9-cons-savings',
  'rp9-cons-batt', 'rp9-cons-payback', 'rp9-cons-graph', 'rp9-cons-inputs', 'rp9-cons-month-chart',
  'rp9-cons-seasonal-controls', 'rp9-appl-ac', 'rp9-appl-ev', 'rp9-ac-watts', 'rp9-ev-note',
  'rp9-appl-note', 'rp9-appl-list',
  'rp9-layout-window', 'rp9-layout-panel', 'rp9-layout-count', 'rp9-layout-kwc', 'rp9-layout-free',
  'rp9-layout-cover', 'rp9-layout-grid', 'rp9-layout-note',
];

const CHIP_GROUPS: { attr: string; values: string[]; badge?: boolean }[] = [
  { attr: 'data-rooftype', values: ['flat', 'pitched'] },
  { attr: 'data-family', values: ['south', 'eastwest'], badge: true },
  { attr: 'data-tilt', values: ['reco', '29', '15', '10'], badge: true },
  { attr: 'data-orient', values: ['auto', 'portrait', 'landscape'], badge: true },
  { attr: 'data-azimuth', values: ['south', 'aligned'], badge: true },
  { attr: 'data-margin', values: ['keep', 'remove'], badge: true },
  { attr: 'data-pitch', values: ['15', '22', '30', '45'] },
  { attr: 'data-facing', values: ['180', '135', '225', '90', '270'] },
];

function el(tag: string, id?: string): HTMLElement {
  const e = document.createElement(tag);
  if (id) e.id = id;
  return e;
}

/** Construit un DOM minimal mais COMPLET (tous les ids/attributs que le script interroge). */
function setupDom() {
  const grad = { addColorStop() {} };
  const ctx2d = new Proxy(
    {},
    {
      get(_t, prop) {
        if (prop === 'createLinearGradient' || prop === 'createRadialGradient' || prop === 'createPattern') return () => grad;
        if (prop === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
        if (prop === 'measureText') return () => ({ width: 0 });
        if (prop === 'canvas') return { width: 512, height: 280 };
        return () => undefined;
      },
      set() {
        return true;
      },
    },
  );
  (HTMLCanvasElement.prototype as unknown as { getContext: () => unknown }).getContext = () => ctx2d;
  document.body.innerHTML = '';
  const root = el('div');
  for (const id of ID_GENERIC) root.appendChild(el('div', id));
  for (const id of ID_INPUTS) root.appendChild(el('input', id));
  for (const id of ID_RANGES) {
    const r = el('input', id) as HTMLInputElement;
    r.type = 'range';
    root.appendChild(r);
  }
  for (const id of ID_BUTTONS) root.appendChild(el('button', id));
  // <select> de l'affinage conso (appareil, BTU, chargeur) + facteurs saisonniers.
  for (const id of ['rp9-appl-kind', 'rp9-ac-btu', 'rp9-ev-kw']) root.appendChild(el('select', id));
  for (const id of ['rp9-ac-eer', 'rp9-ac-hours', 'rp9-ev-hours', 'rp9-ev-km', 'rp9-cons-summer', 'rp9-cons-winter']) {
    root.appendChild(el('input', id));
  }
  const form = el('form', 'rp9-search');
  root.appendChild(form);
  root.appendChild(el('ul', 'rp9-suggestions'));
  for (const g of CHIP_GROUPS) {
    for (const v of g.values) {
      const b = el('button') as HTMLButtonElement;
      b.setAttribute(g.attr, v);
      b.setAttribute('aria-pressed', 'false');
      if (g.badge) {
        const badge = el('span');
        badge.className = 'rp9-reco-badge';
        badge.hidden = true;
        b.appendChild(badge);
      }
      root.appendChild(b);
    }
  }
  const scopeWrap = root.querySelector('#rp9-prod-scope');
  if (scopeWrap) {
    for (const v of ['year', 'month', 'day']) {
      const b = el('button') as HTMLButtonElement;
      b.setAttribute('data-prod-scope', v);
      b.setAttribute('aria-pressed', String(v === 'year'));
      scopeWrap.appendChild(b);
    }
  }
  const table = el('table');
  const thead = el('thead');
  for (const key of ['placedCount', 'annualKwh', 'pctOfTarget']) {
    const th = el('th');
    const btn = el('button') as HTMLButtonElement;
    btn.setAttribute('data-rp9-sort', key);
    const arrow = el('span');
    arrow.className = 'rp9-sort-arrow';
    btn.appendChild(arrow);
    th.appendChild(btn);
    thead.appendChild(th);
  }
  table.appendChild(thead);
  const tbody = el('tbody', 'rp9-compare');
  table.appendChild(tbody);
  root.appendChild(table);
  const filter = el('select', 'rp9-matrix-filter');
  root.appendChild(filter);
  // Champs du diagnostic enrichi que prefillLead pré-remplit (handoff, jamais un POST).
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
  const diag = el('details', 'diag') as HTMLDetailsElement;
  diag.appendChild(el('input', 'lf-area'));
  const orient = el('select', 'lf-orient') as HTMLSelectElement;
  for (const id of ['sud', 'sud-est', 'sud-ouest', 'est', 'ouest']) {
    const o = document.createElement('option');
    o.value = id;
    orient.appendChild(o);
  }
  diag.appendChild(orient);
  diag.appendChild(el('input', 'lf-kwc-est'));
  root.appendChild(diag);
  root.appendChild(el('div', 'simulateur'));
  document.body.appendChild(root);
}

async function loadTool() {
  const mod = await import('../src/scripts/roof-tool-pro11.ts');
  return mod.initRoofToolPro8;
}

function setBill(v: string) {
  const bill = document.getElementById('rp9-bill') as HTMLInputElement;
  bill.value = v;
  bill.dispatchEvent(new window.Event('input', { bubbles: true }));
}

/** Trace un toit : 4 clics carte (timer 240 ms entre chaque) puis « Terminer ». */
function traceRoof(map: FakeMap, side = 16, lng0 = -7.62, lat0 = 33.59) {
  vi.useFakeTimers();
  for (const [lng, lat] of squareCorners(side, lng0, lat0)) {
    map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
    vi.advanceTimersByTime(241);
  }
  vi.useRealTimers();
  (document.getElementById('rp9-finish') as HTMLButtonElement).click();
}

/** Laisse résoudre les promesses (warming PVGIS/production async) + le débattement 280 ms. */
async function flush() {
  for (let i = 0; i < 25; i++) await Promise.resolve();
  await new Promise((r) => setTimeout(r, 350));
  for (let i = 0; i < 25; i++) await Promise.resolve();
}

const txt = (id: string) => document.getElementById(id)?.textContent ?? '';

/** Premier entier (sépare les espaces fines françaises) du texte d'un id. */
const intOf = (id: string): number => Number((txt(id).match(/[\d   ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));
/** kWc décimal (français) du texte d'un id. */
const kwcOf = (id: string): number => {
  const m = txt(id).match(/[\d   ]+(?:[.,]\d+)?/);
  return m ? Number(m[0].replace(/[   ]/g, '').replace(',', '.')) : 0;
};
/** Borne haute (le plus grand nombre) d'un texte « X – Y/an ». */
function highNum(id: string): number {
  const nums = (txt(id).match(/[\d   ]+/g) ?? []).map((s) => Number(s.replace(/[^\d]/g, ''))).filter((n) => n > 0);
  return nums.length ? Math.max(...nums) : 0;
}

/** INVARIANT D'HONNÊTETÉ universel : aucun chiffre rendu ne contient NaN/Infinity/undefined. */
function assertNoGarbage(ids: string[]) {
  for (const id of ids) {
    const s = txt(id);
    expect(s, `${id} ne doit jamais montrer NaN`).not.toMatch(/NaN/);
    expect(s, `${id} ne doit jamais montrer Infinity`).not.toMatch(/Infinity/i);
    expect(s, `${id} ne doit jamais montrer "undefined"`).not.toMatch(/undefined/);
  }
}

const RECO_IDS = ['rp9-reco-kwc', 'rp9-reco-panels', 'rp9-reco-prod', 'rp9-reco-cover', 'rp9-reco-savings', 'rp9-reco-title'];

/** Mock fetch pour les flux qui ont besoin d'une vraie production (fenêtre conso/prod) :
 *  /api/roof-production renvoie une fixture par-kWc mise à l'échelle ; /api/roof-yield un
 *  rendement plausible. Toute URL est enregistrée pour la garde « aucun POST de lead ». */
const PANEL_KWC_TEST = 0.72;
function perKwcFixture() {
  const monthly = [80, 90, 120, 140, 160, 175, 180, 170, 145, 120, 95, 75];
  const annual = monthly.reduce((a, b) => a + b, 0);
  const daysIn = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const bell = (peak: number) => {
    const out = new Array<number>(24).fill(0);
    for (let h = 6; h <= 18; h++) {
      const x = (h - 12) / 4;
      out[h] = peak * Math.exp(-0.5 * x * x);
    }
    return out;
  };
  const typicalDayByMonth: number[][] = [];
  const dailyKwhByMonth: number[] = [];
  for (let m = 0; m < 12; m++) {
    const targetDaily = monthly[m] / daysIn[m];
    const shape = bell(1);
    const shapeSum = shape.reduce((a, b) => a + b, 0);
    const k = shapeSum > 0 ? targetDaily / shapeSum : 0;
    const prof = shape.map((v) => v * k);
    typicalDayByMonth.push(prof);
    dailyKwhByMonth.push(prof.reduce((a, b) => a + b, 0));
  }
  return { annual, monthly, typicalDayByMonth, dailyKwhByMonth };
}
/** ACAL982 (revue) — rendement par kWc d'UN plan (lat, inclinaison, aspect PVGIS) : un nombre fixe, ou la table
 *  COMMITTÉE (`specificYield`) pour que les deux routes du banc répondent selon l'orientation réelle. */
type RendementBanc = number | ((lat: number, tiltDeg: number, aspect: number) => number);
function installProductionFetch(urls: string[], kwhParKwcRendement: RendementBanc = 1700) {
  const fx = perKwcFixture();
  const rendement = (lat: unknown, tilt: unknown, aspect: unknown): number =>
    typeof kwhParKwcRendement === 'number' ? kwhParKwcRendement : kwhParKwcRendement(Number(lat), Number(tilt), Number(aspect));
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: { body?: string }) => {
      urls.push(url);
      const body = init?.body ? (JSON.parse(init.body) as Record<string, unknown>) : {};
      if (url.includes('/api/roof-production')) {
        const panels = Number(body.placedPanels) || 1;
        // Rendement fixe : la fixture telle quelle (inchangé) ; table : la même forme ramenée au rendement du PLAN demandé.
        const kwc = panels * PANEL_KWC_TEST * (typeof kwhParKwcRendement === 'number' ? 1 : rendement(body.lat, body.tiltDeg, body.aspect) / fx.annual);
        return {
          ok: true,
          json: async () => ({
            ok: true,
            source: 'pvgis',
            cacheHit: false,
            placedPanels: panels,
            panelKwc: PANEL_KWC_TEST,
            placedKwc: panels * PANEL_KWC_TEST,
            annualKwh: fx.annual * kwc,
            monthlyKwh: fx.monthly.map((v) => v * kwc),
            dailyKwhByMonth: fx.dailyKwhByMonth.map((v) => v * kwc),
            typicalDayByMonth: fx.typicalDayByMonth.map((prof) => prof.map((v) => v * kwc)),
            specificDate: null,
          }),
        } as unknown as Response;
      }
      const legs = (body.legs as { kwc?: number; tiltDeg?: number; aspect?: number }[]) || [];
      const annual = legs.reduce((a, lg) => a + (lg.kwc || 1) * rendement(body.lat, lg.tiltDeg, lg.aspect), 0);
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }),
  );
}

/** Garde : AUCUNE requête vers une route lead / simulation (handoff, jamais un POST). */
function assertNoLeadPost() {
  const f = fetch as unknown as { mock?: { calls: unknown[][] } };
  if (!f.mock) return;
  for (const c of f.mock.calls) {
    const url = String(c[0]);
    expect(url, 'la preview ne POSTe JAMAIS de lead').not.toContain('/api/preview-lead');
    expect(url, 'la preview ne POSTe JAMAIS de simulation').not.toContain('/api/simulate');
  }
}

// ════════════════════════════════════════════════════════════════════════════════════
// PARCOURS RÉSIDENTIEL COMPLET (toit plat) — l'épine dorsale du test, une SEULE session.
// ════════════════════════════════════════════════════════════════════════════════════
describe('parcours utilisateur complet pro-11 — session résidentielle toit plat de bout en bout', () => {
  let urls: string[];
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    urls = [];
    installProductionFetch(urls); // production réelle → fenêtres conso/prod peuplées
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('déroule facture → tracé → reco → verrou → obstacle → disposition → conso → portées → zones → handoff, honnête partout', async () => {
    const monthlyBill = 1500;
    const ceiling = monthlyBill * 12; // plafond d'économies = facture × 12 (round-trip billMAD)
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });

    // ── ÉTAPE 1 — FACTURE. La saisie produit un lecteur « ≈ X kWh par an » sain.
    setBill(String(monthlyBill));
    await flush();
    const billKwh = intOf('rp9-bill-kwh');
    expect(billKwh, 'la conversion facture → kWh/an est > 0').toBeGreaterThan(0);
    expect(Number.isFinite(billKwh)).toBe(true);
    expect(txt('rp9-bill-kwh')).toMatch(/kWh/);
    assertNoGarbage(['rp9-bill-kwh']);

    // ── ÉTAPE 2 — TYPE DE TOIT : plat (défaut, déjà pressé). On le ré-affirme.
    const flatBtn = document.querySelector<HTMLButtonElement>('[data-rooftype="flat"]')!;
    flatBtn.click();
    expect(flatBtn.getAttribute('aria-pressed')).toBe('true');

    // ── ÉTAPE 3 — TRACÉ d'un toit réaliste (~16 m de côté ≈ 256 m²).
    traceRoof(fakeMaps[0], 16);
    await flush();

    // ── ÉTAPE 4 — RECOMMANDATION calculée et SAINE.
    const kwc = kwcOf('rp9-reco-kwc');
    const panels = intOf('rp9-reco-panels');
    const prod = intOf('rp9-reco-prod');
    const cover = intOf('rp9-reco-cover');
    const area = parseFloat(txt('rp9-area-value').replace(/[^\d.,]/g, '').replace(',', '.'));
    expect(area, 'la surface tracée est affichée et plausible (~256 m²)').toBeGreaterThan(150);
    expect(kwc, 'puissance kWc > 0').toBeGreaterThan(0);
    expect(panels, 'panneaux > 0').toBeGreaterThan(0);
    expect(prod, 'production kWh/an > 0').toBeGreaterThan(0);
    // Couverture SAINE : > 0 et bornée (un grand toit sur une facture modeste peut sur-
    // produire, donc > 100 % est honnête ; ce qu'on exclut c'est l'absurde / le cassé).
    expect(cover, 'couverture facture saine (> 0)').toBeGreaterThan(0);
    expect(cover, 'couverture bornée (jamais une valeur absurde / cassée)').toBeLessThan(300);
    expect(txt('rp9-reco-savings')).toMatch(/\d/);
    assertNoGarbage(RECO_IDS);
    // Plafond facture honnête (borne haute des économies ≤ facture × 12) — c'est le vrai
    // garde-fou : même si la production dépasse la conso, l'économie reste plafonnée.
    expect(highNum('rp9-reco-savings'), 'économies ≤ plafond facture (× 12)').toBeLessThanOrEqual(ceiling + 24);
    // Le besoin (panneaux nécessaires) est le plafond du nombre posé.
    const need = Number((document.getElementById('rp9-need-input') as HTMLInputElement).value.replace(/[^\d]/g, '')) || 0;
    expect(need, 'le besoin est renseigné').toBeGreaterThan(0);
    expect(panels, 'panneaux ≤ besoin (plafond taille-au-besoin)').toBeLessThanOrEqual(need);
    // Couverture cohérente avec production/conso (à l'arrondi près).
    expect(Math.abs(cover - Math.round((prod / billKwh) * 100)), 'couverture ≈ production / conso').toBeLessThanOrEqual(2);
    // La fenêtre de production s'est remplie (étape 4 bis).
    expect((document.getElementById('rp9-prod-window') as HTMLElement).hidden).toBe(false);
    expect(intOf('rp9-prod-headline')).toBeGreaterThan(0);

    // ── ÉTAPE 5 — VERROUILLER UN AXE (orientation Est-Ouest) → re-résolution + badge « Recommandé ».
    document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.click();
    await flush();
    expect(
      document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.getAttribute('aria-pressed'),
      'le verrou Est-Ouest est tenu',
    ).toBe('true');
    const badges = Array.from(document.querySelectorAll<HTMLElement>('.rp9-reco-badge'));
    expect(badges.some((b) => !b.hidden), 'un badge « Recommandé » est posé').toBe(true);
    expect(intOf('rp9-reco-kwc') >= 0 ? kwcOf('rp9-reco-kwc') : 0).toBeGreaterThan(0);
    assertNoGarbage(RECO_IDS);
    expect(highNum('rp9-reco-savings'), 'économies toujours ≤ plafond après verrou').toBeLessThanOrEqual(ceiling + 24);
    // On relâche le verrou pour repartir de l'optimum global pour la suite.
    (document.getElementById('rp9-optimum') as HTMLButtonElement).click();
    await flush();

    const panelsNoObstacle = intOf('rp9-reco-panels');
    expect(panelsNoObstacle).toBeGreaterThan(0);

    // ── ÉTAPE 6 — OBSTACLE : un petit obstacle réduit (clearance respecté) ≤ le compte sans obstacle.
    (document.getElementById('rp9-obstacle') as HTMLButtonElement).click();
    // petit rectangle au centre du toit (un coin de cheminée) — vrai glissé (deltas pixel >> seuil tap)
    fakeMaps[0].fire('mousedown', { lngLat: { lng: -7.6201, lat: 33.5899 }, point: { x: 180, y: 180 } });
    fakeMaps[0].fire('mousemove', { lngLat: { lng: -7.6199, lat: 33.5901 }, point: { x: 230, y: 130 } });
    fakeMaps[0].fire('mouseup', { lngLat: { lng: -7.6199, lat: 33.5901 }, point: { x: 230, y: 130 } });
    await flush();
    const panelsWithObstacle = intOf('rp9-reco-panels');
    expect(panelsWithObstacle, 'un obstacle ne peut qu\'égaler ou réduire la pose').toBeLessThanOrEqual(panelsNoObstacle);
    assertNoGarbage(RECO_IDS);
    expect(highNum('rp9-reco-savings')).toBeLessThanOrEqual(ceiling + 24);
    // Tout effacer pour rétablir le toit nu.
    (document.getElementById('rp9-obstacle-clear') as HTMLButtonElement).click();
    await flush();

    // ── ÉTAPE 7 — ÉDITION DE DISPOSITION (mode disposition). La LATTICE personnalisée
    //    (ctx.layoutPlan + cellules) est posée par le rendu de la scène 3D (scene3d.renderScene),
    //    qui s'auto-annule en jsdom (sceneRoot reste null, faute de WebGL) — le moteur de
    //    disposition est donc honnêtement GATÉ tant que la 3D n'a pas rendu (« couvert
    //    ailleurs » par le test source W69). On vérifie ICI la dégradation HONNÊTE : entrer en
    //    mode disposition ne lève AUCUNE exception, ne pose aucun chiffre cassé, et la fenêtre
    //    reste gatée (jamais un faux « 0 panneau » ou un NaN) faute de lattice GPU.
    const layoutWindow = document.getElementById('rp9-layout-window') as HTMLElement;
    expect(() => (document.getElementById('rp9-layout-toggle') as HTMLButtonElement).click()).not.toThrow();
    await flush();
    expect(() => (document.getElementById('rp9-layout-plus') as HTMLButtonElement).click()).not.toThrow();
    expect(() => (document.getElementById('rp9-layout-minus') as HTMLButtonElement).click()).not.toThrow();
    await flush();
    // Gatée (pas de lattice GPU) : la fenêtre reste masquée, sans chiffre cassé.
    expect(layoutWindow.hidden, 'disposition gatée tant que la 3D GPU n\'a pas rendu (jsdom)').toBe(true);
    assertNoGarbage(['rp9-layout-count', 'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover']);
    // La recommandation principale reste intacte et honnête malgré l'aller-retour en mode.
    expect(kwcOf('rp9-reco-kwc')).toBeGreaterThan(0);
    (document.getElementById('rp9-layout-toggle') as HTMLButtonElement).click(); // sortir du mode
    await flush();
    expect(kwcOf('rp9-reco-kwc'), 'la reco survit à la sortie du mode disposition').toBeGreaterThan(0);
    assertNoGarbage(RECO_IDS);

    // ── ÉTAPE 8 — AFFINER MA CONSOMMATION : ouvrir, ajouter une clim « en plus », vérifier la
    //    croissance + plafond, puis la retirer pour vérifier la réversibilité (W83).
    expect((document.getElementById('rp9-cons-window') as HTMLElement).hidden, 'fenêtre conso offerte').toBe(false);
    (document.getElementById('rp9-cons-toggle') as HTMLButtonElement).click(); // ouvrir l'affinage
    await flush();
    expect((document.getElementById('rp9-cons-panel') as HTMLElement).hidden).toBe(false);
    const panelsBeforeAppliance = intOf('rp9-reco-panels');
    const consTotalBefore = parseFloat(txt('rp9-cons-total').replace(/[^\d.,]/g, '').replace(',', '.'));
    expect(consTotalBefore, 'la conso/jour de base est affichée').toBeGreaterThan(0);
    assertNoGarbage(['rp9-cons-total', 'rp9-cons-self', 'rp9-cons-savings', 'rp9-cons-batt']);
    // Économies conso annuelles plafonnées par la facture (W82 — intégrale invariante au mois).
    expect(highNum('rp9-cons-savings'), 'économies conso ≤ plafond facture').toBeLessThanOrEqual(ceiling + 24);

    // Ajoute une climatisation « en plus » → conso ↑, donc panneaux ↑ (taille-au-besoin).
    const applKind = document.getElementById('rp9-appl-kind') as HTMLSelectElement;
    applKind.value = 'clim';
    applKind.dispatchEvent(new window.Event('change', { bubbles: true }));
    (document.getElementById('rp9-appl-add') as HTMLButtonElement).click();
    await flush();
    expect(document.querySelectorAll('#rp9-appl-list [data-appl]').length, 'la clim est listée').toBe(1);
    const consTotalAfter = parseFloat(txt('rp9-cons-total').replace(/[^\d.,]/g, '').replace(',', '.'));
    expect(consTotalAfter, 'un appareil « en plus » augmente le total conso').toBeGreaterThan(consTotalBefore);
    const panelsWithAppliance = intOf('rp9-reco-panels');
    expect(panelsWithAppliance, 'plus de conso → ≥ panneaux (taille-au-besoin)').toBeGreaterThanOrEqual(panelsBeforeAppliance);
    assertNoGarbage(['rp9-cons-total', 'rp9-cons-self', 'rp9-cons-savings', 'rp9-cons-batt', ...RECO_IDS]);
    expect(highNum('rp9-cons-savings'), 'économies conso restent plafonnées après ajout').toBeLessThanOrEqual(ceiling + 24);
    expect(highNum('rp9-reco-savings'), 'économies reco restent plafonnées après ajout').toBeLessThanOrEqual(ceiling + 24);

    // « Recaler sur ma facture » conserve l'énergie « en plus » (W83) — le total reste > base.
    (document.getElementById('rp9-cons-recal') as HTMLButtonElement).click();
    await flush();
    const consTotalRecal = parseFloat(txt('rp9-cons-total').replace(/[^\d.,]/g, '').replace(',', '.'));
    expect(consTotalRecal, 'Recaler garde l\'énergie « en plus » (≥ base)').toBeGreaterThan(consTotalBefore - 0.5);

    // Retire la clim → le système RÉTRÉCIT (réversibilité W83).
    const delBtn = document.querySelector<HTMLButtonElement>('#rp9-appl-list [data-appl-del]')!;
    delBtn.click();
    await flush();
    expect(document.querySelectorAll('#rp9-appl-list [data-appl]').length, 'la clim est retirée').toBe(0);
    const panelsAfterRemove = intOf('rp9-reco-panels');
    expect(panelsAfterRemove, 'retirer l\'appareil rétrécit (≤ avec appareil)').toBeLessThanOrEqual(panelsWithAppliance);
    assertNoGarbage(['rp9-cons-total', 'rp9-cons-self', 'rp9-cons-savings', ...RECO_IDS]);

    // ── ÉTAPE 9 — PORTÉES DE PRODUCTION : Année/Mois/Jour. L'économie CONSO ANNUELLE (W82)
    //    est INVARIANTE au mois affiché dans le graphe de production.
    const consSavingsYear = txt('rp9-cons-savings');
    document.querySelector<HTMLButtonElement>('[data-prod-scope="month"]')!.click();
    await flush();
    expect(txt('rp9-prod-sub')).toMatch(/Production de/i);
    expect(intOf('rp9-prod-headline'), 'le headline mois est > 0').toBeGreaterThan(0);
    // W82 — l'économie conso annuelle ne bouge pas avec le mois affiché.
    expect(txt('rp9-cons-savings'), 'W82 — économie/an invariante au mois affiché').toBe(consSavingsYear);
    document.querySelector<HTMLButtonElement>('[data-prod-scope="day"]')!.click();
    await flush();
    expect((document.getElementById('rp9-prod-day-picker') as HTMLElement).hidden).toBe(false);
    expect(document.querySelectorAll('#rp9-prod-graph path').length, 'le jour rend une courbe').toBeGreaterThan(0);
    document.querySelector<HTMLButtonElement>('[data-prod-scope="year"]')!.click();
    await flush();
    expect(txt('rp9-prod-headline')).toMatch(/kWh\/an/);
    expect(document.querySelectorAll('#rp9-prod-graph rect').length, 'l\'année rend 12 barres').toBe(12);
    assertNoGarbage(['rp9-prod-headline', 'rp9-prod-sub', 'rp9-prod-savings', 'rp9-cons-savings']);

    // ── ÉTAPE 10 — MULTI-ZONES : ajouter une 2ᵉ zone → totaux = somme des zones.
    const panelsZone1 = intOf('rp9-reco-panels');
    const kwcZone1 = kwcOf('rp9-reco-kwc');
    expect((document.getElementById('rp9-areas-window') as HTMLElement).hidden, 'panneau Zones visible').toBe(false);
    expect(intOf('rp9-areas-total-panels'), 'total = la seule zone tracée').toBe(panelsZone1);
    const addBtn = document.getElementById('rp9-add-area') as HTMLButtonElement;
    expect(addBtn.disabled, '« + Ajouter une zone » actif (zone fermée)').toBe(false);
    addBtn.click();
    traceRoof(fakeMaps[0], 14, -7.60, 33.60); // 2ᵉ zone, centre distinct
    await flush();
    const panelsZone2 = intOf('rp9-reco-panels'); // zone active = zone 2 (live)
    expect(panelsZone2).toBeGreaterThan(0);
    const kwcZone2 = kwcOf('rp9-reco-kwc');
    expect(intOf('rp9-areas-total-panels'), 'totaux = somme des deux zones (panneaux)').toBe(panelsZone1 + panelsZone2);
    expect(kwcOf('rp9-areas-total-kwc'), 'totaux = somme des deux zones (kWc)').toBeCloseTo(kwcZone1 + kwcZone2, 1);
    expect(document.querySelectorAll('#rp9-areas-list [data-area-row]').length, 'deux zones listées').toBe(2);
    assertNoGarbage(['rp9-areas-total-panels', 'rp9-areas-total-kwc', 'rp9-areas-total-prod', 'rp9-areas-total-savings']);
    // L'économie de la zone ACTIVE (reco) reste plafonnée à la facture ; le TOTAL agrège
    // honnêtement chaque zone (chacune plafonnée séparément), donc ≤ nb zones × plafond.
    expect(highNum('rp9-reco-savings'), 'économie de la zone active ≤ plafond facture').toBeLessThanOrEqual(ceiling + 24);
    expect(highNum('rp9-areas-total-savings'), 'total = somme de zones plafonnées (≤ 2 × plafond)').toBeLessThanOrEqual(2 * ceiling + 48);

    // ── ÉTAPE 11 — HANDOFF : cliquer le CTA pré-remplit le diagnostic (jamais un POST).
    const cta = document.getElementById('rp9-cta') as HTMLButtonElement;
    expect(cta.hidden, 'le CTA est offert (config gagnante)').toBe(false);
    cta.click();
    const lfArea = Number((document.getElementById('lf-area') as HTMLInputElement).value);
    const lfKwc = Number((document.getElementById('lf-kwc-est') as HTMLInputElement).value);
    const lfOrient = (document.getElementById('lf-orient') as HTMLSelectElement).value;
    expect(lfArea, 'lf-area pré-rempli et plausible (> 0, fini)').toBeGreaterThan(0);
    expect(Number.isFinite(lfArea)).toBe(true);
    expect(lfKwc, 'lf-kwc-est pré-rempli > 0').toBeGreaterThan(0);
    expect(['sud', 'sud-est', 'sud-ouest', 'est', 'ouest']).toContain(lfOrient);
    expect((document.getElementById('diag') as HTMLDetailsElement).open, 'le diagnostic est ouvert (handoff)').toBe(true);

    // ── INVARIANT GLOBAL — sur TOUTE la session, aucun POST de lead/simulation.
    assertNoLeadPost();
    expect(urls.some((u) => u.includes('/api/preview-lead') || u.includes('/api/simulate'))).toBe(false);
  }, 90000);

  // ACAL383 — le document ÉMIS par une séance scriptée est figé par un golden JSON. Volatiles
  // (nommés un à un, jamais en bloc) : `zones[i].id` (id généré) et `consumption.source.saisi_le` (horodatage).
  // Regénérer À LA MAIN seulement : `ACAL383_REGEN=1 npx vitest run tests/userJourneyPro11.test.ts`.
  it('document émis par la séance complète = golden (ACAL383)', async () => {
    type Api = import('../src/scripts/roofPro11/types').RoofToolApi;
    let api: Api | null = null;
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), onApiReady: (a) => { api = a; } });
    fakeMaps[0].fire('load', {});
    setBill('1500'); await flush();
    traceRoof(fakeMaps[0], 16); await flush();
    (document.getElementById('rp9-obstacle') as HTMLButtonElement).click();
    fakeMaps[0].fire('mousedown', { lngLat: { lng: -7.6201, lat: 33.5899 }, point: { x: 180, y: 180 } });
    fakeMaps[0].fire('mousemove', { lngLat: { lng: -7.6199, lat: 33.5901 }, point: { x: 230, y: 130 } });
    fakeMaps[0].fire('mouseup', { lngLat: { lng: -7.6199, lat: 33.5901 }, point: { x: 230, y: 130 } });
    await flush();
    (document.getElementById('rp9-layout-toggle') as HTMLButtonElement).click(); await flush();
    const doc = JSON.parse(JSON.stringify(api!.serializeLayout())) as Record<string, unknown>;
    (doc.zones as Array<Record<string, unknown>>).forEach((z) => { z.id = '<id>'; }); // volatile 1
    const src = (doc.consumption as { source?: Record<string, unknown> } | undefined)?.source;
    if (src) src.saisi_le = '<horodatage>'; // volatile 2
    const fs = await import('node:fs');
    const golden = (await import('node:path')).resolve(process.cwd(), '../../backend/django_core/apps/calepinage/tests/fixtures/userJourneyPro11.document.json');
    if (process.env.ACAL383_REGEN === '1') fs.writeFileSync(golden, JSON.stringify(doc, null, 2) + '\n');
    const attendu = JSON.parse(fs.readFileSync(golden, 'utf-8')) as Record<string, unknown>;
    const chemins = (v: unknown, p = ''): Record<string, unknown> =>
      v && typeof v === 'object'
        ? Object.assign({}, ...Object.entries(v).map(([k, x]) => chemins(x, `${p}/${k}`)))
        : { [p]: v };
    expect(chemins(doc), 'clé émise changée : voir le chemin en différence').toEqual(chemins(attendu));
  }, 60000);

  // ACAL913 — catalogue, AUCUN choix : le pan porte le premier module choisissable (jamais
  // le 720 Wc de l'atelier), et le document émet `geometry.moduleId` + `modules[]` (mutant :
  // pan sans `moduleId` ⇒ échec).
  it('catalogue, aucun choix ⇒ le pan porte le module de départ (ACAL913)', async () => {
    type Api = import('../src/scripts/roofPro11/types').RoofToolApi;
    let api: Api | null = null;
    const module = { id: 'cs-710', produitId: 41, libelle: 'Canadian Solar 710 W', longueurMm: 2384,
      largeurMm: 1303, epaisseurMm: 35, poidsKg: 34, pmaxWc: 710, source: 'fiche produit du stock' };
    const modulesDisponibles = { calepinage: 1, champs_requis: [], motif_liste_vide: null,
      modules: [{ module, selectionnable: true, champs_manquants: [], motif: null }] };
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      modulesDisponibles, onApiReady: (a: Api) => { api = a; } } as Parameters<typeof init>[0]);
    fakeMaps[0].fire('load', {});
    setBill('1500'); await flush();
    traceRoof(fakeMaps[0], 16); await flush();
    // Le pan PORTE le module (sélecteur + mention) ; jsdom ne rend pas `geometry` (aucune scène
    // Three, cf. golden ACAL383) : l'émission `geometry.moduleId` + `modules[]` d'un pan qui
    // porte un `moduleId` est prouvée par `cablageModules.test.ts` (CALX110).
    expect(api).not.toBeNull();
    expect(document.getElementById('rp9-pan-module-mention')?.textContent)
      .toBe('Canadian Solar 710 W — module de départ, à confirmer');
  }, 180000);

  // ACAL982 — UNE grandeur, UNE valeur : carte, Total « Zones », document émis et onglet Production. Un cas = une
  // ligne ; l'échec nomme le cas, la grandeur, les deux surfaces. `geometry.kwc` (non émis sous jsdom) : le serveur
  // (`test_acal_verdict_unique.py::GrandeurUnique`). Mutant : `720` remis dans `paintCard` ⇒ échec.
  const MODULE_710 = { id: 'cs-710', produitId: 41, libelle: 'Canadian Solar 710 W', longueurMm: 2384,
    largeurMm: 1303, epaisseurMm: 35, poidsKg: 34, pmaxWc: 710, source: 'fiche produit du stock' };
  // ACAL982 (revue) — le champ au sol du jumeau serveur (`test_acal_verdict_unique.py::CHAMP_982`), recopié tel quel.
  const CHAMP_982 = { id: 'champ-1', kind: 'sol', label: 'CHAMP-SOL', moduleWc: 710, tiltDeg: 20.0, rowAzimuthDeg: 90.0,
    engine: { modules: 24 } };
  const CAS_982: { cas: string; catalogue?: boolean; puces?: string[]; table?: boolean; champ?: boolean }[] = [
    { cas: 'pan Sud' },
    { cas: 'pan est-ouest 15°', puces: ['[data-family="eastwest"]', '[data-tilt="15"]'] },
    // ACAL982 (revue) — les deux routes répondent selon le PLAN demandé (table committée `specificYield`) : un onglet
    // qui interroge UN plan sud au lieu des deux jambes est-ouest y diffère de la carte (le banc fixe ne le voit pas).
    { cas: 'pan est-ouest 15° (rendement de la table par plan)', puces: ['[data-family="eastwest"]', '[data-tilt="15"]'], table: true },
    { cas: 'module catalogue 710 W', catalogue: true },
    { cas: 'toit + champ', catalogue: true, champ: true },
  ];
  it.each(CAS_982)('une grandeur, une valeur — $cas (ACAL982)', async ({ cas, catalogue, puces, table, champ }) => {
    type Api = import('../src/scripts/roofPro11/types').RoofToolApi;
    // UN rendement par kWc pour les deux routes (le banc par défaut met 1 700 au rendement, 1 550 à la production) ;
    // `table` : celui de la table committée au plan demandé, pour les deux routes.
    const { specificYield } = await import('../src/lib/estimatorBrainV2');
    installProductionFetch([], table ? (lat, tilt, aspect) => specificYield(lat, tilt, aspect) : perKwcFixture().annual);
    let api: Api | null = null;
    const modulesDisponibles = catalogue ? { calepinage: 1, champs_requis: [], motif_liste_vide: null,
      modules: [{ module: MODULE_710, selectionnable: true, champs_manquants: [], motif: null }] } : undefined;
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), modulesDisponibles,
      onApiReady: (a: Api) => { api = a; } } as Parameters<typeof init>[0]);
    fakeMaps[0].fire('load', {}); setBill('1500'); await flush(); traceRoof(fakeMaps[0], 16); await flush();
    for (const puce of puces ?? []) { document.querySelector<HTMLButtonElement>(puce)!.click(); await flush(); }
    if (champ) { api!.appliquerSection('poseSurfaces', [CHAMP_982]); await flush(); }
    document.querySelector<HTMLButtonElement>('[data-prod-scope="year"]')?.click(); await flush();
    const doc = api!.serializeLayout() as unknown as { result: { annualKwh: number }; zones: { result?: { annualKwh?: number } }[];
      poseSurfaces?: { id?: string }[] };
    // Le champ est bien dans la session (sinon le cas ne prouverait rien) ; il n'entre ni dans la carte, ni au Total des pans.
    if (champ) expect(doc.poseSurfaces?.map((s) => s.id), `${cas} — le champ au document`).toEqual(['champ-1']);
    const surfaces: Record<string, Record<string, number | undefined>> = {
      kWc: { 'carte Recommandation': kwcOf('rp9-reco-kwc'), 'Total « Zones »': kwcOf('rp9-areas-total-kwc') },
      'production annuelle': { 'carte Recommandation': intOf('rp9-reco-prod'), 'Total « Zones »': intOf('rp9-areas-total-prod'),
        'document result.annualKwh': Math.round(doc.result.annualKwh),
        'document zones[0].result.annualKwh': Math.round(doc.zones[0].result?.annualKwh ?? NaN),
        'onglet Production': intOf('rp9-prod-headline') },
      // Le champ compte au site, une fois : « Total du site » = pan (carte) + 24 modules × 710 W (la ligne recopiée).
      ...(champ ? { 'kWc du site': {
        'table du site « Total du site »': Number((document.querySelector('[data-site-resume]')?.textContent ?? '')
          .match(/([\d   ]+(?:[.,]\d+)?) kWc/)?.[1].replace(/[   ]/g, '').replace(',', '.') ?? NaN),
        'carte + champ (24 × 710 W)': Math.round((kwcOf('rp9-reco-kwc') + (CHAMP_982.engine.modules * CHAMP_982.moduleWc) / 1000) * 100) / 100,
      } } : {}),
    };
    if (catalogue) expect(txt('rp9-reco-panels'), `${cas} — le module posé`).toMatch(/× 710 W$/);
    for (const [grandeur, lues] of Object.entries(surfaces)) {
      const [[premiere, attendu], ...autres] = Object.entries(lues);
      expect(attendu, `${cas} — ${grandeur} : ${premiere} absente`).toBeGreaterThan(0);
      for (const [surface, valeur] of autres) {
        expect(valeur, `${cas} — ${grandeur} : ${premiere} = ${attendu}, ${surface} = ${valeur}`).toBeCloseTo(attendu!, 3);
      }
    }
  }, 180000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// SOUS-PARCOURS TOIT EN PENTE — une 2ᵉ session courte (l'inclinaison/azimut imposés par la
// pente) : pente + face → recommandation pente saine + handoff d'orientation suivant la face.
// ════════════════════════════════════════════════════════════════════════════════════
describe('parcours utilisateur pro-11 — sous-parcours toit en pente (face sud-ouest)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    // PVGIS injoignable → repli table « estimé » (chemin déterministe, sans réseau).
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network in test'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('pente + face → reco pente saine, plafond tenu, et le handoff suit la face réelle', async () => {
    const monthlyBill = 1200;
    const ceiling = monthlyBill * 12;
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill(String(monthlyBill));
    traceRoof(fakeMaps[0], 16);
    await flush();

    // Bascule en toit en pente : les contrôles plats se masquent, le bloc pente apparaît.
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    await flush();
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('rp9-pitched-controls') as HTMLElement).hidden).toBe(false);
    // Choisit une pente 30° et la face sud-ouest (225°).
    document.querySelector<HTMLButtonElement>('[data-pitch="30"]')!.click();
    await flush();
    document.querySelector<HTMLButtonElement>('[data-facing="225"]')!.click();
    await flush();

    // Recommandation pente SAINE.
    expect(txt('rp9-reco-title')).toMatch(/pente/i);
    expect(kwcOf('rp9-reco-kwc'), 'puissance pente > 0').toBeGreaterThan(0);
    expect(intOf('rp9-reco-panels'), 'panneaux pente > 0').toBeGreaterThan(0);
    expect(intOf('rp9-reco-prod'), 'production pente > 0').toBeGreaterThan(0);
    expect(intOf('rp9-reco-cover')).toBeGreaterThan(0);
    assertNoGarbage(RECO_IDS);
    expect(highNum('rp9-reco-savings'), 'économies pente ≤ plafond facture').toBeLessThanOrEqual(ceiling + 24);
    // Le besoin plafonne toujours la pose.
    const need = Number((document.getElementById('rp9-need-input') as HTMLInputElement).value.replace(/[^\d]/g, '')) || 0;
    expect(intOf('rp9-reco-panels')).toBeLessThanOrEqual(need);

    // Handoff : l'orientation pré-remplie SUIT la face (225° → sud-ouest), aucun POST.
    (document.getElementById('rp9-cta') as HTMLButtonElement).click();
    expect((document.getElementById('lf-orient') as HTMLSelectElement).value).toBe('sud-ouest');
    expect(Number((document.getElementById('lf-kwc-est') as HTMLInputElement).value)).toBeGreaterThan(0);
    assertNoLeadPost();
  }, 60000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// ACAL356 / ACAL357 — l'atelier rouvert depuis son document (boot devis RÉEL, sérialisé par
// `onApiReady.serializeLayout`). ACAL356 : la production VIVANTE (carte, total « Zones »,
// `result.annualKwh`) suit le dérate horizon × ombrage de `renderConfig`. ACAL357 : les
// ombres et la matrice appartiennent au SITE — « + Ajouter une zone » les garde.
// ════════════════════════════════════════════════════════════════════════════════════
describe('parcours atelier pro-11 — dérate vivant et ombres du site (ACAL356, ACAL357)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
    // Le cadrage d'un contour relu appelle `resize()` puis `once('idle')` : doublures inertes.
    Object.assign(FakeMap.prototype, { resize() { return this; }, once() { return this; } });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  type Api = import('../src/scripts/roofPro11/types').RoofToolApi;
  type Doc = Record<string, unknown> & {
    result: { annualKwh: number };
    zones: unknown[];
    shadeObstructions?: Array<{ id: string }>;
    shading12x24?: unknown;
  };
  const copie = <T>(d: T): T => JSON.parse(JSON.stringify(d)) as T;

  /** Boot neuf (module rechargé : il ne s'initialise qu'une fois) ; sans `hydrate` = session neuve. */
  async function boot(hydrate?: Record<string, unknown>): Promise<() => Api> {
    setupDom();
    fakeMaps.length = 0;
    vi.resetModules();
    document.body.appendChild(el('button', 'rp9-shade-add')); // WJ19 — « Tracer une ombre »
    const init = await loadTool();
    let api: Api | null = null;
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      ...(hydrate ? { hydrate: hydrate as never } : {}),
      onApiReady: (a) => { api = a; },
    });
    fakeMaps[0].fire('load', {});
    return () => api!;
  }
  const rouvrir = (doc: unknown, id: number) =>
    boot({ devis: { id, geometrie: { roof_layout: copie(doc) }, cibleVendue: false } });
  const lecture = (api: Api) => ({
    carte: intOf('rp9-reco-prod'),
    zones: intOf('rp9-areas-total-prod'),
    doc: (api.serializeLayout() as Doc).result.annualKwh,
  });

  it('horizon 25° (session neuve) et matrice 0,8 relue', async () => {
    const api = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    const avant = lecture(api());
    expect(avant.doc).toBeGreaterThan(0);
    const docSansDerate = copie(api().serializeLayout() as Doc);
    // Horizon 25° sur six azimuts : la carte, le total « Zones » et le document baissent
    // du MÊME facteur (horizonAnnualFactor ; l'ombrage proche reste à 1).
    const points = [0, 60, 120, 180, 240, 300].map((azimuthDeg) => ({ azimuthDeg, heightDeg: 25 }));
    api().appliquerSection('horizonProfile', { source: 'saisie', points });
    const apres = lecture(api());
    const f = apres.doc / avant.doc;
    expect(f).toBeLessThan(0.99);
    expect(apres.carte / avant.carte).toBeCloseTo(f, 3);
    expect(apres.zones / avant.zones).toBeCloseTo(f, 3);
    const docDerate = copie(api().serializeLayout() as Doc);

    const relire = async (doc: Doc, geste: boolean) => {
      const a = await rouvrir(doc, 7);
      if (geste) {
        vi.useFakeTimers();
        setBill('3000');
        vi.advanceTimersByTime(321); // la facture est débattue (320 ms) avant le recalcul
        vi.useRealTimers();
      }
      return lecture(a());
    };
    // Persistance : enregistré dératé puis rouvert sans geste ⇒ le dératé est relu tel quel.
    expect((await relire(docDerate, false)).doc).toBe(apres.doc);
    // Le même toit rouvert et recalculé (facture ressaisie ; document sans production stockée,
    // sinon ACAL31 réémet celle relue) : sans matrice (référence), puis matrice 0,8 relue.
    const { result: _stocke, ...sansProduction } = docSansDerate;
    const reference = await relire(sansProduction as Doc, true);
    expect(reference.doc).toBeGreaterThan(0);
    const matrice = Array.from({ length: 12 }, () => Array(24).fill(0.8));
    const ombre = await relire({ ...sansProduction, shading12x24: matrice } as Doc, true);
    for (const k of ['carte', 'zones', 'doc'] as const) expect(ombre[k] / reference[k]).toBeCloseTo(0.8, 3);
  }, 120000);

  // ACAL378 — la matrice d'horizon dépend de la latitude (perte mensuelle sur la course du
  // soleil) : rouvert, elle doit être celle du toit, pas celle de la latitude par défaut
  // (33,5°) posée avant le chargement du pan. Runner 20/11 : 8 142,02 → 8 141,84 sans geste.
  it('horizon 25° enregistré, rouvert puis recalculé sans changement : production IDENTIQUE', async () => {
    const api = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    api().appliquerSection('horizonProfile', { source: 'saisie', points: [0, 45, 90, 135, 180, 225, 270, 315].map((azimuthDeg) => ({ azimuthDeg, heightDeg: 25 })) });
    const docDerate = copie(api().serializeLayout() as Doc);
    expect(docDerate.result.annualKwh).toBeGreaterThan(0);
    // Production stockée retirée (sinon ACAL31 réémet celle relue) : le dérate est RECALCULÉ.
    const { result: _stocke, ...sansProduction } = docDerate;
    const a = await rouvrir(sansProduction, 8);
    vi.useFakeTimers();
    setBill('3000'); // même facture : recalcul, rien ne change
    vi.advanceTimersByTime(321);
    vi.useRealTimers();
    const relu = (a().serializeLayout() as Doc).result.annualKwh;
    expect(relu).toBe(docDerate.result.annualKwh); // toBe = Object.is
  }, 120000);

  // ACAL381 — même piège pour l'OMBRAGE PROCHE : le facteur annuel de l'atelier lit la matrice
  // à la latitude du toit ; rouvert, il ne doit pas garder celle de la latitude par défaut (33,5°).
  it('ombrage proche enregistré, rouvert puis recalculé sans changement : production IDENTIQUE', async () => {
    // Curseur d'heure de prise de vue (absent du banc) : son `input` recalcule l'ombrage
    // EN SESSION, une fois le toit tracé (centroïde connu).
    const enCours = boot(); // setupDom() a déjà tourné (partie synchrone) : on ajoute le curseur
    const heure = document.createElement('input');
    heure.id = 'rp9-shade-hour';
    document.body.appendChild(heure);
    const api = await enCours;
    setBill('3000');
    traceRoof(fakeMaps[0]);
    // Un immeuble à l'EST qui masque le soleil bas du matin (un immeuble au sud qui masque
    // midi ferait tout perdre aux heures masquées, quelle que soit la latitude).
    api().appliquerSection('environment', [{ id: 'env-1', kind: 'batiment', centerLng: -7.6195, centerLat: 33.59, heightM: 20, lengthM: 40, widthM: 10 }]);
    heure.value = '10.5';
    heure.dispatchEvent(new Event('input'));
    const docDerate = copie(api().serializeLayout() as Doc) as Doc & { shading12x24?: number[][] | null };
    expect(docDerate.shading12x24?.flat().some((f) => f < 1)).toBe(true);
    expect(docDerate.result.annualKwh).toBeGreaterThan(0);
    // Production stockée retirée (sinon ACAL31 réémet celle relue) : le dérate est RECALCULÉ
    // depuis la matrice ENREGISTRÉE.
    const { result: _stocke, ...sansProduction } = docDerate;
    const a = await rouvrir(sansProduction, 9);
    // Rouvert puis enregistré SANS geste (le piège du runner d'ACAL378), puis après un recalcul.
    expect((a().serializeLayout() as Doc).result.annualKwh).toBe(docDerate.result.annualKwh); // Object.is
    vi.useFakeTimers();
    setBill('3000'); // même facture : recalcul, rien ne change
    vi.advanceTimersByTime(321);
    vi.useRealTimers();
    expect((a().serializeLayout() as Doc).result.annualKwh).toBe(docDerate.result.annualKwh); // Object.is
  }, 120000);

  // ACAL367 — rouvert AVEC sa production enregistrée (document NON dépouillé de `result`) puis
  // ombré : le document baisse du facteur de la carte ; D-ACAL-VER2-1 : un document stocké
  // déjà ombré sans signature de dérate est dératé au prochain enregistrement.
  const horizon25 = { source: 'saisie', points: [0, 60, 120, 180, 240, 300].map((azimuthDeg) => ({ azimuthDeg, heightDeg: 25 })) };
  const kwhDesPans = (d: Doc) => (d.zones as Array<{ result?: { annualKwh?: number } }>).map((z) => z.result?.annualKwh ?? 0);
  async function rouvrirAvecGeste(doc: Doc, id: number): Promise<() => Api> {
    const a = await rouvrir(doc, id);
    vi.useFakeTimers();
    setBill('3000');
    vi.advanceTimersByTime(321); // la facture est débattue (320 ms) avant le recalcul
    vi.useRealTimers();
    return a;
  }
  async function enregistreAvecProduction(): Promise<Doc> {
    const neuf = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    return copie(neuf().serializeLayout() as Doc);
  }

  it('rouvert AVEC sa production enregistrée puis horizon 25° : le document baisse du facteur de la carte', async () => {
    const enregistre = await enregistreAvecProduction();
    expect(enregistre.result.annualKwh).toBeGreaterThan(0);
    const api = await rouvrirAvecGeste(enregistre, 9);
    const avant = lecture(api());
    const pansAvant = kwhDesPans(api().serializeLayout() as Doc);
    api().appliquerSection('horizonProfile', horizon25);
    const apres = lecture(api());
    const f = apres.carte / avant.carte;
    expect(f).toBeLessThan(0.99);
    expect(apres.zones / avant.zones).toBeCloseTo(f, 3);
    expect(apres.doc / avant.doc).toBeCloseTo(f, 3);
    const derate = copie(api().serializeLayout() as Doc);
    kwhDesPans(derate).forEach((kwh, i) => { if (pansAvant[i] > 0) expect(kwh / pansAvant[i]).toBeCloseTo(f, 3); });
    expect(typeof (derate.result as Record<string, unknown>).signatureOmbrage).toBe('string');
    // Persistance : rouvert sans geste, la production dératée est relue telle quelle.
    expect(lecture((await rouvrir(derate, 9))()).doc).toBe(apres.doc);
  }, 120000);

  it('D-ACAL-VER2-1 — document stocké avec un horizon et sans signature : production dératée au prochain enregistrement', async () => {
    const enregistre = await enregistreAvecProduction();
    expect((enregistre.result as Record<string, unknown>).signatureOmbrage).toBeUndefined(); // aucun ombrage ⇒ aucune signature
    const ancien = { ...enregistre, horizonProfile: horizon25 } as Doc; // ombré par section, production jamais dératée
    const sortie = copie((await rouvrirAvecGeste(ancien, 10))().serializeLayout() as Doc);
    expect(sortie.result.annualKwh).toBeLessThan(enregistre.result.annualKwh * 0.99);
    expect(typeof (sortie.result as Record<string, unknown>).signatureOmbrage).toBe('string');
    // Signature égale : rouvert sans geste, le dératé est réémis tel quel (ACAL31 conservé).
    expect(lecture((await rouvrir(sortie, 10))()).doc).toBe(sortie.result.annualKwh);
  }, 120000);

  // ACAL367 — le rejeu de la contre-visite tel quel : rouvert SANS ressaisir la facture (besoin
  // auto, aucune cible serveur). La facture vide ne doit pas lire « remplir le toit » : le
  // document montait à 57 296 kWh depuis 25 433 enregistrés.
  it('rouvert sans ressaisir la facture puis horizon 25° : le document baisse, il ne bondit pas au toit plein', async () => {
    const enregistre = await enregistreAvecProduction();
    const api = await rouvrir(enregistre, 13);
    const avant = lecture(api());
    expect(avant.doc).toBe(enregistre.result.annualKwh);
    expect(avant.carte).toBe(Math.round(enregistre.result.annualKwh));
    api().appliquerSection('horizonProfile', horizon25);
    const apres = lecture(api());
    const f = apres.carte / avant.carte;
    expect(f).toBeLessThan(0.99);
    expect(apres.doc / avant.doc).toBeCloseTo(f, 3);
  }, 120000);

  it('D-ACAL-VER2-1 — ancien document ombré sans signature, rouvert SANS geste : production dératée, jamais au-dessus de l’enregistrée', async () => {
    const enregistre = await enregistreAvecProduction();
    const ancien = { ...enregistre, horizonProfile: horizon25 } as Doc;
    const sortie = copie((await rouvrir(ancien, 14))().serializeLayout() as Doc);
    expect(sortie.result.annualKwh).toBeLessThan(enregistre.result.annualKwh * 0.99);
    expect(sortie.result.annualKwh).toBeGreaterThan(0);
  }, 120000);

  // ACAL366 — une section « zones » (onglet Pente, panneau Relevé) est posée sur le pan VIVANT :
  // « Enregistrer » garde 35° (jamais l'ancienne pente sous un jeton neuf), puis rouvrir la relit.
  it('section « zones » (pente 35°, azimut relevé) appliquée au pan vivant puis gardée par serializeLayout', async () => {
    const neuf = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    const base = copie(neuf().serializeLayout() as Doc) as Doc & { zones: Array<Record<string, unknown>> };
    base.zones[0] = { ...base.zones[0], roofType: 'pitched', pitchDeg: 15, facingAzimuthDeg: 180 };
    const api = await rouvrir(base, 11);
    const z1 = String(base.zones[0].id);
    const champs = {
      pitchDeg: 35, pitchSource: { mode: 'degres', degres: 35 }, facingAzimuthDeg: 200, facingManual: true,
      facingAzimuthSource: 'releve', facingAzimuthPrecisionDeg: 5, pitchSuggestion: { degres: 34, decision: 'refusee' },
    };
    const zonesRendues = base.zones.map((z) => (z.id === z1 ? { ...z, ...champs } : z));
    api().appliquerSection('zones', zonesRendues);
    const attendus = (doc: Doc) => {
      const z = (doc.zones as Array<Record<string, unknown>>).find((x) => x.id === z1)!;
      for (const [cle, valeur] of Object.entries(champs)) expect(z[cle]).toEqual(valeur);
    };
    const enregistre = copie(api().serializeLayout() as Doc);
    attendus(enregistre);
    expect(enregistre.result.annualKwh).toBeGreaterThan(0);
    // Persistance : rouvert depuis l'enregistrement complet, la pente et ses provenances relues.
    attendus((await rouvrir(enregistre, 11))().serializeLayout() as Doc);
  }, 120000);

  // ACAL366 — « production recalculée sur 35° » : un pan rouvert AVEC sa production à 15° ne
  // réémet plus la production relue une fois sa pente changée (la pose peut rester la même).
  it('section « zones » sur un pan rouvert AVEC sa production : le document suit la carte recalculée', async () => {
    const neuf = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    const { result: _sansProduction, ...trace } = copie(neuf().serializeLayout() as Doc);
    const pan = { ...(trace.zones as Array<Record<string, unknown>>)[0], roofType: 'pitched', pitchDeg: 15, facingAzimuthDeg: 180, neededAuto: false };
    delete pan.result;
    const a15 = await rouvrir({ ...trace, zones: [pan] }, 12);
    const enregistre = copie(a15().serializeLayout() as Doc);
    expect(enregistre.result.annualKwh).toBeGreaterThan(0);
    const api = await rouvrir(enregistre, 12);
    const avant = lecture(api());
    expect(avant.doc).toBe(enregistre.result.annualKwh);
    api().appliquerSection('zones', [{ ...pan, pitchDeg: 35, pitchSource: { mode: 'degres', degres: 35 } }]);
    const apres = lecture(api());
    expect(apres.carte).not.toBe(avant.carte);
    expect(Math.round(apres.doc)).toBe(apres.carte);
    // Persistance : rouvert sans geste, la production recalculée sur 35° est relue telle quelle.
    const relu = copie(api().serializeLayout() as Doc);
    expect(lecture((await rouvrir(relu, 12))()).doc).toBe(relu.result.annualKwh);
  }, 120000);

  // ACAL379 — la section « zones » rend TOUS les pans à leurs valeurs ENREGISTRÉES (« Saisie de la
  // pente », décision IGN) : seul ce qui diffère du document relu est écrit, la saisie en cours reste.
  it('section « zones » ne défait pas la saisie non enregistrée des pans', async () => {
    const neuf = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    traceRoof(fakeMaps[0], 16, -7.6195);
    const base = copie(neuf().serializeLayout() as Doc) as Doc & { zones: Array<Record<string, unknown>> };
    const stockees = base.zones.map((z, i) => ({ ...z, roofType: 'pitched', pitchDeg: i ? 20 : 15 }));
    const [z1, z2] = stockees.map((z) => String(z.id));
    const api = await rouvrir({ ...base, activeAreaId: z1, zones: stockees }, 15);
    const curseur = document.getElementById('rp9-pitch-range') as HTMLInputElement;
    const pente = (id: string, v: number) => {
      document.querySelector<HTMLElement>(`#rp9-areas-list [data-area-select="${id}"]`)?.click();
      curseur.value = String(v);
      curseur.dispatchEvent(new Event('input'));
    };
    pente(z2, 40);
    pente(z1, 30);
    const pentes = (doc: Doc) => (doc.zones as Array<Record<string, unknown>>).map((z) => z.pitchDeg);
    expect(pentes(api().serializeLayout() as Doc)).toEqual([30, 40]); // la saisie, avant toute section
    // Décision IGN sur z1 (zones stockées + la décision), puis pente d'un 3e pan enregistrée.
    api().appliquerSection('zones', stockees.map((z) => (z.id === z1 ? { ...z, pitchSuggestion: { degres: 34, decision: 'refusee' } } : z)));
    api().appliquerSection('zones', [...stockees, { id: 'z-autre', pitchDeg: 25 }]);
    const enregistre = copie(api().serializeLayout() as Doc);
    expect(pentes(enregistre)).toEqual([30, 40]);
    expect(curseur.value).toBe('30');
    expect(document.getElementById('rp9-pitch-value')!.textContent).toBe('30°');
    // Une pente réellement changée par le serveur (z2 → 35°) est écrite ; rendue à nouveau, rien ne bouge.
    for (let i = 0; i < 2; i++) api().appliquerSection('zones', stockees.map((z) => (z.id === z2 ? { ...z, pitchDeg: 35 } : z)));
    expect(pentes(api().serializeLayout() as Doc)).toEqual([30, 35]);
    // Persistance : rouvert depuis l'enregistrement, 30° et 40° relus.
    expect(pentes((await rouvrir(enregistre, 15))().serializeLayout() as Doc)).toEqual([30, 40]);
  }, 120000);

  // ACAL380 — un pan dessiné pendant la séance (absent du document relu) : la provenance que lui
  // donne une section « zones » vit sur sa fiche (`ctx.areas`), est émise puis relue.
  it('pan dessiné en séance garde sa provenance', async () => {
    const neuf = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    const base = copie(neuf().serializeLayout() as Doc);
    const api = await rouvrir(base, 16);
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    traceRoof(fakeMaps[0], 16, -7.6195);
    const dessine = (copie(api().serializeLayout() as Doc).zones as Array<Record<string, unknown>>)[1];
    const provenance = { facingAzimuthSource: 'releve', facingAzimuthPrecisionDeg: 5, pitchSuggestion: { degres: 34, decision: 'refusee' } };
    api().appliquerSection('zones', [{ ...dessine, facingAzimuthDeg: 200, ...provenance }]);
    const attendus = (doc: Doc) => {
      const z = (doc.zones as Array<Record<string, unknown>>).find((x) => x.id === dessine.id)!;
      expect({ ...z, ...provenance, facingAzimuthDeg: 200 }).toEqual(z);
    };
    const enregistre = copie(api().serializeLayout() as Doc);
    attendus(enregistre);
    // Persistance : rouvert depuis l'enregistrement complet, les trois champs relus.
    attendus((await rouvrir(enregistre, 16))().serializeLayout() as Doc);
  }, 120000);

  // ACAL417 — pente 22° et face Sud de départ : non pressées, nommées « à confirmer », puis source écrite au clic.
  it('pente et face de départ : mentions à confirmer, puis source écrite au clic', async () => {
    const api = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    await flush();
    const presses = () => Array.from(document.querySelectorAll('[data-pitch],[data-facing]')).filter((b) => b.getAttribute('aria-pressed') === 'true');
    expect(presses()).toEqual([]);
    expect(txt('rp9-pitch-note')).toBe('Pente : 22° par défaut — à confirmer');
    expect(txt('rp9-facing-note')).toBe('Face : Sud par défaut — à confirmer');
    expect((api().serializeLayout() as Doc).zones[0]).not.toHaveProperty('pitchSource');
    document.querySelector<HTMLButtonElement>('[data-pitch="30"]')!.click();
    await flush();
    expect(txt('rp9-pitch-note')).toBe('');
    expect(document.querySelector('[data-pitch="30"]')!.getAttribute('aria-pressed')).toBe('true');
    expect(txt('rp9-facing-note')).toMatch(/à confirmer/);
    const doc = copie(api().serializeLayout() as Doc);
    expect((doc.zones[0] as Record<string, unknown>).pitchSource).toEqual({ mode: 'degres', degres: 30 });
    // rouvert : pente confirmée (puce pressée, aucune mention), face encore à confirmer.
    await rouvrir(doc, 17);
    expect(txt('rp9-pitch-note')).toBe('');
  }, 120000);

  // ACAL413 — « Effacer » avec un contour nomme ce qui sera perdu et ne fait rien sur refus.
  it('« Effacer » avec un contour demande en nommant le pan, et ne fait rien sur refus', async () => {
    await boot();
    traceRoof(fakeMaps[0]);
    // Acceptation ACAL490 (oracle 4) : la question est posée DANS l'atelier, jamais par window.confirm.
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);
    const repondre = (libelle: string) =>
      Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-question-effacer button')).find((b) => b.textContent === libelle)!.click();
    (document.getElementById('rp9-clear') as HTMLButtonElement).click();
    expect(document.getElementById('rp9-question-effacer')?.getAttribute('role')).toBe('alertdialog');
    expect(txt('rp9-question-effacer-texte')).toMatch(/^Effacer 1 pan/);
    expect(document.getElementById('rp9-etat-vide')?.hidden).toBe(true); // posée : rien n'est encore effacé
    repondre('Garder');
    expect(document.getElementById('rp9-question-effacer')).toBeNull();
    expect(document.getElementById('rp9-etat-vide')?.hidden).toBe(true); // refus : le contour reste fermé
    (document.getElementById('rp9-clear') as HTMLButtonElement).click();
    repondre('Effacer');
    expect(document.getElementById('rp9-etat-vide')?.hidden).toBe(false); // accepté : site vierge, la carte d'aide revient
    expect(confirmSpy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  }, 300000);

  // ACAL925 — « Effacer » ne perd pas la cible hydratée (lead à 4 panneaux : 4 après Effacer et un nouveau tracé).
  it('ACAL925 — hydratation cible.panneaux 4, Effacer, retracer ⇒ 4 panneaux voulus, besoin non automatique', async () => {
    const lead = { id: 7, cible: { panneaux: 4 }, cibleVendue: false, geometrie: { roof_point: { lat: 33.59, lng: -7.62 } } };
    const besoin = () => (document.getElementById('rp9-need-input') as HTMLInputElement).value;
    const api = await boot({ devis: lead });
    traceRoof(fakeMaps[0]);
    await flush();
    expect(besoin()).toBe('4');
    (document.getElementById('rp9-clear') as HTMLButtonElement).click();
    Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-question-effacer button')).find((b) => b.textContent === 'Effacer')?.click();
    expect(document.getElementById('rp9-etat-vide')?.hidden).toBe(false);
    traceRoof(fakeMaps[0]);
    await flush();
    expect(besoin()).toBe('4');
    const zones = (api().serializeLayout() as { zones: Array<{ neededPanels: number; neededAuto: boolean }> }).zones;
    expect(zones[0].neededPanels).toBe(4);
    expect(zones[0].neededAuto).toBe(false);
  }, 300000);

  // ACAL925 — sans cible hydratée, « Effacer » reste ce qu'il était (aucune cible inventée).
  it('ACAL925 — sans cible hydratée, Effacer puis retracer ne fixe aucun nombre', async () => {
    const api = await boot();
    traceRoof(fakeMaps[0]);
    (document.getElementById('rp9-clear') as HTMLButtonElement).click();
    Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-question-effacer button')).find((b) => b.textContent === 'Effacer')?.click();
    traceRoof(fakeMaps[0]);
    await flush();
    const zones = (api().serializeLayout() as { zones: Array<{ neededAuto: boolean }> }).zones;
    expect(zones[0].neededAuto).toBe(true);
  }, 300000);

  // ACAL956 — la fermeture cadre le toit entier (zoom d'ajustement) et incline à PITCH_VIEW.
  it('ACAL956 — à la fermeture, le dernier jumpTo porte zoom = zoomToFitRing(sommets) et pitch = 58', async () => {
    await boot();
    traceRoof(fakeMaps[0]);
    await flush();
    const dernier = fakeMaps[0].jumpToCalls.at(-1) as { zoom?: number; pitch?: number };
    expect(dernier.pitch).toBe(PITCH_VIEW);
    expect(dernier.zoom).toBe(zoomToFitRing(squareCorners(16)));
  }, 300000);

  // ACAL926 — un double-clic à un NOUVEL endroit pose le dernier coin ; sur le dernier sommet, aucun sommet parasite.
  it('ACAL926 — 3 clics puis clic + dblclick à un 4ᵉ point éloigné ⇒ 4 sommets ; double-clic sur le dernier sommet ⇒ 3', async () => {
    const coins = squareCorners(16, -7.62, 33.59);
    const finir = async (pointDuDouble: { x: number; y: number }) => {
      const api = await boot();
      vi.useFakeTimers();
      for (const [lng, lat] of coins.slice(0, 3)) {
        fakeMaps[0].fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
        vi.advanceTimersByTime(241);
      }
      const [lng, lat] = coins[3];
      const evt = { lngLat: { lng, lat }, point: pointDuDouble, preventDefault() {} };
      fakeMaps[0].fire('click', evt);
      fakeMaps[0].fire('click', evt);
      fakeMaps[0].fire('dblclick', evt);
      vi.advanceTimersByTime(241);
      vi.useRealTimers();
      return (api().serializeLayout() as { zones: Array<{ vertices: unknown[] }> }).zones[0].vertices.length;
    };
    expect(await finir({ x: 200, y: 200 })).toBe(4); // loin du dernier sommet (la doublure project() rend 0,0)
    expect(await finir({ x: 0, y: 0 })).toBe(3); // sur le dernier sommet : comme aujourd'hui
  }, 300000);

  // ACAL985 (garde K-SAISIE-PERDUE) — UNE séance scriptée. Matrice lignes × colonnes (l'échec nomme les deux) :
  //   facture × lead (consommation servie) · cible × Effacer · 4ᵉ coin × double-clic.
  it('ACAL985 — facture du lead, tracé fermé par double-clic, Effacer, retracé : rien de saisi ne se perd', async () => {
    const lead = { id: 7, cible: { panneaux: 4 }, cibleVendue: false, geometrie: { roof_point: { lat: 33.59, lng: -7.62 } } };
    const api = await boot({ devis: lead });
    const zones = () => (api().serializeLayout() as { zones: Array<{ vertices: unknown[]; neededPanels: number }> }).zones;
    // Tracé : 3 clics puis clic + double-clic à un 4ᵉ coin éloigné (comme ACAL926).
    const coins = squareCorners(16, -7.62, 33.59);
    vi.useFakeTimers();
    for (const [lng, lat] of coins.slice(0, 3)) {
      fakeMaps[0].fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    const [lng, lat] = coins[3];
    const evt = { lngLat: { lng, lat }, point: { x: 200, y: 200 }, preventDefault() {} };
    fakeMaps[0].fire('click', evt);
    fakeMaps[0].fire('click', evt);
    fakeMaps[0].fire('dblclick', evt);
    vi.advanceTimersByTime(241);
    vi.useRealTimers();
    await flush();
    expect(zones()[0].vertices.length, 'ligne 4ᵉ coin × colonne double-clic : le coin est gardé (4 sommets, pas un triangle)').toBe(4);
    expect(zones()[0].neededPanels, 'ligne cible × colonne lead : la cible du lead est portée par le pan').toBe(4);
    // Effacer puis retracer : la cible hydratée reste celle du lead.
    (document.getElementById('rp9-clear') as HTMLButtonElement).click();
    Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-question-effacer button')).find((b) => b.textContent === 'Effacer')?.click();
    traceRoof(fakeMaps[0]);
    await flush();
    expect(zones()[0].neededPanels, 'ligne cible × colonne Effacer : 4 panneaux voulus après Effacer et un nouveau tracé').toBe(4);
    expect(zones()[0].vertices.length, 'ligne 4ᵉ coin × colonne Effacer : le retracé garde ses quatre coins').toBe(4);
    // Facture (900 MAD/mois) : sa consommation atteint le document émis.
    setBill('900');
    await flush();
    const billKwh = (api().serializeLayout() as { billKwh: number | null }).billKwh;
    expect(billKwh, 'ligne facture × colonne lead : la consommation saisie atteint le document').toBeGreaterThan(0);
  }, 300000);

  // ACAL410 (acceptation ACAL490) — « 2 pans » puis « 4 pans » : la liste des zones suit le document.
  it('« Forme du toit » : la liste des zones compte les pans découpés (2 puis 4)', async () => {
    Object.assign(FakeMap.prototype, { getCenter() { return { lng: -7.62, lat: 33.59 }; } });
    for (const [libelle, n] of [['2 pans', 2], ['4 pans', 4]] as const) {
      const api = await boot();
      setBill('3000');
      // Le geste de l'acceptation : toit 12 × 8 m par cotes, orientation 0°.
      const cotes = document.getElementById('rp9-toit-cotes')!;
      const champs = Array.from(cotes.querySelectorAll<HTMLInputElement>('input'));
      for (const [i, v] of ['12', '8', '0'].entries()) {
        champs[i].value = v;
        champs[i].dispatchEvent(new Event('input', { bubbles: true }));
      }
      Array.from(cotes.querySelectorAll<HTMLButtonElement>('button')).find((b) => b.textContent === 'Créer le toit')!.click();
      await flush();
      expect(txt('rp9-status')).toContain('Toit créé : 12 × 8 m');
      const puce = Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-formes-toit button')).find((b) => b.textContent === libelle)!;
      puce.click();
      await flush();
      expect(txt('rp9-status')).toContain(`Toit découpé en ${n} pans`);
      expect((api().serializeLayout() as Doc).zones, `${libelle} : document`).toHaveLength(n);
      expect(document.querySelectorAll('#rp9-areas-list [data-area-row]').length, `${libelle} : liste à jour`).toBe(n);
    }
  }, 120000);

  // Acceptation ACAL490 (ACAL399) — « + Ajouter une zone » rend actif un pan VIDE : le document
  // gardait `pin: null` (centroïde du pan actif vide) ⇒ simulation refusée « site.pin » et
  // « Pas de position GPS sur la fiche » à la réouverture.
  it('« + Ajouter une zone » puis enregistrer : l’épingle du site est gardée', async () => {
    const neuf = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    const base = copie(neuf().serializeLayout() as Doc & { pin: unknown });
    expect(base.pin).not.toBeNull();
    const api = await rouvrir(base, 18);
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    const apres = copie(api().serializeLayout() as Doc & { pin: unknown });
    expect(apres.zones).toHaveLength(2);
    expect(apres.pin, 'épingle du document relu').toEqual(base.pin);
    // Session neuve (sans document relu) : l'épingle suit le pan tracé, jamais null.
    const session = await boot();
    setBill('3000');
    traceRoof(fakeMaps[0]);
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    expect((session().serializeLayout() as Doc & { pin: unknown }).pin).not.toBeNull();
  }, 120000);

  // ACAL420 — l'état vide dit le prochain geste sur la carte, puis s'efface à la fermeture du contour.
  it('l’état vide dit le prochain geste, puis s’efface à la fermeture du contour', async () => {
    await boot();
    const carte = () => document.getElementById('rp9-etat-vide') as HTMLElement;
    expect(carte().textContent).toMatch(/^1 · Localisez le toit/);
    expect(carte().getAttribute('aria-hidden')).toBe('true');
    expect(carte().style.pointerEvents).toBe('none');
    vi.useFakeTimers();
    const [[lng, lat]] = squareCorners(16);
    fakeMaps[0].fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
    vi.advanceTimersByTime(241);
    vi.useRealTimers();
    expect(carte().textContent).toMatch(/^2 · Un clic par coin/);
    vi.useFakeTimers();
    for (const [lng2, lat2] of squareCorners(16).slice(1)) {
      fakeMaps[0].fire('click', { lngLat: { lng: lng2, lat: lat2 }, point: { x: 0, y: 0 } });
      vi.advanceTimersByTime(241);
    }
    vi.useRealTimers();
    (document.getElementById('rp9-finish') as HTMLButtonElement).click();
    expect(carte().hidden).toBe(true);
  }, 60000);

  it('« + Ajouter une zone » garde les ombres et la matrice du document', async () => {
    const { readFileSync } = await import('node:fs');
    const { resolve } = await import('node:path');
    const chemin = resolve(process.cwd(), '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json');
    const exemple = (JSON.parse(readFileSync(chemin, 'utf8')) as { exemple: Record<string, unknown> }).exemple;
    const matrice = Array.from({ length: 12 }, () => Array(24).fill(0.8));
    const ouvrir = async (doc: unknown) => {
      const enCours = rouvrir(doc, 3);
      const heure = document.createElement('input'); // ACAL496 — l'heure solaire de prise de vue est SAISIE
      heure.id = 'rp9-shade-hour';
      document.body.appendChild(heure);
      const a = await enCours;
      return () => a().serializeLayout() as Doc;
    };
    // ACAL496 — la date de prise de vue est celle du document (ACAL509), l'heure celle saisie.
    const enregistrer = await ouvrir({ ...exemple, shading12x24: matrice, imageCapture: { date: '2025-03-21', source: 'essai' } });
    expect(enregistrer().shading12x24).toEqual(matrice); // la matrice 0,8 relue
    const heureSaisie = document.getElementById('rp9-shade-hour') as HTMLInputElement;
    heureSaisie.value = '10.5';
    heureSaisie.dispatchEvent(new Event('input'));
    // Une ombre tracée sur le pan actif (pied puis bout).
    (document.getElementById('rp9-shade-add') as HTMLButtonElement).click();
    for (const lat of [2.9999, 3.0001]) fakeMaps[0].fire('click', { lngLat: { lng: 5, lat }, point: { x: 0, y: 0 } });
    const avant = enregistrer();
    expect(avant.shadeObstructions?.map((o) => o.id)).toEqual(['shade-1', 'sh-1', 'sh-2']);
    (document.getElementById('rp9-add-area') as HTMLButtonElement).click();
    const apres = enregistrer();
    expect(apres.zones).toHaveLength(3);
    expect(apres.shadeObstructions).toEqual(avant.shadeObstructions);
    expect(apres.shading12x24).toEqual(avant.shading12x24);
    // Persistance : rouvert après l'ajout, ombres et matrice relues identiques.
    const relu = (await ouvrir(apres))();
    expect(relu.shadeObstructions).toEqual(apres.shadeObstructions);
    expect(relu.shading12x24).toEqual(apres.shading12x24);
  }, 120000);

  // ACAL496 — sans date ni heure déclarées : aucune ombre tracée, aucune hauteur relue touchée.
  it('sans date de prise de vue : tracer une ombre est refusé en le disant ; les hauteurs relues restent', async () => {
    const { readFileSync } = await import('node:fs');
    const { resolve } = await import('node:path');
    const chemin = resolve(process.cwd(), '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json');
    const exemple = (JSON.parse(readFileSync(chemin, 'utf8')) as { exemple: Record<string, unknown> }).exemple;
    const enCours = rouvrir({ ...exemple }, 3);
    const heure = document.createElement('input');
    heure.id = 'rp9-shade-hour';
    document.body.appendChild(heure);
    const api = await enCours;
    const avant = (api().serializeLayout() as Doc).shadeObstructions;
    heure.value = '10.5';
    heure.dispatchEvent(new Event('input')); // recalcul d'ombrage sans date
    (document.getElementById('rp9-shade-add') as HTMLButtonElement).click();
    for (const lat of [2.9999, 3.0001]) fakeMaps[0].fire('click', { lngLat: { lng: 5, lat }, point: { x: 0, y: 0 } });
    const apres = (api().serializeLayout() as Doc).shadeObstructions;
    expect(apres).toEqual(avant);
  }, 120000);
});

// ACAL421 — « Conception automatique » : le contour posé sur un atelier SANS pan tracé occupe
// le pan vide de départ (aucun pan fantôme area-1 gardé) ; un pan déjà tracé n'est pas écrasé.
describe('parcours utilisateur pro-11 — ACAL421 contour posé sur le pan vide', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network in test'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('atelier vide : le contour remplace le pan vide ; pan tracé : il s’ajoute', async () => {
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), onApiReady: (a) => { api = a; } });
    fakeMaps[0].fire('load', {});
    setBill('1500');
    const contour = squareCorners(16);
    expect(api!.ajouterPanDepuisContour(contour).ok).toBe(true);
    const doc = api!.serializeLayout() as { zones: Array<{ vertices: unknown }> };
    expect(doc.zones).toHaveLength(1);
    expect(doc.zones[0].vertices).toEqual(contour);
    api!.ajouterPanDepuisContour(squareCorners(12, -7.6195));
    expect((api!.serializeLayout() as { zones: unknown[] }).zones).toHaveLength(2);
  }, 60000);
});

describe('parcours utilisateur pro-11 — ACAL492 Ctrl + D sans obstacle parle', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network in test'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('sans obstacle sélectionné, le geste atteint le bouton et #rp9-status dit « Sélectionnez d’abord »', async () => {
    const bouton = document.createElement('button');
    bouton.id = 'rp9-obs-duplicate';
    document.body.appendChild(bouton);
    const init = await loadTool();
    let api: import('../src/scripts/roofPro11/types').RoofToolApi | null = null;
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document), onApiReady: (a) => { api = a; } });
    fakeMaps[0].fire('load', {});
    api!.raccourcis.dupliquer();
    expect(txt('rp9-status')).toContain('Sélectionnez d’abord un obstacle à dupliquer.');
  }, 300000);
});

// Maquette Main (22/11, ACAL1288) — dans l'atelier plein écran (`.cal-coque`), les formes du toit sont six
// tuiles illustrées + « Tracé libre » ; hors coque (mode lead), les mêmes puces texte qu'avant.
describe('parcours utilisateur pro-11 — tuiles « Forme du toit » de la coque', () => {
  const monter = async (dansCoque: boolean, contour: () => [number, number][]) => {
    const { monterFormesToit } = await import('../src/scripts/roofPro11/formesToit');
    document.body.innerHTML = `<div class="${dansCoque ? 'rp9-host cal-coque' : 'rp9-host'}"><div><button id="rp9-add-area"></button></div></div>`;
    const statuts: string[] = [];
    const appliques: number[] = [];
    const f = monterFormesToit({
      ancre: document.getElementById('rp9-add-area'), contour, pente: () => 30, existants: () => [{ id: 'area-1' }],
      obstacles: () => 0, appliquer: (pans) => void appliques.push(pans.length), setStatus: (m) => void statuts.push(m),
    });
    const tuiles = () => Array.from(document.querySelectorAll<HTMLButtonElement>('#rp9-formes-toit button'));
    return { f, statuts, appliques, tuiles };
  };
  const carre = (): [number, number][] => [[-7.62, 33.59], [-7.6199, 33.59], [-7.6199, 33.5901], [-7.62, 33.5901]];

  it('coque : libellés « En L »/« En T », 7 tuiles (classe + data-forme du pictogramme CSS), Tracé libre, hook de la grille', async () => {
    const { tuiles } = await monter(true, carre);
    expect(tuiles().map((b) => b.textContent)).toEqual(['Plat', '1 pan', '2 pans', '4 pans', 'En L', 'En T', 'Tracé libre']);
    expect(tuiles().map((b) => b.dataset.forme)).toEqual(['flat', 'shed', 'gable', 'hip', 'l_gable', 't_gable', 'libre']);
    expect(document.getElementById('rp9-formes-toit')?.dataset.testid).toBe('cal-toit-formes');
    for (const b of tuiles()) {
      expect(b.classList.contains('rp9-tuile-forme'), b.textContent!).toBe(true);
      expect(b.getAttribute('aria-pressed')).toBe('false');
    }
  });

  it('coque : la forme appliquée est choisie (aria-pressed) ; contour ouvert ⇒ formes choisissables, la bulle dit l’ordre (T4-U2-005), Tracé libre le dit', async () => {
    let ferme = true;
    const { f, statuts, appliques, tuiles } = await monter(true, () => (ferme ? carre() : []));
    f.rafraichir();
    tuiles().find((b) => b.dataset.forme === 'gable')!.click();
    expect(appliques).toEqual([2]);
    expect(tuiles().filter((b) => b.getAttribute('aria-pressed') === 'true').map((b) => b.textContent)).toEqual(['2 pans']);
    ferme = false;
    f.rafraichir();
    expect(tuiles().every((b) => b.getAttribute('aria-pressed') === 'false')).toBe(true);
    // T4-U2-005 (4aa4a6800e) — la forme se choisit AVANT « Créer le toit » : plus aucune tuile grisée, les six formes
    // disent l'ordre dans leur bulle ; Tracé libre n'en porte pas.
    expect(tuiles().filter((b) => b.hasAttribute('aria-disabled')).length).toBe(0);
    expect(tuiles().filter((b) => b.title === 'Choisissez la forme, puis saisissez la longueur et la largeur et « Créer le toit ».').length).toBe(6);
    expect(document.getElementById('rp9-formes-toit')!.hidden, 'coque : la grille reste visible contour ouvert').toBe(false);
    tuiles().find((b) => b.dataset.forme === 'libre')!.click();
    expect(statuts.at(-1)).toMatch(/^Tracé libre : cliquez sur la carte/);
    expect(appliques).toEqual([2]);
  });

  it('toit rouvert : la tuile suit la géométrie des pans quand elle est sans ambiguïté, sinon aucune', async () => {
    const { formeDuToit, decouperContour } = await import('../src/scripts/roofPro11/formesToit');
    const decoupe = (forme: 'gable' | 'hip') => {
      const v = decouperContour(carre(), forme, 22, []);
      if (!v.ok) throw new Error(v.motif);
      return v.pans;
    };
    expect(formeDuToit([{ id: 'a', vertices: carre(), roofType: 'flat' }])).toBe('flat');
    expect(formeDuToit([{ id: 'a', vertices: carre(), roofType: 'pitched', facingAzimuthDeg: 180 }])).toBe('shed');
    expect(formeDuToit(decoupe('gable'))).toBe('gable');
    expect(formeDuToit(decoupe('hip'))).toBe('hip');
    // Un pan encore à tracer (ajout en cours) ne change pas la forme lue sur les pans tracés.
    expect(formeDuToit([...decoupe('gable'), { id: 'z', vertices: [] }])).toBe('gable');
    // Deux pans en pente SANS arête commune (deux bâtiments) : aucune forme.
    const loin = carre().map(([x, y]): [number, number] => [x + 0.01, y]);
    expect(formeDuToit([
      { id: 'a', vertices: carre(), roofType: 'pitched', facingAzimuthDeg: 180 },
      { id: 'b', vertices: loin, roofType: 'pitched', facingAzimuthDeg: 0 },
    ])).toBeNull();
    // Un plat + une pente, ou rien de tracé : aucune forme.
    expect(formeDuToit([{ id: 'a', vertices: carre(), roofType: 'flat' }, { id: 'b', vertices: loin, roofType: 'pitched' }])).toBeNull();
    expect(formeDuToit([])).toBeNull();
    // Coque : la tuile déduite est choisie au rafraîchissement, sans aucun clic.
    document.body.innerHTML = '<div class="rp9-host cal-coque"><div><button id="rp9-add-area"></button></div></div>';
    const { monterFormesToit } = await import('../src/scripts/roofPro11/formesToit');
    const f = monterFormesToit({
      ancre: document.getElementById('rp9-add-area'), contour: carre, pente: () => 22, existants: () => decoupe('gable'),
      obstacles: () => 0, appliquer: () => {}, setStatus: () => {},
    });
    f.rafraichir();
    const choisies = Array.from(document.querySelectorAll('#rp9-formes-toit button[aria-pressed="true"]')).map((b) => b.textContent);
    expect(choisies).toEqual(['2 pans']);
  });

  it('hors coque (mode lead) : puces texte, sans pictogramme ni Tracé libre ni état choisi', async () => {
    const { f, tuiles } = await monter(false, () => []);
    f.rafraichir();
    expect(document.getElementById('rp9-formes-toit')!.hidden, 'lead : masquée tant que le contour est ouvert').toBe(true);
    expect(tuiles().map((b) => b.textContent)).toEqual(['Plat', '1 pan', '2 pans', '4 pans', 'En L', 'En T']);
    expect(document.querySelector('.rp9-tuile-forme')).toBeNull();
    tuiles()[2].click();
    expect(tuiles().some((b) => b.hasAttribute('aria-pressed') || b.hasAttribute('aria-disabled'))).toBe(false);
    expect(document.getElementById('rp9-formes-toit')?.dataset.testid).toBeUndefined();
  });
});
