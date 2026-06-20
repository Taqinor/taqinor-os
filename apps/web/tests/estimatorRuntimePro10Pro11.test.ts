// @vitest-environment jsdom
//
// HARNESS D'EXÉCUTION (jsdom) pour les scripts d'estimateur pro-10 (W34, toit plat) et
// pro-11 (W35, toit en pente) — la couche INTERACTIVE que les tests de moteur (V7/V8) et
// les tests de garde "chaîne de caractères" NE FONT PAS tourner. Ici on MONTE vraiment le
// script dans un faux DOM, avec MapLibre mocké (et donc Three.js jamais instancié :
// `renderScene` s'auto-annule car `sceneRoot` reste null), on simule un tracé de toit, et
// on vérifie que l'OPTIMISEUR VIVANT se déclenche et remplit la carte de résultats — puis
// qu'un changement d'option RE-RÉSOUT en direct. C'est ce qui attrape un sélecteur cassé,
// un null deref, une erreur de câblage : des bugs qu'aucun test de moteur ne voit.
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
  // W77 — on capte les setData par id de source pour pouvoir compter les sommets posés
  // (`rp9-pts`) et vérifier qu'aucun coin n'est jeté en traçant vite.
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
  queryRenderedFeatures() { return []; }
  triggerRepaint() {}
  project() { return { x: 0, y: 0 }; }
  unproject() { return { lng: 0, lat: 0 }; }
  remove() {}
  setStyle() {}
}

