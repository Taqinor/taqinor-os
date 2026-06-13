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
import maplibregl from 'maplibre-gl';
// CSS importée comme URL (et non en effet de bord) : Vite émet l'asset mais
// n'injecte AUCUN <link> sur la page. On l'ajoute nous-mêmes à l'init de la
// carte → la CSS MapLibre (~69 ko) ne se charge qu'à l'ouverture de l'outil,
// jamais au chargement de la page. (Le suffixe ?url garde le versionnage Vite.)
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import { layoutPanels, type LngLat } from '../lib/roof';

interface InitOptions {
  maptilerKey: string;
  reducedMotion: boolean;
  initialQuery?: string;
}

const GOLD = '#f3cc66';
const PANEL_FILL = '#2b4cc0';
const PANEL_EDGE = '#dde5f8';
// Maroc — centre par défaut + cadrage du pays pour le géocodage.
const MOROCCO_CENTER: [number, number] = [-7.09, 31.79];

let booted = false;

const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);

export function initRoofTool(opts: InitOptions): void {
  if (booted) return;
  booted = true;

  // Charge la CSS MapLibre à la demande (jamais au chargement de la page).
  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = maplibreCssUrl;
  document.head.appendChild(cssLink);

  const mapEl = $('rt-map');
  const statusEl = $('rt-status');
  const orientEl = $<HTMLSelectElement>('rt-orient');
  const finishBtn = $<HTMLButtonElement>('rt-finish');
  const clearBtn = $<HTMLButtonElement>('rt-clear');
  const searchForm = $<HTMLFormElement>('rt-search');
  const addressEl = $<HTMLInputElement>('rt-address');
  if (!mapEl) return;

  const setStatus = (msg: string) => {
    if (statusEl) statusEl.textContent = msg;
  };

  const map = new maplibregl.Map({
    container: mapEl,
    style: `https://api.maptiler.com/maps/hybrid/style.json?key=${encodeURIComponent(opts.maptilerKey)}`,
    center: MOROCCO_CENTER,
    zoom: 5,
    attributionControl: { compact: true },
    // Le mouvement de caméra animé est neutralisé sous prefers-reduced-motion.
    fadeDuration: opts.reducedMotion ? 0 : 300,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.doubleClickZoom.disable(); // le double-clic ferme le tracé

  let vertices: LngLat[] = [];
  let closed = false;
  let clickTimer: ReturnType<typeof setTimeout> | null = null;

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
    map.addLayer({
      id: 'rt-line',
      type: 'line',
      source: 'rt-line',
      paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] },
    });
    map.addLayer({
      id: 'rt-pts',
      type: 'circle',
      source: 'rt-pts',
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
    src('rt-line')?.setData({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: vertices },
      properties: {},
    } as never);
    src('rt-pts')?.setData({
      type: 'FeatureCollection',
      features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
    } as never);
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
      const target = { center, zoom: 19 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
      setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer.');
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
        setStatus('Estimation prête. Recevez l’étude détaillée sur WhatsApp.');
        return;
      }
    } catch {
      /* repli ci-dessous */
    }
    // Le serveur a déjà un repli local ; si même le proxy échoue, on affiche
    // au moins la taille du système sans la production.
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
    const panel = $('rt-results');
    const cta = $<HTMLButtonElement>('rt-cta');
    const set = (id: string, v: string) => {
      const el = $(id);
      if (el) el.textContent = v;
    };
    if (!r || r.count === 0) {
      set('rt-res-kwc', '—');
      set('rt-res-panels', '—');
      set('rt-res-area', '—');
      set('rt-res-prod', '—');
      set('rt-res-savings', '—');
      set('rt-res-note', r && r.count === 0 ? 'Tracé trop petit pour estimer une installation.' : 'Tracez votre toit pour découvrir votre potentiel solaire.');
      if (cta) cta.hidden = true;
      panel?.classList.remove('rt-results--ready');
      return;
    }
    set('rt-res-kwc', `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
    set('rt-res-panels', `${fmt(r.count)} panneaux`);
    set('rt-res-area', `${fmt(Math.round(r.areaM2))} m²`);
    set('rt-res-prod', r.annualKwh != null ? `${fmt(r.annualKwh)} kWh/an` : 'estimation en cours…');
    set(
      'rt-res-savings',
      r.savings ? `${fmt(r.savings.low)} – ${fmt(r.savings.high)} MAD/an` : '—',
    );
    set(
      'rt-res-note',
      r.source === 'pvgis'
        ? 'Production issue de PVGIS (Commission européenne) — fourchette indicative, pas un devis.'
        : r.annualKwh != null
          ? 'Production estimée (productible moyen Maroc) — fourchette indicative, pas un devis.'
          : 'Taille du système estimée — la production sera précisée par l’étude.',
    );
    panel?.classList.add('rt-results--ready');

    // Pré-remplit le diagnostic enrichi (réutilise EXACTEMENT le formulaire et
    // toute sa plomberie : seuil, consentement, webhook, CAPI inchangés).
    if (cta) {
      cta.hidden = false;
      cta.onclick = () => {
        const area = $<HTMLInputElement>('lf-area');
        const orient = $<HTMLSelectElement>('lf-orient');
        const kwc = $<HTMLInputElement>('lf-kwc-est');
        if (area) area.value = String(Math.round(r.areaM2));
        if (orient) orient.value = orientEl?.value || 'sud';
        // Point décimal explicite (cleanEnrichment accepte « . » comme « , »).
        if (kwc) kwc.value = String(Math.round(r.kwc * 100) / 100);
        // Ouvre la section facultative pour montrer le pré-remplissage.
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
