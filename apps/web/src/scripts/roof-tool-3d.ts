/**
 * Estimateur de toiture — VARIANTE 3D (preview privé /preview/toiture-3d).
 *
 * Même carte (MapLibre + tuiles satellite MapTiler), même tracé, MÊME calcul
 * (src/lib/roof.ts → layoutPanels) et MÊME flux lead (pré-remplit le diagnostic
 * enrichi de production, sans jamais poster de lead lui-même) que la version 2D.
 * SEULE la PRÉSENTATION change :
 * une fois le toit fermé, on bascule en vue 3D et on extrude le bâtiment, le toit
 * et les panneaux avec les couches `fill-extrusion` NATIVES de MapLibre — AUCUNE
 * dépendance ajoutée (pas de Three.js).
 *
 * Comme la version 2D, ce module est le SEUL — avec roof-tool.ts — à importer
 * MapLibre + sa CSS, et il n'est JAMAIS importé statiquement : uniquement via
 * `import()` dynamique depuis la page de l'outil. Vite l'isole donc dans un chunk
 * chargé À LA DEMANDE — aucune autre page ne télécharge MapLibre.
 *
 * PVGIS : appelé côté serveur uniquement (/api/roof-estimate), jamais ici.
 */
import maplibregl from 'maplibre-gl';
// CSS importée comme URL (et non en effet de bord) : Vite émet l'asset mais
// n'injecte aucun <link>. On l'ajoute nous-mêmes à l'init → ~69 ko chargés
// seulement à l'ouverture de l'outil, jamais au chargement de la page.
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import { layoutPanels, type LngLat } from '../lib/roof';

interface InitOptions {
  maptilerKey: string;
  reducedMotion: boolean;
  initialQuery?: string;
  /** Appelé dès que la carte EXISTE — la page sait alors ne plus jamais
   *  rebasculer sur le repli (une carte vivante ne disparaît pas). */
  onReady?: () => void;
}

const GOLD = '#f3cc66';
// Bâtiment : blanc-azur lumineux (le dégradé vertical natif de MapLibre l'ombre
// vers la base → relief propre et « premium » sur fond satellite).
const BUILDING_COLOR = '#e4e9f6';
// Toit en pente : légèrement plus chaud/contrasté que les murs.
const ROOF_CAP_COLOR = '#c4ccdf';
// Panneaux : bleu Majorelle vif (couleur de marque).
const PANEL_COLOR = '#2a47c4';
const PANEL_TOP = '#3f5fd8';
// Maroc — centre par défaut + cadrage du pays pour le géocodage.
const MOROCCO_CENTER: [number, number] = [-7.09, 31.79];

const FLOOR_HEIGHT_M = 3; // hauteur d'étage approximative
const PITCH_VIEW = 56; // inclinaison caméra en vue 3D

let booted = false;

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);