vi.mock('maplibre-gl', () => {
  class NavigationControl {}
  // W91 — GeolocateControl natif mocké : un émetteur d'événements minimal (on/fire) pour
  // que l'entrée puisse s'abonner à `geolocate` et qu'un test déclenche une position.
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
  'rp9-finish', 'rp9-clear', 'rp9-need-minus', 'rp9-need-plus', 'rp9-tilt-reco',
  'rp9-obstacle', 'rp9-obstacle-clear', 'rp9-obs-delete', 'rp9-obs-plus', 'rp9-obs-minus',
  'rp9-optimum', 'rp9-optimum-apply', 'rp9-cta',
  // W50 — pickers de la fenêtre de production.
  'rp9-prod-month-prev', 'rp9-prod-month-next',
  'rp9-prod-day-prev', 'rp9-prod-day-next', 'rp9-prod-day-reset',
];
const ID_GENERIC = [
  'rp9-map', 'rp9-status', 'rp9-bill-kwh', 'rp9-config', 'rp9-azimuth-group', 'rp9-compass-arrow',
  'rp9-area-value', 'rp9-need-note', 'rp9-tilt-value', 'rp9-obs-edit', 'rp9-obs-dims',
  'rp9-optimum-note', 'rp9-optimum-card', 'rp9-optimum-label', 'rp9-optimum-source', 'rp9-optimum-kwc',
  'rp9-optimum-panels', 'rp9-optimum-prod', 'rp9-optimum-cover', 'rp9-optimum-why',
  'rp9-flat-controls', 'rp9-flat-only', 'rp9-pitched-controls', 'rp9-pitch-value', 'rp9-pitched-note',
  'rp9-reco-title', 'rp9-reco-kwc', 'rp9-reco-panels', 'rp9-reco-prod', 'rp9-reco-cover',
  'rp9-reco-savings', 'rp9-reco-why', 'rp9-reco-bifacial', 'rp9-results', 'rp9-maxline', 'rp9-compare-wrap',
  // W50 — fenêtre de production (conteneur, scope, labels, headline, graphe, source, économies).
  'rp9-prod-window', 'rp9-prod-scope', 'rp9-prod-month-picker', 'rp9-prod-month-label',
  'rp9-prod-day-picker', 'rp9-prod-day-label', 'rp9-prod-headline', 'rp9-prod-sub',
  'rp9-prod-graph', 'rp9-prod-source', 'rp9-prod-savings',
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
  // jsdom n'a ni WebGL ni canvas 2D. Le script (a) sonde `getContext('webgl')` — il
  // lèverait « WebGL indisponible » (repli gracieux normal) — et (b) génère une texture
  // panneau via un contexte 2D. On renvoie un faux contexte truthy dont les méthodes sont
  // des no-op et `createLinearGradient` renvoie un dégradé stub. Le calque Three.js ne
  // démarre jamais (addLayer mocké n'appelle pas onAdd) → la texture/GL ne sert jamais.
  const grad = { addColorStop() {} };
  const ctx2d = new Proxy(
    {},
    {
      get(_t, prop) {
        if (prop === 'createLinearGradient' || prop === 'createRadialGradient' || prop === 'createPattern') return () => grad;
        if (prop === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
        if (prop === 'measureText') return () => ({ width: 0 });
        if (prop === 'canvas') return { width: 512, height: 280 };
        return () => undefined; // toute autre méthode = no-op
      },
      set() {
        return true; // fillStyle = ... → ignoré
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
  // formulaire d'adresse
  const form = el('form', 'rp9-search');
  root.appendChild(form);
  // groupes de puces (avec badge « Recommandé » là où le script l'attend)
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
  // W50 — les puces de scope [data-prod-scope] vivent À L'INTÉRIEUR de #rp9-prod-scope
  // (le script les interroge via prodScopeWrap.querySelectorAll). On les y insère.
  const scopeWrap = root.querySelector('#rp9-prod-scope');
  if (scopeWrap) {
    for (const v of ['year', 'month', 'day']) {
      const b = el('button') as HTMLButtonElement;
      b.setAttribute('data-prod-scope', v);
      b.setAttribute('aria-pressed', String(v === 'year'));
      scopeWrap.appendChild(b);
    }
  }
  // tableau matrice : <table><tbody id=rp9-compare> + en-têtes de tri + filtre
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
  document.body.appendChild(root);
}

async function loadTool() {
  // import dynamique APRÈS le mock + le DOM ; même export que la page (initRoofToolPro8).
  const mod = await import('../src/scripts/roof-tool-pro11.ts');
  return mod.initRoofToolPro8;
}

function setBill(v: string) {
  const bill = document.getElementById('rp9-bill') as HTMLInputElement;
  bill.value = v;
  bill.dispatchEvent(new window.Event('input', { bubbles: true }));
}

/** Trace un toit : 4 clics carte (timer 240 ms entre chaque) puis « Terminer ». */
function traceRoof(map: FakeMap, side = 16) {
  vi.useFakeTimers();
  for (const [lng, lat] of squareCorners(side)) {
    map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
    vi.advanceTimersByTime(241); // laisse le clic se transformer en sommet
  }
  vi.useRealTimers();
  (document.getElementById('rp9-finish') as HTMLButtonElement).click(); // close() → optimiseur
}

const txt = (id: string) => document.getElementById(id)?.textContent ?? '';

describe('runtime pro-10/pro-11 — montage du script sans crash', () => {
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

  it('initRoofToolPro8 monte sans lancer d\'exception et crée la carte', async () => {
    const init = await loadTool();
    expect(() => init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) })).not.toThrow();
    expect(fakeMaps.length).toBe(1); // la carte a bien été instanciée
  });
});

describe('runtime W34 (toit plat) — l\'optimiseur vivant se déclenche et remplit la carte', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('tracer un toit lance le calcul et remplit puissance + production + couverture', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    // l'optimiseur vivant a posé un résultat (pas le « — » initial)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-kwc')).not.toBe('—');
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);
    expect(txt('rp9-reco-cover')).toMatch(/%/);
    // un badge « Recommandé » est posé quelque part (au moins un visible)
    const badges = Array.from(document.querySelectorAll<HTMLElement>('.rp9-reco-badge'));
    expect(badges.some((b) => !b.hidden)).toBe(true);
  });

  it('changer une option (pleine rive) RE-RÉSOUT en direct sans casser la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    const before = txt('rp9-reco-kwc');
    const removeMargin = document.querySelector<HTMLButtonElement>('[data-margin="remove"]')!;
    expect(() => removeMargin.click()).not.toThrow();
    // la marge verrouillée est tenue (puce pressée) et la carte reste remplie
    expect(removeMargin.getAttribute('aria-pressed')).toBe('true');
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(before).toMatch(/kWc/);
  });

  it('le tableau matrice (comparatif) est rempli et visible après le tracé', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    const rows = document.querySelectorAll('#rp9-compare tr');
    expect(rows.length).toBeGreaterThan(1); // plus d'une config évaluée affichée
    expect((document.getElementById('rp9-compare-wrap') as HTMLElement).hidden).toBe(false);
  });
});

