/**
 * W112 — BOOT « CAPTURE CLIENT » (page publique /devis/mon-toit).
 *
 * Construit UNIQUEMENT : la carte satellite MapLibre + le géocodeur d'adresse
 * (réutilise createMapDraw) + le PIN sur le toit (tracer le contour est
 * OPTIONNEL). Il n'instancie JAMAIS createScene3d / createOptimizer /
 * createMatrix ni aucune UI de production : aucune carte de panneaux, aucun
 * optimiseur, aucune 3D ne peut apparaître sur cette page publique.
 *
 * Le boot COMPLET (non-capture) reste octet pour octet inchangé : initRoofToolPro8
 * ne dévie vers ce module que lorsque `opts.captureOnly === true`.
 *
 * GARDE-FOU : ce module ne POSTe AUCUN lead (comme tout le builder). Seule la page
 * publique, via son endpoint dédié /api/capture-lead, soumet — jamais l'outil.
 */
import maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import { isSimplePolygon, type LngLat } from '../../lib/roof';
import { buildSatelliteStyle } from '../../lib/roofConfig';
import { GOLD, MOROCCO_CENTER } from './constants';
import { $ } from './dom';
import { type Ctx } from './context';
import { createMapDraw } from './mapDraw';
import { type InitOptions } from './types';

/**
 * Démarre le mode capture client. Construit la carte + le géocodeur + le pin/tracé,
 * câble le bouton « Terminer le tracé » et « Effacer », et notifie la page à chaque
 * changement de pin/contour via `opts.onCaptureChange`.
 */
