// ACAL851 — le HARNAIS d'exécution jsdom des scripts pro-10/pro-11, sorti tel quel de
// `estimatorRuntimePro10Pro11.test.ts` (mock `maplibre-gl`, `FakeMap`, DOM minimal, tracé).
// Le `vi.mock` posé ici s'applique : le script est importé DYNAMIQUEMENT (`loadTool`), après.
import { vi } from 'vitest';

// ── MapLibre mock : un faux Map qui capture les handlers et n'instancie AUCUN WebGL.
//    addLayer N'APPELLE PAS onAdd → le calque Three.js ne démarre jamais → sceneRoot reste
//    null → renderScene s'auto-annule. L'optimiseur + le DOM tournent quand même.
export const fakeMaps: FakeMap[] = [];
export class FakeMap {
  handlers: Record<string, ((e: unknown) => void)[]> = {};
  // W113 (atterrissage) — handlers ONE-SHOT (`map.once`) séparés : `fire` les invoque puis
  // les vide. Indispensable pour la re-assertion d'atterrissage `map.once('idle', …)`.
  onceHandlers: Record<string, ((e: unknown) => void)[]> = {};
  controls: unknown[] = [];
  flyToCalls: unknown[] = [];
  jumpToCalls: unknown[] = [];
  easeToCalls: unknown[] = [];
  resizeCalls = 0;
  doubleClickZoom = { disable() {}, enable() {} };
  dragPan = { disable() {}, enable() {} };
  constructor() {
    fakeMaps.push(this);
  }
  on(ev: string, h: (e: unknown) => void) {
    (this.handlers[ev] ||= []).push(h);
    return this;
  }
  // W113 (atterrissage) — `map.once(ev, h)` : un handler qui ne se déclenche qu'une fois.
  once(ev: string, h: (e: unknown) => void) {
    (this.onceHandlers[ev] ||= []).push(h);
    return this;
  }
  fire(ev: string, e: unknown) {
    (this.handlers[ev] || []).forEach((h) => h(e));
    const once = this.onceHandlers[ev] || [];
    this.onceHandlers[ev] = [];
    once.forEach((h) => h(e));
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
  // W113 (atterrissage) — `resize()` recale la taille du conteneur avant un déplacement caméra.
  resize() { this.resizeCalls += 1; return this; }
  easeTo(opts: unknown) { this.easeToCalls.push(opts); return this; }
  flyTo(opts: unknown) { this.flyToCalls.push(opts); return this; }
  jumpTo(opts: unknown) { this.jumpToCalls.push(opts); return this; }
  getBearing() { return 0; }
  getCanvas() { return { style: {} as Record<string, string>, width: 800, height: 600 }; }
  getContainer() { return document.getElementById('rp9-map'); }
  // W92 — les tests peuvent forcer le résultat du hit-test (sommet/obstacle) en posant
  // queryHits[layerId] ; sinon aucun hit (comportement par défaut inchangé).
  queryHits: Record<string, Array<{ properties: Record<string, unknown> }>> = {};
  queryRenderedFeatures(_pt: unknown, opts?: { layers?: string[] }) {
    const layer = opts?.layers?.[0];
    return (layer && this.queryHits[layer]) || [];
  }
  triggerRepaint() {}
  project() { return { x: 0, y: 0 }; }
  unproject() { return { lng: 0, lat: 0 }; }
  remove() {}
  // ACAL377 — style refusé : le script bascule sur un fond de repli local.
  styleLoaded = false;
  isStyleLoaded() { return this.styleLoaded; }
  setStyleCalls: unknown[] = [];
  setStyle(style: unknown) { this.setStyleCalls.push(style); }
}

// W113 — marqueurs MapLibre instanciés (le repère client de l'hydratation). On capture
// chaque Marker créé (couleur + lngLat + ajout/retrait) pour vérifier l'hydratation pin.
export interface FakeMarkerRecord { color?: string; lngLat: [number, number] | null; added: boolean; removed: boolean }
export const fakeMarkers: FakeMarkerRecord[] = [];

vi.mock('maplibre-gl', () => {
  class NavigationControl {}
  // W113 — Marker mocké : un faux marqueur chaînable qui enregistre sa couleur, sa position
  // et son cycle add/remove dans `fakeMarkers` (jamais de DOM/WebGL réel).
  class Marker {
    rec: FakeMarkerRecord;
    constructor(opts?: { color?: string }) {
      this.rec = { color: opts?.color, lngLat: null, added: false, removed: false };
      fakeMarkers.push(this.rec);
    }
    setLngLat(ll: [number, number]) { this.rec.lngLat = ll; return this; }
    addTo() { this.rec.added = true; return this; }
    remove() { this.rec.removed = true; return this; }
  }
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
  const api = { Map: FakeMap, NavigationControl, GeolocateControl, Marker, Point, MercatorCoordinate, GeoJSONSource: class {} };
  return { default: api, ...api };
});

// Un carré de `side` mètres autour d'un point — 4 coins lng/lat pour tracer un toit.
export function squareCorners(side: number, lng0 = -7.62, lat0 = 33.59): [number, number][] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

const ID_INPUTS = ['rp9-bill', 'rp9-address', 'rp9-need-input', 'rp9-cible-kwh', 'rp9-obs-length', 'rp9-obs-width', 'rp9-overhang-input'];
const ID_RANGES = ['rp9-tilt-range', 'rp9-pitch-range', 'rp9-facing-range'];
const ID_BUTTONS = [
  'rp9-finish', 'rp9-clear', 'rp9-undo-point', 'rp9-need-minus', 'rp9-need-plus', 'rp9-tilt-reco',
  'rp9-obstacle', 'rp9-obstacle-clear', 'rp9-obs-delete', 'rp9-obs-plus', 'rp9-obs-minus',
  'rp9-optimum', 'rp9-optimum-apply', 'rp9-cta',
  // W50 — pickers de la fenêtre de production.
  'rp9-prod-month-prev', 'rp9-prod-month-next',
  'rp9-prod-day-prev', 'rp9-prod-day-next', 'rp9-prod-day-reset',
  // W78 (W97 §2) — « + Ajouter une zone » (multi-zones).
  'rp9-add-area',
];
const ID_GENERIC = [
  'rp9-map', 'rp9-status', 'rp9-bill-kwh', 'rp9-config', 'rp9-azimuth-group', 'rp9-compass-arrow',
  'rp9-area-value', 'rp9-need-note', 'rp9-tilt-value', 'rp9-obs-edit', 'rp9-obs-dims',
  'rp9-optimum-note', 'rp9-optimum-card', 'rp9-optimum-label', 'rp9-optimum-source', 'rp9-optimum-kwc',
  'rp9-optimum-panels', 'rp9-optimum-prod', 'rp9-optimum-cover', 'rp9-optimum-why',
  'rp9-flat-controls', 'rp9-flat-only', 'rp9-pitched-controls', 'rp9-pitch-value', 'rp9-pitched-note', 'rp9-facing-note',
  // Correction fine du sens de la pente (curseur + lecture vivante).
  'rp9-facing-value',
  'rp9-reco-title', 'rp9-reco-kwc', 'rp9-reco-panels', 'rp9-reco-prod', 'rp9-reco-cover',
  'rp9-reco-savings', 'rp9-reco-why', 'rp9-reco-bifacial', 'rp9-results', 'rp9-maxline', 'rp9-compare-wrap',
  // W50 — fenêtre de production (conteneur, scope, labels, headline, graphe, source, économies).
  'rp9-prod-window', 'rp9-prod-scope', 'rp9-prod-month-picker', 'rp9-prod-month-label',
  'rp9-prod-day-picker', 'rp9-prod-day-label', 'rp9-prod-headline', 'rp9-prod-sub',
  'rp9-prod-graph', 'rp9-prod-source', 'rp9-prod-savings',
  // W78 (W97 §2) — panneau « Zones » : conteneur, liste, totaux agrégés (panneaux/kWc/prod/éco).
  'rp9-areas-window', 'rp9-areas-list', 'rp9-areas-total-panels', 'rp9-areas-total-kwc',
  'rp9-areas-total-prod', 'rp9-areas-total-savings',
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
export function setupDom() {
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
    // jsdom clampe à [min,max] (défaut 0–100) : on pose des bornes assez larges
    // (sens de la pente 0–359°) pour que les valeurs de test ne soient pas écrêtées.
    r.min = '0';
    r.max = '359';
    r.step = 'any';
    root.appendChild(r);
  }
  for (const id of ID_BUTTONS) root.appendChild(el('button', id));
  // formulaire d'adresse + liste de suggestions (W93 — combobox autocomplétion)
  const form = el('form', 'rp9-search');
  root.appendChild(form);
  root.appendChild(el('ul', 'rp9-suggestions'));
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
  // W97 §1 — champs du diagnostic enrichi que prefillLead pré-remplit (handoff, jamais
  // un POST). lf-orient est un <select> ; prefillLead remonte au <details> parent + défile
  // vers #simulateur (jsdom n'a pas scrollIntoView → on le stubbe juste avant).
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
  const diag = el('details', 'diag') as HTMLDetailsElement;
  diag.appendChild(el('input', 'lf-area'));
  // W110 — coordonnées client surfacées en haut (le composant relocalisé) : Nom / Téléphone /
  // Ville. prefillLead les reporte quand fournis, et remplit la ville depuis rp9-address.
  diag.appendChild(el('input', 'lf-name'));
  diag.appendChild(el('input', 'lf-phone'));
  diag.appendChild(el('input', 'lf-city'));
  const orient = el('select', 'lf-orient') as HTMLSelectElement;
  for (const id of ['sud', 'sud-est', 'sud-ouest', 'est', 'ouest']) {
    const o = document.createElement('option');
    o.value = id;
    orient.appendChild(o);
  }
  diag.appendChild(orient);
  diag.appendChild(el('input', 'lf-kwc-est'));
  root.appendChild(diag);
  // Champs OBLIGATOIRES du diagnostic « une page » (pro-11) que prefillLead pré-remplit
  // depuis le simulateur : adresse (texte), tranche de facture + type de toiture (selects).
  root.appendChild(el('input', 'lf-city'));
  const billSel = el('select', 'lf-bill') as HTMLSelectElement;
  for (const id of ['lt800', '800-1000', '1000-1500', '1500-3000', '3000-5000', '5000-10000', 'gt10000']) {
    const o = document.createElement('option');
    o.value = id;
    billSel.appendChild(o);
  }
  root.appendChild(billSel);
  const roofSel = el('select', 'lf-roof') as HTMLSelectElement;
  for (const id of ['villa', 'hangar', 'toit_plat', 'autre']) {
    const o = document.createElement('option');
    o.value = id;
    roofSel.appendChild(o);
  }
  root.appendChild(roofSel);
  root.appendChild(el('div', 'simulateur'));
  document.body.appendChild(root);
}

export async function loadTool() {
  // import dynamique APRÈS le mock + le DOM ; même export que la page (initRoofToolPro8).
  const mod = await import('../src/scripts/roof-tool-pro11.ts');
  return mod.initRoofToolPro8;
}

export function setBill(v: string) {
  const bill = document.getElementById('rp9-bill') as HTMLInputElement;
  bill.value = v;
  bill.dispatchEvent(new window.Event('input', { bubbles: true }));
}

/** Trace un toit : 4 clics carte (timer 240 ms entre chaque) puis « Terminer ». */
export function traceRoof(map: FakeMap, side = 16) {
  vi.useFakeTimers();
  for (const [lng, lat] of squareCorners(side)) {
    map.fire('click', { lngLat: { lng, lat }, point: { x: 0, y: 0 } });
    vi.advanceTimersByTime(241); // laisse le clic se transformer en sommet
  }
  vi.useRealTimers();
  (document.getElementById('rp9-finish') as HTMLButtonElement).click(); // close() → optimiseur
}

export const txt = (id: string) => document.getElementById(id)?.textContent ?? '';
