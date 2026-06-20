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
  const api = { Map: FakeMap, NavigationControl, GeolocateControl, Point, MercatorCoordinate, GeoJSONSource: class {} };
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

const ID_INPUTS = ['rp9-bill', 'rp9-address', 'rp9-need-input', 'rp9-obs-length', 'rp9-obs-width'];
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
  'rp9-flat-controls', 'rp9-flat-only', 'rp9-pitched-controls', 'rp9-pitch-value', 'rp9-pitched-note',
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
function installProductionFetch(urls: string[]) {
  const fx = perKwcFixture();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: { body?: string }) => {
      urls.push(url);
      const body = init?.body ? (JSON.parse(init.body) as Record<string, unknown>) : {};
      if (url.includes('/api/roof-production')) {
        const panels = Number(body.placedPanels) || 1;
        const kwc = panels * PANEL_KWC_TEST;
        return {
          ok: true,
          json: async () => ({
            ok: true,
            source: 'pvgis',
            cacheHit: false,
            placedPanels: panels,
            panelKwc: PANEL_KWC_TEST,
            placedKwc: kwc,
            annualKwh: fx.annual * kwc,
            monthlyKwh: fx.monthly.map((v) => v * kwc),
            dailyKwhByMonth: fx.dailyKwhByMonth.map((v) => v * kwc),
            typicalDayByMonth: fx.typicalDayByMonth.map((prof) => prof.map((v) => v * kwc)),
            specificDate: null,
          }),
        } as unknown as Response;
      }
      const legs = (body.legs as { kwc?: number }[]) || [];
      const annual = legs.reduce((a, lg) => a + (lg.kwc || 1) * 1700, 0);
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