export function bootCaptureOnly(opts: InitOptions): void {
  const mapEl = $('rp9-map');
  if (!mapEl) return;

  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const statusEl = $('rp9-status');
  const finishBtn = $<HTMLButtonElement>('rp9-finish');
  const clearBtn = $<HTMLButtonElement>('rp9-clear');
  const undoPointBtn = $<HTMLButtonElement>('rp9-undo-point');
  const areaValueEl = $('rp9-area-value');

  const setStatus = (msg: string) => {
    if (statusEl) statusEl.textContent = msg;
  };

  // — État minimal : le PIN (un seul point posé) + un tracé OPTIONNEL —
  // `vertices` sert au géocodeur partagé (createMapDraw lit ctx.vertices/closed) et,
  // si l'utilisateur trace un contour, le pin = centroïde du contour ; sinon le pin
  // est le seul point posé.
  let pin: LngLat | null = null;
  let vertices: LngLat[] = [];
  let closed = false;

  // Contexte MINIMAL pour createMapDraw : il ne lit que ctx.opts / ctx.vertices /
  // ctx.closed (cf. mapDraw.ts). On caste un objet partiel — aucun autre champ n'est
  // touché en mode capture (ni scène 3D, ni optimiseur).
  const ctx = {
    opts,
    get vertices() {
      return vertices;
    },
    set vertices(v: LngLat[]) {
      vertices = v;
    },
    get closed() {
      return closed;
    },
    set closed(v: boolean) {
      closed = v;
    },
  } as unknown as Ctx;

  const map = new maplibregl.Map({
    container: mapEl,
    style: buildSatelliteStyle({ maptilerKey: opts.maptilerKey, mapboxToken: opts.mapboxToken }) as maplibregl.StyleSpecification | string,
    center: MOROCCO_CENTER,
    zoom: 5,
    pitch: 0,
    maxPitch: 0,
    attributionControl: { compact: true },
    fadeDuration: opts.reducedMotion ? 0 : 300,
  });
  opts.onReady?.();

  map.on('error', (e: unknown) => {
    const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
    console.warn('[capture-toit] erreur carte (non bloquante) :', msg);
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), 'top-right');
  const geolocate = new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: false,
    showUserLocation: true,
  });
  map.addControl(geolocate, 'top-right');
  geolocate.on('geolocate', (e: { coords?: { longitude: number; latitude: number } }) => {
    const c = e?.coords;
    if (!c) return;
    const target = { center: [c.longitude, c.latitude] as LngLat, zoom: 19, pitch: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.flyTo({ ...target, essential: true });
  });
  map.doubleClickZoom.disable();

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  const empty = { type: 'FeatureCollection', features: [] } as const;

  /** Pin courant {lat,lng} (centroïde si un contour est tracé, sinon le point posé). */
  function currentPin(): { lat: number; lng: number } | null {
    if (vertices.length >= 3) {
      let lng = 0;
      let lat = 0;
      for (const [x, y] of vertices) {
        lng += x;
        lat += y;
      }
      return { lng: lng / vertices.length, lat: lat / vertices.length };
    }
    if (pin) return { lng: pin[0], lat: pin[1] };
    return null;
  }

  /** Contour en [[lat,lng],…] (vide si pas de tracé fermé d'au moins 3 points). */
  function currentOutline(): Array<[number, number]> {
    if (vertices.length < 3) return [];
    return vertices.map(([lng, lat]) => [lat, lng] as [number, number]);
  }

  function notify() {
    opts.onCaptureChange?.({ pin: currentPin(), outline: currentOutline() });
  }

  function updateAreaReadout() {
    // En capture, pas de calcul d'aire : on indique seulement l'état du repère.
    if (!areaValueEl) return;
    if (vertices.length >= 3) areaValueEl.textContent = 'contour tracé';
    else if (pin) areaValueEl.textContent = 'repère posé';
    else areaValueEl.textContent = '—';
  }

  function redrawPin() {
    const features: GeoJSON.Feature[] = [];
    const p = pin && vertices.length < 3 ? pin : null;
    if (p) features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: { kind: 'pin' } });
    srcOf('rp9-pin')?.setData({ type: 'FeatureCollection', features } as never);
  }

  // — Géocodeur partagé (recherche d'adresse + autocomplétion W93) : il ne lit que
  //   ctx.opts/vertices/closed et pilote le formulaire #rp9-search. Le tracé du
  //   contour (addVertex) est utilisé seulement si l'utilisateur trace ; le pin
  //   simple est géré ici (clic carte).
  const mapDraw = createMapDraw(ctx, { map, setStatus, updateAreaReadout });
  const addVertex = mapDraw.addVertex;
  const redrawTrace = mapDraw.redrawTrace;

  map.on('load', () => {
    map.addSource('rp9-line', { type: 'geojson', data: empty as never });
    map.addSource('rp9-pts', { type: 'geojson', data: empty as never });
    map.addSource('rp9-pin', { type: 'geojson', data: empty as never });
    map.addLayer({ id: 'rp9-line', type: 'line', source: 'rp9-line', paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
    map.addLayer({ id: 'rp9-pts', type: 'circle', source: 'rp9-pts', paint: { 'circle-radius': 5, 'circle-color': GOLD, 'circle-stroke-color': '#070b1d', 'circle-stroke-width': 1.5 } });
    map.addLayer({
      id: 'rp9-pin',
      type: 'circle',
      source: 'rp9-pin',
      paint: { 'circle-radius': 9, 'circle-color': GOLD, 'circle-stroke-color': '#070b1d', 'circle-stroke-width': 2.5 },
    });
    if (opts.initialQuery) void mapDraw.geocode(opts.initialQuery, true);
    else setStatus('Cherchez votre adresse, puis posez un repère sur votre toit.');
    // W113 — hydratation : sème pin/contour quand un lead est fourni.
    if (opts.hydrate?.lead) seedFromLead(opts.hydrate.lead);
  });

  /** Pose/déplace le PIN simple (un seul point) sur le toit. Efface tout tracé. */
  function setPin(v: LngLat) {
    pin = v;
    vertices = [];
    closed = false;
    redrawTrace();
    srcOf('rp9-line')?.setData(empty as never);
    redrawPin();
    updateAreaReadout();
    if (undoPointBtn) undoPointBtn.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    setStatus('Repère posé. Vous pouvez l’ajuster, ou tracer le contour (facultatif), puis remplir vos coordonnées.');
    notify();
  }

  // Clic carte : en mode capture, un clic SIMPLE pose/déplace le pin. Si le visiteur
  // a commencé un contour (≥1 sommet via le double-clic), le clic ajoute un sommet.
  map.on('click', (e) => {
    const lngLat: LngLat = [e.lngLat.lng, e.lngLat.lat];
    if (vertices.length > 0 && !closed) {
      addVertex(lngLat);
      pin = null;
      redrawPin();
      if (finishBtn) finishBtn.disabled = vertices.length < 3;
      if (undoPointBtn) undoPointBtn.hidden = vertices.length < 1;
      notify();
      return;
    }
    setPin(lngLat);
  });

  // Double-clic : DÉMARRE/poursuit un tracé de contour (optionnel). Le 1ᵉʳ double-clic
  // convertit le pin en 1ᵉʳ sommet ; les suivants ferment le contour (≥3 sommets).
  map.on('dblclick', (e) => {
    e.preventDefault();
    if (closed) return;
    if (vertices.length >= 3 && isSimplePolygon(vertices)) {
      closed = true;
      redrawTrace();
      srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [...vertices, vertices[0]] }, properties: {} } as never);
      if (finishBtn) finishBtn.disabled = true;
      if (undoPointBtn) undoPointBtn.hidden = true;
      setStatus('Contour tracé. Remplissez vos coordonnées ci-dessous, puis envoyez.');
      updateAreaReadout();
      notify();
      return;
    }
    // démarre le tracé sur ce point (et reprend le pin s'il existait)
    const start: LngLat = [e.lngLat.lng, e.lngLat.lat];
    if (vertices.length === 0) {
      vertices = pin ? [pin] : [];
      pin = null;
      redrawPin();
    }
    addVertex(start);
    setStatus('Tracez le contour de votre toit. Double-cliquez pour fermer (facultatif).');
    notify();
  });

  finishBtn?.addEventListener('click', () => {
    if (closed || vertices.length < 3) return;
    if (!isSimplePolygon(vertices)) {
      setStatus('Votre tracé se croise — corrigez-le (« Effacer ») avant de fermer.');
      return;
    }
    closed = true;
    redrawTrace();
    srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [...vertices, vertices[0]] }, properties: {} } as never);
    finishBtn.disabled = true;
    if (undoPointBtn) undoPointBtn.hidden = true;
    setStatus('Contour tracé. Remplissez vos coordonnées ci-dessous, puis envoyez.');
    updateAreaReadout();
    notify();
  });

  undoPointBtn?.addEventListener('click', () => {
    if (closed || vertices.length === 0) return;
    vertices.pop();
    redrawTrace();
    if (vertices.length === 0) {
      if (undoPointBtn) undoPointBtn.hidden = true;
      setStatus('Cherchez votre adresse, puis posez un repère sur votre toit.');
    }
    if (finishBtn) finishBtn.disabled = vertices.length < 3;
    updateAreaReadout();
    notify();
  });

  clearBtn?.addEventListener('click', () => {
    pin = null;
    vertices = [];
    closed = false;
    redrawTrace();
    srcOf('rp9-line')?.setData(empty as never);
    redrawPin();
    if (finishBtn) finishBtn.disabled = true;
    if (undoPointBtn) undoPointBtn.hidden = true;
    updateAreaReadout();
    setStatus('Cherchez votre adresse, puis posez un repère sur votre toit.');
    notify();
  });

  /** W113 — sème pin/contour depuis un lead (réutilisable hors capture). */
  function seedFromLead(lead: { roof_point?: { lat: number; lng: number } | null; roof_outline?: Array<[number, number]> | null }) {
    if (Array.isArray(lead.roof_outline) && lead.roof_outline.length >= 3) {
      vertices = lead.roof_outline.map(([lat, lng]) => [lng, lat] as LngLat);
      closed = true;
      pin = null;
      redrawTrace();
      srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [...vertices, vertices[0]] }, properties: {} } as never);
      redrawPin();
    } else if (lead.roof_point && Number.isFinite(lead.roof_point.lat) && Number.isFinite(lead.roof_point.lng)) {
      pin = [lead.roof_point.lng, lead.roof_point.lat];
      vertices = [];
      closed = false;
      redrawPin();
    } else {
      return;
    }
    const p = currentPin();
    if (p) {
      const target = { center: [p.lng, p.lat] as LngLat, zoom: 19, pitch: 0 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
    }
    updateAreaReadout();
    notify();
  }
}
