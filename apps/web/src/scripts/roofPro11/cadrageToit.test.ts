// F6 — cadrage de la caméra sur tous les pans (module neuf, sans test voisin).
import { describe, expect, it, vi } from 'vitest';
import { apiCamera, cadrerToit, type CarteCadrable } from './cadrageToit';
import type { LngLat } from '../../lib/roof';
import * as THREE from 'three';
import { creerPoignees3d } from './poigneesSommets3d';
import { poserPresentation } from './presentationCarte';
import { cibleFermetureToit } from './vueFermetureToit'; // ACAL1422

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
  it('margesPx (coque v2 : rail 108, inspecteur 416, barre 88) : toit au centre de la zone LIBRE ; sans marges, inchangé', () => {
    const plein = carte();
    cadrerToit(plein.map, sources(), { zoomMax: 22 });
    const libre = carte();
    cadrerToit(libre.map, sources(), { zoomMax: 22, basPx: 0, margesPx: { haut: 88, gauche: 108, droite: 416, bas: 0 } });
    const a = plein.map.jumpTo.mock.calls[0][0];
    const b = libre.map.jumpTo.mock.calls[0][0];
    // Zoom sur la zone libre : 446 × 702 px (plus petite dimension 446 au lieu de 790) ⇒ log2(790 / 446) cran de moins.
    expect(a.zoom - b.zoom).toBeCloseTo(Math.log2(790 / 446), 6);
    const mpp = (2 * Math.PI * R * Math.cos((toit[0][1] * Math.PI) / 180)) / (512 * 2 ** b.zoom);
    // Le centre de la zone libre est 154 px à GAUCHE et 44 px plus BAS que celui de la carte : la caméra se pose 154 px à
    // l'est et 44 px au nord du toit, pour que le toit tombe au milieu de la zone libre.
    expect((b.center[0] - a.center[0]) * DEG2M * Math.cos((toit[0][1] * Math.PI) / 180)).toBeCloseTo(154 * mpp, 1);
    expect((b.center[1] - a.center[1]) * DEG2M).toBeCloseTo(44 * mpp, 1);
  });
  it('apiCamera expose appliquerVue (inchangée) et cadrerToit', () => {
    const { map } = carte();
    const api = apiCamera(map, sources(), true);
    api.appliquerVue('dessus');
    expect(map.jumpTo).toHaveBeenCalledWith({ pitch: 0, bearing: 0 });
    expect(api.cadrerToit({ zoomMax: 22 })).toBe(true);
  });
});

// H6 — mode présentation (vue client) : tout marqueur d'édition se tait, un doigt fait tourner la maison.
function cartePresentable() {
  const vis: Record<string, string | undefined> = { 'rp9-pts': undefined, 'rp9-line': undefined, 'rp9-ref-contour-line': 'none', 'rp9-obs': undefined };
  const ev: Record<string, Array<() => void>> = {};
  const dom: Record<string, (e: Partial<PointerEvent>) => void> = {};
  let cap = 10;
  const map = {
    ...carte().map,
    getLayer: (id: string) => (id in vis ? {} : undefined),
    getLayoutProperty: (id: string) => vis[id],
    setLayoutProperty: vi.fn((id: string, _n: string, v: string) => { vis[id] = v; }),
    triggerRepaint: vi.fn(),
    on: vi.fn((t: string, f: () => void) => { (ev[t] ||= []).push(f); }),
    off: vi.fn((t: string, f: () => void) => { ev[t] = (ev[t] || []).filter((g) => g !== f); }),
    getBearing: () => cap,
    setBearing: (c: number) => { cap = c; },
    dragPan: { enable: vi.fn(), disable: vi.fn() },
    getCanvasContainer: () => ({
      addEventListener: (t: string, f: (e: Partial<PointerEvent>) => void) => { dom[t] = f; },
      removeEventListener: (t: string) => { delete dom[t]; },
    }),
  };
  return { map: map as unknown as CarteCadrable & typeof map, vis, ev, dom, cap: () => cap };
}

describe('cibleFermetureToit — la caméra après « Terminer le tracé » (ACAL1422)', () => {
  const anneau = rect(-7.62, 33.59, 9, 7);
  const carte = { getZoom: () => 21, getPitch: () => 0, getContainer: () => ({ clientWidth: 970, clientHeight: 790 }) };
  const entree = { anneau, centre: [-7.6199, 33.5900] as LngLat, carte };

  it('option ERP : le zoom cible dépasse 19 pour un toit de 9 × 7 m et la vue reste Plan', () => {
    const cible = cibleFermetureToit({ ...entree, erp: true });
    expect(cible.zoom).toBeGreaterThan(20.5); // 9 m ≈ 42 % de 790 px
    expect(cible.zoom).toBeLessThanOrEqual(22);
    expect(cible.pitch).toBe(0); // Plan reste Plan
  });

  it('site public : plafond 19 et vue inclinée, comme avant ; la carte n’est pas lue', () => {
    const illisible = { getZoom: () => 21, getPitch: () => { throw new Error('lue'); }, getContainer: () => { throw new Error('lue'); } };
    const cible = cibleFermetureToit({ ...entree, carte: illisible, erp: false });
    expect(cible.zoom).toBeLessThanOrEqual(19);
    expect(cible.pitch).toBeGreaterThan(0);
  });
});


