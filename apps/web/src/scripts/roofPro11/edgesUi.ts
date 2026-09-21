/**
 * CALX94 — CORRECTION MANUELLE du type d'une arête de contour, depuis l'atelier.
 *
 * Jusqu'ici le type d'arête était DÉDUIT à chaque sérialisation (`edges.ts`) et rien ne
 * permettait de le corriger : le champ `manuel` du contrat existait, mais aucune interface
 * ne l'écrivait, et `serializeLayout` re-déduisait tout à chaque export — une correction
 * aurait été effacée. Ce module ajoute les deux moitiés qui manquaient :
 *  - un clic sur un segment du contour (mode « corriger une arête ») ouvre un sélecteur des
 *    SIX types, libellés en français, créé ICI si la page hôte ne le fournit pas (même
 *    patron que `obstaclesUi.ts` `ensureTypePicker` : aucune page à modifier) ;
 *  - le choix écrit `{ index, type, manuel: true }` dans `ctx.areas[].edges`, et
 *    `serializeLayout` (`prefill.ts`) superpose ces saisies à la déduction via
 *    `fusionnerAretesSaisies` — la correction voyage donc dans le document et survit à
 *    autant de sérialisations qu'on veut.
 *
 * Géométrie : le segment cliqué est celui dont la DISTANCE au point est la plus faible, en
 * mètres (projection ENU locale, même formule que le reste de roofPro11), et seulement si
 * elle est sous la tolérance de saisie ; sinon AUCUNE arête n'est choisie (on ne corrige
 * jamais une arête au hasard parce que le doigt a glissé).
 *
 * Ce module ne dessine RIEN en 3D : il expose `couleurArete` (lecture de
 * `EDGE_COLOR_BY_TYPE` sur le type RETENU, corrigé compris) pour que la scène colore le
 * segment. Crochet attendu : `scene3d.ts` — colorer chaque segment du contour avec
 * `edgesUi.couleurArete(i)`. Crochet attendu : `roof-tool-pro11.ts` — router le clic carte
 * vers `edgesUi.handleMapClick(lngLat)` et ne pas traiter ce clic comme un geste de tracé
 * quand `edgesUi.isEdgeMode()` est vrai (tant que ce crochet n'existe pas, le module
 * s'abonne lui-même au clic de la carte, mais UNIQUEMENT pendant que le mode est armé).
 *
 * CALX99 — PRENDRE L'AZIMUT D'UN PAN DEPUIS UNE ARÊTE CLIQUÉE (parité HelioScope, « Set
 * Azimuth to ___ »). Deuxième mode « clic sur arête », mutuellement exclusif avec le
 * précédent (armer l'un désarme l'autre — un seul geste de clic possible à la fois) : le
 * clic retient l'arête la plus proche (même `areteAuPoint`/même tolérance) et écrit
 * directement `ctx.facingAzimuthDeg` = cap de la normale sortante du segment
 * (`azimutNormaleArete`, `snap.ts`) + `ctx.facingManual = true` — le MÊME geste que les
 * boutons cardinaux de `roof-tool-pro11.ts:3226-3236` (override manuel PAR ZONE, qui gagne
 * ensuite sur `autoInferFacing`). Aucune étape de confirmation : contrairement à la
 * correction de type, un clic suffit. Crochet attendu : `roof-tool-pro11.ts` — quand
 * `deps.redraw` est câblé, le faire pointer vers la MÊME re-résolution qu'un clic sur un
 * bouton cardinal (`pitchedRecompute()` sur un pan en pente fermé), pour que le nouvel
 * azimut recalcule la pose 3D et pas seulement son affichage ; ce module ne peut pas
 * l'appeler lui-même (fonction privée de `roof-tool-pro11.ts`).
 */
import { type LngLat } from '../../lib/roof';
import { DEG2RAD, DEG2M } from './constants';
import { $ } from './dom';
import { type Ctx } from './context';
import {
  EDGE_COLOR_BY_TYPE,
  EDGE_TYPES,
  EDGE_TYPE_LABELS,
  deduceEdgeDetails,
  isEdgeType,
  type EdgeDeductionZone,
  type EdgeType,
  type SerializedEdge,
} from './edges';
import { azimutNormaleArete } from './snap';
import { type AreaRecord } from './types';

/** CALX94 — convention de dessin (tolérance de POINTAGE, aucune portée d'ingénierie) :
 *  au-delà de 2 m du segment le plus proche, le clic n'a visé aucune arête et rien n'est
 *  sélectionné. N'entre dans aucun calcul de production ni de surface posable. */
