// Briques communes aux trois outils de toiture (roof-tool, roof-tool-3d,
// roof-tool-pro) : jusque-là copiées à l'identique dans chacun. Aucun
// changement de comportement ni de texte — simple mutualisation.
import { layoutPanels, type LngLat } from '../lib/roof';

export const GOLD = '#f3cc66';
// Maroc — centre par défaut + cadrage du pays pour le géocodage.
export const MOROCCO_CENTER: [number, number] = [-7.09, 31.79];

export const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
export const fmt = (n: number) => new Intl.NumberFormat('fr-FR').format(n);

/** Charge la CSS MapLibre à la demande (jamais au chargement de la page). */
export function injectMaplibreCss(href: string): void {
  const cssLink = document.createElement('link');
  cssLink.rel = 'stylesheet';
  cssLink.href = href;
  document.head.appendChild(cssLink);
}

/** Lève si WebGL est indisponible (la page bascule alors sur son repli). */
export function assertWebGL(): void {
  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    throw new Error('WebGL indisponible');
  }
}

export const maptilerStyleUrl = (key: string) =>
  `https://api.maptiler.com/maps/hybrid/style.json?key=${encodeURIComponent(key)}`;

export const mapErrorWarner = (tag: string) => (e: unknown) => {
  const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
  console.warn(`[${tag}] erreur carte (non bloquante) :`, msg);
};

/** Données GeoJSON du tracé en cours (ligne + sommets). */
export function traceGeoJson(vertices: LngLat[]) {
  return {
    line: {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: vertices },
      properties: {},
    },
    points: {
      type: 'FeatureCollection',
      features: vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
    },
  };
}

interface ClickMap {
  on(type: 'click' | 'dblclick', cb: (e: any) => void): unknown;
}

/** Clic = ajoute un sommet (différé pour distinguer du double-clic). Double-clic = ferme. */
export function wireVertexClicks(
  map: ClickMap,
  isClosed: () => boolean,
  addVertex: (v: LngLat) => void,
  close: () => void,
): void {
  let clickTimer: ReturnType<typeof setTimeout> | null = null;
  map.on('click', (e) => {
    if (isClosed()) return;
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
}

/** Géocodage MapTiler (Maroc, FR). null = adresse introuvable ; lève si le service échoue. */
export async function geocodeCenter(query: string, maptilerKey: string): Promise<[number, number] | null> {
  const url =
    `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json` +
    `?key=${encodeURIComponent(maptilerKey)}&country=ma&limit=1&language=fr`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('geocode');
  const data = (await res.json()) as { features?: Array<{ center?: [number, number] }> };
  return data.features?.[0]?.center ?? null;
}

/** Production via le proxy serveur PVGIS (jamais d'appel PVGIS direct). null = repli. */
export async function fetchRoofEstimate(
  ring: LngLat[],
  kwc: number,
  orientation: string,
): Promise<{ annualKwh: number; savings: { low: number; high: number }; source?: string } | null> {
  let lng = 0;
  let lat = 0;
  for (const [x, y] of ring) {
    lng += x;
    lat += y;
  }
  lng /= ring.length;
  lat /= ring.length;
  try {
    const res = await fetch('/api/roof-estimate', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ lat, lon: lng, kwc, orientation }),
    });
    const data = await res.json();
    if (res.ok && data.ok) return data;
  } catch {
    /* repli côté appelant */
  }
  return null;
}

export interface RoofResults {
  count: number;
  kwc: number;
  areaM2: number;
  annualKwh: number | null;
  savings: { low: number; high: number } | null;
  source?: string;
}

/** Rendu du panneau de résultats (espace réservé → aucun saut de page). */
export function renderRoofResults(
  prefix: string,
  r: RoofResults | null,
  orientEl: HTMLSelectElement | null,
  reducedMotion: boolean,
  texts: { tooSmall: string; pvgis: string },
): void {
  const panel = $(`${prefix}-results`);
  const cta = $<HTMLButtonElement>(`${prefix}-cta`);
  const set = (id: string, v: string) => {
    const el = $(id);
    if (el) el.textContent = v;
  };
  if (!r || r.count === 0) {
    set(`${prefix}-res-kwc`, '—');
    set(`${prefix}-res-panels`, '—');
    set(`${prefix}-res-area`, '—');
    set(`${prefix}-res-prod`, '—');
    set(`${prefix}-res-savings`, '—');
    set(
      `${prefix}-res-note`,
      r && r.count === 0 ? texts.tooSmall : 'Tracez votre toit pour découvrir votre potentiel solaire.',
    );
    if (cta) cta.hidden = true;
    panel?.classList.remove(`${prefix}-results--ready`);
    return;
  }
  set(`${prefix}-res-kwc`, `${r.kwc.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} kWc`);
  set(`${prefix}-res-panels`, `${fmt(r.count)} panneaux`);
  set(`${prefix}-res-area`, `${fmt(Math.round(r.areaM2))} m²`);
  set(`${prefix}-res-prod`, r.annualKwh != null ? `${fmt(r.annualKwh)} kWh/an` : 'estimation en cours…');
  set(`${prefix}-res-savings`, r.savings ? `${fmt(r.savings.low)} – ${fmt(r.savings.high)} MAD/an` : '—');
  set(
    `${prefix}-res-note`,
    r.source === 'pvgis'
      ? texts.pvgis
      : r.annualKwh != null
        ? 'Production estimée (productible moyen Maroc) — fourchette indicative, pas un devis.'
        : 'Taille du système estimée — la production sera précisée par l’étude.',
  );
  panel?.classList.add(`${prefix}-results--ready`);

  // Pré-remplit le diagnostic enrichi — RÉUTILISE EXACTEMENT le même formulaire
  // et toute sa plomberie (seuil, consentement, webhook, CAPI) : on n'écrit que
  // dans ses champs, on ne poste aucun lead ici.
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
        behavior: reducedMotion ? 'auto' : 'smooth',
        block: 'start',
      });
    };
  }
}

