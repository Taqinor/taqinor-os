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
import { availableOptionalLayers, getOptionalLayer, optionalLayerSourceSpec } from '../../lib/roofConfig';
import { $ } from './dom';
import { type Ctx } from './context';
import { contraindreAngle, pointDepuisCap, PAS_ANGLE_DEG } from './snap';

/**
 * WJ41 — libellés/messages de statut de la carte/géocodeur, tous LOCALISABLES.
 * Définis ici (module feuille, sans dépendance vers captureBoot.ts — évite un
 * import circulaire) et réexportés par captureBoot.ts qui les consomme aussi.
 * Le boot complet (non-capture) reste inchangé : `opts.strings` est optionnel
 * et absent → replis FR ci-dessous (CAPTURE_STRINGS_FR), comportement identique
 * à avant WJ41 pour la page FR.
 */
export interface CaptureStrings {
  searchAddressThenPin: string;
  pinPlaced: string;
  outlineTraced: string;
  traceOutline: string;
  outlineCrosses: string;
  pointWouldCross: string;
  doubleClickToClose: string;
  cornerPlaced: (n: number) => string;
  lastPointUndone: (n: number) => string;
  /** Message initial du builder COMPLET (non-capture) : « cliquez les coins…
   *  double-cliquez pour fermer et lancer le calcul » (distinct du message
   *  capture-only `searchAddressThenPin`). */
  clickCornersToClose: string;
  searchingAddress: string;
  addressNotFound: string;
  chooseFromList: string;
  searchUnavailable: string;
}

/** Replis FR — texte OCTET POUR OCTET identique au comportement pré-WJ41. */
export const CAPTURE_STRINGS_FR: CaptureStrings = {
  searchAddressThenPin: 'Cherchez votre adresse, puis posez un repère sur votre toit.',
  pinPlaced: 'Repère posé. Vous pouvez l’ajuster, ou tracer le contour (facultatif), puis remplir vos coordonnées.',
  outlineTraced: 'Contour tracé. Remplissez vos coordonnées ci-dessous, puis envoyez.',
  traceOutline: 'Tracez le contour de votre toit. Double-cliquez pour fermer (facultatif).',
  outlineCrosses: 'Votre tracé se croise — corrigez-le (« Effacer ») avant de fermer.',
  pointWouldCross: 'Ce point croiserait votre tracé — placez-le ailleurs pour garder un contour simple.',
  doubleClickToClose: 'Double-cliquez (ou « Terminer ») pour fermer le toit et lancer le calcul.',
  cornerPlaced: (n) => `Coin ${n} placé — continuez à tracer le contour.`,
  lastPointUndone: (n) => `Dernier point annulé — ${n} coin(s) restant(s). Continuez le tracé.`,
  clickCornersToClose: 'Cliquez les coins de votre toit. Double-cliquez pour fermer et lancer le calcul.',
  searchingAddress: 'Recherche de l’adresse…',
  addressNotFound: 'Adresse introuvable. Précisez la ville ou déplacez la carte à la main.',
  chooseFromList: 'Choisissez votre adresse dans la liste, puis cliquez les coins de votre toit.',
  searchUnavailable: 'Recherche indisponible. Déplacez la carte à la main pour trouver votre toit.',
};


// ————————————————————————————————————————————————————————————————————————
// CAL49 — GÉOCODAGE DANS LE PAYS DU PROJET
//
// Les deux appels MapTiler forçaient `&country=ma` : une adresse française était
// mécaniquement introuvable. Le pays vient désormais du contexte (CAL47, section
// `imagerie` des réglages société) ; `ma` reste le REPLI quand le contexte est muet,
// donc le comportement marocain d'aujourd'hui est byte-identique. Le pays filtré est
// affiché à côté du champ de recherche, pour qu'un « adresse introuvable » soit
// compréhensible. Les gardes anti-course W75 (jeton + AbortController) sont intacts.
// ————————————————————————————————————————————————————————————————————————

/** Pays de géocodage par DÉFAUT, historique du builder (contexte muet). */
export const GEOCODE_DEFAULT_COUNTRY = 'ma';

/** Code pays ISO 3166-1 alpha-2 normalisé (minuscules), ou le repli `ma`. */
export function geocodeCountry(pays?: string | null): string {
  const c = (pays ?? '').trim().toLowerCase();
  return /^[a-z]{2}$/.test(c) ? c : GEOCODE_DEFAULT_COUNTRY;
}