export const EDGE_PICK_TOL_M = 2;

/** La part de la carte dont ce module a besoin : s'abonner/se désabonner du clic. Typé
 *  structurellement pour que le module reste testable sans MapLibre. */
export interface EdgeMapLike {
  on: (type: 'click', handler: (e: { lngLat: { lng: number; lat: number } }) => void) => void;
  off: (type: 'click', handler: (e: { lngLat: { lng: number; lat: number } }) => void) => void;
}

/** Dépendances injectées (toutes optionnelles : le module fonctionne sans page hôte). */
export interface EdgesUiDeps {
  /** La carte, pour armer le clic pendant le mode « corriger une arête » ou « prendre
   *  l'azimut ». */
  map?: EdgeMapLike | null;
  /** Re-dessin (contour 2D + scène 3D) après une correction de type OU une prise d'azimut
   *  (CALX99). */
  redraw?: () => void;
  /** Bandeau de statut de l'atelier. */
  setStatus?: (msg: string) => void;
  /** Élément où accrocher les contrôles créés ici (défaut : `#rp9-edges-host`, sinon la
   *  fenêtre « Plusieurs zones »). Absent des deux côtés ⇒ aucun contrôle n'est créé et le
   *  module reste pilotable par son API. */
  anchor?: HTMLElement | null;
}

export interface EdgesUi {
  /** Arme/désarme le mode « corriger une arête » (le clic carte y sélectionne un segment). */
  setEdgeMode: (on: boolean) => void;
  isEdgeMode: () => boolean;
  /** CALX99 — arme/désarme le mode « prendre l'azimut d'une arête » : un clic y écrit
   *  directement l'azimut du pan actif (aucune sélection persistée, contrairement au mode
   *  de correction de type). Mutuellement exclusif avec `setEdgeMode` : armer celui-ci
   *  désarme l'autre. */
  setAzimuthMode: (on: boolean) => void;
  isAzimuthMode: () => boolean;
  /** Traite un clic carte : selon le mode armé, sélectionne l'arête la plus proche (mode
   *  type) ou lui prend directement son azimut (mode azimut). `true` si le clic a été traité
   *  (l'appelant peut alors ignorer son propre traitement du clic). */
  handleMapClick: (lngLat: LngLat) => boolean;
  /** Arête sélectionnée (rang du segment) ou null. */
  selectedEdge: () => number | null;
  selectEdge: (index: number | null) => void;
  /** Écrit le type CORRIGÉ de l'arête `index` sur la zone active (`manuel: true`). */
  setEdgeType: (index: number, type: EdgeType) => void;
  /** Type RETENU pour le segment `index` : le type corrigé s'il existe, sinon le type
   *  déduit, sinon 'inconnue' (contour trop court / zone absente). */
  typeArete: (index: number) => EdgeType;
  /** Couleur 3D du segment `index` (hex Three.js), suivant le type RETENU. */
  couleurArete: (index: number) => number;
  /** Re-remplit le sélecteur depuis l'état courant (après un chargement de document). */
  refresh: () => void;
  /** Désabonne le clic carte (fin de vie du module). */
  destroy: () => void;
}

/** Projection ENU (m) autour d'une origine — même formule que `edges.ts`/`scene3d.ts`. */
function toEnu(ring: readonly LngLat[], origin: LngLat): [number, number][] {
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  return ring.map(([lng, lat]) => [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M]);
}

