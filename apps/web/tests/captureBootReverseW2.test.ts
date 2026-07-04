// @vitest-environment jsdom
//
// W2 — boot CAPTURE : poser un repère déclenche un GÉOCODAGE INVERSE qui re-notifie
// la page avec `address` rempli (l'adresse est LUE DEPUIS LA CARTE). On monte le vrai
// script (MapLibre mocké) et on stube fetch pour renvoyer un place_name reverse.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fakeMaps: FakeMap[] = [];
class FakeMap {
  handlers: Record<string, ((e: unknown) => void)[]> = {};
  sourceData: Record<string, unknown> = {};
  doubleClickZoom = { disable() {}, enable() {} };
  constructor() {
    fakeMaps.push(this);
  }
  on(ev: string, h: (e: unknown) => void) {
    (this.handlers[ev] ||= []).push(h);
    return this;
  }
  once(ev: string, h: (e: unknown) => void) {
    // MapLibre Map.once — utilisé par bootCaptureOnly (WJ62, hasRenderedOnce).
    return this.on(ev, h);
  }
  fire(ev: string, e: unknown) {
    (this.handlers[ev] || []).forEach((h) => h(e));
  }
  addControl() {
    return this;
  }
  addLayer() {
    return this;
  }
  addSource() {
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
  getCanvas() { return { style: {} as Record<string, string>, width: 800, height: 600 }; }
  getContainer() { return document.getElementById('rp9-map'); }
  remove() {}
  setStyle() {}
}

vi.mock('maplibre-gl', () => {
  class NavigationControl {}
  class GeolocateControl {
    on() { return this; }
  }
  class Point { constructor(public x: number, public y: number) {} }
  const api = { Map: FakeMap, NavigationControl, GeolocateControl, Point, GeoJSONSource: class {} };
  return { default: api, ...api };
});

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

describe('W2 — capture : repère → reverseGeocode → onCaptureChange({ address })', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupCaptureDom();
  });
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  // Import lourd (roof-tool-pro11) sous jsdom : on laisse une marge généreuse.
  it('poser un repère remonte d\'abord le pin, puis une adresse géocodée inverse', { timeout: 20000 }, async () => {
    let reverseUrl = '';
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        reverseUrl = String(url);
        return { ok: true, json: async () => ({ features: [{ place_name: 'Hay Riad, Rabat, Maroc' }] }) } as unknown as Response;
      }),
    );

    const states: Array<{ pin: { lat: number; lng: number } | null; address?: string | null }> = [];
    const init = await loadTool();
    init({
      maptilerKey: 'KEY',
      reducedMotion: true,
      captureOnly: true,
      onCaptureChange: (s) => states.push(s),
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    map.fire('click', { lngLat: { lng: -6.84, lat: 34.02 }, point: { x: 0, y: 0 } });

    // micro-tâches : laisse le reverseGeocode (promesse) se résoudre + re-notifier
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));

    // 1er onCaptureChange = pin sans adresse ; un onCaptureChange ULTÉRIEUR porte l'adresse
    expect(states[0].pin).toEqual({ lat: 34.02, lng: -6.84 });
    const withAddr = states.find((s) => s.address);
    expect(withAddr?.address).toBe('Hay Riad, Rabat, Maroc');
    // l'URL appelée est bien l'endpoint reverse {lng},{lat}.json
    expect(reverseUrl).toContain('/geocoding/');
    expect(reverseUrl).toContain('.json');
    expect(reverseUrl).toContain('language=fr');
    expect(reverseUrl).toContain('country=ma');
  });
});