/** URL de RECHERCHE d'adresse MapTiler, bornée au pays du projet. */
export function geocodeSearchUrl(query: string, key: string, pays?: string | null): string {
  return (
    `https://api.maptiler.com/geocoding/${encodeURIComponent(query)}.json` +
    `?key=${encodeURIComponent(key)}&country=${geocodeCountry(pays)}&limit=5&language=fr`
  );
}

/** URL de géocodage INVERSE MapTiler, bornée au même pays. */
export function geocodeReverseUrl(lng: number, lat: number, key: string, pays?: string | null): string {
  return (
    `https://api.maptiler.com/geocoding/${encodeURIComponent(lng)},${encodeURIComponent(lat)}.json` +
    `?key=${encodeURIComponent(key)}&language=fr&country=${geocodeCountry(pays)}`
  );
}

/** Mention affichée à côté du champ de recherche : « Recherche limitée au pays : FR ». */
export function geocodeCountryNote(pays?: string | null): string {
  return `Recherche limitée au pays : ${geocodeCountry(pays).toUpperCase()}`;
}


// ————————————————————————————————————————————————————————————————————————
// CAL103 — CALQUES EXPLICITES, ORDRE DE SUPERPOSITION DÉTERMINÉ
//
// Les couches s'allumaient par des bascules dispersées et l'ordre de rendu n'était
// que l'ordre d'ajout. `ORDRE_RENDU_CALQUES` fige la superposition, du FOND vers le
// DESSUS, et `MAPLIBRE_LAYERS_PAR_CALQUE` dit quelles couches MapLibre chaque calque
// pilote. Un calque dont aucune couche n'existe sur la carte est un no-op silencieux
// (mode capture, aperçu…), jamais une exception.
//
// Le panneau d'écran (`features/calepinage/PanneauCalques.jsx`) est la SEULE source
// d'intention ; ici on ne fait qu'appliquer. Les bascules historiques (tracé client,
// photo calée, carte d'accès solaire) continuent de fonctionner : elles pilotent les
// mêmes couches par leurs propres chemins.
// ————————————————————————————————————————————————————————————————————————

/** Identifiants de calques, DU FOND VERS LE DESSUS. Ordre = contrat, testé. */
export const ORDRE_RENDU_CALQUES: readonly string[] = [
  'imagerie',
  'cadastre',
  'photo',
  'plan',
  'trace_client',
  'obstacles',
  'zones',
  'panneaux',
  'ombres',
  'mesures',
];

/** Couches MapLibre pilotées par chaque calque. Les calques rendus hors MapLibre
 *  (panneaux et ombres vivent dans la couche WebGL de la scène 3D) n'en listent
 *  aucune : l'hôte les pilote par la scène, pas par la carte. */
export const MAPLIBRE_LAYERS_PAR_CALQUE: Readonly<Record<string, readonly string[]>> = {
  imagerie: [],
  cadastre: ['rp9-opt-cadastre'],
  photo: [],
  plan: [],
  trace_client: ['rp9-ref-contour-fill', 'rp9-ref-contour-line'],
  obstacles: ['rp9-obs', 'rp9-obs-outline', 'rp9-obs-label'],
  zones: ['rp9-zones', 'rp9-zones-outline', 'rp9-zones-label'],
  panneaux: [],
  ombres: [],
  mesures: ['rp9-mesure-line', 'rp9-mesure-label'],
};

/** Propriété d'opacité MapLibre selon le type de couche — `fill-opacity` sur un
 *  remplissage, `line-opacity` sur une ligne, etc. `null` = pas d'opacité pilotable. */
export function opacityPropFor(type: string | undefined): string | null {
  switch (type) {
    case 'fill':
      return 'fill-opacity';
    case 'line':
      return 'line-opacity';
    case 'symbol':
      return 'text-opacity';
    case 'raster':
      return 'raster-opacity';
    case 'circle':
      return 'circle-opacity';
    default:
      return null;
  }
}