/** Distance (m) d'un point à un segment, en ENU. */
function distPointSegM(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return Math.hypot(p[0] - a[0], p[1] - a[1]);
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/**
 * CALX94 — rang du segment de `vertices` le plus proche de `point`, ou `null` si le contour
 * a moins de 3 sommets ou si le plus proche est au-delà de `tolM`. Fonction PURE : c'est la
 * seule géométrie du clic, et elle ne choisit jamais « par défaut » un segment lointain.
 */
export function areteAuPoint(
  vertices: readonly LngLat[],
  point: LngLat,
  tolM: number = EDGE_PICK_TOL_M,
): number | null {
  const n = vertices.length;
  if (n < 3) return null;
  const enu = toEnu(vertices, vertices[0]);
  const p = toEnu([point], vertices[0])[0];
  let best = -1;
  let bestD = Infinity;
  for (let i = 0; i < n; i++) {
    const d = distPointSegM(p, enu[i], enu[(i + 1) % n]);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  return best >= 0 && bestD <= tolM ? best : null;
}

export function createEdgesUi(ctx: Ctx, deps: EdgesUiDeps = {}): EdgesUi {
  const { map = null, redraw, setStatus } = deps;
  let edgeMode = false;
  let selected: number | null = null;
  // CALX99 — deuxième mode « clic sur arête », mutuellement exclusif avec `edgeMode`.
  let azimuthMode = false;
  let mapSubscribed = false;
  /** Dernier azimut pris (pour le lire dans le panneau) — remis à zéro à chaque
   *  désarmement du mode, jamais persisté ailleurs que dans `ctx`/le document. */
  let lastAzimuth: { index: number; azimutDeg: number } | null = null;

  /** Contour EFFECTIF de la zone active : l'état d'édition vivant s'il existe, sinon le
   *  contour figé de l'enregistrement (même règle que `serializeLayout`). */
  function contourActif(): LngLat[] {
    if (ctx.vertices && ctx.vertices.length >= 3) return ctx.vertices;
    return ctx.activeArea()?.vertices ?? [];
  }

  /** Types DÉDUITS de la zone active (pour afficher ce que la machine, elle, propose).
   *  Les voisins sont les autres zones — mêmes valeurs que la sérialisation. */
  function deduits(): SerializedEdge[] {
    const active = ctx.activeArea();
    if (!active) return [];
    const ring = contourActif();
    if (ring.length < 3) return [];
    const zoneOf = (a: AreaRecord, v?: LngLat[]): EdgeDeductionZone => ({
      vertices: v ?? a.vertices,
      roofType: a.roofType,
      facingAzimuthDeg: a.facingAzimuthDeg,
      ...(Number.isFinite(a.pitchDeg) ? { pitchDeg: a.pitchDeg } : {}),
    });
    const others = ctx.areas.filter((a) => a.id !== active.id).map((a) => zoneOf(a));
    return deduceEdgeDetails(zoneOf(active, ring), others).map(({ index, type }) => ({ index, type }));
  }

  /** Saisie existante pour le segment `index` sur la zone active, ou undefined. */
  function saisie(index: number): SerializedEdge | undefined {
    return ctx.activeArea()?.edges?.find((e) => e.index === index);
  }

  function typeArete(index: number): EdgeType {
    const s = saisie(index);
    if (s && s.manuel === true && isEdgeType(s.type)) return s.type;
    const d = deduits().find((e) => e.index === index);
    return d ? d.type : 'inconnue';
  }

  function couleurArete(index: number): number {
    return EDGE_COLOR_BY_TYPE[typeArete(index)];
  }

  function setEdgeType(index: number, type: EdgeType) {
    const active = ctx.activeArea();
    if (!active) return;
    if (!isEdgeType(type)) {
      showError(`Type d’arête inconnu — le champ « Type d’arête » n’a pas été modifié.`);
      return;
    }
    const ring = contourActif();
    if (!Number.isInteger(index) || index < 0 || index >= ring.length) {
      showError('Ce segment n’existe plus dans le contour — la correction n’a pas été enregistrée.');
      return;
    }
    ctx.pushWorkshopHistory?.();
    const edges = active.edges ? [...active.edges] : [];
    const at = edges.findIndex((e) => e.index === index);
    const precedent = at >= 0 ? edges[at] : undefined;
    const entree: SerializedEdge = {
      index,
      type,
      manuel: true,
      // Le retrait saisi de CETTE arête (CALX81/CALX95) n'est pas touché par une correction
      // de TYPE : ce sont deux saisies indépendantes.
      ...(precedent && typeof precedent.retraitM === 'number' && Number.isFinite(precedent.retraitM)
        ? { retraitM: precedent.retraitM }
        : {}),
    };
    if (at >= 0) edges[at] = entree;
    else edges.push(entree);
    edges.sort((a, b) => a.index - b.index);
    active.edges = edges;
    showError(null);
    setStatus?.(`Arête nº${index + 1} : ${EDGE_TYPE_LABELS[type]} (corrigé à la main).`);
    refresh();
    redraw?.();
  }

  // ─────────── Contrôles DOM créés ICI si la page ne les fournit pas ───────────
  const anchor = deps.anchor ?? $('rp9-edges-host') ?? ctx.dom.areasWindowEl ?? null;
  const panel = ensurePanel();
  const modeBtn = panel ? $<HTMLButtonElement>('rp9-edge-mode') : null;
  const azimuthBtn = panel ? $<HTMLButtonElement>('rp9-edge-azimuth-mode') : null;
  const select = panel ? $<HTMLSelectElement>('rp9-edge-type') : null;
  const infoEl = panel ? $('rp9-edge-info') : null;
  const errorEl = panel ? $('rp9-edge-error') : null;

  function ensurePanel(): HTMLElement | null {
    const existing = $('rp9-edge-panel');
    if (existing) return existing;
    if (!anchor || typeof document.createElement !== 'function') return null;
    const el = document.createElement('div');
    el.id = 'rp9-edge-panel';
    el.className = 'rp9-edge-panel mt-2';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'rp9-edge-mode';
    btn.className = 'rp9-btn';
    btn.textContent = 'Corriger le type d’une arête';
    el.appendChild(btn);
    // CALX99 — deuxième geste : prendre l'azimut du pan depuis une arête cliquée.
    const btnAzimuth = document.createElement('button');
    btnAzimuth.type = 'button';
    btnAzimuth.id = 'rp9-edge-azimuth-mode';
    btnAzimuth.className = 'rp9-btn';
    btnAzimuth.textContent = 'Prendre l’azimut du pan sur une arête';
    el.appendChild(btnAzimuth);
    const label = document.createElement('label');
    label.className = 'rp9-edge-type-row';
    label.setAttribute('for', 'rp9-edge-type');
    label.textContent = 'Type d’arête ';
    const sel = document.createElement('select');
    sel.id = 'rp9-edge-type';
    sel.className = 'rp9-input';
    for (const t of EDGE_TYPES) {
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = EDGE_TYPE_LABELS[t];
      sel.appendChild(opt);
    }
    label.appendChild(sel);
    el.appendChild(label);
    const info = document.createElement('p');
    info.id = 'rp9-edge-info';
    info.className = 'rp9-edge-info';
    el.appendChild(info);
    // Règle maison : un refus s'affiche SOUS le champ fautif et le NOMME.
    const err = document.createElement('p');
    err.id = 'rp9-edge-error';
    err.className = 'rp9-edge-error';
    err.hidden = true;
    el.appendChild(err);
    anchor.appendChild(el);
    return el;
  }

  function showError(msg: string | null) {
    if (!errorEl) return;
    errorEl.textContent = msg ?? '';
    errorEl.hidden = !msg;
  }

  function refresh() {
    if (panel) panel.setAttribute('data-mode', edgeMode ? 'on' : azimuthMode ? 'azimuth' : 'off');
    if (modeBtn) modeBtn.setAttribute('aria-pressed', edgeMode ? 'true' : 'false');
    if (azimuthBtn) azimuthBtn.setAttribute('aria-pressed', azimuthMode ? 'true' : 'false');
    if (select) select.disabled = selected === null;
    // CALX99 — le mode azimut n'a pas de sélection persistée : un clic écrit directement
    // l'azimut du pan actif. Le panneau affiche seulement la consigne, puis le résultat du
    // dernier clic pris (jusqu'au désarmement du mode).
    if (azimuthMode) {
      if (infoEl) {
        infoEl.textContent = lastAzimuth
          ? `Azimut pris depuis l’arête nº${lastAzimuth.index + 1} : ${Math.round(lastAzimuth.azimutDeg)}° (réglage manuel du pan).`
          : 'Cliquez un segment du contour pour en prendre l’azimut (perpendiculaire sortante).';
      }
      return;
    }
    if (selected === null) {
      if (infoEl) {
        infoEl.textContent = edgeMode
          ? 'Cliquez un segment du contour pour corriger son type.'
          : 'Aucune arête sélectionnée.';
      }
      return;
    }
    const retenu = typeArete(selected);
    if (select) select.value = retenu;
    if (infoEl) {
      const s = saisie(selected);
      const deduit = deduits().find((e) => e.index === selected);
      const origine =
        s && s.manuel === true
          ? 'corrigé à la main'
          : deduit
            ? 'déduit du tracé'
            : 'non déduit';
      infoEl.textContent = `Arête nº${selected + 1} — ${EDGE_TYPE_LABELS[retenu]} (${origine}).`;
    }
  }

  function selectEdge(index: number | null) {
    const ring = contourActif();
    selected = index !== null && Number.isInteger(index) && index >= 0 && index < ring.length ? index : null;
    showError(null);
    refresh();
  }

  /**
   * CALX99 — prend l'azimut du pan actif depuis l'arête la plus proche du clic : écrit
   * `ctx.facingAzimuthDeg`/`ctx.facingManual` (le MÊME override par zone que les boutons
   * cardinaux) et, quand une zone est déjà enregistrée, persiste `facingManual` dessus
   * (même geste que `roof-tool-pro11.ts:3236` — la valeur d'azimut elle-même reste lue
   * LIVE depuis `ctx` pour la zone active, `prefill.ts` le fait déjà). Aucun azimut n'est
   * posé quand le clic ne vise aucune arête ou que le segment est dégénéré.
   */
  function handleAzimuthClick(lngLat: LngLat): boolean {
    const ring = contourActif();
    const idx = areteAuPoint(ring, lngLat);
    if (idx === null) {
      setStatus?.('Aucune arête sous le clic — visez un segment du contour pour en prendre l’azimut.');
      return false;
    }
    const azimutDeg = azimutNormaleArete(ring[idx], ring[(idx + 1) % ring.length]);
    if (!Number.isFinite(azimutDeg)) {
      setStatus?.('Arête dégénérée — aucun azimut n’en a été tiré.');
      return false;
    }
    ctx.pushWorkshopHistory?.();
    ctx.facingAzimuthDeg = azimutDeg;
    ctx.facingManual = true;
    const active = ctx.activeArea();
    if (active) active.facingManual = true; // même geste que les boutons cardinaux
    lastAzimuth = { index: idx, azimutDeg };
    setStatus?.(`Azimut pris depuis l’arête nº${idx + 1} : ${Math.round(azimutDeg)}° (réglage manuel du pan).`);
    refresh();
    redraw?.();
    return true;
  }

  function handleMapClick(lngLat: LngLat): boolean {
    if (azimuthMode) return handleAzimuthClick(lngLat);
    if (!edgeMode) return false;
    const idx = areteAuPoint(contourActif(), lngLat);
    if (idx === null) {
      selectEdge(null);
      setStatus?.('Aucune arête sous le clic — visez un segment du contour.');
      return false;
    }
    selectEdge(idx);
    return true;
  }

  const onMapClick = (e: { lngLat: { lng: number; lat: number } }) => {
    handleMapClick([e.lngLat.lng, e.lngLat.lat]);
  };

  /** Le clic carte n'est capté QUE pendant l'un des deux modes : hors des deux, le
   *  dispatcher de tracé de `roof-tool-pro11.ts` garde exactement son comportement
   *  d'aujourd'hui. Un seul abonnement, partagé par les deux modes. */
  function syncMapSubscription() {
    const veut = edgeMode || azimuthMode;
    if (veut === mapSubscribed) return;
    mapSubscribed = veut;
    if (!map) return;
    if (veut) map.on('click', onMapClick);
    else map.off('click', onMapClick);
  }

  function setEdgeMode(on: boolean) {
    if (on === edgeMode) {
      refresh();
      return;
    }
    edgeMode = on;
    // CALX99 — un seul mode « clic sur arête » à la fois : armer celui-ci désarme l'autre.
    if (on && azimuthMode) {
      azimuthMode = false;
      lastAzimuth = null;
    }
    syncMapSubscription();
    if (!on) selected = null;
    refresh();
  }

  function setAzimuthMode(on: boolean) {
    if (on === azimuthMode) {
      refresh();
      return;
    }
    azimuthMode = on;
    if (on && edgeMode) {
      edgeMode = false;
      selected = null;
    }
    if (!on) lastAzimuth = null;
    syncMapSubscription();
    refresh();
  }

  modeBtn?.addEventListener('click', () => setEdgeMode(!edgeMode));
  azimuthBtn?.addEventListener('click', () => setAzimuthMode(!azimuthMode));
  select?.addEventListener('change', () => {
    if (selected === null) return;
    const v = select.value;
    if (!isEdgeType(v)) {
      showError('Type d’arête non reconnu — le champ « Type d’arête » n’a pas été enregistré.');
      return;
    }
    setEdgeType(selected, v);
  });

  refresh();

  return {
    setEdgeMode,
    isEdgeMode: () => edgeMode,
    setAzimuthMode,
    isAzimuthMode: () => azimuthMode,
    handleMapClick,
    selectedEdge: () => selected,
    selectEdge,
    setEdgeType,
    typeArete,
    couleurArete,
    refresh,
    destroy: () => {
      if (map && mapSubscribed) map.off('click', onMapClick);
      edgeMode = false;
      azimuthMode = false;
      mapSubscribed = false;
    },
  };
}
