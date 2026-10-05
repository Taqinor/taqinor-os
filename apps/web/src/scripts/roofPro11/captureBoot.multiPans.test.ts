// @vitest-environment jsdom
// ACAL304 (D-ACAL-27, moitié site) — CAPTURE MULTI-PANS sur /devis/mon-toit.
//
// SOURCE RÉELLE : `bootCaptureOnly` + `createMapDraw` + `isSimplePolygon` ne sont pas
// simulés. Seule la FRONTIÈRE carte (MapLibre) est remplacée par une carte factice qui
// route clics/double-clics comme le ferait la vraie, et le géocodage inverse réseau est
// coupé (fetch factice).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Handler = (e: unknown) => void;
const handlers: Record<string, Handler[]> = {};
const sources: Record<string, { data: unknown }> = {};

vi.mock('maplibre-gl', () => {
  class FakeMap {
    doubleClickZoom = { disable: () => {} };
    constructor() {
      for (const k of Object.keys(handlers)) delete handlers[k];
      for (const k of Object.keys(sources)) delete sources[k];
    }
    on(ev: string, fn: Handler) {
      (handlers[ev] ??= []).push(fn);
    }
    once(ev: string, fn: Handler) {
      (handlers[ev] ??= []).push(fn);
    }
    addControl() {}
    addSource(id: string, spec: { data: unknown }) {
      sources[id] = { data: spec.data };
    }
    addLayer() {}
    getSource(id: string) {
      const s = sources[id];
      return s ? { setData: (d: unknown) => { s.data = d; } } : undefined;
    }
    getZoom() { return 10; }
    jumpTo() {}
    flyTo() {}
    getCenter() { return { lng: -7.6, lat: 33.5 }; }
  }
  class Ctl {}
  return { Map: FakeMap, NavigationControl: Ctl, GeolocateControl: class { on() {} } };
});
vi.mock('maplibre-gl/dist/maplibre-gl.css?url', () => ({ default: 'x.css' }));

import { bootCaptureOnly, buildRoofLayout, type CaptureState } from './captureBoot';

const fire = (ev: string, e: unknown) => (handlers[ev] ?? []).forEach((h) => h(e));
const click = (lng: number, lat: number) => fire('click', { lngLat: { lng, lat } });
const dbl = (lng: number, lat: number) => fire('dblclick', { lngLat: { lng, lat }, preventDefault: () => {} });
const press = (id: string) => (document.getElementById(id) as HTMLButtonElement).click();

/** Dessine un carré fermé (3 clics + « Terminer le tracé ») d'origine (lng0, lat0). */
function dessinerPan(lng0: number, lat0: number) {
  click(lng0, lat0);
  click(lng0 + 0.0002, lat0);
  click(lng0 + 0.0002, lat0 + 0.0002);
  click(lng0, lat0 + 0.0002);
  press('rp9-finish');
}

let etats: CaptureState[];
const dernier = () => etats[etats.length - 1];

function monter(extra: Partial<Parameters<typeof bootCaptureOnly>[0]> = {}) {
  etats = [];
  bootCaptureOnly({
    maptilerKey: 'K',
    reducedMotion: true,
    roofInputMode: () => 'draw',
    onCaptureChange: (s) => etats.push(s),
    ...extra,
  } as Parameters<typeof bootCaptureOnly>[0]);
  fire('load', {});
}

beforeEach(() => {
  document.body.innerHTML = `
    <div id="rp9-map"></div><p id="rp9-status"></p>
    <button id="rp9-finish" disabled></button>
    <button id="rp9-undo-point" hidden></button>
    <button id="rp9-clear"></button>
    <button id="rp9-add-pan" hidden></button>
    <button id="rp9-remove-pan" hidden></button>
    <span id="rp9-area-value"></span>`;
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))));
});
afterEach(() => vi.unstubAllGlobals());

