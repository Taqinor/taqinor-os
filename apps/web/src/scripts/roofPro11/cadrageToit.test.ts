// F6 — cadrage de la caméra sur tous les pans (module neuf, sans test voisin).
import { describe, expect, it, vi } from 'vitest';
import { apiCamera, cadrerToit, type CarteCadrable } from './cadrageToit';
import type { LngLat } from '../../lib/roof';

const R = 6378137;
const DEG2M = (Math.PI / 180) * R;
function rect(lng0: number, lat0: number, wEW: number, hNS: number): LngLat[] {
  const dLat = hNS / DEG2M;
  const dLng = wEW / (DEG2M * Math.cos((lat0 * Math.PI) / 180));
  return [[lng0, lat0], [lng0 + dLng, lat0], [lng0 + dLng, lat0 + dLat], [lng0, lat0 + dLat]];
}

function carte({ moving = false } = {}) {
  const handlers: Record<string, Array<(e: { originalEvent?: unknown }) => void>> = {};
  const once: Record<string, Array<() => void>> = {};
  const map = {
    resize: vi.fn(),
    jumpTo: vi.fn(),
    easeTo: vi.fn(),
    isMoving: vi.fn(() => moving),
    once: vi.fn((t: string, fn: () => void) => { (once[t] ||= []).push(fn); }),
    on: vi.fn((t: string, fn: (e: { originalEvent?: unknown }) => void) => { (handlers[t] ||= []).push(fn); }),
    off: vi.fn(),
    getContainer: () => ({ clientWidth: 970, clientHeight: 790 }),
  };
  const fire = (t: string, e: { originalEvent?: unknown } = {}) => {
    (handlers[t] || []).forEach((f) => f(e));
    const l = once[t] || [];
    once[t] = [];
    l.forEach((f) => f());
  };
  return { map: map as unknown as CarteCadrable & typeof map, fire };
}

const toit = rect(-7.62, 33.59, 9, 6);
const sources = (anneaux: LngLat[][] = [toit], trace = false) => ({ anneaux: () => anneaux, azimut: () => 180, trace: () => trace });

describe('cadrerToit — le toit remplit la carte (F6)', () => {
  it('pose centre + zoom SANS animation, pente et cap non fournis (vue courante gardée)', () => {
    const { map } = carte();
    expect(cadrerToit(map, sources(), { zoomMax: 22 })).toBe(true);
    expect(map.easeTo).not.toHaveBeenCalled();
    const cible = map.jumpTo.mock.calls[0][0];
    expect(Object.keys(cible).sort()).toEqual(['center', 'zoom']);
    // 9 m occupent 42 % de 790 px ≈ 332 px : zoom ≈ 21,2 (bien au-delà du plafond 19 du site public).
    expect(cible.zoom).toBeGreaterThan(20.9);
    expect(cible.zoom).toBeLessThan(21.5);
  });
  it('sans zoomMax : le plafond d’aujourd’hui (19) est gardé', () => {
    const { map } = carte();
    cadrerToit(map, sources());
    expect(map.jumpTo.mock.calls[0][0].zoom).toBe(19);
  });
  it('tous les pans : la boîte englobe les deux toits', () => {
    const { map } = carte();
    const autre = rect(-7.6195, 33.59, 9, 6);
    cadrerToit(map, sources([toit, autre]), { zoomMax: 22 });
    const seul = carte();
    cadrerToit(seul.map, sources(), { zoomMax: 22 });
    expect(map.jumpTo.mock.calls[0][0].zoom).toBeLessThan(seul.map.jumpTo.mock.calls[0][0].zoom);
  });
  it('rien pendant un tracé, rien sans pan', () => {
    const a = carte();
    expect(cadrerToit(a.map, sources([toit], true))).toBe(false);
    expect(cadrerToit(a.map, sources([[], [[0, 0]]]))).toBe(false);
    expect(a.map.jumpTo).not.toHaveBeenCalled();
  });
  it('caméra en mouvement (atterrissage du boot) : attend la fin, puis cadre', () => {
    const { map, fire } = carte({ moving: true });
    cadrerToit(map, sources(), { zoomMax: 22 });
    expect(map.jumpTo).not.toHaveBeenCalled();
    fire('moveend');
    expect(map.jumpTo).toHaveBeenCalledTimes(1);
  });
  it('re-posé au prochain idle, SAUF si l’utilisateur a touché la carte', () => {
    const a = carte();
    cadrerToit(a.map, sources(), { zoomMax: 22 });
    a.fire('idle');
    expect(a.map.jumpTo).toHaveBeenCalledTimes(2);
    const b = carte();
    cadrerToit(b.map, sources(), { zoomMax: 22 });
    b.fire('movestart', { originalEvent: {} });
    b.fire('idle');
    expect(b.map.jumpTo).toHaveBeenCalledTimes(1);
  });
  it('H1 — basPx (tiroir de la tablette) : cadré dans la partie VISIBLE, centre de carte plus au sud, zoom sur la hauteur visible', () => {
    const plein = carte();
    cadrerToit(plein.map, sources(), { zoomMax: 22 });
    const tiroir = carte();
    cadrerToit(tiroir.map, sources(), { zoomMax: 22, basPx: 280 });
    const a = plein.map.jumpTo.mock.calls[0][0];
    const b = tiroir.map.jumpTo.mock.calls[0][0];
    expect(b.zoom).toBeLessThan(a.zoom); // 510 px visibles au lieu de 790
    expect(b.center[0]).toBeCloseTo(a.center[0], 9);
    // 140 px (la moitié du tiroir) à ce zoom, en mètres, vers le sud.
    const mpp = (2 * Math.PI * R * Math.cos((b.center[1] * Math.PI) / 180)) / (512 * 2 ** b.zoom);
    expect((a.center[1] - b.center[1]) * DEG2M).toBeCloseTo(140 * mpp, 1);
  });
  it('apiCamera expose appliquerVue (inchangée) et cadrerToit', () => {
    const { map } = carte();
    const api = apiCamera(map, sources(), true);
    api.appliquerVue('dessus');
    expect(map.jumpTo).toHaveBeenCalledWith({ pitch: 0, bearing: 0 });
    expect(api.cadrerToit({ zoomMax: 22 })).toBe(true);
  });
});