describe('runtime W35 (toit en pente) — l\'optimiseur pente se déclenche', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('basculer en « Toit en pente » re-calcule la pose affleurante et remplit la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    // bascule pente (via la puce data-rooftype, câblée par createRoofTypeSelect)
    const pitchedBtn = document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!;
    expect(() => pitchedBtn.click()).not.toThrow();
    // les contrôles propres au plat sont masqués, le bloc pente visible
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('rp9-pitched-controls') as HTMLElement).hidden).toBe(false);
    // la carte affiche un résultat pente (puissance + production)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);
    expect(txt('rp9-reco-title')).toMatch(/pente/i);
  });

  it('en pente, changer la pose (paysage) re-résout sans casser la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    const landscape = document.querySelector<HTMLButtonElement>('[data-orient="landscape"]')!;
    expect(() => landscape.click()).not.toThrow();
    expect(landscape.getAttribute('aria-pressed')).toBe('true');
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });

  // W47 — en pente, les orientations IMPOSSIBLES (plein-sud tourné via data-family,
  // tente Est-Ouest, azimut) sont confinées à #rp9-flat-only, masqué dès le passage en
  // pente. « Alignée toit » est l'orientation de fait (coplanaire). Le toit plat les
  // ré-offre quand on rebascule (rien n'est cassé).
  it('W47 — passer en pente masque les orientations plates impossibles (flat-only caché)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    // plat : les orientations sont offertes
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(false);
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    // pente : flat-only masqué → plein-sud tourné / Est-Ouest / azimut non offerts
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(true);
    expect((document.getElementById('rp9-pitched-controls') as HTMLElement).hidden).toBe(false);
    // la carte pente est remplie (pose affleurante alignée toit par défaut)
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-title')).toMatch(/pente/i);
    // rebascule plat : les orientations re-apparaissent (rien cassé)
    document.querySelector<HTMLButtonElement>('[data-rooftype="flat"]')!.click();
    expect((document.getElementById('rp9-flat-only') as HTMLElement).hidden).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W46 — L'OPTIMISEUR RE-RÉSOUT APRÈS CHAQUE VERROU (pas seulement les deux premiers).
// On MONTE le vrai script avec une surface PVGIS injectée (rendement qui dépend de
// l'inclinaison ET de l'aspect) sur un toit TOURNÉ, puis on VERROUILLE des axes un par un
// (3ᵉ, 4ᵉ, 5ᵉ verrou) en vérifiant que chaque verrou est TENU et que les axes encore AUTO
// sont re-résolus (la production change quand un verrou déplace réellement l'optimum). On
// vérifie aussi que LIBÉRER un axe (« Recommandé » de l'inclinaison) garde TOUS les autres
// verrous accumulés — le bug W46 = un bouton qui effaçait tout après quelques verrous.
// ════════════════════════════════════════════════════════════════════════════════════

/** Toit RECTANGULAIRE TOURNÉ de `rotDeg` (sens horaire) → « aligné toit » est un vrai choix
 *  distinct du plein sud et l'Est-Ouest diffère. */
function rotatedCorners(lenM: number, widM: number, rotDeg: number, lng0 = -7.62, lat0 = 33.59): [number, number][] {
  const r = (rotDeg * Math.PI) / 180;
  const cos = Math.cos(r), sin = Math.sin(r);
  const mPerLat = 111320, mPerLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const corners: [number, number][] = [[-lenM / 2, -widM / 2], [lenM / 2, -widM / 2], [lenM / 2, widM / 2], [-lenM / 2, widM / 2]];
  return corners.map(([x, y]) => {
    const xr = x * cos - y * sin, yr = x * sin + y * cos;
    return [lng0 + xr / mPerLng, lat0 + yr / mPerLat] as [number, number];
  });
}

/** Trace un toit à partir de coins lng/lat fournis (toit tourné), puis « Terminer ». */
function traceCorners(map: FakeMap, corners: [number, number][]) {
  vi.useFakeTimers();
  for (const [lng, lat] of corners) {
    map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
    vi.advanceTimersByTime(241);
  }
  vi.useRealTimers();
  (document.getElementById('rp9-finish') as HTMLButtonElement).click();
}

/** Laisse résoudre les promesses PVGIS (warming async) + le débattement 280 ms du tilt. */
async function flushPvgis() {
  for (let i = 0; i < 25; i++) await Promise.resolve();
  await new Promise((r) => setTimeout(r, 350));
  for (let i = 0; i < 25; i++) await Promise.resolve();
}

/** Production annuelle (kWh) affichée, en nombre (sépare les espaces fines). */
function prod(): number {
  return Number((txt('rp9-reco-prod').match(/[\d   ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));
}
/** Valeurs des puces d'un groupe actuellement « pressées » (verrou ou miroir du gagnant). */
function pressedVals(attr: string): string[] {
  return Array.from(document.querySelectorAll<HTMLButtonElement>(`[${attr}]`))
    .filter((b) => b.getAttribute('aria-pressed') === 'true')
    .map((b) => b.getAttribute(attr) || '');
}

describe('W46 (toit plat) — re-résolution après CHAQUE verrou (3ᵉ, 4ᵉ, Nᵉ)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    // PVGIS PRÉSENT : rendement = surface non triviale en (inclinaison, aspect) → chaque
    // verrou qui déplace l'optimum DOIT changer la production. Pic à 29°, plein sud.
    vi.stubGlobal('fetch', vi.fn(async (_url: string, init: { body: string }) => {
      const body = JSON.parse(init.body) as { legs: { tiltDeg: number; aspect: number; kwc: number }[] };
      let annual = 0;
      for (const lg of body.legs) {
        const y = Math.max(200, 1800 - Math.abs(lg.tiltDeg - 29) * 12 - Math.abs(lg.aspect) * 8);
        annual += (lg.kwc || 1) * y;
      }
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it('verrouiller le 3ᵉ puis le 4ᵉ axe re-résout (la production change) et TIENT tous les verrous', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('2500');
    traceCorners(fakeMaps[0], rotatedCorners(30, 18, 35));
    await flushPvgis();

    // Verrou 1 : orientation Est-Ouest (sous-optimale ici → l'optimum change vraiment).
    document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.click();
    await flushPvgis();
    const afterLock1 = prod();
    expect(pressedVals('data-family')).toContain('eastwest');

    // Verrou 2 : pose paysage.
    document.querySelector<HTMLButtonElement>('[data-orient="landscape"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-orient')).toContain('landscape');

    // Verrou 3 : inclinaison 10° (loin du pic 29° → la production DOIT chuter).
    document.querySelector<HTMLButtonElement>('[data-tilt="10"]')!.click();
    await flushPvgis();
    const afterLock3 = prod();
    expect(pressedVals('data-tilt')).toContain('10');
    expect(afterLock3).toBeLessThan(afterLock1); // le 3ᵉ verrou a bien re-résolu
    // tous les verrous précédents sont TENUS (accumulation)
    expect(pressedVals('data-family')).toContain('eastwest');
    expect(pressedVals('data-orient')).toContain('landscape');

    // Verrou 4 : marge pleine rive — re-résout encore (le 4ᵉ verrou n'est pas ignoré).
    document.querySelector<HTMLButtonElement>('[data-margin="remove"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-margin')).toContain('remove');
    // les trois verrous précédents tiennent toujours
    expect(pressedVals('data-family')).toContain('eastwest');
    expect(pressedVals('data-orient')).toContain('landscape');
    expect(pressedVals('data-tilt')).toContain('10');

    // Changer un axe DÉJÀ verrouillé (inclinaison 10 → 29 = le pic) re-résout : production remonte.
    const beforeRetilt = prod();
    document.querySelector<HTMLButtonElement>('[data-tilt="29"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-tilt')).toContain('29');
    expect(prod()).toBeGreaterThan(beforeRetilt); // 29° (pic) > 10°
    // les autres verrous restent tenus pendant ce changement
    expect(pressedVals('data-family')).toContain('eastwest');
    expect(pressedVals('data-orient')).toContain('landscape');
    expect(pressedVals('data-margin')).toContain('remove');
  }, 60000);

  it('libérer l\'inclinaison (« Recommandé ») garde les AUTRES verrous accumulés (W46 §3)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('2500');
    traceCorners(fakeMaps[0], rotatedCorners(30, 18, 35));
    await flushPvgis();

    document.querySelector<HTMLButtonElement>('[data-family="eastwest"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-orient="landscape"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-tilt="10"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-tilt')).toContain('10');

    // LIBÉRER l'inclinaison via la puce « Recommandé » — ne doit PAS effacer family/orient.
    document.querySelector<HTMLButtonElement>('[data-tilt="reco"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-family')).toContain('eastwest'); // verrou conservé
    expect(pressedVals('data-orient')).toContain('landscape'); // verrou conservé
    // l'inclinaison est re-libérée : la production remonte vers l'optimum tenu (≠ 10° figé)
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);

    // Le BOUTON tilt-reco dédié (rp9-tilt-reco) doit faire pareil (ne pas tout réinitialiser).
    document.querySelector<HTMLButtonElement>('[data-tilt="15"]')!.click();
    await flushPvgis();
    expect(pressedVals('data-tilt')).toContain('15');
    (document.getElementById('rp9-tilt-reco') as HTMLButtonElement).click();
    await flushPvgis();
    expect(pressedVals('data-family')).toContain('eastwest'); // toujours tenu
    expect(pressedVals('data-orient')).toContain('landscape'); // toujours tenu
  }, 60000);

  it('la séquence se termine quand TOUS les axes sont verrouillés (rien ne flotte)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('2500');
    traceCorners(fakeMaps[0], rotatedCorners(30, 18, 35));
    await flushPvgis();

    // Verrouille les CINQ axes exposés : orientation(famille) + azimut + inclinaison + pose + marge.
    document.querySelector<HTMLButtonElement>('[data-family="south"]')!.click();
    await flushPvgis();
    // azimut visible seulement sur toit tourné → présent ici
    const aligned = document.querySelector<HTMLButtonElement>('[data-azimuth="aligned"]')!;
    aligned.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-tilt="29"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-orient="portrait"]')!.click();
    await flushPvgis();
    document.querySelector<HTMLButtonElement>('[data-margin="remove"]')!.click();
    await flushPvgis();

    // Tous tenus, la carte reste remplie (pas de crash, pas de blanc).
    expect(pressedVals('data-azimuth')).toContain('aligned');
    expect(pressedVals('data-tilt')).toContain('29');
    expect(pressedVals('data-orient')).toContain('portrait');
    expect(pressedVals('data-margin')).toContain('remove');
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
    expect(txt('rp9-reco-prod')).toMatch(/kWh\/an/);

    // « Réinitialiser » relâche TOUT → retour à l'optimum global.
    (document.getElementById('rp9-optimum') as HTMLButtonElement).click();
    await flushPvgis();
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  }, 60000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// W50 — FENÊTRE « PRODUCTION ESTIMÉE » (Année / Mois / Jour). On MONTE le vrai script,
// mock /api/roof-production (jamais PVGIS directement), trace un toit, et vérifie : le
// scope donne la bonne série (Année=12 mois, Jour=courbe 24 h), le cyclage mois parcourt
// les 12 mois, le jour démarre sur le jour TYPE puis une date précise le surcharge, et
// éditer le nombre de panneaux rescale toutes les figures (linéarité, sans nouvel appel
// PVGIS direct). Le client appelle bien /api/roof-production.
// ════════════════════════════════════════════════════════════════════════════════════