/** Zone de statut (texte seul) d'un outil. */
export const makeSetStatus = (statusEl: HTMLElement | null) => (msg: string) => {
  if (statusEl) statusEl.textContent = msg;
};

interface TraceMap {
  addLayer(layer: any): unknown;
}

/** Couches du tracé en cours (ligne pointillée + sommets), sources `<p>-line` / `<p>-pts`. */
export function addTraceLayers(map: TraceMap, p: string): void {
  map.addLayer({
    id: `${p}-line`,
    type: 'line',
    source: `${p}-line`,
    paint: { 'line-color': GOLD, 'line-width': 2.5, 'line-dasharray': [2, 1.5] },
  });
  map.addLayer({
    id: `${p}-pts`,
    type: 'circle',
    source: `${p}-pts`,
    paint: {
      'circle-radius': 5,
      'circle-color': GOLD,
      'circle-stroke-color': '#070b1d',
      'circle-stroke-width': 1.5,
    },
  });
}

/** Recherche d'adresse : champ + soumission du formulaire → geocode(q). */
export function wireSearchForm(
  searchForm: HTMLFormElement | null,
  addressEl: HTMLInputElement | null,
  geocode: (q: string) => unknown,
): void {
  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = addressEl?.value.trim();
    if (q) void geocode(q);
  });
}

interface FlyMap {
  jumpTo(t: any): unknown;
  flyTo(t: any): unknown;
}

/** Cherche l'adresse puis cadre la carte dessus (zoom 19). */
export async function geocodeAndFly(
  query: string,
  maptilerKey: string,
  map: FlyMap,
  reducedMotion: boolean,
  setStatus: (m: string) => void,
  okMessage: string,
  topView: boolean,
): Promise<void> {
  setStatus('Recherche de l’adresse…');
  try {
    const center = await geocodeCenter(query, maptilerKey);
    if (!center) {
      setStatus('Adresse introuvable. Précisez la ville ou déplacez la carte à la main.');
      return;
    }
    // Recherche d'adresse = vue de dessus pour tracer (pitch 0) sur les outils 3D.
    const target = topView ? ({ center, zoom: 19, pitch: 0 } as const) : ({ center, zoom: 19 } as const);
    if (reducedMotion) map.jumpTo(target);
    else map.flyTo({ ...target, essential: true });
    setStatus(okMessage);
  } catch {
    setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
  }
}

/** Estime la production (proxy PVGIS) puis affiche ; repli = taille seule. */
export async function estimateAndShow<L extends { kwc: number }>(
  ring: LngLat[],
  layout: L,
  orientEl: HTMLSelectElement | null,
  showResults: (r: any) => void,
  setStatus: (m: string) => void,
  okMessage: string,
): Promise<void> {
  const data = await fetchRoofEstimate(ring, layout.kwc, orientEl?.value || 'sud');
  if (data) {
    showResults({ ...layout, annualKwh: data.annualKwh, savings: data.savings, source: data.source });
    setStatus(okMessage);
    return;
  }
  // Le serveur a déjà un repli local ; si même le proxy échoue, on affiche
  // au moins la taille du système sans la production.
  showResults({ ...layout, annualKwh: null, savings: null });
  setStatus('Production momentanément indisponible — la taille du système reste indicative.');
}

/** Carte MapLibre commune : satellite hybride MapTiler centré sur le Maroc. */
export function createRoofMap(
  ML: { Map: new (o: any) => any },
  mapEl: HTMLElement,
  opts: { maptilerKey: string; reducedMotion: boolean },
  extra: Record<string, unknown> = {},
) {
  return new ML.Map({
    container: mapEl,
    style: maptilerStyleUrl(opts.maptilerKey),
    center: MOROCCO_CENTER,
    zoom: 5,
    ...extra,
    attributionControl: { compact: true },
    // Le mouvement de caméra animé est neutralisé sous prefers-reduced-motion.
    fadeDuration: opts.reducedMotion ? 0 : 300,
  });
}

/** Re-estimer si l'orientation change après fermeture (la production en dépend). */
export function wireOrientReestimate(
  orientEl: HTMLSelectElement | null,
  closedRing: () => LngLat[] | null,
  estimate: (ring: LngLat[], layout: ReturnType<typeof layoutPanels>) => unknown,
): void {
  orientEl?.addEventListener('change', () => {
    const ring = closedRing();
    if (!ring) return;
    const layout = layoutPanels(ring);
    if (layout.count > 0) void estimate(ring, layout);
  });
}
