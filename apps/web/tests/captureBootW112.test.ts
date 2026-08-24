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
  once(ev: string, h: (e: unknown) => void) {
    // MapLibre Map.once — utilisé par bootCaptureOnly (WJ62, hasRenderedOnce).
    return this.on(ev, h);
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
  // Caméra : `getZoom` existe sur la vraie carte MapLibre et `landOn`
  // (captureBoot) s'en sert comme PLANCHER de zoom — on enregistre les cibles
  // pour prouver l'atterrissage serré du flux « pointer ».
  zoom = 5;
  cameraTargets: Array<{ center?: unknown; zoom?: number }> = [];
  getZoom() { return this.zoom; }
  private moveTo(t?: { center?: unknown; zoom?: number }) {
    if (t) {
      this.cameraTargets.push(t);
      if (typeof t.zoom === 'number') this.zoom = t.zoom;
    }
    return this;
  }
  easeTo() { return this; }
  flyTo(t?: { center?: unknown; zoom?: number }) { return this.moveTo(t); }
  jumpTo(t?: { center?: unknown; zoom?: number }) { return this.moveTo(t); }
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

// ——— POINTER ou DESSINER : un CHOIX explicite, plus un flux deviné ———
// Le geste était implicite : clic = repère, et seul un DOUBLE-clic (qui n'existe
// pas au doigt) démarrait un contour, sans que rien ne l'annonce. `roofInputMode`
// rend le choix explicite ; en « pointer », la carte atterrit serrée sur le
// repère pour que la page puisse demander « C'est bien votre toit ? » sur une
// image lisible.
describe('capture — choix explicite du geste (pointer / dessiner)', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupCaptureDom();
  });
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it('mode « dessiner » : le PREMIER clic ouvre le contour (plus de double-clic à deviner)', async () => {
    const init = await loadTool();
    let last: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]> } | null = null;
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => 'draw' as const,
      onCaptureChange: (s) => { last = s; },
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.591 }, point: { x: 0, y: 0 } });
    expect(last).not.toBeNull();
    // 3 sommets tracés — et AUCUN repère simple posé au passage.
    expect(last!.outline.length).toBe(3);
    expect(last!.pin).not.toBeNull(); // le pin remonté est le CENTROÏDE du contour
    const finish = document.getElementById('rp9-finish') as HTMLButtonElement;
    expect(finish.disabled).toBe(false); // « Terminer le tracé » devient utilisable
  });

  it('mode « pointer » : un clic pose le repère ET fait atterrir la carte serrée dessus', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => 'point' as const,
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    expect(map.cameraTargets.length).toBe(0);
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    // La confirmation visuelle repose sur cet atterrissage : sans lui, le
    // visiteur valide « oui c'est mon toit » sur une vue large.
    expect(map.cameraTargets.length).toBe(1);
    expect(map.cameraTargets[0].center).toEqual([-7.6, 33.59]);
    expect(map.cameraTargets[0].zoom).toBeGreaterThanOrEqual(19);
  });

  it('`landOn` ne DÉZOOME jamais un visiteur déjà plus près que le plancher', async () => {
    const init = await loadTool();
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => 'point' as const,
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    map.zoom = 21;
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    expect(map.cameraTargets[0].zoom).toBe(21);
  });

  it('mode « pointer » : un double-clic reste un simple repère, il n\'ouvre AUCUN contour', async () => {
    // « Terminer le tracé » est masqué hors du geste « dessiner » : un contour
    // ouvert par mégarde n'aurait plus de sortie, et sous 3 sommets currentPin()
    // rend null — la confirmation « C'est bien votre toit ? » disparaissait avec
    // le repère. En « pointer », le double-clic ne doit donc rien tracer.
    const init = await loadTool();
    let last: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]> } | null = null;
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => 'point' as const,
      onCaptureChange: (s) => { last = s; },
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    // Un vrai double-clic = deux `click` puis un `dblclick` (MapLibre).
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('dblclick', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 }, preventDefault() {} });
    expect(last).not.toBeNull();
    expect(last!.outline).toEqual([]);
    expect(last!.pin).toEqual({ lat: 33.59, lng: -7.6 });
  });

  it('mode « dessiner » : le double-clic ferme bien le contour (le geste traceur est intact)', async () => {
    const init = await loadTool();
    let last: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]> } | null = null;
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => 'draw' as const,
      onCaptureChange: (s) => { last = s; },
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.591 }, point: { x: 0, y: 0 } });
    map.fire('dblclick', { lngLat: { lng: -7.599, lat: 33.591 }, point: { x: 0, y: 0 }, preventDefault() {} });
    expect(last!.outline.length).toBe(3);
    const finish = document.getElementById('rp9-finish') as HTMLButtonElement;
    expect(finish.disabled).toBe(true); // contour fermé : plus rien à terminer
  });

  it('sans `roofInputMode` (flux historique), le double-clic ouvre TOUJOURS un contour', async () => {
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
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('dblclick', { lngLat: { lng: -7.599, lat: 33.59 }, point: { x: 0, y: 0 }, preventDefault() {} });
    // Le repère devient le 1ᵉʳ sommet et le double-clic en ajoute un 2ᵉ : sous
    // 3 sommets, currentPin() rend null — comportement historique, inchangé.
    expect(last!.outline).toEqual([]);
    expect(last!.pin).toBeNull();
  });

  it('sans `roofInputMode` (flux historique), un clic pose le repère SANS bouger la caméra', async () => {
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
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    expect(last!.pin).toEqual({ lat: 33.59, lng: -7.6 });
    expect(last!.outline).toEqual([]);
    expect(map.cameraTargets.length).toBe(0);
  });
});