describe('modePresentation — vue client sans marqueur d\'édition (H6)', () => {
  it('masque les calques d\'édition présents, garde les autres, et rend chacun tel quel à la sortie', () => {
    const c = cartePresentable();
    const api = apiCamera(c.map, sources(), true);
    expect(api.modePresentation(true)).toBe(true);
    expect(c.vis['rp9-pts']).toBe('none');
    expect(c.vis['rp9-line']).toBe('none');
    expect(c.vis['rp9-obs']).toBeUndefined(); // un obstacle est une donnée, pas un marqueur
    c.vis['rp9-pts'] = 'visible'; // un module le ré-affiche (bascule de pente)…
    c.ev.idle.forEach((f) => f()); // …il est re-masqué au prochain repos de la carte
    expect(c.vis['rp9-pts']).toBe('none');
    expect(api.modePresentation(false)).toBe(false);
    expect(c.vis['rp9-pts']).toBe('visible');
    expect(c.vis['rp9-ref-contour-line']).toBe('none'); // masqué avant : reste masqué
    expect(c.ev.idle).toEqual([]);
    expect(c.map.triggerRepaint).toHaveBeenCalledTimes(2);
  });
  it('un doigt fait tourner (cap), deux doigts ne tournent pas ; déplacer la carte est rendu à la sortie', () => {
    const c = cartePresentable();
    const api = apiCamera(c.map, sources(), true);
    api.modePresentation(true);
    expect(c.map.dragPan.disable).toHaveBeenCalled();
    c.dom.pointerdown({ pointerId: 1, button: 0, clientX: 100 });
    c.dom.pointermove({ pointerId: 1, clientX: 150 });
    expect(c.cap()).toBeCloseTo(10 - 50 * 0.4, 6);
    c.dom.pointerdown({ pointerId: 2, button: 0, clientX: 300 });
    c.dom.pointermove({ pointerId: 1, clientX: 250 });
    expect(c.cap()).toBeCloseTo(-10, 6); // pincement : la carte garde la main
    c.dom.pointerup({ pointerId: 1 });
    c.dom.pointerup({ pointerId: 2 });
    api.modePresentation(false);
    expect(c.map.dragPan.enable).toHaveBeenCalled();
    expect(c.dom.pointermove).toBeUndefined();
  });
  it('les poignées 3D des coins (vue inclinée) se taisent en présentation : invisibles et insaisissables', () => {
    const c = cartePresentable();
    const carte3d = Object.assign(c.map, { getPitch: () => 60, getCanvas: () => ({ clientWidth: 390, clientHeight: 464 }) });
    const p = creerPoignees3d(carte3d as never);
    const scene = new THREE.Scene();
    p.poser(scene, toit, toit[0], 6);
    p.suivre(new THREE.Matrix4().makePerspective(-1, 1, 1, -1, 1, 1000).elements);
    const groupe = scene.children.at(-1)!;
    expect(groupe.visible).toBe(true);
    poserPresentation(carte3d as never, true);
    expect(groupe.visible).toBe(false);
    expect(c.vis['rp9-pts']).toBe('none');
    expect(p.ecran()).toEqual([]);
    p.masquer()(); // la capture d'image rend l'état « présentation », pas l'état d'avant
    expect(groupe.visible).toBe(false);
    poserPresentation(carte3d as never, false);
    expect(groupe.visible).toBe(true);
    expect(c.vis['rp9-pts']).toBe('none'); // vue inclinée : le cercle du sol reste caché (ACAL1185)
  });
});

