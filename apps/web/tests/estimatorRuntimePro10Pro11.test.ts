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
  addControl() { return this; }
  addLayer() { return this; }
  addSource() { return this; }
  getSource() { return { setData() {} }; }
  getLayer() { return null; }
  removeLayer() {}
  easeTo() { return this; }
  flyTo() { return this; }
  jumpTo() { return this; }
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
  class Point {
    x: number; y: number;
    constructor(x: number, y: number) { this.x = x; this.y = y; }
  }
  const MercatorCoordinate = {
    fromLngLat: () => ({ x: 0, y: 0, z: 0, meterInMercatorCoordinateUnits: () => 1e-7 }),
  };
  const api = { Map: FakeMap, NavigationControl, Point, MercatorCoordinate, GeoJSONSource: class {} };
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
];
const ID_GENERIC = [
  'rp9-map', 'rp9-status', 'rp9-bill-kwh', 'rp9-config', 'rp9-azimuth-group', 'rp9-compass-arrow',
  'rp9-area-value', 'rp9-need-note', 'rp9-tilt-value', 'rp9-obs-edit', 'rp9-obs-dims',
  'rp9-optimum-note', 'rp9-optimum-card', 'rp9-optimum-label', 'rp9-optimum-source', 'rp9-optimum-kwc',
  'rp9-optimum-panels', 'rp9-optimum-prod', 'rp9-optimum-cover', 'rp9-optimum-why',
  'rp9-flat-controls', 'rp9-flat-only', 'rp9-pitched-controls', 'rp9-pitch-value', 'rp9-pitched-note',
  'rp9-reco-title', 'rp9-reco-kwc', 'rp9-reco-panels', 'rp9-reco-prod', 'rp9-reco-cover',
  'rp9-reco-savings', 'rp9-reco-why', 'rp9-reco-bifacial', 'rp9-results', 'rp9-maxline', 'rp9-compare-wrap',
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
});
