/**
 * Estimateur de toiture — colle carte + tracé (preview privé).
 *
 * SEUL module qui importe MapLibre + sa CSS : il n'est JAMAIS importé
 * statiquement, uniquement via `import()` dynamique depuis la page de l'outil.
 * Vite l'isole donc dans un chunk chargé À LA DEMANDE — aucune autre page ne
 * télécharge MapLibre. Toute la géométrie pure (aire, pavage, kWc, économies)
 * vit dans src/lib/roof.ts (testée) ; ici, rien que du DOM et de la carte.
 *
 * MapTiler : tuiles satellite (hybride) + géocodage, via une clé PUBLIQUE
 * restreinte par domaine. PVGIS : appelé côté serveur uniquement
 * (/api/roof-estimate) — jamais depuis le navigateur.
 */
import * as maplibregl from 'maplibre-gl';
// CSS importée comme URL (et non en effet de bord) : Vite émet l'asset mais
// n'injecte AUCUN <link> sur la page. On l'ajoute nous-mêmes à l'init de la
// carte → la CSS MapLibre (~69 ko) ne se charge qu'à l'ouverture de l'outil,
// jamais au chargement de la page. (Le suffixe ?url garde le versionnage Vite.)
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import { GOLD, MOROCCO_CENTER, $, addTraceLayers, estimateAndShow, geocodeAndFly, injectMaplibreCss, makeSetStatus, mapErrorWarner, maptilerStyleUrl, renderRoofResults, traceGeoJson, wireSearchForm, wireVertexClicks, createRoofMap, wireOrientReestimate, type RoofResults } from './roofToolShared';
import { layoutPanels, type LngLat } from '../lib/roof';

interface InitOptions {
  maptilerKey: string;
  reducedMotion: boolean;
  initialQuery?: string;
  /** Appelé dès que la carte EXISTE — la page sait alors ne plus jamais
   *  rebasculer sur le repli (une carte vivante ne disparaît pas). */
  onReady?: () => void;
}

const PANEL_FILL = '#2b4cc0';
const PANEL_EDGE = '#dde5f8';

let booted = false;


