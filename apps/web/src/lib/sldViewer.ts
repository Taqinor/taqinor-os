/**
 * WJ129 — Visionneuse plein écran du schéma électrique (SLD) : géométrie PURE
 * du pan/zoom/pinch, aucune bibliothèque, aucun DOM. La page
 * /proposition/[token] (section « Schéma électrique ») branche ces fonctions
 * sur des écouteurs Pointer Events/wheel — voir le <script> qui suit la
 * section `#sld` dans [token].astro. Tout est déterministe et testable sous
 * vitest sans jsdom : viewport/contenu/points sont de simples nombres, jamais
 * des éléments DOM.
 *
 * Le schéma backend (`sld_svg`, apps/ventes/single_line_diagram.py côté
 * serveur) n'a pas de viewBox FIXE d'une avance connue (le nombre de
 * composants varie par devis) — ces fonctions prennent donc TOUJOURS la
 * taille du contenu en paramètre (lue au runtime sur le SVG réel via
 * `parseViewBoxSize`), jamais une constante codée en dur.
 */

/** Une dimension (viewport ou contenu), en pixels CSS. */
export interface Size {
  width: number;
  height: number;
}

/** Un point (curseur, doigt, translation), en pixels CSS. */
export interface Point {
  x: number;
  y: number;
}

/** Limites d'échelle de la visionneuse — 0.5× à 5×, comme demandé. */
export const SLD_MIN_SCALE = 0.5;
export const SLD_MAX_SCALE = 5;

/** Facteur de zoom appliqué par un double-tap/double-clic (zoom ×2 depuis le fit). */
export const SLD_DOUBLE_TAP_ZOOM = 2;

/** Borne `value` entre `min` et `max` (jamais NaN en sortie : repli sur `min`). */
export function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

/**
 * Échelle « contain » : le plus grand facteur qui fait tenir ENTIÈREMENT le
 * contenu dans le viewport (ni débordement en largeur, ni en hauteur) — le
 * départ de la visionneuse (« fit-to-width/height »). Entrées invalides
 * (viewport ou contenu nul/négatif) → repli 1 (jamais NaN/Infinity).
 */
export function fitScale(viewport: Size, content: Size): number {
  if (!(viewport.width > 0) || !(viewport.height > 0) || !(content.width > 0) || !(content.height > 0)) {
    return 1;
  }
  return Math.min(viewport.width / content.width, viewport.height / content.height);
}

/** Translation qui centre le contenu (à `scale`) dans le viewport. */
export function centeredTranslate(viewport: Size, content: Size, scale: number): Point {
  const w = content.width * scale;
  const h = content.height * scale;
  return { x: (viewport.width - w) / 2, y: (viewport.height - h) / 2 };
}

/** Distance euclidienne entre deux points (ex. les deux doigts d'un pincement). */
export function pointDistance(a: Point, b: Point): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

/** Point médian entre deux points (centre du pincement). */
export function pointMidpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/**
 * Nouvelle échelle pendant un pincement à deux doigts : le ratio de la
 * distance courante sur la distance de départ, appliqué à l'échelle de
 * départ, borné aux limites. Distance de départ ou courante invalide
 * (÷0, capteur qui glisse) → renvoie l'échelle de départ inchangée (bornée)
 * plutôt qu'un saut incohérent.
 */
export function pinchScale(
  startScale: number,
  startDistance: number,
  currentDistance: number,
  min: number = SLD_MIN_SCALE,
  max: number = SLD_MAX_SCALE,
): number {
  if (!(startDistance > 0) || !(currentDistance > 0)) return clamp(startScale, min, max);
  return clamp(startScale * (currentDistance / startDistance), min, max);
}

/**
 * Calcule la translation à appliquer pour qu'un `anchor` (point de l'écran —
 * curseur, milieu du pincement, point du double-tap) reste visuellement
 * IMMOBILE quand l'échelle passe de `scale` à `newScale`. Formule standard
 * « zoom au point » : on retrouve le point du contenu sous l'ancre à
 * l'ancienne échelle, puis on repositionne ce même point du contenu sous
 * l'ancre à la nouvelle échelle. Réutilisée pour la molette, le pincement ET
 * le double-tap — un seul calcul, trois déclencheurs.
 */
