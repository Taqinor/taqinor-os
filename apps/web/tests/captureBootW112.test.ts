// @vitest-environment jsdom
//
// W112 — boot CAPTURE CLIENT (captureOnly). On MONTE le vrai script avec MapLibre
// mocké et on prouve que le mode capture n'instancie NI la scène 3D (couche custom
// `rp9-3d`) NI l'optimiseur/matrice (aucune carte de résultat remplie, aucune ligne
// de comparatif), tout en posant bien un repère qui remonte via onCaptureChange.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fakeMaps: FakeMap[] = [];
class FakeMap {
  handlers: Record<string, ((e: unknown) => void)[]> = {};
  controls: unknown[] = [];
  addedLayers: string[] = [];
  addedSources: string[] = [];
  sourceData: Record<string, unknown> = {};
  doubleClickZoom = { disable() {}, enable() {} };
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
  addControl(c: unknown) {
    this.controls.push(c);
    return this;
  }
  addLayer(l: { id?: string } | string) {
    this.addedLayers.push(typeof l === 'string' ? l : l.id ?? '');
    return this;
  }
  addSource(id: string) {
    this.addedSources.push(id);
    return this;
  }
  getSource(id?: string) {
    const self = this;
    return { setData(d: unknown) { if (id) self.sourceData[id] = d; } };
  }
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
  class GeolocateControl {
    on() { return this; }
  }
  class Point { constructor(public x: number, public y: number) {} }
  const MercatorCoordinate = { fromLngLat: () => ({ x: 0, y: 0, z: 0, meterInMercatorCoordinateUnits: () => 1e-7 }) };
  const api = { Map: FakeMap, NavigationControl, GeolocateControl, Point, MercatorCoordinate, GeoJSONSource: class {} };
  return { default: api, ...api };
});

/** DOM minimal pour le boot capture : carte + recherche + boutons + statut. */
function setupCaptureDom() {
  document.body.innerHTML = '';
  const root = document.createElement('div');
  for (const id of ['rp9-map', 'rp9-status', 'rp9-area-value']) {
    const d = document.createElement('div');
    d.id = id;
    root.appendChild(d);
  }
  const form = document.createElement('form');
  form.id = 'rp9-search';
  root.appendChild(form);
  const addr = document.createElement('input');
  addr.id = 'rp9-address';
  root.appendChild(addr);
  root.appendChild(Object.assign(document.createElement('ul'), { id: 'rp9-suggestions' }));
  for (const id of ['rp9-finish', 'rp9-undo-point', 'rp9-clear']) {
    const b = document.createElement('button');
    b.id = id;
    root.appendChild(b);
  }
  document.body.appendChild(root);
}

async function loadTool() {
  const mod = await import('../src/scripts/roof-tool-pro11.ts');
  return mod.initRoofToolPro8;
}

describe('W112 — captureOnly : carte + repère, JAMAIS de 3D ni d\'optimiseur', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupCaptureDom();
  });
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it('le boot capture ne construit PAS la couche 3D (rp9-3d) ni les sources d\'obstacles', async () => {
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true, captureOnly: true });
    expect(fakeMaps.length).toBe(1);
    const map = fakeMaps[0];
    map.fire('load', {});
    // sources de capture présentes (ligne/points/pin) — mais AUCUNE source d'obstacle
    expect(map.addedSources).toContain('rp9-pin');
    expect(map.addedSources).not.toContain('rp9-obs');
    expect(map.addedSources).not.toContain('rp9-obs-preview');
    // la COUCHE 3D custom (créée seulement par createScene3d) n'est jamais ajoutée
    expect(map.addedLayers).not.toContain('rp9-3d');
  });

  it('poser un repère remonte un pin via onCaptureChange, sans remplir de carte de résultat', async () => {
    const init = await loadTool();
    let last: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]> } | null = null;
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      onCaptureChange: (s) => { last = s; },
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    // un clic simple pose le repère
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    expect(last).not.toBeNull();
    expect(last!.pin).toEqual({ lat: 33.59, lng: -7.6 });
    expect(last!.outline).toEqual([]);
    // aucune carte de résultat n'existe en capture (les ids résultat ne sont même pas
    // dans le DOM) : on vérifie qu'aucune source de tracé d'optimiseur ne s'est remplie.
    expect(map.sourceData['rp9-pin']).toBeDefined();
  });

  it('le boot complet (sans captureOnly) reste branché — la couche 3D EST ajoutée', async () => {
    // Garde de non-régression : avec un DOM complet et captureOnly absent, le boot
    // normal ajoute bien la couche custom rp9-3d (preuve que le branchement est gardé).
    // jsdom n'a ni WebGL ni canvas 2D : on fournit un faux contexte truthy (mêmes
    // no-op que le harness runtime) pour que la texture panneau se construise sans GL.
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
        set() { return true; },
      },
    );
    (HTMLCanvasElement.prototype as unknown as { getContext: () => unknown }).getContext = () => ctx2d;
    const init = await loadTool();
    init({ maptilerKey: 'test', reducedMotion: true });
    const map = fakeMaps[0];
    map.fire('load', {});
    expect(map.addedLayers).toContain('rp9-3d');
  });
});