export function initRoofTool(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  // Charge la CSS MapLibre à la demande (jamais au chargement de la page).
  injectMaplibreCss(maplibreCssUrl);

  const mapEl = $('rt-map');
  const statusEl = $('rt-status');
  const orientEl = $<HTMLSelectElement>('rt-orient');
  const finishBtn = $<HTMLButtonElement>('rt-finish');
  const clearBtn = $<HTMLButtonElement>('rt-clear');
  const searchForm = $<HTMLFormElement>('rt-search');
  const addressEl = $<HTMLInputElement>('rt-address');
  if (!mapEl) return;

  const setStatus = makeSetStatus(statusEl);

  const map = createRoofMap(maplibregl, mapEl, opts, {});

  // La carte EXISTE : on le signale immédiatement. Toute erreur de
  // configuration ultérieure ne doit jamais la faire disparaître ni rebasculer
  // sur le repli (le repli est réservé aux échecs réels : clé absente, style
  // injoignable).
  opts.onReady?.();

  // Erreurs MapLibre non fatales (une tuile/un sprite qui 4xx, etc.) :
  // journalisées, JAMAIS bloquantes — elles ne vident pas la carte.
  map.on('error', mapErrorWarner('roof-tool'));

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.doubleClickZoom.disable(); // le double-clic ferme le tracé

  let vertices: LngLat[] = [];
  let closed = false;

  const empty = { type: 'FeatureCollection', features: [] } as const;

  map.on('load', () => {
    map.addSource('rt-line', { type: 'geojson', data: empty as never });
    map.addSource('rt-pts', { type: 'geojson', data: empty as never });
    map.addSource('rt-roof', { type: 'geojson', data: empty as never });
    map.addSource('rt-panels', { type: 'geojson', data: empty as never });

    map.addLayer({
      id: 'rt-roof-fill',
      type: 'fill',
      source: 'rt-roof',
      paint: { 'fill-color': GOLD, 'fill-opacity': 0.12 },
    });
    map.addLayer({
      id: 'rt-panels-fill',
      type: 'fill',
      source: 'rt-panels',
      paint: { 'fill-color': PANEL_FILL, 'fill-opacity': 0.78 },
    });
    map.addLayer({
      id: 'rt-panels-edge',
      type: 'line',
      source: 'rt-panels',
      paint: { 'line-color': PANEL_EDGE, 'line-width': 0.6 },
    });
    addTraceLayers(map, 'rt');

    if (opts.initialQuery) void geocode(opts.initialQuery);
    else setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  const src = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  function redrawTrace() {
    const trace = traceGeoJson(vertices);
    src('rt-line')?.setData(trace.line as never);
    src('rt-pts')?.setData(trace.points as never);
    if (finishBtn) finishBtn.disabled = vertices.length < 3 || closed;
  }

  function addVertex(v: LngLat) {
    if (closed) return;
    vertices.push(v);
    redrawTrace();
    if (vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit.');
    else setStatus(`Coin ${vertices.length} placé — continuez à tracer le contour.`);
  }

  function reset() {
    vertices = [];
    closed = false;
    src('rt-line')?.setData(empty as never);
    src('rt-pts')?.setData(empty as never);
    src('rt-roof')?.setData(empty as never);
    src('rt-panels')?.setData(empty as never);
    showResults(null);
    if (finishBtn) finishBtn.disabled = true;
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
  }

  function close() {
    if (closed || vertices.length < 3) return;
    closed = true;
    if (finishBtn) finishBtn.disabled = true;
    const ring: LngLat[] = [...vertices];
    src('rt-roof')?.setData({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [[...ring, ring[0]]] },
      properties: {},
    } as never);
    src('rt-line')?.setData(empty as never);
    src('rt-pts')?.setData(empty as never);

    const layout = layoutPanels(ring);
    src('rt-panels')?.setData({
      type: 'FeatureCollection',
      features: layout.panels.map((p) => ({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [p] },
        properties: {},
      })),
    } as never);

    if (layout.count === 0) {
      setStatus('Surface trop petite pour un panneau — élargissez le tracé (« Effacer » pour recommencer).');
      showResults({ ...layout, annualKwh: null, savings: null });
      return;
    }
    setStatus('Tracé fermé. Estimation de la production en cours…');
    showResults({ ...layout, annualKwh: null, savings: null });
    void estimate(ring, layout);
  }

  // Clic = ajoute un sommet (différé pour distinguer du double-clic). Double-clic = ferme.
  wireVertexClicks(map, () => closed, addVertex, close);

  finishBtn?.addEventListener('click', close);
  clearBtn?.addEventListener('click', reset);

  wireOrientReestimate(orientEl, () => (closed && vertices.length >= 3 ? [...vertices] : null), estimate);

  wireSearchForm(searchForm, addressEl, (q) => geocode(q));

  const geocode = (query: string) =>
    geocodeAndFly(query, opts.maptilerKey, map, opts.reducedMotion, setStatus,
      'Cliquez les coins de votre toit. Double-cliquez pour fermer.', false);

  // — Production via le proxy serveur PVGIS (jamais d'appel PVGIS direct) —
  const estimate = (ring: LngLat[], layout: ReturnType<typeof layoutPanels>) =>
    estimateAndShow(ring, layout, orientEl, showResults, setStatus,
      'Estimation prête. Recevez l’étude détaillée sur WhatsApp.');

  // — Rendu du panneau de résultats (espace réservé → aucun saut de page) —
  const showResults = (r: RoofResults | null) =>
    renderRoofResults('rt', r, orientEl, opts.reducedMotion, {
      tooSmall: 'Tracé trop petit pour estimer une installation.',
      pvgis:
        'Production issue de PVGIS (Commission européenne) — fourchette indicative, pas un devis.',
    });
}