const PANEL_KWC_TEST = 0.72;

/** Production PAR 1 kWc déterministe (mensuels distincts → on repère le mois affiché). */
function perKwcFixture() {
  const monthly = [80, 90, 120, 140, 160, 175, 180, 170, 145, 120, 95, 75]; // kWh/kWc/mois
  const annual = monthly.reduce((a, b) => a + b, 0);
  const daysIn = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const bell = (peak: number) => {
    const out = new Array<number>(24).fill(0);
    for (let h = 6; h <= 18; h++) {
      const x = (h - 12) / 4;
      out[h] = peak * Math.exp(-0.5 * x * x);
    }
    const s = out.reduce((a, b) => a + b, 0);
    return out.map((v) => (s > 0 ? v : 0));
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

/** Mock fetch : /api/roof-production renvoie la fixture mise à l'échelle par placedPanels ;
 *  /api/roof-yield renvoie un rendement plausible ; toute URL est enregistrée. */
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
        const monthlyKwh = fx.monthly.map((v) => v * kwc);
        const annualKwh = fx.annual * kwc;
        const dailyKwhByMonth = fx.dailyKwhByMonth.map((v) => v * kwc);
        const typicalDayByMonth = fx.typicalDayByMonth.map((prof) => prof.map((v) => v * kwc));
        let specificDate = null;
        if (typeof body.dateMonth === 'number' && typeof body.dateDay === 'number') {
          // Date précise : profil clairement DIFFÉRENT du jour type (pic ×3) → on le repère.
          const peak = 3;
          const out = new Array<number>(24).fill(0);
          for (let h = 6; h <= 18; h++) {
            const x = (h - 12) / 4;
            out[h] = peak * Math.exp(-0.5 * x * x);
          }
          const hourlyKw = out.map((v) => v * kwc);
          specificDate = {
            month: body.dateMonth,
            day: body.dateDay,
            hourlyKw,
            dailyKwh: hourlyKw.reduce((a, b) => a + b, 0),
            yearsAveraged: 5,
          };
        }
        return {
          ok: true,
          json: async () => ({
            ok: true,
            source: 'pvgis',
            cacheHit: false,
            placedPanels: panels,
            panelKwc: PANEL_KWC_TEST,
            placedKwc: kwc,
            annualKwh,
            monthlyKwh,
            dailyKwhByMonth,
            typicalDayByMonth,
            specificDate,
          }),
        } as unknown as Response;
      }
      // /api/roof-yield : rendement plausible (PVGIS GPS exact) pour l'optimiseur.
      const legs = (body.legs as { kwc?: number }[]) || [];
      const annual = legs.reduce((a, lg) => a + (lg.kwc || 1) * 1700, 0);
      return { ok: true, json: async () => ({ ok: true, annualKwh: annual }) } as unknown as Response;
    }),
  );
}

