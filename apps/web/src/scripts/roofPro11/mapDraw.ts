/**
 * Tracé du contour + recherche d'adresse (géocodage) du builder pro-11. Extrait
 * de roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * Contient : `redrawTrace`/`addVertex` (placement des sommets avec le garde W76
 * d'auto-intersection), et `geocode` (recherche d'adresse MapTiler) avec le
 * garde anti-course W75 INTACT (jeton `geoToken` + `AbortController` + débounce
 * ~300 ms de la soumission). La construction de la carte, le boot `map.on('load')`
 * (qui ajoute la couche WebGL de la scène 3D) et l'orchestration `close()` restent
 * dans l'entrée car ils sont indissociables de la scène 3D / du pipeline de calcul.
 */
import maplibregl from 'maplibre-gl';
import { isSimplePolygon, type LngLat } from '../../lib/roof';
import { $ } from './dom';
import { type Ctx } from './context';

/** Dépendances injectées (carte + bandeau de statut + re-lecture d'aire + bouton finir). */
export interface MapDrawDeps {
  /** La carte MapLibre (sources GeoJSON du tracé + flyTo/jumpTo de la recherche). */
  map: maplibregl.Map;
  /** Affiche un message dans le bandeau de statut. */
  setStatus: (msg: string) => void;
  /** Met à jour l'étiquette d'aire du toit (lecture des sommets). */
  updateAreaReadout: () => void;
}

export interface MapDraw {
  redrawTrace: () => void;
  addVertex: (v: LngLat) => void;
  geocode: (query: string) => Promise<void>;
}

export function createMapDraw(ctx: Ctx, deps: MapDrawDeps): MapDraw {
  const { map, setStatus, updateAreaReadout } = deps;
  const opts = ctx.opts;

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  const finishBtn = $<HTMLButtonElement>('rp9-finish');
  const searchForm = $<HTMLFormElement>('rp9-search');
  const addressEl = $<HTMLInputElement>('rp9-address');

  function redrawTrace() {
    srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: ctx.vertices }, properties: {} } as never);
    srcOf('rp9-pts')?.setData({ type: 'FeatureCollection', features: ctx.vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })) } as never);
    if (finishBtn) finishBtn.disabled = ctx.vertices.length < 3 || ctx.closed;
    updateAreaReadout();
  }

  function addVertex(v: LngLat) {
    if (ctx.closed) return;
    // W76 — refuse un point qui ferait CROISER le contour (nœud papillon). isSimplePolygon
    // traite l'anneau comme FERMÉ (dernier→premier), donc tester [...vertices, v] vérifie à
    // la fois la nouvelle arête et l'arête de fermeture implicite v→1ᵉʳ sommet. Un anneau
    // croisé fausse l'aire géodésique (la shoelace s'annule) et le pavage.
    if (ctx.vertices.length >= 3 && !isSimplePolygon([...ctx.vertices, v])) {
      setStatus('Ce point croiserait votre tracé — placez-le ailleurs pour garder un contour simple.');
      return;
    }
    ctx.vertices.push(v);
    redrawTrace();
    if (ctx.vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et lancer le calcul.');
    else setStatus(`Coin ${ctx.vertices.length} placé — continuez à tracer le contour.`);
  }

  // W75 — débounce la soumission de recherche (~300 ms, comme le débounce billTimer de la
  // facture) : des « Entrée » rapprochés ne lancent qu'UNE requête, celle de la dernière saisie.
  let geoSubmitTimer: ReturnType<typeof setTimeout> | null = null;
  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = addressEl?.value.trim();
    if (!q) return;
    if (geoSubmitTimer != null) clearTimeout(geoSubmitTimer);
    setStatus('Recherche de l’adresse…');
    geoSubmitTimer = setTimeout(() => {
      geoSubmitTimer = null;
      void geocode(q);
    }, 300);
  });

  // W75 — jeton + AbortController anti-course : deux recherches concurrentes ne peuvent
  // plus « gagner » dans le désordre (le flyTo lent ne supplante plus le rapide). Chaque
  // appel incrémente geoToken, annule la requête précédente, et ignore sa réponse si un
  // appel plus récent est parti entre-temps.
  let geoToken = 0;
  let geoAbort: AbortController | null = null;
  async function geocode(query: string) {
    const myToken = ++geoToken;
    geoAbort?.abort();
    const ctrl = new AbortController();
    geoAbort = ctrl;
    setStatus('Recherche de l’adresse…');
    try {
      const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json?key=${encodeURIComponent(opts.maptilerKey)}&country=ma&limit=1&language=fr`;
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) throw new Error('geocode');
      const data = (await res.json()) as { features?: Array<{ center?: [number, number] }> };
      if (myToken !== geoToken) return; // une recherche plus récente l'a emporté
      const center = data.features?.[0]?.center;
      if (!center) {
        setStatus('Adresse introuvable. Précisez la ville ou déplacez la carte à la main.');
        return;
      }
      const target = { center, zoom: 19, pitch: 0 } as const;
      if (opts.reducedMotion) map.jumpTo(target);
      else map.flyTo({ ...target, essential: true });
      setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et lancer le calcul.');
    } catch (err) {
      if ((err as Error)?.name === 'AbortError' || myToken !== geoToken) return; // annulée / périmée
      setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
    }
  }

  return { redrawTrace, addVertex, geocode };
}