describe('ACAL304 — capture multi-pans', () => {
  it('trois pans fermés donnent roofLayout à trois zones et roofOutline = premier pan', () => {
    monter();
    dessinerPan(-7.6, 33.5);
    press('rp9-add-pan');
    dessinerPan(-7.5995, 33.5);
    press('rp9-add-pan');
    dessinerPan(-7.599, 33.5);

    const s = dernier();
    expect(s.layout?.version).toBe(2);
    expect(s.layout?.source).toBe('lead');
    expect(s.layout?.zones).toHaveLength(3);
    expect(s.layout?.zones.map((z) => z.label)).toEqual(['Pan 1', 'Pan 2', 'Pan 3']);
    // sommets zones en [lng, lat]
    expect(s.layout?.zones[0].vertices[0]).toEqual([-7.6, 33.5]);
    // roofOutline = PREMIER pan, en [lat, lng]
    expect(s.outline).toHaveLength(4);
    expect(s.outline[0]).toEqual([33.5, -7.6]);
    expect(s.outline[1][1]).toBeCloseTo(-7.5998, 9);
    expect(s.outline[3]).toEqual([33.5002, -7.6]);
    // roofPoint = centroïde du premier pan
    expect(s.pin?.lng).toBeCloseTo(-7.5999, 6);
    expect(s.pin?.lat).toBeCloseTo(33.5001, 6);
    expect(s.pans).toHaveLength(3);
    // aucun chiffre ajouté (ni pente, ni module, ni puissance)
    expect(Object.keys(s.layout!).sort()).toEqual(['pin', 'source', 'version', 'zones']);
    expect(Object.keys(s.layout!.zones[0]).sort()).toEqual(['id', 'label', 'vertices']);
    // chaque pan reste visible : la source des pans contient les deux pans précédents
    const fc = sources['rp9-pans'].data as { features: unknown[] };
    expect(fc.features).toHaveLength(2);
  });

  it('un seul pan : corps identique à aujourd’hui', () => {
    monter();
    dessinerPan(-7.6, 33.5);
    const s = dernier();
    expect(s.layout).toBeNull();
    expect(s.pans).toHaveLength(1);
    expect(s.outline).toHaveLength(4);
    expect(buildRoofLayout([])).toBeNull();
  });

  it('contour croisé refusé', () => {
    monter();
    // nœud papillon : le 4e point ferait croiser l'anneau => refusé par isSimplePolygon
    click(-7.6, 33.5);
    click(-7.5998, 33.5002);
    click(-7.5998, 33.5);
    click(-7.6, 33.5002);
    // le 4e point (qui croiserait AB et CD) n'est PAS posé : le contour reste à 3 sommets
    expect(dernier().outline).toHaveLength(3);
    expect(dernier().outline).not.toContainEqual([33.5002, -7.6]);
    expect(document.getElementById('rp9-status')!.textContent).toMatch(/croiser/);
    expect(dernier().layout).toBeNull();
  });

  it('« Retirer ce pan » retire le dernier pan', () => {
    monter();
    dessinerPan(-7.6, 33.5);
    press('rp9-add-pan');
    dessinerPan(-7.5995, 33.5);
    expect(dernier().layout?.zones).toHaveLength(2);
    press('rp9-remove-pan');
    expect(dernier().pans).toHaveLength(1);
    expect(dernier().layout).toBeNull();
    expect(dernier().outline[0]).toEqual([33.5, -7.6]);
  });

  it('restauration sessionStorage des pans', () => {
    monter();
    dessinerPan(-7.6, 33.5);
    press('rp9-add-pan');
    dessinerPan(-7.5995, 33.5);
    press('rp9-add-pan');
    dessinerPan(-7.599, 33.5);
    const sauve = JSON.parse(JSON.stringify(dernier().pans));

    // remontée : la page repasse les pans persistés
    monter({ hydratePans: sauve });
    const s = dernier();
    expect(s.pans).toEqual(sauve);
    expect(s.layout?.zones).toHaveLength(3);
    expect(s.outline).toEqual(sauve[0]);
  });
});