/** kWh affichés dans le headline de la fenêtre de production (nombre). */
function prodHeadlineKwh(): number {
  return Number((txt('rp9-prod-headline').match(/[\d  ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));
}

describe('W50 — fenêtre de production : scope, cyclage, jour type/date, rescale', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function mount() {
    const urls: string[] = [];
    installProductionFetch(urls);
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    traceRoof(fakeMaps[0]);
    await flushPvgis();
    return urls;
  }

  it('la fenêtre se remplit (kWh/an) et le client appelle /api/roof-production', async () => {
    const urls = await mount();
    expect((document.getElementById('rp9-prod-window') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-prod-headline')).toMatch(/kWh\/an/);
    expect(prodHeadlineKwh()).toBeGreaterThan(0);
    // le client appelle bien la route serveur — JAMAIS PVGIS directement
    expect(urls.some((u) => u.includes('/api/roof-production'))).toBe(true);
    expect(urls.some((u) => u.includes('pvgis') || u.includes('re.jrc.ec.europa.eu'))).toBe(false);
    // un graphe SVG a été rendu (12 barres mensuelles)
    expect(document.querySelectorAll('#rp9-prod-graph rect').length).toBe(12);
  }, 60000);

  it('toggle Mois puis Jour change la série (Jour = courbe 24 points)', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-prod-scope="month"]')!.click();
    await flushPvgis();
    expect(txt('rp9-prod-sub')).toMatch(/Production de/i);
    expect((document.getElementById('rp9-prod-month-picker') as HTMLElement).hidden).toBe(false);
    // Jour : une courbe (path) au lieu de barres
    document.querySelector<HTMLButtonElement>('[data-prod-scope="day"]')!.click();
    await flushPvgis();
    expect((document.getElementById('rp9-prod-day-picker') as HTMLElement).hidden).toBe(false);
    expect(document.querySelectorAll('#rp9-prod-graph path').length).toBeGreaterThan(0);
    expect(txt('rp9-prod-sub')).toMatch(/jour type/i); // défaut = jour type
  }, 60000);

  it('cycler les mois parcourt les 12 mois et revient au point de départ', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-prod-scope="month"]')!.click();
    await flushPvgis();
    const next = document.getElementById('rp9-prod-month-next') as HTMLButtonElement;
    const seen = new Set<string>();
    for (let i = 0; i < 12; i++) {
      seen.add(txt('rp9-prod-month-label'));
      next.click();
      await flushPvgis();
    }
    expect(seen.size).toBe(12); // tous les mois affichés
  }, 60000);

  it('le jour démarre sur le JOUR TYPE ; une date choisie le surcharge', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-prod-scope="day"]')!.click();
    await flushPvgis();
    const typicalKwh = prodHeadlineKwh();
    expect(txt('rp9-prod-day-label')).toMatch(/jour type/i);
    // choisir une date précise (flèche jour suivant) → le profil change (pic ×3 dans le mock)
    (document.getElementById('rp9-prod-day-next') as HTMLButtonElement).click();
    await flushPvgis();
    expect(txt('rp9-prod-day-label')).not.toMatch(/jour type/i); // date précise affichée
    expect(prodHeadlineKwh()).toBeGreaterThan(typicalKwh); // la date pic ×3 > jour type
    // « Jour type » ramène au profil moyen
    const resetBtn = document.getElementById('rp9-prod-day-reset') as HTMLButtonElement;
    expect(resetBtn.hidden).toBe(false);
    resetBtn.click();
    await flushPvgis();
    expect(txt('rp9-prod-day-label')).toMatch(/jour type/i);
  }, 60000);

  it('éditer le nombre de panneaux rescale les figures (linéarité)', async () => {
    await mount();
    const before = prodHeadlineKwh();
    expect(before).toBeGreaterThan(0);
    // augmente le besoin → plus de panneaux posés → production plus haute
    const needInput = document.getElementById('rp9-need-input') as HTMLInputElement;
    const baseNeed = Number(needInput.value.replace(/[^\d]/g, '')) || 1;
    needInput.value = String(baseNeed + 6);
    needInput.dispatchEvent(new window.Event('input', { bubbles: true }));
    await flushPvgis();
    const after = prodHeadlineKwh();
    expect(after).toBeGreaterThan(before); // plus de panneaux → plus de production
  }, 60000);

  it('en pente, la fenêtre reflète la pose affleurante (building) et reste remplie', async () => {
    await mount();
    document.querySelector<HTMLButtonElement>('[data-rooftype="pitched"]')!.click();
    await flushPvgis();
    expect((document.getElementById('rp9-prod-window') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-prod-headline')).toMatch(/kWh\/an/);
  }, 60000);
});