// ————————————————————————————————————————————————————————————————————————
// CALX90 — SAISIE CLAVIER DE LA LONGUEUR ET DE L'ANGLE DU SEGMENT EN COURS
//
// Aucune entrée clavier ne posait ni ne cotait un sommet : `addVertex` n'était appelé que
// depuis le clic/tap de la carte, et la mesure n'existait qu'APRÈS coup (`mesureUi.ts`).
// Parité HelioScope (dimensions exactes tapées au clavier sur un Field Segment).
//
// RÈGLE DURE : les DEUX valeurs sont saisies, jamais l'une supposée à partir de l'autre.
// Un champ vide REFUSE la pose en NOMMANT le champ fautif (règle fondateur : l'erreur
// désigne le champ, jamais un « non enregistré » générique).
// ————————————————————————————————————————————————————————————————————————

/** Champ d'une saisie de segment — celui que l'erreur doit désigner. */
export type ChampSegment = 'longueur' | 'angle';

export type SaisieSegment =
  | { ok: true; distanceM: number; capDeg: number }
  | { ok: false; champ: ChampSegment; motif: string };

/** Nombre à la française (virgule décimale, espaces insécables tolérés). */
function nombreSaisi(s: string | null | undefined): number {
  return Number.parseFloat((s ?? '').replace(/\s/g, '').replace(',', '.'));
}

/**
 * CALX90 — lit le couple « longueur (m) / angle (° depuis le nord) ». Ne pose RIEN tant que
 * les deux ne sont pas saisis et valides : jamais un angle supposé, jamais une longueur de
 * repli. Le refus nomme le champ fautif ET donne le motif en clair.
 */