// J1 (tour 4) — la vue client TENUE de trois quarts : posée à l'entrée, reposée après tout mouvement qui n'est pas un
// geste de l'utilisateur (atterrissage de l'hydratation, recalage), jusqu'au premier geste.
function carteCamera() {
  const ev: Record<string, Array<() => void>> = {};
  const dom: Record<string, (e: Partial<PointerEvent>) => void> = {};
  const cam = { lng: -7.6, lat: 33.6, zoom: 5, pitch: 0, bearing: 0 };
  const attrs: Record<string, string> = { 'aria-label': 'Map', role: 'region', tabindex: '0' };
  const fire = (t: string) => (ev[t] || []).slice().forEach((f) => f());
  const bouger = (o: Partial<typeof cam> & { center?: LngLat }) => {
    if (o.center) { cam.lng = o.center[0]; cam.lat = o.center[1]; }
    for (const k of ['zoom', 'pitch', 'bearing'] as const) if (o[k] !== undefined) cam[k] = o[k]!;
  };
  const map = {
    resize: vi.fn(),
    jumpTo: vi.fn((o: Partial<typeof cam> & { center?: LngLat }) => { bouger(o); fire('moveend'); }),
    easeTo: vi.fn((o: Partial<typeof cam>) => { bouger(o); fire('moveend'); }),
    isMoving: () => false,
    once: vi.fn((t: string, fn: () => void) => { const g = () => { ev[t] = ev[t].filter((h) => h !== g); fn(); }; (ev[t] ||= []).push(g); }),
    on: vi.fn((t: string, f: () => void) => { (ev[t] ||= []).push(f); }),
    off: vi.fn((t: string, f: () => void) => { ev[t] = (ev[t] || []).filter((g) => g !== f); }),
    getContainer: () => ({ clientWidth: 390, clientHeight: 464 }),
    getCenter: () => ({ lng: cam.lng, lat: cam.lat }),
    getZoom: () => cam.zoom,
    getPitch: () => cam.pitch,
    getBearing: () => cam.bearing,
    setBearing: (c: number) => { cam.bearing = c; },
    setPadding: vi.fn(),
    getCanvas: () => ({
      getAttribute: (n: string) => attrs[n] ?? null,
      setAttribute: (n: string, v: string) => { attrs[n] = v; },
      removeAttribute: (n: string) => { delete attrs[n]; },
    }),
    getCanvasContainer: () => ({
      addEventListener: (t: string, f: (e: Partial<PointerEvent>) => void) => { dom[t] = f; },
      removeEventListener: (t: string) => { delete dom[t]; },
    }),
    dragPan: { enable: vi.fn(), disable: vi.fn() },
  };
  return { map: map as unknown as CarteCadrable & typeof map, cam, attrs, dom, fire };
}

describe('modePresentation — vue client tenue de trois quarts (J1)', () => {
  it('pose 3/4 + cadrage à l\'entrée ; un atterrissage du constructeur (pente 58°, cap 0) est corrigé au repos', () => {
    vi.useFakeTimers();
    try {
      const c = carteCamera();
      let anneaux: LngLat[][] = []; // avant l'hydratation : aucun pan
      const api = apiCamera(c.map, { anneaux: () => anneaux, azimut: () => 180, trace: () => false }, true);
      const prete = vi.fn();
      api.modePresentation(true, { vue: 'trois-quarts', cadrage: { zoomMax: 22, cielPx: 180 }, surPrete: prete });
      vi.runAllTimers();
      expect([c.cam.pitch, c.cam.bearing]).toEqual([58, 45]);
      expect(prete).not.toHaveBeenCalled(); // rien n'est cadré : la 3D n'est pas « prête »
      // L'hydratation : les pans arrivent et la caméra atterrit (W120 / go3DView : pente gardée, cap 0).
      anneaux = [toit];
      c.map.jumpTo({ center: [-7.62, 33.59], zoom: 19, pitch: 58, bearing: 0 } as never);
      vi.runAllTimers();
      expect([c.cam.pitch, c.cam.bearing]).toEqual([58, 45]);
      expect(c.cam.zoom).toBeGreaterThan(20);
      expect(c.map.jumpTo.mock.calls.at(-1)![0]).toMatchObject({ padding: { top: 180, bottom: 0, left: 0, right: 0 } });
      expect(prete).toHaveBeenCalledTimes(1);
      // Une étape qui reposerait « Plan » (pente 0) hors geste : la vue client est reposée.
      c.map.easeTo({ pitch: 0, bearing: 0 } as never);
      vi.runAllTimers();
      expect([c.cam.pitch, c.cam.bearing]).toEqual([58, 45]);
      // Le client tourne la maison : la vue n'est plus jamais reposée.
      c.dom.pointerdown({ pointerId: 1, button: 0, clientX: 100 });
      c.dom.pointermove({ pointerId: 1, clientX: 200 });
      c.dom.pointerup({ pointerId: 1 });
      c.fire('idle');
      vi.runAllTimers();
      expect(c.cam.bearing).toBeCloseTo(5, 6);
      api.modePresentation(false);
      expect(c.map.setPadding).toHaveBeenCalledWith({ top: 0, bottom: 0, left: 0, right: 0 });
    } finally {
      vi.useRealTimers();
    }
  });
  it('la toile est nommée en français et sort de l\'ordre de tabulation ; ses attributs sont rendus à la sortie', () => {
    const c = carteCamera();
    const api = apiCamera(c.map, sources(), true);
    api.modePresentation(true);
    expect(c.attrs).toMatchObject({ 'aria-label': 'Vue 3D de la maison', role: 'img', tabindex: '-1' });
    api.modePresentation(false);
    expect(c.attrs).toMatchObject({ 'aria-label': 'Map', role: 'region', tabindex: '0' });
  });
});
