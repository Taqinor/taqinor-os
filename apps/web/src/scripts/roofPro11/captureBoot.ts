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
import { createMapDraw, type CaptureStrings, CAPTURE_STRINGS_FR } from './mapDraw';
import { type InitOptions } from './types';

// WJ41 — réexportés pour que les pages mon-toit.astro puissent importer le
// type/replis directement depuis captureBoot.ts si besoin (mapDraw.ts en reste
// la SEULE source de vérité).
export type { CaptureStrings };
export { CAPTURE_STRINGS_FR };

/** `initRoofToolPro8`/`bootCaptureOnly` acceptent un `opts.strings` optionnel sans
 *  modifier `types.ts` (hors périmètre WJ41) : on élargit le type localement par
 *  intersection. Absent → CAPTURE_STRINGS_FR (rendu FR inchangé).
 *
 * WJ62 — `opts.dir` (optionnel, absent → 'ltr', comportement inchangé) : la page
 * AR le passe 'rtl' pour déplacer les contrôles carte (géolocalisation, zoom) en
 * haut-à-gauche — en RTL le haut-DROIT est déjà occupé visuellement par le sens
 * de lecture/les boutons de langue, et MapLibre ne fait pas ce choix seul.
 * `opts.onMapError` (optionnel) : notifie la page d'une panne carte SURVENUE EN
 * COURS DE SESSION (tuiles/style — après un premier rendu réussi), pour révéler
 * le panneau de repli adresse existant au lieu d'un simple `console.warn` muet. */
export type CaptureOptions = InitOptions & {
  strings?: CaptureStrings;
  dir?: 'ltr' | 'rtl';
  onMapError?: () => void;
  /** WJ62 — message affiché dans le bandeau de statut quand la géolocalisation
   *  est refusée/indisponible (`GeolocationPositionError`). Localisé par la page
   *  (pas dans `CaptureStrings`, hors périmètre mapDraw.ts) ; absent → replis FR. */
  geolocateErrorMsg?: string;
  /**
   * MODE DE SAISIE DU TOIT, choisi EXPLICITEMENT par le visiteur sur la page
   * (« pointer » vs « dessiner »). Lu à CHAQUE clic (fonction, pas valeur : le
   * visiteur peut changer d'avis en cours de route).
   *
   * Le flux historique était IMPLICITE — un clic simple posait le repère, et il
   * fallait DEVINER qu'un double-clic démarrait un contour. En mode `'draw'`, le
   * PREMIER clic ouvre directement le contour ; en mode `'point'`, la carte
   * atterrit serrée sur le repère posé pour que la page puisse demander
   * « C'est bien votre toit ? » sur une image lisible.
   *
   * Absent (ou `undefined` renvoyé) → comportement historique à l'octet près.
   */
  roofInputMode?: () => 'point' | 'draw' | undefined;
};

/**
 * Démarre le mode capture client. Construit la carte + le géocodeur + le pin/tracé,
 * câble le bouton « Terminer le tracé » et « Effacer », et notifie la page à chaque
 * changement de pin/contour via `opts.onCaptureChange`.
 */
