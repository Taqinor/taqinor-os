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
  /** W92 — retire le dernier sommet posé (pendant le tracé, avant fermeture). */
  undoLastPoint: () => void;
  /** W93 — `autoSelect` (programmatique, ex. initialQuery) vole directement au 1ᵉʳ
   *  résultat ; sinon la liste de suggestions est peuplée et on attend la sélection. */
  geocode: (query: string, autoSelect?: boolean) => Promise<void>;
  /** W2 — géocodage INVERSE : du couple (lng, lat) du repère vers le libellé d'adresse
   *  le plus pertinent (`place_name`). Retourne `null` si rien n'est trouvé ou si la
   *  requête échoue/est annulée. Même clé MapTiler + même garde anti-course (jeton +
   *  AbortController) que `geocode`. */
  reverseGeocode: (lng: number, lat: number, opts?: { signal?: AbortSignal }) => Promise<string | null>;
}

export function createMapDraw(ctx: Ctx, deps: MapDrawDeps): MapDraw {
  const { map, setStatus, updateAreaReadout } = deps;
  const opts = ctx.opts;

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  const finishBtn = $<HTMLButtonElement>('rp9-finish');
  // W92 — bouton « Annuler le dernier point » : visible pendant le tracé (≥1 coin, non fermé).
  const undoPointBtn = $<HTMLButtonElement>('rp9-undo-point');
  const searchForm = $<HTMLFormElement>('rp9-search');
  const addressEl = $<HTMLInputElement>('rp9-address');
  // W93 — liste de suggestions (combobox). Peut être null (harness jsdom partiel).
  const suggestionsEl = $<HTMLUListElement>('rp9-suggestions');

  function redrawTrace() {
    srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: ctx.vertices }, properties: {} } as never);
    // W92 — chaque sommet porte son index `idx` : le hit-test du glissé-sommet sait quel
    // `ctx.vertices[i]` déplacer (parité avec le glissé d'obstacle).
    srcOf('rp9-pts')?.setData({ type: 'FeatureCollection', features: ctx.vertices.map((v, idx) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: { idx } })) } as never);
    if (finishBtn) finishBtn.disabled = ctx.vertices.length < 3 || ctx.closed;
    // W92 — « Annuler le dernier point » : seulement pendant le tracé (au moins un coin posé).
    if (undoPointBtn) undoPointBtn.hidden = ctx.closed || ctx.vertices.length < 1;
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

  // W92 — retire le DERNIER sommet posé pendant le tracé (avant fermeture). N'agit pas une
  // fois le toit fermé (le glissé-sommet édite alors les coins). Re-dessine + remet à jour
  // le statut/les boutons via redrawTrace.
  function undoLastPoint() {
    if (ctx.closed || ctx.vertices.length === 0) return;
    ctx.vertices.pop();
    redrawTrace();
    if (ctx.vertices.length === 0) setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et lancer le calcul.');
    else if (ctx.vertices.length >= 3) setStatus('Double-cliquez (ou « Terminer ») pour fermer le toit et lancer le calcul.');
    else setStatus(`Dernier point annulé — ${ctx.vertices.length} coin(s) restant(s). Continuez le tracé.`);
  }
  undoPointBtn?.addEventListener('click', undoLastPoint);

  // ═══════════ W93 — AUTOCOMPLÉTION D'ADRESSE (combobox WAI-ARIA) ═══════════
  // Une suggestion MapTiler retenue (libellé affiché + coordonnées de vol).
  interface GeoSuggestion {
    label: string;
    center: [number, number];
  }
  let suggestions: GeoSuggestion[] = [];
  let activeIdx = -1; // index survolé au clavier (aria-activedescendant)

  /** Vole vers une adresse (sélection) — respecte reduced-motion. */
  function flyToCenter(center: [number, number]) {
    const target = { center, zoom: 19, pitch: 0 } as const;
    if (opts.reducedMotion) map.jumpTo(target);
    else map.flyTo({ ...target, essential: true });
    setStatus('Cliquez les coins de votre toit. Double-cliquez pour fermer et lancer le calcul.');
  }

  /** Ferme la liste de suggestions et réinitialise l'état combobox/aria. */
  function closeSuggestions() {
    suggestions = [];
    activeIdx = -1;
    if (suggestionsEl) {
      suggestionsEl.innerHTML = '';
      suggestionsEl.hidden = true;
    }
    addressEl?.setAttribute('aria-expanded', 'false');
    addressEl?.removeAttribute('aria-activedescendant');
  }

  /** Sélectionne la suggestion `i` : vole à son centre, remplit le champ, ferme la liste. */
  function selectSuggestion(i: number) {
    const s = suggestions[i];
    if (!s) return;
    if (addressEl) addressEl.value = s.label;
    flyToCenter(s.center);
    closeSuggestions();
  }

  /** (Re)peint la liste + met à jour la sélection clavier (aria-activedescendant). */
  function renderSuggestions() {
    if (!suggestionsEl) return;
    if (suggestions.length === 0) {
      closeSuggestions();
      return;
    }
    suggestionsEl.innerHTML = '';
    suggestions.forEach((s, i) => {
      const li = document.createElement('li');
      li.id = `rp9-suggestion-${i}`;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', String(i === activeIdx));
      li.textContent = s.label;
      li.className =
        'cursor-pointer px-3 py-2.5 text-sm text-lune-soft' +
        (i === activeIdx ? ' bg-brass-400/20 text-white' : ' hover:bg-white/10');
      // mousedown (pas click) : se déclenche AVANT le blur du champ → la liste ne se
      // ferme pas avant la sélection.
      li.addEventListener('mousedown', (ev) => {
        ev.preventDefault();
        selectSuggestion(i);
      });
      suggestionsEl.appendChild(li);
    });
    suggestionsEl.hidden = false;
    addressEl?.setAttribute('aria-expanded', 'true');
    if (activeIdx >= 0) addressEl?.setAttribute('aria-activedescendant', `rp9-suggestion-${activeIdx}`);
    else addressEl?.removeAttribute('aria-activedescendant');
  }

  // W75 — jeton + AbortController anti-course : deux recherches concurrentes ne peuvent
  // plus « gagner » dans le désordre. Chaque appel incrémente geoToken, annule la requête
  // précédente, et ignore sa réponse si un appel plus récent est parti entre-temps.
  let geoToken = 0;
  let geoAbort: AbortController | null = null;
  // W93 — geocode RÉCUPÈRE jusqu'à 5 suggestions et peuple la liste ; il ne VOLE plus de
  // lui-même (sauf `autoSelect`, utilisé pour l'`initialQuery` programmatique). Le vol n'a
  // lieu QUE sur sélection (clic / Entrée), garde anti-course W75 conservée.
  async function geocode(query: string, autoSelect = false) {
    const myToken = ++geoToken;
    geoAbort?.abort();
    const ctrl = new AbortController();
    geoAbort = ctrl;
    setStatus('Recherche de l’adresse…');
    try {
      const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json?key=${encodeURIComponent(opts.maptilerKey)}&country=ma&limit=5&language=fr`;
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) throw new Error('geocode');
      const data = (await res.json()) as {
        features?: Array<{ center?: [number, number]; place_name?: string; text?: string }>;
      };
      if (myToken !== geoToken) return; // une recherche plus récente l'a emporté
      suggestions = (data.features ?? [])
        .filter((f): f is { center: [number, number]; place_name?: string; text?: string } => Array.isArray(f.center) && f.center.length === 2)
        .slice(0, 5)
        .map((f) => ({ label: f.place_name || f.text || query, center: f.center }));
      activeIdx = -1;
      if (suggestions.length === 0) {
        closeSuggestions();
        setStatus('Adresse introuvable. Précisez la ville ou déplacez la carte à la main.');
        return;
      }
      if (autoSelect) {
        // appel programmatique (initialQuery) : on vole directement au 1ᵉʳ résultat.
        selectSuggestion(0);
        return;
      }
      renderSuggestions();
      setStatus('Choisissez votre adresse dans la liste, puis cliquez les coins de votre toit.');
    } catch (err) {
      if ((err as Error)?.name === 'AbortError' || myToken !== geoToken) return; // annulée / périmée
      closeSuggestions();
      setStatus('Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.');
    }
  }

  // W2 — GÉOCODAGE INVERSE : le repère (lng, lat) → libellé d'adresse. Réutilise la clé
  // MapTiler et le MÊME garde anti-course que `geocode` (jeton `revToken` distinct +
  // AbortController), plus un `opts.signal` externe optionnel (annulation par l'appelant
  // si un nouveau repère est posé avant la fin). Endpoint reverse MapTiler :
  // /geocoding/{lng},{lat}.json — language=fr, country=ma. Retourne le meilleur
  // `place_name` (premier feature) ou null. NE LÈVE JAMAIS (parité avec geocode).
  let revToken = 0;
  let revAbort: AbortController | null = null;
  async function reverseGeocode(lng: number, lat: number, opts2: { signal?: AbortSignal } = {}): Promise<string | null> {
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
    const myToken = ++revToken;
    revAbort?.abort();
    const ctrl = new AbortController();
    revAbort = ctrl;
    // Si l'appelant fournit un signal, on relaie son abort vers notre contrôleur.
    opts2.signal?.addEventListener('abort', () => ctrl.abort(), { once: true });
    try {
      const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(lng)},${encodeURIComponent(lat)}.json?key=${encodeURIComponent(opts.maptilerKey)}&language=fr&country=ma`;
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) throw new Error('reverse-geocode');
      const data = (await res.json()) as { features?: Array<{ place_name?: string; text?: string }> };
      if (myToken !== revToken) return null; // un appel plus récent l'a emporté
      // Premier feature exploitable : on préfère son `place_name`, sinon son `text`.
      const best = (data.features ?? []).find(
        (f) => (typeof f.place_name === 'string' && f.place_name.length > 0) || (typeof f.text === 'string' && f.text.length > 0),
      );
      if (!best) return null;
      return best.place_name && best.place_name.length > 0 ? best.place_name : best.text ?? null;
    } catch {
      return null; // annulée / périmée / réseau : pas d'adresse, on n'écrase rien
    }
  }

  // W93 — saisie débouncée (~300 ms, comme le débounce billTimer) : peuple la liste au fil
  // de la frappe sans rafale de requêtes.
  let geoInputTimer: ReturnType<typeof setTimeout> | null = null;
  addressEl?.addEventListener('input', () => {
    const q = addressEl.value.trim();
    if (geoInputTimer != null) clearTimeout(geoInputTimer);
    if (q.length < 3) {
      closeSuggestions(); // trop court : pas de requête
      return;
    }
    geoInputTimer = setTimeout(() => {
      geoInputTimer = null;
      void geocode(q);
    }, 300);
  });

  // W93 — navigation clavier de la combobox : flèches déplacent la sélection,
  // Entrée valide, Échap ferme.
  addressEl?.addEventListener('keydown', (e) => {
    if (suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIdx = (activeIdx + 1) % suggestions.length;
      renderSuggestions();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIdx = (activeIdx - 1 + suggestions.length) % suggestions.length;
      renderSuggestions();
    } else if (e.key === 'Enter') {
      if (activeIdx >= 0) {
        e.preventDefault();
        selectSuggestion(activeIdx);
      }
    } else if (e.key === 'Escape') {
      closeSuggestions();
    }
  });
  // Fermer la liste quand le champ perd le focus (laisse le mousedown poser sa sélection).
  addressEl?.addEventListener('blur', () => {
    setTimeout(closeSuggestions, 100);
  });

  // W93 — soumission : valide la suggestion survolée, sinon la 1ᵉʳ disponible ; si la liste
  // est vide (Entrée avant toute frappe débouncée), lance une recherche auto-sélectionnée.
  searchForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (suggestions.length > 0) {
      selectSuggestion(activeIdx >= 0 ? activeIdx : 0);
      return;
    }
    const q = addressEl?.value.trim();
    if (!q) return;
    void geocode(q, true);
  });

  return { redrawTrace, addVertex, undoLastPoint, geocode, reverseGeocode };
}