export function lireSaisieSegment(longueurBrute: string, angleBrut: string): SaisieSegment {
  if (!(longueurBrute ?? '').trim()) {
    return { ok: false, champ: 'longueur', motif: 'Longueur manquante — saisissez la longueur du côté, en mètres.' };
  }
  const distanceM = nombreSaisi(longueurBrute);
  if (!Number.isFinite(distanceM) || distanceM <= 0) {
    return { ok: false, champ: 'longueur', motif: 'Longueur invalide — saisissez un nombre de mètres supérieur à 0.' };
  }
  if (!(angleBrut ?? '').trim()) {
    return { ok: false, champ: 'angle', motif: 'Angle manquant — saisissez le cap du côté en degrés (0 = nord, 90 = est).' };
  }
  const capDeg = nombreSaisi(angleBrut);
  if (!Number.isFinite(capDeg)) {
    return { ok: false, champ: 'angle', motif: 'Angle invalide — saisissez un cap en degrés (0 = nord, 90 = est).' };
  }
  return { ok: true, distanceM, capDeg };
}

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
  /** CAL54 — allume/éteint un calque optionnel (cadastre…). PUREMENT VISUEL : aucune
   *  entrée de calcul n'est touchée. Renvoie false si le calque n'est pas proposable
   *  (non déclaré, ou hors de son pays). */
  setOptionalLayer: (id: string, visible: boolean) => boolean;
  /** CAL54 — identifiants des calques optionnels actuellement proposables. */
  optionalLayerIds: () => string[];
  /** CAL103 — applique visibilité + opacité d'un calque. Renvoie false si le calque
   *  n'existe pas dans l'ordre de rendu. Un calque sans couche MapLibre est un no-op. */
  setLayerState: (id: string, state: { visible: boolean; opacite?: number }) => boolean;
  addVertex: (v: LngLat) => void;
  /** W92 — retire le dernier sommet posé (pendant le tracé, avant fermeture). */
  undoLastPoint: () => void;
  /** CALX90 — pose le sommet coté au clavier (longueur + cap depuis le sommet précédent).
   *  Retourne false et n'ajoute RIEN quand un champ manque/est invalide, ou quand aucun
   *  sommet précédent n'existe : l'erreur est affichée sous le champ fautif. */
  poserSegmentSaisi: () => boolean;
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
  // WJ41 — `opts.strings` n'existe pas sur `InitOptions` (types.ts, hors
  // périmètre) : lu via cast local. Absent → CAPTURE_STRINGS_FR (rendu FR
  // inchangé, comportement pré-WJ41).
  const t = (opts as { strings?: CaptureStrings }).strings ?? CAPTURE_STRINGS_FR;

  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  const finishBtn = $<HTMLButtonElement>('rp9-finish');
  // W92 — bouton « Annuler le dernier point » : visible pendant le tracé (≥1 coin, non fermé).
  const undoPointBtn = $<HTMLButtonElement>('rp9-undo-point');
  const searchForm = $<HTMLFormElement>('rp9-search');
  const addressEl = $<HTMLInputElement>('rp9-address');
  // W93 — liste de suggestions (combobox). Peut être null (harness jsdom partiel).
  const suggestionsEl = $<HTMLUListElement>('rp9-suggestions');

  // CAL49 — pays du projet (réglages société CAL47) ; muet ⇒ repli `ma` historique.
  const projectCountry = (): string => geocodeCountry(opts.imagery?.pays);
  // CAL49 — le pays filtré est AFFICHÉ à côté du champ : « adresse introuvable » devient
  // lisible. La note est créée à côté du champ si l'hôte n'en fournit pas déjà une.
  ensureCountryNote();
  function ensureCountryNote() {
    if (!addressEl || typeof document.createElement !== 'function') return;
    let note = $('rp9-geocode-country');
    if (!note) {
      note = document.createElement('span');
      note.id = 'rp9-geocode-country';
      note.className = 'rp9-geocode-country text-xs opacity-70';
      addressEl.parentElement?.appendChild(note);
    }
    note.textContent = geocodeCountryNote(opts.imagery?.pays);
  }

  // CAL54 — CALQUES OPTIONNELS. Superposition raster PURE : on ajoute une source et une
  // couche raster au-dessus du fond, et rien d'autre. Aucun `ctx` n'est lu ni écrit, donc
  // ni le compte de modules ni la production ne peuvent bouger.
  const OPTIONAL_LAYER_PREFIX = 'rp9-opt-';
  function optionalLayerIds(): string[] {
    return availableOptionalLayers(opts.imagery).map((l) => l.id);
  }
  function setOptionalLayer(id: string, visible: boolean): boolean {
    const layer = getOptionalLayer(id);
    if (!layer) return false;
    if (!optionalLayerIds().includes(id)) return false;
    const key = `${OPTIONAL_LAYER_PREFIX}${id}`;
    if (!visible) {
      if (map.getLayer?.(key)) map.removeLayer(key);
      if (map.getSource?.(key)) map.removeSource(key);
      return true;
    }
    if (!map.getSource?.(key)) map.addSource(key, optionalLayerSourceSpec(layer) as never);
    if (!map.getLayer?.(key)) map.addLayer({ id: key, type: 'raster', source: key } as never);
    return true;
  }

  // CAL103 — application de l'état d'un calque sur la carte. Tout est défensif : une
  // couche absente (mode capture, style pas encore chargé) ne fait rien.
  function setLayerState(id: string, state: { visible: boolean; opacite?: number }): boolean {
    if (!ORDRE_RENDU_CALQUES.includes(id)) return false;
    for (const layerId of MAPLIBRE_LAYERS_PAR_CALQUE[id] ?? []) {
      const layer = map.getLayer?.(layerId) as { type?: string } | undefined;
      if (!layer) continue;
      try {
        map.setLayoutProperty(layerId, 'visibility', state.visible ? 'visible' : 'none');
        const prop = opacityPropFor(layer.type);
        if (prop && typeof state.opacite === 'number') map.setPaintProperty(layerId, prop, state.opacite);
      } catch {
        /* couche pas encore prête : rien à faire, l'appel suivant la trouvera */
      }
    }
    return true;
  }

  function redrawTrace() {
    srcOf('rp9-line')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: ctx.vertices }, properties: {} } as never);
    // W92 — chaque sommet porte son index `idx` : le hit-test du glissé-sommet sait quel
    // `ctx.vertices[i]` déplacer (parité avec le glissé d'obstacle).
    srcOf('rp9-pts')?.setData({ type: 'FeatureCollection', features: ctx.vertices.map((v, idx) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: { idx } })) } as never);
    if (finishBtn) finishBtn.disabled = ctx.vertices.length < 3 || ctx.closed;
    // W92 — « Annuler le dernier point » : seulement pendant le tracé (au moins un coin posé).
    if (undoPointBtn) undoPointBtn.hidden = ctx.closed || ctx.vertices.length < 1;
    syncCoteBox(); // CALX90 — la saisie cotée suit les mêmes conditions d'affichage
    updateAreaReadout();
  }

  // ————————————————————————————————————————————————————————————————————————
  // CALX89 — AIDES AU TRACÉ : puce « Angles droits » (magnétisme angulaire)
  //
  // Le constructeur crée LUI-MÊME ses contrôles quand la page hôte ne les fournit pas
  // (patron `obstaclesUi.ts` `ensureTypePicker` / `zones.ts` `ensureStatsTable`) : aucune
  // page n'a à être modifiée. La puce est ÉTEINTE par défaut — tant qu'on ne l'allume pas,
  // `appliquerAidesTrace` rend le point cliqué tel quel et le tracé est celui d'aujourd'hui,
  // point pour point. Alt maintenue désactive l'aide LE TEMPS D'UN POINT (échappatoire
  // standard des outils de dessin).
  // ————————————————————————————————————————————————————————————————————————
  const traceChipsEl = ensureTraceChips();
  function ensureTraceChips(): HTMLElement | null {
    const existing = $('rp9-trace-chips');
    if (existing) return existing;
    const anchor = finishBtn?.parentElement ?? undoPointBtn?.parentElement ?? searchForm?.parentElement ?? null;
    if (!anchor || typeof document.createElement !== 'function') return null;
    const box = document.createElement('div');
    box.id = 'rp9-trace-chips';
    box.className = 'rp9-trace-chips mt-2 flex flex-wrap items-center gap-2 text-xs';
    anchor.appendChild(box);
    return box;
  }

  /** CALX89 — la puce et son pas, créés dans le bandeau d'aides. */
  const angleChipEl = ensureAngleChip();
  const anglePasEl = $<HTMLSelectElement>('rp9-snap-angle-pas');
  function ensureAngleChip(): HTMLButtonElement | null {
    const existing = $<HTMLButtonElement>('rp9-snap-angle');
    if (existing) return existing;
    if (!traceChipsEl || typeof document.createElement !== 'function') return null;
    const wrap = document.createElement('span');
    wrap.className = 'rp9-snap-angle-row inline-flex items-center gap-1';
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.id = 'rp9-snap-angle';
    chip.className = 'rp9-btn';
    chip.textContent = 'Angles droits';
    chip.setAttribute('aria-pressed', 'false'); // ÉTEINTE par défaut
    chip.title = 'Cale chaque côté sur un multiple d’angle. Alt maintenue : un point libre.';
    const select = document.createElement('select');
    select.id = 'rp9-snap-angle-pas';
    select.className = 'rp9-input';
    select.setAttribute('aria-label', 'Pas d’angle');
    for (const pas of PAS_ANGLE_DEG) {
      const opt = document.createElement('option');
      opt.value = String(pas);
      opt.textContent = `${pas}°`;
      select.appendChild(opt);
    }
    wrap.appendChild(chip);
    wrap.appendChild(select);
    traceChipsEl.appendChild(wrap);
    return chip;
  }

  /** Alt maintenue : suspend l'aide le temps d'un point (jamais mémorisé). */
  let altEnfoncee = false;
  if (typeof document.addEventListener === 'function') {
    document.addEventListener('keydown', (e) => {
      if ((e as KeyboardEvent).key === 'Alt') altEnfoncee = true;
    });
    document.addEventListener('keyup', (e) => {
      if ((e as KeyboardEvent).key === 'Alt') altEnfoncee = false;
    });
    // Le focus peut partir pendant qu'Alt est enfoncée (Alt+Tab) : on ne garde jamais l'état.
    window.addEventListener?.('blur', () => {
      altEnfoncee = false;
    });
  }
  angleChipEl?.addEventListener('click', () => {
    const on = angleChipEl.getAttribute('aria-pressed') === 'true';
    angleChipEl.setAttribute('aria-pressed', String(!on));
    setStatus(
      !on
        ? `Angles droits : chaque côté se cale au multiple de ${pasAngleDeg() || 90}°. Maintenez Alt pour un point libre.`
        : 'Angles droits désactivés — les points se posent exactement où vous cliquez.',
    );
  });

  /** Pas d'angle ACTIF (°), ou 0 quand la puce est éteinte / Alt maintenue — 0 = aide neutre. */
  function pasAngleDeg(): number {
    if (angleChipEl?.getAttribute('aria-pressed') !== 'true') return 0;
    if (altEnfoncee) return 0;
    const v = Number.parseFloat(anglePasEl?.value ?? '');
    return Number.isFinite(v) && v > 0 ? v : 0;
  }

  /**
   * CALX89 — applique les aides au tracé au point cliqué. Toute aide éteinte ⇒ `v` est
   * rendu TEL QUEL (même référence), donc le tracé reste celui d'aujourd'hui.
   */
  function appliquerAidesTrace(v: LngLat): LngLat {
    const n = ctx.vertices.length;
    return contraindreAngle(ctx.vertices[n - 1], ctx.vertices[n - 2], v, pasAngleDeg());
  }

  function addVertex(v: LngLat) {
    if (ctx.closed) return;
    // CALX89 — le point cliqué passe d'abord par les AIDES AU TRACÉ (magnétisme angulaire).
    // Puce éteinte (ou Alt maintenue) ⇒ `v` revient tel quel, donc le tracé est identique à
    // celui d'aujourd'hui, point pour point.
    const p = appliquerAidesTrace(v);
    // W76 — refuse un point qui ferait CROISER le contour (nœud papillon). isSimplePolygon
    // traite l'anneau comme FERMÉ (dernier→premier), donc tester [...vertices, v] vérifie à
    // la fois la nouvelle arête et l'arête de fermeture implicite v→1ᵉʳ sommet. Un anneau
    // croisé fausse l'aire géodésique (la shoelace s'annule) et le pavage.
    if (ctx.vertices.length >= 3 && !isSimplePolygon([...ctx.vertices, p])) {
      setStatus(t.pointWouldCross);
      return;
    }
    ctx.vertices.push(p);
    redrawTrace();
    if (ctx.vertices.length >= 3) setStatus(t.doubleClickToClose);
    else setStatus(t.cornerPlaced(ctx.vertices.length));
  }

  // ————————————————————————————————————————————————————————————————————————
  // CALX90 — la saisie « longueur (m) / angle (°) », créée par le module s'il faut.
  // Visible seulement pendant le TRACÉ et dès qu'un sommet existe (il faut une origine) ;
  // Échap la ferme sans rien poser. Le refus s'affiche SOUS le champ fautif.
  // ————————————————————————————————————————————————————————————————————————
  const coteBoxEl = ensureCoteBox();
  function ensureCoteBox(): HTMLElement | null {
    const existing = $('rp9-cote');
    if (existing) return existing;
    if (!traceChipsEl || typeof document.createElement !== 'function') return null;
    const box = document.createElement('span');
    box.id = 'rp9-cote';
    box.className = 'rp9-cote inline-flex flex-wrap items-center gap-1';
    box.hidden = true;
    box.innerHTML =
      `<label class="inline-flex items-center gap-1" for="rp9-cote-longueur">Longueur (m)` +
      `<input type="text" id="rp9-cote-longueur" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<label class="inline-flex items-center gap-1" for="rp9-cote-angle">Angle (° / nord)` +
      `<input type="text" id="rp9-cote-angle" class="rp9-input w-20" inputmode="decimal" /></label>` +
      `<button type="button" id="rp9-cote-poser" class="rp9-btn">Poser le point</button>` +
      `<span id="rp9-cote-erreur" class="rp9-cote-erreur text-alert-300" role="alert" hidden></span>`;
    traceChipsEl.appendChild(box);
    return box;
  }
  const coteLongueurEl = $<HTMLInputElement>('rp9-cote-longueur');
  const coteAngleEl = $<HTMLInputElement>('rp9-cote-angle');
  const cotePoserBtn = $<HTMLButtonElement>('rp9-cote-poser');
  const coteErreurEl = $('rp9-cote-erreur');

  /** Affiche (ou efface) le refus SOUS le champ fautif et met le focus dessus. */
  function montrerRefusCote(refus: { champ: ChampSegment; motif: string } | null) {
    const champEl = refus?.champ === 'angle' ? coteAngleEl : coteLongueurEl;
    for (const el of [coteLongueurEl, coteAngleEl]) el?.removeAttribute('aria-invalid');
    if (!coteErreurEl) return;
    if (!refus) {
      coteErreurEl.textContent = '';
      coteErreurEl.hidden = true;
      return;
    }
    coteErreurEl.textContent = refus.motif;
    coteErreurEl.hidden = false;
    champEl?.setAttribute('aria-invalid', 'true');
    champEl?.focus?.();
  }

  /** Montre la saisie seulement quand elle a un sens (tracé ouvert, au moins un sommet). */
  function syncCoteBox() {
    if (coteBoxEl) coteBoxEl.hidden = ctx.closed || ctx.vertices.length < 1;
  }

  function poserSegmentSaisi(): boolean {
    const origine = ctx.vertices[ctx.vertices.length - 1];
    if (ctx.closed || !origine) {
      montrerRefusCote({ champ: 'longueur', motif: 'Posez d’abord un premier coin : la cote part du sommet précédent.' });
      return false;
    }
    const lu = lireSaisieSegment(coteLongueurEl?.value ?? '', coteAngleEl?.value ?? '');
    if (!lu.ok) {
      montrerRefusCote(lu);
      return false;
    }
    montrerRefusCote(null);
    const avant = ctx.vertices.length;
    // Un sommet coté au clavier est EXACT : il ne repasse pas par le magnétisme angulaire
    // (qui corrigerait la direction que l'utilisateur vient justement de taper).
    const p = pointDepuisCap(origine, lu.capDeg, lu.distanceM);
    if (ctx.vertices.length >= 3 && !isSimplePolygon([...ctx.vertices, p])) {
      montrerRefusCote({ champ: 'angle', motif: t.pointWouldCross });
      return false;
    }
    ctx.vertices.push(p);
    redrawTrace();
    if (ctx.vertices.length >= 3) setStatus(t.doubleClickToClose);
    else setStatus(t.cornerPlaced(ctx.vertices.length));
    if (coteLongueurEl) coteLongueurEl.value = '';
    if (coteAngleEl) coteAngleEl.value = '';
    coteLongueurEl?.focus?.();
    return ctx.vertices.length > avant;
  }

  cotePoserBtn?.addEventListener('click', () => {
    poserSegmentSaisi();
  });
  for (const el of [coteLongueurEl, coteAngleEl]) {
    el?.addEventListener('keydown', (e) => {
      const key = (e as KeyboardEvent).key;
      if (key === 'Enter') {
        e.preventDefault();
        poserSegmentSaisi();
      } else if (key === 'Escape') {
        // Échap ferme la saisie SANS RIEN POSER.
        e.preventDefault();
        if (coteLongueurEl) coteLongueurEl.value = '';
        if (coteAngleEl) coteAngleEl.value = '';
        montrerRefusCote(null);
        if (coteBoxEl) coteBoxEl.hidden = true;
        el.blur?.();
      }
    });
  }

  // W92 — retire le DERNIER sommet posé pendant le tracé (avant fermeture). N'agit pas une
  // fois le toit fermé (le glissé-sommet édite alors les coins). Re-dessine + remet à jour
  // le statut/les boutons via redrawTrace.
  function undoLastPoint() {
    if (ctx.closed || ctx.vertices.length === 0) return;
    ctx.vertices.pop();
    redrawTrace();
    if (ctx.vertices.length === 0) setStatus(t.clickCornersToClose);
    else if (ctx.vertices.length >= 3) setStatus(t.doubleClickToClose);
    else setStatus(t.lastPointUndone(ctx.vertices.length));
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
    setStatus(t.clickCornersToClose);
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
    setStatus(t.searchingAddress);
    try {
      // WJ41 — `language=fr` stays fixed regardless of page locale: Moroccan
      // addresses are indexed best in French in MapTiler/OSM, and changing the
      // returned address TEXT is a data-quality decision outside WJ41's scope
      // (system messages + placeholders), not a hardcoded UI string.
      const url = geocodeSearchUrl(query, opts.maptilerKey, projectCountry());
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
        setStatus(t.addressNotFound);
        return;
      }
      if (autoSelect) {
        // appel programmatique (initialQuery) : on vole directement au 1ᵉʳ résultat.
        selectSuggestion(0);
        return;
      }
      renderSuggestions();
      setStatus(t.chooseFromList);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError' || myToken !== geoToken) return; // annulée / périmée
      closeSuggestions();
      setStatus(t.searchUnavailable);
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
      const url = geocodeReverseUrl(lng, lat, opts.maptilerKey, projectCountry());
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

  return {
    redrawTrace,
    setOptionalLayer,
    optionalLayerIds,
    setLayerState,
    addVertex,
    undoLastPoint,
    poserSegmentSaisi,
    geocode,
    reverseGeocode,
  };
}