export function bootCaptureOnly(opts: CaptureOptions): void {
  const t = opts.strings ?? CAPTURE_STRINGS_FR;
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

  // WJ62 — une panne carte SURVENUE EN COURS DE SESSION (tuiles/style, après un
  // premier rendu réussi) laissait le visiteur bloqué sur une carte figée sans
  // aucun signal ; on la rend VISIBLE en révélant le panneau de repli adresse
  // déjà présent sur la page (même mécanisme que l'échec de clé au boot), au
  // lieu d'un simple `console.warn` muet. `hasRenderedOnce` distingue une
  // première erreur transitoire (avant le tout premier rendu, où `load` suivra
  // souvent quand même) d'une VRAIE panne en session.
  let hasRenderedOnce = false;
  map.once('load', () => {
    hasRenderedOnce = true;
  });
  map.on('error', (e: unknown) => {
    const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
    console.warn('[capture-toit] erreur carte :', msg);
    if (hasRenderedOnce) opts.onMapError?.();
  });
  // WJ62 — sous RTL, les contrôles (zoom, géolocalisation) passent en haut-à-
  // gauche : en haut-à-droite ils chevauchent visuellement le sens de lecture
  // RTL et les boutons de langue déjà présents dans cet angle sur la page AR.
  const controlCorner = opts.dir === 'rtl' ? 'top-left' : 'top-right';
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), controlCorner);
  const geolocate = new maplibregl.GeolocateControl({
    positionOptions: { enableHighAccuracy: true },
    trackUserLocation: false,
    showUserLocation: true,
  });
  map.addControl(geolocate, controlCorner);
  /**
   * ATTERRISSAGE sur un point : recentre la carte serrée dessus. Un seul et même
   * comportement pour la géolocalisation, l'hydratation d'un repère existant
   * (W113/WJ61) et la confirmation « pointer » — jamais trois variantes.
   * `minZoom` est un PLANCHER : on ne dézoome jamais un visiteur déjà plus près.
   */
  function landOn(lngLat: LngLat, minZoom = 19) {
    const target = {
      center: lngLat,
      zoom: Math.max(map.getZoom() || 0, minZoom),
      pitch: 0,
    } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.flyTo({ ...target, essential: true });
  }

  geolocate.on('geolocate', (e: { coords?: { longitude: number; latitude: number } }) => {
    const c = e?.coords;
    if (!c) return;
    landOn([c.longitude, c.latitude]);
  });
  // WJ62 — un refus/échec de géolocalisation (permission refusée, indisponible,
  // délai dépassé) était un silence total : le bandeau de statut annonce
  // maintenant clairement l'échec + invite à chercher l'adresse ou poser le
  // repère à la main (le reste du parcours reste inchangé et non bloqué).
  geolocate.on('error', () => {
    setStatus(opts.geolocateErrorMsg ?? 'Localisation refusée — cherchez votre adresse ou posez le repère à la main.');
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

  // W2 — annule un reverse-geocode en vol quand un nouveau repère est posé : seul le
  // dernier repère doit remplir l'adresse (anti-course, comme la recherche d'adresse).
  let revAbort: AbortController | null = null;

  function notify(address?: string | null) {
    opts.onCaptureChange?.({ pin: currentPin(), outline: currentOutline(), address });
  }

  // W2 — RÉSOUT l'adresse depuis le repère courant (géocodage inverse) puis re-notifie
  // la page avec `address` rempli. Lancé après chaque pose/déplacement de repère/contour ;
  // ne fait rien sans repère (effacement). Tolère l'échec (address null → on n'écrase rien).
  function refreshAddressFromPin() {
    const p = currentPin();
    if (!p) return;
    revAbort?.abort();
    const ctrl = new AbortController();
    revAbort = ctrl;
    void reverseGeocode(p.lng, p.lat, { signal: ctrl.signal }).then((address) => {
      if (ctrl.signal.aborted) return; // un repère plus récent a pris la main
      if (address) notify(address);
    });
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
  // W2 — géocodage inverse (repère → adresse), partagé avec la recherche d'adresse.
  const reverseGeocode = mapDraw.reverseGeocode;

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
    else setStatus(t.searchAddressThenPin);
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
    setStatus(t.pinPlaced);
    // Choix EXPLICITE « pointer » : la carte atterrit serrée sur le repère. C'est
    // la moitié « preuve visuelle » de la confirmation que la page affiche
    // ensuite — sans elle, le visiteur valide « oui c'est mon toit » sur une vue
    // large où il ne distingue rien. Flux « dessiner » et flux historique
    // (option absente) : aucun déplacement de caméra, comme avant.
    if (opts.roofInputMode?.() === 'point') landOn(v);
    notify();
    // W2 — lit l'adresse DEPUIS la carte : remplit le champ adresse + capture le GPS.
    refreshAddressFromPin();
  }

  // Clic carte : en mode capture, un clic SIMPLE pose/déplace le pin. Si le visiteur
  // a commencé un contour (≥1 sommet via le double-clic), le clic ajoute un sommet.
  //
  // BUG FONDATEUR (24/08) — un contour déjà FERMÉ (closed === true, ≥3 sommets)
  // tombait dans le repli `setPin(lngLat)` tout en bas de ce handler, qui fait
  // INCONDITIONNELLEMENT `vertices = []; closed = false;` : un simple clic sur la
  // carte APRÈS avoir terminé le tracé — qu'il vienne d'un visiteur qui rebascule
  // sur « Pointer mon toit » pour ajuster, d'une main qui glisse, ou d'un doigt sur
  // mobile — effaçait tout le contour EN SILENCE et le remplaçait par un pin seul.
  // Scénario vécu : pin posé, puis passage en « Dessiner mon toit » et tracé
  // terminé → la fiche CRM ne montrait plus que le pin. Un contour fermé ne se
  // réinitialise plus que via le bouton explicite « Effacer » (rp9-clear,
  // ci-dessous) — jamais un clic de carte : même esprit que la garde GPS du
  // webhook (jamais d'écrasement d'une donnée déjà captée par du vide).
  map.on('click', (e) => {
    const lngLat: LngLat = [e.lngLat.lng, e.lngLat.lat];
    if (closed) {
      setStatus(t.outlineTraced);
      return;
    }
    if (vertices.length > 0 && !closed) {
      addVertex(lngLat);
      pin = null;
      redrawPin();
      if (finishBtn) finishBtn.disabled = vertices.length < 3;
      if (undoPointBtn) undoPointBtn.hidden = vertices.length < 1;
      notify();
      // W2 — le centroïde du contour bouge à chaque sommet : rafraîchit l'adresse.
      refreshAddressFromPin();
      return;
    }
    // Choix EXPLICITE « dessiner » : le PREMIER clic ouvre le contour. Le
    // double-clic restait la seule porte d'entrée du tracé et rien ne
    // l'annonçait — une interaction qui n'existe même pas au doigt sur mobile.
    if (!closed && opts.roofInputMode?.() === 'draw') {
      // Un pin déjà posé (visiteur d'abord passé par « Pointer mon toit ») devient
      // le PREMIER sommet du tracé au lieu d'être silencieusement perdu — même
      // patron que le double-clic historique plus bas (`vertices = pin ? [pin] :
      // []`) : le pin reste la position de départ, le tracé ajoute la forme.
      if (pin) vertices = [pin];
      pin = null;
      redrawPin();
      // `addVertex` pose lui-même le bon message (« Coin N placé… », puis
      // « Double-cliquez pour fermer » dès 3 sommets) : on ne l'écrase pas avec
      // une consigne générique, il est plus précis.
      addVertex(lngLat);
      if (finishBtn) finishBtn.disabled = vertices.length < 3;
      if (undoPointBtn) undoPointBtn.hidden = vertices.length < 1;
      updateAreaReadout();
      notify();
      refreshAddressFromPin();
      return;
    }
    setPin(lngLat);
  });

  // Double-clic : DÉMARRE/poursuit un tracé de contour (optionnel). Le 1ᵉʳ double-clic
  // convertit le pin en 1ᵉʳ sommet ; les suivants ferment le contour (≥3 sommets).
  map.on('dblclick', (e) => {
    e.preventDefault();
    // …mais UNIQUEMENT dans le geste « dessiner ». En mode « pointer », la page
    // masque « Terminer le tracé » (syncRoofModeCards : finishBtn.hidden =
    // roofInputMode !== 'draw') : un double-clic ouvrait donc un contour que le
    // visiteur n'avait pas choisi, SANS le bouton pour en sortir — et tant que
    // ce contour a moins de 3 sommets, currentPin() rend null, ce qui faisait
    // aussi disparaître la confirmation « C'est bien votre toit ? ». Ici, un
    // double-clic n'est qu'un repère de plus : les deux clics qui le composent
    // sont déjà passés par le handler `click` ci-dessus, qui a posé le repère.
    // Le flux HISTORIQUE (pas de cartes de geste, donc `roofInputMode` absent)
    // garde le double-clic traceur, inchangé.
    const inputMode = opts.roofInputMode?.();
    if (inputMode && inputMode !== 'draw') return;
    if (closed) return;
    if (vertices.length >= 3 && isSimplePolygon(vertices)) {
      closed = true;
      redrawTrace();
      srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [...vertices, vertices[0]] }, properties: {} } as never);
      if (finishBtn) finishBtn.disabled = true;
      if (undoPointBtn) undoPointBtn.hidden = true;
      setStatus(t.outlineTraced);
      updateAreaReadout();
      notify();
      refreshAddressFromPin();
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
    setStatus(t.traceOutline);
    notify();
    refreshAddressFromPin();
  });

  finishBtn?.addEventListener('click', () => {
    if (closed || vertices.length < 3) return;
    if (!isSimplePolygon(vertices)) {
      setStatus(t.outlineCrosses);
      return;
    }
    closed = true;
    redrawTrace();
    srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: [...vertices, vertices[0]] }, properties: {} } as never);
    finishBtn.disabled = true;
    if (undoPointBtn) undoPointBtn.hidden = true;
    setStatus(t.outlineTraced);
    updateAreaReadout();
    notify();
    refreshAddressFromPin();
  });

  undoPointBtn?.addEventListener('click', () => {
    if (closed || vertices.length === 0) return;
    vertices.pop();
    redrawTrace();
    if (vertices.length === 0) {
      if (undoPointBtn) undoPointBtn.hidden = true;
      setStatus(t.searchAddressThenPin);
    }
    if (finishBtn) finishBtn.disabled = vertices.length < 3;
    updateAreaReadout();
    notify();
  });

  clearBtn?.addEventListener('click', () => {
    pin = null;
    vertices = [];
    closed = false;
    // W2 — annule un reverse-geocode en vol : aucune adresse périmée ne doit arriver
    // après l'effacement.
    revAbort?.abort();
    redrawTrace();
    srcOf('rp9-line')?.setData(empty as never);
    redrawPin();
    if (finishBtn) finishBtn.disabled = true;
    if (undoPointBtn) undoPointBtn.hidden = true;
    updateAreaReadout();
    setStatus(t.searchAddressThenPin);
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
    if (p) landOn([p.lng, p.lat]);
    updateAreaReadout();
    notify();
  }
}