export function zoomAtPoint(translate: Point, scale: number, newScale: number, anchor: Point): Point {
  if (!(scale > 0)) return translate;
  const contentX = (anchor.x - translate.x) / scale;
  const contentY = (anchor.y - translate.y) / scale;
  return {
    x: anchor.x - contentX * newScale,
    y: anchor.y - contentY * newScale,
  };
}

/**
 * Bascule d'échelle d'un double-tap/double-clic : proche du fit → zoom ×2
 * (borné) ; déjà zoomé (quel que soit le niveau) → retour au fit. `epsilon`
 * absorbe les imprécisions flottantes d'un fit calculé dynamiquement.
 */
export function doubleTapScale(
  currentScale: number,
  fitScaleValue: number,
  zoomFactor: number = SLD_DOUBLE_TAP_ZOOM,
  min: number = SLD_MIN_SCALE,
  max: number = SLD_MAX_SCALE,
  epsilon: number = 0.02,
): number {
  const nearFit = Math.abs(currentScale - fitScaleValue) <= epsilon;
  return nearFit ? clamp(fitScaleValue * zoomFactor, min, max) : fitScaleValue;
}

/**
 * Borne UN axe de translation pour que le contenu mis à l'échelle ne quitte
 * jamais totalement le viewport : contenu plus petit que le viewport → centré
 * (pas de marge de pan, rien à explorer) ; contenu plus grand → la
 * translation reste entre `viewport - contenu` (bord loin visible) et `0`
 * (bord proche visible), jamais au-delà.
 */
export function clampPanAxis(translateAxis: number, viewportSize: number, scaledContentSize: number): number {
  if (scaledContentSize <= viewportSize) {
    return (viewportSize - scaledContentSize) / 2;
  }
  const min = viewportSize - scaledContentSize;
  const max = 0;
  return clamp(translateAxis, min, max);
}

/** Borne les DEUX axes d'une translation (voir `clampPanAxis`) pour `content` affiché à `scale`. */
export function clampTranslate(translate: Point, viewport: Size, content: Size, scale: number): Point {
  const w = content.width * scale;
  const h = content.height * scale;
  return {
    x: clampPanAxis(translate.x, viewport.width, w),
    y: clampPanAxis(translate.y, viewport.height, h),
  };
}

/** Un tap horodaté (position + heure), pour la détection de double-tap ci-dessous. */
export interface TapRecord {
  x: number;
  y: number;
  time: number;
}

/**
 * Vrai quand `next` forme un double-tap/double-clic avec `prev` : assez
 * proche dans le temps (`maxDelayMs`, défaut 300 ms) ET dans l'espace
 * (`maxDistPx`, défaut 40 px — un doigt ne retombe jamais pixel-parfait).
 * `prev` absent (premier tap de la page) → jamais un double-tap.
 */
export function isDoubleTap(
  prev: TapRecord | null,
  next: TapRecord,
  maxDelayMs: number = 300,
  maxDistPx: number = 40,
): boolean {
  if (!prev) return false;
  const dt = next.time - prev.time;
  if (dt < 0 || dt > maxDelayMs) return false;
  return pointDistance(prev, next) <= maxDistPx;
}

/**
 * Parse un attribut `viewBox` SVG (`"minX minY width height"`, séparateurs
 * espace OU virgule) en dimensions de contenu. `null` si absent, malformé, ou
 * largeur/hauteur non positive — jamais une taille inventée : l'appelant
 * retombe alors sur les attributs `width`/`height` du SVG, ou une valeur par
 * défaut explicite.
 */
export function parseViewBoxSize(viewBox: string | null | undefined): Size | null {
  if (!viewBox || typeof viewBox !== 'string') return null;
  const parts = viewBox.trim().split(/[\s,]+/).map(Number);
  if (parts.length !== 4 || parts.some((n) => !Number.isFinite(n))) return null;
  const width = parts[2];
  const height = parts[3];
  if (!(width > 0) || !(height > 0)) return null;
  return { width, height };
}