// ════════════════════════════════════════════════════════════════════════════════════
// W91 — bouton « ma position » (GeolocateControl natif MapLibre, aucune dépendance ajoutée).
// On vérifie que le contrôle est bien AJOUTÉ à la carte, et qu'une position géolocalisée
// recentre en zoom 19 (flyTo en mouvement normal, jumpTo en reduced-motion).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W91 (map) — bouton ma position (GeolocateControl)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  function geolocateControl(map: FakeMap) {
    return map.controls.find(
      (c) => typeof (c as { fire?: unknown }).fire === 'function' && 'geoHandlers' in (c as object),
    ) as { fire: (ev: string, e: unknown) => void } | undefined;
  }

  it('un GeolocateControl est ajouté à la carte', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    expect(geolocateControl(fakeMaps[0])).toBeDefined();
  });

  it('géolocaliser recentre en zoom 19 (flyTo en mouvement normal)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: false, roofType: createRoofTypeSelect(document) });
    const ctrl = geolocateControl(fakeMaps[0])!;
    ctrl.fire('geolocate', { coords: { longitude: -7.62, latitude: 33.59 } });
    const calls = fakeMaps[0].flyToCalls as Array<{ center: [number, number]; zoom: number }>;
    expect(calls.length).toBeGreaterThan(0);
    const last = calls[calls.length - 1];
    expect(last.zoom).toBe(19);
    expect(last.center).toEqual([-7.62, 33.59]);
  });

  it('en reduced-motion, géolocaliser saute (jumpTo) en zoom 19', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    const ctrl = geolocateControl(fakeMaps[0])!;
    ctrl.fire('geolocate', { coords: { longitude: -7.62, latitude: 33.59 } });
    const calls = fakeMaps[0].jumpToCalls as Array<{ center: [number, number]; zoom: number }>;
    expect(calls.some((c) => c.zoom === 19)).toBe(true);
  });
});