export function initRoofTool3D(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  // Repli immédiat si WebGL est indisponible : on lève, la page affiche le repli
  // gracieux (le bloc try/catch + onReady côté page s'en charge).
  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    throw new Error('WebGL indisponible');
  }

  // Charge la CSS MapLibre à la demande (jamais au chargement de la page).
  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const mapEl = $('r3-map');
  const statusEl = $('r3-status');
  const orientEl = $<HTMLSelectElement>('r3-orient');
  const floorsEl = $<HTMLSelectElement>('r3-floors');
  const pitchEl = $<HTMLInputElement>('r3-pitch');
  const finishBtn = $<HTMLButtonElement>('r3-finish');
  const clearBtn = $<HTMLButtonElement>('r3-clear');
  const searchForm = $<HTMLFormElement>('r3-search');
  const addressEl = $<HTMLInputElement>('r3-address');
  const buildPanel = $('r3-build-controls');
  if (!mapEl) return;

  const setStatus = (msg: string) => {
    if (statusEl) statusEl.textContent = msg;
  };

  const map = new maplibregl.Map({
    container: mapEl,
    style: `https://api.maptiler.com/maps/hybrid/style.json?key=${encodeURIComponent(opts.maptilerKey)}`,
    center: MOROCCO_CENTER,
    zoom: 5,
    pitch: 0,
    maxPitch: 75,
    attributionControl: { compact: true },
    fadeDuration: opts.reducedMotion ? 0 : 300,
  });

  // La carte EXISTE : on le signale immédiatement (cf. roof-tool.ts).
  opts.onReady?.();

  map.on('error', (e: unknown) => {
    const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
    console.warn('[roof-tool-3d] erreur carte (non bloquante) :', msg);
  });

  // Compas visible : aide à comprendre qu'on peut faire pivoter / réorienter.
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
  map.doubleClickZoom.disable(); // le double-clic ferme le tracé
  // Rotation/inclinaison au glisser activées par défaut (drag droit / 2 doigts) —
  // on les laisse pour l'orbite ; aucune rotation automatique n'est ajoutée.

  let vertices: LngLat[] = [];
  let closed = false;
  let clickTimer: ReturnType<typeof setTimeout> | null = null;
  let lastLayout: ReturnType<typeof layoutPanels> | null = null;

  const empty = { type: 'FeatureCollection', features: [] } as const;

  map.on('load', () => {
    // Tracé (vue de dessus) : ligne + points.
    map.addSource('r3-line', { type: 'geojson', data: empty as never });
    map.addSource('r3-pts', { type: 'geojson', data: empty as never });
    // Volumes 3D : bâtiment, toit (pente), panneaux.
    map.addSource('r3-building', { type: 'geojson', data: empty as never });
    map.addSource('r3-cap', { type: 'geojson', data: empty as never });
    map.addSource('r3-panels', { type: 'geojson', data: empty as never });

    // — Murs du bâtiment (0 → hauteur, hauteur lue par entité) —
    map.addLayer({
      id: 'r3-building-3d',
      type: 'fill-extrusion',
      source: 'r3-building',
      paint: {
        'fill-extrusion-color': BUILDING_COLOR,
        'fill-extrusion-height': ['get', 'h'],
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.95,
        'fill-extrusion-vertical-gradient': true,
      },
    });
    // — Toit en pente (gradins concentriques : base/hauteur par entité) —
    map.addLayer({
      id: 'r3-cap-3d',
      type: 'fill-extrusion',
      source: 'r3-cap',
      paint: {
        'fill-extrusion-color': ROOF_CAP_COLOR,
        'fill-extrusion-height': ['get', 'h'],
        'fill-extrusion-base': ['get', 'base'],
        'fill-extrusion-opacity': 0.95,
        'fill-extrusion-vertical-gradient': true,
      },
    });
    // — Panneaux (fines dalles posées sur le toit) —
    map.addLayer({
      id: 'r3-panels-3d',
      type: 'fill-extrusion',
      source: 'r3-panels',
      paint: {
        'fill-extrusion-color': ['interpolate', ['linear'], ['get', 'shade'], 0, PANEL_COLOR, 1, PANEL_TOP],
        'fill-extrusion-height': ['get', 'h'],
        'fill-extrusion-base': ['get', 'base'],
        'fill-extrusion-opacity': 0.97,
      },
    });

    // — Tracé (au-dessus, visible en vue de dessus) —
    map.addLayer({
      id: 'r3-line',
      type: 'line',
      source: 'r3-line',
      paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] },
    });
    map.addLayer({
      id: 'r3-pts',
      type: 'circle',
      source: 'r3-pts',
      paint: {
        'circle-radius': 5,
        'circle-color': GOLD,
        'circle-stroke-color': '#070b1d',
        'circle-stroke-width': 1.5,
      },
    });

    if (opts.initialQuery) void geocode(opts.initialQuery);
    else setStatus('Cherchez votre adresse, puis cliquez les coins de votre toit.');
  });

  const src = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  function redrawTrace() {
    src('r3-line')?.setData({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: vertices },
      properties: {},
    } as never);
    src('r3-pts')?.setData({
      type: 'FeatureCollection',
      features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
    } as never);
    if (finishBtn) finishBtn.disabled = vertices.length < 3 || closed;
  }

  function addVertex(v: LngLat) {
    if (closed) return;
    vertices.push(v);
    redrawTrace();
    if (vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et le voir en 3D.');
    else setStatus(`Coin ${vertices.length} placé — continuez à tracer le contour.`);
  }

  function clearVolumes() {
    src('r3-building')?.setData(empty as never);
    src('r3-cap')?.setData(empty as never);
    src('r3-panels')?.setData(empty as never);
  }

  function reset() {
    vertices = [];
    closed = false;
    lastLayout = null;
    src('r3-line')?.setData(empty as never);
    src('r3-pts')?.setData(empty as never);
    clearVolumes();
    showResults(null);
    if (buildPanel) buildPanel.hidden = true;
    if (finishBtn) finishBtn.disabled = true;
    // Retour à la vue de dessus pour retracer.
    const target = { pitch: 0, bearing: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 600 });
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
  }

  // — Géométrie 3D : centroïde + mise à l'échelle vers le centre (gradins toit) —
  function centroid(ring: LngLat[]): LngLat {
    let x = 0;
    let y = 0;
    for (const [lng, lat] of ring) {
      x += lng;
      y += lat;
    }
    return [x / ring.length, y / ring.length];
  }
  function scaledRing(ring: LngLat[], c: LngLat, s: number): LngLat[] {
    const r = ring.map(([lng, lat]) => [c[0] + (lng - c[0]) * s, c[1] + (lat - c[1]) * s] as LngLat);
    return [...r, r[0]];
  }

  // Construit (ou reconstruit) les volumes 3D à partir du tracé + des réglages.
  function build3D(ring: LngLat[]) {
    const floors = Math.max(1, Math.min(3, parseInt(floorsEl?.value || '2', 10) || 2));
    const wallH = floors * FLOOR_HEIGHT_M;
    const pitched = !!pitchEl?.checked;

    // Bâtiment : prisme vertical du contour, 0 → hauteur des murs.
    const closedRing: LngLat[] = [...ring, ring[0]];
    src('r3-building')?.setData({
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [closedRing] },
      properties: { h: wallH },
    } as never);

    // Toit : plat (plan au sommet des murs) ou pente douce (pyramide tronquée).
    let roofTop = wallH;
    if (pitched) {
      const c = centroid(ring);
      const STEPS = 6;
      const pitchH = 1.4; // pente DOUCE volontaire (massing approximatif, pas un modèle exact)
      roofTop = wallH + pitchH;
      const feats = [] as unknown[];
      for (let k = 0; k < STEPS; k++) {
        const s0 = 1 - (k / STEPS) * 0.2; // resserre légèrement vers le sommet
        const base = wallH + (pitchH * k) / STEPS;
        const h = wallH + (pitchH * (k + 1)) / STEPS;
        feats.push({
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [scaledRing(ring, c, s0)] },
          properties: { base, h },
        });
      }
      src('r3-cap')?.setData({ type: 'FeatureCollection', features: feats } as never);
    } else {
      src('r3-cap')?.setData(empty as never);
    }

    // Panneaux : fines dalles posées juste au-dessus du plan de toit.
    const base = roofTop + 0.06;
    const h = roofTop + 0.22;
    const layout = lastLayout!;
    src('r3-panels')?.setData({
      type: 'FeatureCollection',
      features: layout.panels.map((p, i) => ({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [p] },
        // léger damier d'ombrage pour distinguer les panneaux à l'orbite
        properties: { base, h, shade: i % 2 === 0 ? 0 : 1 },
      })),
    } as never);
  }

  function go3DView(ring: LngLat[]) {
    let lng = 0;
    let lat = 0;
    for (const [x, y] of ring) {
      lng += x;
      lat += y;
    }
    const center: [number, number] = [lng / ring.length, lat / ring.length];
    const target = { center, pitch: PITCH_VIEW } as const;
    // Sous prefers-reduced-motion : bascule instantanée, AUCUNE animation.
    if (opts.reducedMotion) map.jumpTo(target);
    else map.easeTo({ ...target, duration: 1100, essential: true });
  }

  function close() {
    if (closed || vertices.length < 3) return;
    closed = true;
    if (finishBtn) finishBtn.disabled = true;
    const ring: LngLat[] = [...vertices];
    src('r3-line')?.setData(empty as never);
    src('r3-pts')?.setData(empty as never);

    const layout = layoutPanels(ring);
    lastLayout = layout;

    if (layout.count === 0) {
      clearVolumes();
      // On montre quand même le bâtiment pour le contexte, sans panneaux.
      build3D(ring);
      go3DView(ring);
      setStatus('Surface trop petite pour un panneau — élargissez le tracé (« Effacer » pour recommencer).');
      showResults({ ...layout, annualKwh: null, savings: null });
      if (buildPanel) buildPanel.hidden = false;
      return;
    }

    build3D(ring);
    go3DView(ring);
    if (buildPanel) buildPanel.hidden = false;
    setStatus('Toit fermé en 3D. Faites glisser pour pivoter et incliner. Estimation en cours…');
    showResults({ ...layout, annualKwh: null, savings: null });
    void estimate(ring, layout);
  }

  // Clic = ajoute un sommet (différé pour distinguer du double-clic). Double-clic = ferme.
  map.on('click', (e) => {
    if (closed) return;
    if (clickTimer) return;
    const lngLat: LngLat = [e.lngLat.lng, e.lngLat.lat];
    clickTimer = setTimeout(() => {
      clickTimer = null;
      addVertex(lngLat);
    }, 240);
  });
  map.on('dblclick', (e) => {
    e.preventDefault();
    if (clickTimer) {
      clearTimeout(clickTimer);
      clickTimer = null;
    }
    close();
  });

  finishBtn?.addEventListener('click', close);
  clearBtn?.addEventListener('click', reset);

  // Réglages du bâtiment (étages / toit en pente) : reconstruisent les volumes
  // SANS rien réestimer (la puissance/production ne dépend que de l'emprise).
  const rebuild = () => {
    if (closed && vertices.length >= 3 && lastLayout) build3D([...vertices]);
  };
  floorsEl?.addEventListener('change', rebuild);
  pitchEl?.addEventListener('change', rebuild);

  // Re-estimer si l'orientation change après fermeture (la production en dépend).
  orientEl?.addEventListener('change', () => {
    if (closed && vertices.length >= 3) {
      const ring: LngLat[] = [...vertices];
      const layout = layoutPanels(ring);
      if (layout.count > 0) void estimate(ring, layout);
    }
  });

  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = addressEl?.value.trim();
    if (q) void geocode(q);
  });

  async function geocode(query: string) {
    setStatus('Recherche de l’adresse…');
    try {
      const url =
        `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json` +
        `?key=${encodeURIComponent(opts.maptilerKey)}&country=ma&limit=1&language=fr`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('geocode');
      const data = (await res.json()) as { features?: Array<{ center?: [number, number] }> };
      const center = data.features?.[0]?.center;
      if (!center) {
        setStatus('Adresse introuvable. Précisez la ville ou déplacez la carte à la main.');
        return;
      }
      // Recherche d'adresse = vue de dessus pour tracer (pitch 0).
      const target = { center, zoom: 19, pitch: 0 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
      setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et voir la 3D.');
    } catch {
      setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
    }
  }

  // — Production via le proxy serveur PVGIS (jamais d'appel PVGIS direct) —
  async function estimate(ring: LngLat[], layout: ReturnType<typeof layoutPanels>) {
    let lng = 0;
    let lat = 0;
    for (const [x, y] of ring) {
      lng += x;
      lat += y;
    }
    lng /= ring.length;
    lat /= ring.length;
    const orientation = orientEl?.value || 'sud';
    try {
      const res = await fetch('/api/roof-estimate', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ lat, lon: lng, kwc: layout.kwc, orientation }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        showResults({ ...layout, annualKwh: data.annualKwh, savings: data.savings, source: data.source });
        setStatus('Estimation prête. Faites pivoter le bâtiment, puis recevez l’étude sur WhatsApp.');
        return;
      }
    } catch {
      /* repli ci-dessous */
    }
    showResults({ ...layout, annualKwh: null, savings: null });
    setStatus('Production momentanément indisponible — la taille du système reste indicative.');
  }

  // — Rendu du panneau de résultats (espace réservé → aucun saut de page) —
  interface Results {
    count: number;
    kwc: number;
    areaM2: number;
    annualKwh: number | null;
    savings: { low: number; high: number } | null;
    source?: string;
  }
  function showResults(r: Results | null) {
    const panel = $('r3-results');
    const cta = $<HTMLButtonElement>('r3-cta');
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    if (!r || r.count === 0) {
      set('r3-res-kwc', '—');
      set('r3-res-panels', '—');
      set('r3-res-area', '—');
      set('r3-res-prod', '—');
      set('r3-res-savings', '—');
      set('r3-res-note', r && r.count === 0 ? 'Tracé trop petit pour estimer une installation.' : 'Tracez votre toit pour découvrir votre potentiel solaire.');
      if (cta) cta.hidden = true;
      panel?.classList.remove('r3-results--ready');
      return;
    }
    set('r3-res-kwc', `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('r3-res-panels', `${fmt(r.count)} panneaux`);
    set('r3-res-area', `${fmt(Math.round(r.areaM2))} m²`);
    set('r3-res-prod', r.annualKwh != null ? `${fmt(r.annualKwh)} kWh/an` : 'estimation en cours…');
    set('r3-res-savings', r.savings ? `${fmt(r.savings.low)} – ${fmt(r.savings.high)} MAD/an` : '—');
    set(
      'r3-res-note',
      r.source === 'pvgis'
        ? 'Production issue de PVGIS (Commission européenne) — fourchette indicative, pas un devis.'
        : r.annualKwh != null
          ? 'Production estimée (productible moyen Maroc) — fourchette indicative, pas un devis.'
          : 'Taille du système estimée — la production sera précisée par l’étude.',
    );
    panel?.classList.add('r3-results--ready');

    // Pré-remplit le diagnostic enrichi — RÉUTILISE EXACTEMENT le même formulaire
    // et toute sa plomberie (seuil 1 000 MAD, consentement, webhook, CAPI) que la
    // version 2D : on n'écrit que dans ses champs, on ne poste aucun lead ici.
    if (cta) {
      cta.hidden = false;
      cta.onclick = () => {
        const area = $<HTMLInputElement>('lf-area');
        const orient = $<HTMLSelectElement>('lf-orient');
        const kwc = $<HTMLInputElement>('lf-kwc-est');
        if (area) area.value = String(Math.round(r.areaM2));
        if (orient) orient.value = orientEl?.value || 'sud';
        if (kwc) kwc.value = String(Math.round(r.kwc * 100) / 100);
        const details = (area?.closest('details') as HTMLDetailsElement | null) ?? null;
        if (details) details.open = true;
        document.getElementById('simulateur')?.scrollIntoView({
          behavior: opts.reducedMotion ? 'auto' : 'smooth',
          block: 'start',
        });
      };
    }
  }
}