// ——— BUG FONDATEUR (24/08) : pin posé, puis passage en « Dessiner mon toit »,
// contour tracé — la fiche CRM ne montrait ensuite QUE le pin. Cause racine :
// un clic de carte APRÈS la fermeture du contour retombait dans `setPin()`,
// qui efface `vertices`/`closed` sans confirmation. Ces tests prouvent (a) que
// le pin posé en mode « pointer » devient le 1ᵉʳ sommet du tracé au lieu
// d'être perdu au changement de mode, et (b) qu'un contour FERMÉ survit à un
// clic de carte supplémentaire — seul « Effacer » peut désormais le vider.
describe('capture — pin puis tracé : rien ne se perd au changement de mode', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    setupCaptureDom();
  });
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
  });

  it('pin posé en « pointer », puis tracé en « dessiner » : le pin devient le 1ᵉʳ sommet du contour', async () => {
    const init = await loadTool();
    let last: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]> } | null = null;
    let mode: 'point' | 'draw' = 'point';
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => mode,
      onCaptureChange: (s) => { last = s; },
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    // 1) « Pointer mon toit » : un clic pose le pin.
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    expect(last!.pin).toEqual({ lat: 33.59, lng: -7.6 });
    expect(last!.outline).toEqual([]);
    // 2) Le visiteur bascule sur « Dessiner mon toit » (aucune interaction carte).
    mode = 'draw';
    // 3) Deux clics de plus suffisent à fermer un triangle (le pin posé plus haut
    //    compte comme le 1ᵉʳ sommet) — la fiche doit porter les 3 sommets, pas
    //    seulement le pin d'origine.
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.591 }, point: { x: 0, y: 0 } });
    expect(last!.outline.length).toBe(3);
    // Le pin d'origine est bien l'un des sommets tracés (converti, pas jeté).
    expect(last!.outline).toContainEqual([33.59, -7.6]);
  });

  it('un contour FERMÉ survit à un clic de carte supplémentaire — seul « Effacer » le vide', async () => {
    const init = await loadTool();
    let last: { pin: { lat: number; lng: number } | null; outline: Array<[number, number]> } | null = null;
    init({
      maptilerKey: 'test',
      reducedMotion: true,
      captureOnly: true,
      roofInputMode: () => 'draw' as const,
      onCaptureChange: (s) => { last = s; },
    });
    const map = fakeMaps[0];
    map.fire('load', {});
    map.fire('click', { lngLat: { lng: -7.6, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.59 }, point: { x: 0, y: 0 } });
    map.fire('click', { lngLat: { lng: -7.599, lat: 33.591 }, point: { x: 0, y: 0 } });
    const finish = document.getElementById('rp9-finish') as HTMLButtonElement;
    finish.dispatchEvent(new Event('click'));
    expect(last!.outline.length).toBe(3);
    const outlineBeforeStrayClick = last!.outline;

    // Clic accidentel APRÈS la fermeture du contour : ne doit RIEN effacer.
    map.fire('click', { lngLat: { lng: 12.34, lat: 56.78 }, point: { x: 0, y: 0 } });
    expect(last!.outline).toEqual(outlineBeforeStrayClick);
    expect(last!.outline.length).toBe(3);

    // Seul le bouton « Effacer » remet tout à zéro.
    const clear = document.getElementById('rp9-clear') as HTMLButtonElement;
    clear.dispatchEvent(new Event('click'));
    expect(last!.outline).toEqual([]);
    expect(last!.pin).toBeNull();
  });
});