// ════════════════════════════════════════════════════════════════════════════════════
// W77 — PARITÉ TACTILE DU TRACÉ : double-tap pour finir + aucun coin perdu en traçant vite.
// On compte les sommets réellement posés via la source `rp9-pts` captée par FakeMap, et on
// vérifie que (1) tracer 4 coins distincts PLUS VITE que le délai anti-dblclick n'en perd
// aucun, (2) un double-tap tactile au même endroit FERME le tracé, (3) le double-clic
// desktop ferme SANS laisser de sommet parasite (comportement desktop inchangé).
// ════════════════════════════════════════════════════════════════════════════════════
describe('runtime W77 (map) — parité tactile du tracé', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  // Nombre de sommets actuellement posés (features de la source rp9-pts).
  function vertexCount(map: FakeMap): number {
    const d = map.sourceData['rp9-pts'] as { features?: unknown[] } | undefined;
    return d?.features?.length ?? 0;
  }

  // 4 coins d'un carré, à des POINTS écran DISTINCTS (sinon le garde double-tap les
  // confondrait). lng/lat n'ont pas besoin d'être exacts pour le comptage de sommets.
  const corners: Array<{ lng: number; lat: number; x: number; y: number }> = [
    { lng: -7.62, lat: 33.59, x: 100, y: 100 },
    { lng: -7.619, lat: 33.59, x: 300, y: 100 },
    { lng: -7.619, lat: 33.591, x: 300, y: 300 },
    { lng: -7.62, lat: 33.591, x: 100, y: 300 },
  ];

  it('tracer 4 coins PLUS VITE que le délai ne perd aucun sommet', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    const map = fakeMaps[0];
    vi.useFakeTimers();
    // chaque clic n'avance le temps que de 50 ms (< 240 ms) → l'ancien code jetait
    // les coins rapides ; le nouveau pose d'abord le précédent.
    for (const c of corners) {
      map.fire('click', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      vi.advanceTimersByTime(50);
    }
    vi.advanceTimersByTime(300); // laisse le dernier délai s'écouler
    vi.useRealTimers();
    expect(vertexCount(map)).toBe(4); // les 4 coins posés, aucun perdu
  });

  it('double-tap tactile au même endroit FERME le tracé', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    // pose 3 coins distincts au doigt (touchend + click synthétique chacun)
    vi.useFakeTimers();
    for (const c of corners.slice(0, 3)) {
      map.fire('touchend', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      map.fire('click', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      vi.advanceTimersByTime(241); // chaque coin posé
    }
    expect(vertexCount(map)).toBe(3);
    // double-tap au MÊME endroit (dans la fenêtre 300 ms) = terminer
    const last = corners[2];
    map.fire('touchend', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y } });
    vi.advanceTimersByTime(120);
    map.fire('touchend', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y } });
    vi.useRealTimers();
    // close() a tourné → la config est visible et le calcul rempli
    expect((document.getElementById('rp9-config') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });

  it('double-clic desktop ferme SANS laisser de sommet parasite (desktop inchangé)', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document) });
    setBill('1500');
    const map = fakeMaps[0];
    vi.useFakeTimers();
    for (const c of corners.slice(0, 3)) {
      map.fire('click', { lngLat: { lng: c.lng, lat: c.lat }, point: { x: c.x, y: c.y } });
      vi.advanceTimersByTime(241);
    }
    expect(vertexCount(map)).toBe(3);
    // double-clic au même endroit que le 3ᵉ coin : 2ᵉ clic immédiat puis dblclick
    const last = corners[2];
    map.fire('click', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y } });
    map.fire('dblclick', { lngLat: { lng: last.lng, lat: last.lat }, point: { x: last.x, y: last.y }, preventDefault() {} });
    vi.useRealTimers();
    // fermé avec EXACTEMENT 3 sommets (le clic du double-clic n'a pas ajouté de 4ᵉ)
    expect((document.getElementById('rp9-config') as HTMLElement).hidden).toBe(false);
    expect(txt('rp9-reco-kwc')).toMatch(/kWc/);
  });
});
