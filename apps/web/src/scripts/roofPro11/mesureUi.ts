/**
 * CAL102 — outil de MESURE (distance cumulée, surface d'un polygone fermé, angle),
 * persistable comme annotation du calepinage.
 *
 * Constat : aucune règle de mesure n'existait dans l'atelier — les seules distances
 * affichées venaient d'un glissé en placement libre (FreeCheck.edgeM/panelM), rien pour
 * vérifier une cote sur l'image satellite elle-même. La GÉOMÉTRIE ci-dessous est PURE
 * (mêmes formules que `lib/roof.ts` geodesicAreaM2/geodesicPerimeterM — projection locale
 * équirectangulaire, échelle cos(latitude moyenne), rayon WGS84 : AUCUNE dimension
 * inventée) ; la couche UI en bas de fichier n'est qu'un pont vers `ctx.measurements`.
 */
import { geodesicAreaM2, type LngLat } from '../../lib/roof';
import { DEG2RAD, WGS84_RADIUS } from './constants';
import { type Ctx } from './context';

export type MeasureKind = 'distance' | 'area' | 'angle';

/** Une mesure posée : ses points (lng/lat, mêmes coordonnées que le tracé du toit), son
 *  genre, et la valeur calculée AU MOMENT de la pose (m pour distance/angle-support, m²
 *  pour surface, ° pour angle) — recalculable à tout instant depuis `points` via
 *  `measureValue`, jamais une valeur figée séparée de sa géométrie source. */
export interface Measurement {
  id: string;
  kind: MeasureKind;
  points: LngLat[];
  /** Libellé posé par l'utilisateur (optionnel — « côté sud », « toiture principale »…). */
  label?: string;
}

/** Distance géodésique (m) entre deux points lng/lat — même projection locale que
 *  `geodesicPerimeterM` (échelle cos(latitude moyenne), rayon WGS84). */
export function segmentDistanceM(a: LngLat, b: LngLat): number {
  const midLat = ((a[1] + b[1]) / 2) * DEG2RAD;
  const de = (b[0] - a[0]) * DEG2RAD * Math.cos(midLat) * WGS84_RADIUS;
  const dn = (b[1] - a[1]) * DEG2RAD * WGS84_RADIUS;
  return Math.hypot(de, dn);
}

/** Distance CUMULÉE (m) le long d'une polyligne ouverte (≥ 2 points) — somme des segments
 *  consécutifs, PAS une fermeture sur le premier point (à la différence d'une aire). */
export function cumulativeDistanceM(points: readonly LngLat[]): number {
  if (!Array.isArray(points) || points.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < points.length; i++) total += segmentDistanceM(points[i - 1], points[i]);
  return total;
}

/** Surface (m²) du polygone FERMÉ formé par ≥ 3 points — réutilise directement
 *  `geodesicAreaM2` (aucune formule dupliquée : la même aire que le tracé du toit
 *  utiliserait sur ce même contour). */
export function polygonAreaM2(points: readonly LngLat[]): number {
  return geodesicAreaM2([...points]);
}

/** Angle (°, 0–180) formé au sommet `points[1]` par les deux segments vers `points[0]` et
 *  `points[2]` — projection locale équirectangulaire (même repère que les distances
 *  ci-dessus), donc cohérent avec elles sur une même mesure. Nécessite exactement 3 points ;
 *  renvoie 0 si un segment est dégénéré (deux points confondus). */
export function vertexAngleDeg(points: readonly LngLat[]): number {
  if (!Array.isArray(points) || points.length !== 3) return 0;
  const origin = points[1];
  const toEnu = (p: LngLat): [number, number] => {
    const midLat = ((p[1] + origin[1]) / 2) * DEG2RAD;
    return [(p[0] - origin[0]) * DEG2RAD * Math.cos(midLat) * WGS84_RADIUS, (p[1] - origin[1]) * DEG2RAD * WGS84_RADIUS];
  };
  const [ax, ay] = toEnu(points[0]);
  const [bx, by] = toEnu(points[2]);
  const la = Math.hypot(ax, ay);
  const lb = Math.hypot(bx, by);
  if (la === 0 || lb === 0) return 0;
  const cos = Math.max(-1, Math.min(1, (ax * bx + ay * by) / (la * lb)));
  return (Math.acos(cos) * 180) / Math.PI;
}

/** Valeur calculée d'une mesure selon son genre — TOUJOURS dérivée de `points`, jamais une
 *  valeur séparée susceptible de diverger de la géométrie posée. */
export function measureValue(m: Pick<Measurement, 'kind' | 'points'>): number {
  switch (m.kind) {
    case 'distance':
      return cumulativeDistanceM(m.points);
    case 'area':
      return polygonAreaM2(m.points);
    case 'angle':
      return vertexAngleDeg(m.points);
    default:
      return 0;
  }
}

/** Une mesure est-elle GÉOMÉTRIQUEMENT VALIDE pour son genre (assez de points, genre
 *  reconnu) ? Distance ≥ 2 points, surface ≥ 3, angle exactement 3. */
export function isMeasureValid(m: Pick<Measurement, 'kind' | 'points'>): boolean {
  if (!Array.isArray(m.points)) return false;
  if (m.kind === 'distance') return m.points.length >= 2;
  if (m.kind === 'area') return m.points.length >= 3;
  if (m.kind === 'angle') return m.points.length === 3;
  return false;
}

/** Libellé FR lisible de la valeur d'une mesure. */
export function formatMeasure(m: Pick<Measurement, 'kind' | 'points'>): string {
  const v = measureValue(m);
  if (m.kind === 'area') return `${v.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} m²`;
  if (m.kind === 'angle') return `${Math.round(v)}°`;
  return `${v.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} m`;
}

// ————————————————————————————————————————————————————————————————————————
// CALX128 — UNE MESURE EST AFFICHÉE AVEC SA PRÉCISION, JAMAIS ARRONDIE EN SILENCE
//
// `formatMeasure` arrondit (2 décimales en mètres, 1 en m², le degré entier) sans le dire :
// « 12,35 m » se lit comme une mesure exacte alors que c'est un arrondi au centimètre. Le
// bloc ci-dessous rend la MÊME valeur, mais accompagnée de l'arrondi appliqué — on peut
// donc l'afficher, l'annoncer au clavier (zone `aria-live`) et le relire sans ambiguïté.
//
// AUCUN chiffre n'est inventé : la valeur reste `measureValue(m)`, dérivée des points posés.
// Seule la FAÇON de la dire change.
// ————————————————————————————————————————————————————————————————————————

/** Nombre de décimales affichées par genre — CONVENTION D'AFFICHAGE, nommée et dite. */
export const DECIMALES_MESURE: Readonly<Record<MeasureKind, number>> = {
  distance: 2, // centimètre
  area: 1, // décimètre carré
  angle: 0, // degré
};

/** Unité affichée par genre. */
export const UNITE_MESURE: Readonly<Record<MeasureKind, string>> = {
  distance: 'm',
  area: 'm²',
  angle: '°',
};

/** Comment l'arrondi se dit, en clair — c'est ce que la zone d'annonces lit à voix haute. */
export const ARRONDI_MESURE: Readonly<Record<MeasureKind, string>> = {
  distance: 'arrondi au centimètre',
  area: 'arrondi au décimètre carré',
  angle: 'arrondi au degré',
};

/** Une mesure prête à afficher : sa valeur BRUTE, son texte, et l'arrondi appliqué. */
export interface MesureAffichee {
  /** La valeur exacte calculée depuis les points — jamais tronquée. */
  valeur: number;
  /** La valeur arrondie telle qu'elle est écrite (utile pour comparer ce qui est LU). */
  valeurAffichee: number;
  /** « 12,35 m » — le nombre + son unité, sans la mention d'arrondi. */
  texte: string;
  unite: string;
  decimales: number;
  /** « arrondi au centimètre ». */
  arrondi: string;
  /** « 12,35 m (arrondi au centimètre) » — le libellé COMPLET, celui qui ne ment pas. */
  texteComplet: string;
}

/**
 * CALX128 — la mesure, DITE avec sa précision. Un genre inconnu ne produit ni chiffre ni
 * unité inventés : sa valeur est rendue telle quelle et l'arrondi est déclaré inconnu.
 */
export function formatMesurePrecise(m: Pick<Measurement, 'kind' | 'points'>): MesureAffichee {
  const valeur = measureValue(m);
  const decimales = DECIMALES_MESURE[m.kind] ?? 2;
  const unite = UNITE_MESURE[m.kind] ?? '';
  const arrondi = ARRONDI_MESURE[m.kind] ?? 'arrondi non déclaré';
  const facteur = Math.pow(10, decimales);
  const valeurAffichee = Math.round(valeur * facteur) / facteur;
  const nombre = valeur.toLocaleString('fr-FR', {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
  const texte = unite ? `${nombre} ${unite}` : nombre;
  return { valeur, valeurAffichee, texte, unite, decimales, arrondi, texteComplet: `${texte} (${arrondi})` };
}

/** Comment chaque genre de mesure se nomme à l'écran et dans une annonce. */
export const LIBELLE_GENRE_MESURE: Readonly<Record<MeasureKind, string>> = {
  distance: 'Distance',
  area: 'Surface',
  angle: 'Angle',
};

/** Le minimum de points EXIGÉ par genre — c'est lui que nomme un refus de fin de mesure. */
export const POINTS_MINIMUM_MESURE: Readonly<Record<MeasureKind, number>> = {
  distance: 2,
  area: 3,
  angle: 3,
};

/**
 * CALX128 — la phrase d'une mesure posée : son genre, sa valeur et l'arrondi appliqué.
 * C'est ce que la zone `aria-live` annonce quand un point de mesure est posé au clavier.
 */
export function decrireMesure(m: Pick<Measurement, 'kind' | 'points'>): string {
  const genre = LIBELLE_GENRE_MESURE[m.kind] ?? 'Mesure';
  return `${genre} : ${formatMesurePrecise(m).texteComplet}.`;
}

/**
 * CALX128 — le motif d'une mesure qu'on ne peut pas encore terminer : il NOMME combien de
 * points manquent, jamais un « mesure invalide » générique.
 */
export function motifMesureIncomplete(kind: MeasureKind, poses: number): string {
  const minimum = POINTS_MINIMUM_MESURE[kind] ?? 2;
  const genre = (LIBELLE_GENRE_MESURE[kind] ?? 'Mesure').toLowerCase();
  const manquants = Math.max(0, minimum - poses);
  return (
    `Mesure incomplète : une ${genre} demande ${minimum} points, ${poses} posé(s) — ` +
    `il en manque ${manquants}. Rien n’est enregistré.`
  );
}

// ═══════════ Couche UI — pont vers `ctx.measurements` (persistance du calepinage) ═══════════

export interface MesureUiDeps {
  /** Repeint la liste des mesures à l'écran (échafaudage `rp9-mesure-*`, optionnel). */
  render?: () => void;
}

export interface MesureUi {
  /** Mesures posées sur le pan ACTIF (lecture — copie, jamais la référence vivante). */
  list: () => Measurement[];
  /** Ajoute une mesure (genre + points). Refusée (renvoie null) si géométriquement
   *  invalide pour son genre — jamais posée à moitié. */
  add: (kind: MeasureKind, points: readonly LngLat[], label?: string) => Measurement | null;
  /** Retire une mesure par id. */
  remove: (id: string) => boolean;
  /** Vide toutes les mesures du pan actif. */
  clear: () => void;

  // — CAL102 — SESSION interactive : un point posé à la fois (même esprit que le tracé du
  // toit ou le glissé-dessin d'obstacle), pour que l'appelant carte (roof-tool-pro11.ts)
  // n'ait qu'à router ses clics/taps ici, sans connaître la mécanique de mesure. —
  /** Une mesure est-elle en cours de pose ? */
  isActive: () => boolean;
  /** Genre de la mesure en cours, ou null hors session. */
  activeKind: () => MeasureKind | null;
  /** Démarre une session du genre donné (remplace une session en cours sans la poser —
   *  parité avec « changer d'outil abandonne le tracé en cours »). */
  begin: (kind: MeasureKind) => void;
  /** Pose un point dans la session en cours. No-op hors session. Le genre « angle » se
   *  plafonne à 3 points (les points au-delà sont ignorés — jamais un angle à 4 sommets). */
  addPoint: (p: LngLat) => void;
  /** Retire le DERNIER point posé (parité « annuler le dernier point » du tracé du toit). */
  undoPoint: () => void;
  /** Points de la session en cours (copie), pour l'aperçu vivant sur la carte. */
  sessionPoints: () => LngLat[];
  /** Termine la session : pose la mesure si géométriquement valide pour son genre (et vide
   *  la session), sinon la GARDE ouverte et renvoie null (l'utilisateur peut ajouter les
   *  points manquants). */
  finish: (label?: string) => Measurement | null;
  /** Abandonne la session en cours SANS rien poser. */
  cancel: () => void;
}

let nextMeasureId = 0;
/** Générateur d'id STABLE dans une session (préfixe + compteur) — jamais Math.random() dans
 *  un module par ailleurs déterministe, mais unique tant que la page vit. */
function makeMeasureId(): string {
  nextMeasureId += 1;
  return `mes${nextMeasureId}`;
}

/** CAL102 — pont UI : `ctx.measurements` est le stockage (persisté avec le calepinage, cf.
 *  `types.ts`/`prefill.ts` pour le format de sauvegarde), ce module n'en est que la porte
 *  d'entrée contrôlée (jamais une mesure invalide posée). Optionnel côté `ctx` — un `ctx`
 *  antérieur à CAL102 n'en porte pas, jamais lu en aveugle. */
export function createMesureUi(ctx: Ctx, deps: MesureUiDeps = {}): MesureUi {
  function ensure(): Measurement[] {
    if (!Array.isArray(ctx.measurements)) ctx.measurements = [];
    return ctx.measurements;
  }
  function list(): Measurement[] {
    return ensure().map((m) => ({ ...m, points: m.points.map((p) => [p[0], p[1]] as LngLat) }));
  }
  function add(kind: MeasureKind, points: readonly LngLat[], label?: string): Measurement | null {
    const m: Measurement = { id: makeMeasureId(), kind, points: points.map((p) => [p[0], p[1]] as LngLat), label };
    if (!isMeasureValid(m)) return null;
    ensure().push(m);
    deps.render?.();
    return m;
  }
  function remove(id: string): boolean {
    const arr = ensure();
    const idx = arr.findIndex((m) => m.id === id);
    if (idx < 0) return false;
    arr.splice(idx, 1);
    deps.render?.();
    return true;
  }
  function clear() {
    ensure().length = 0;
    deps.render?.();
  }

  // — CAL102 — session interactive —
  let session: { kind: MeasureKind; points: LngLat[] } | null = null;
  const MAX_POINTS: Record<MeasureKind, number> = { distance: Infinity, area: Infinity, angle: 3 };
  function isActive(): boolean {
    return session != null;
  }
  function activeKind(): MeasureKind | null {
    return session?.kind ?? null;
  }
  function begin(kind: MeasureKind) {
    session = { kind, points: [] };
    deps.render?.();
  }
  function addPoint(p: LngLat) {
    if (!session) return;
    if (session.points.length >= MAX_POINTS[session.kind]) return;
    session.points.push([p[0], p[1]]);
    deps.render?.();
  }
  function undoPoint() {
    if (!session || !session.points.length) return;
    session.points.pop();
    deps.render?.();
  }
  function sessionPoints(): LngLat[] {
    return session ? session.points.map((p) => [p[0], p[1]] as LngLat) : [];
  }
  function finish(label?: string): Measurement | null {
    if (!session) return null;
    const m = add(session.kind, session.points, label);
    if (m) session = null; // pose réussie : la session se referme
    return m; // invalide : session GARDÉE (l'utilisateur complète), deps.render déjà appelé par add() si posé
  }
  function cancel() {
    if (!session) return;
    session = null;
    deps.render?.();
  }

  return { list, add, remove, clear, isActive, activeKind, begin, addPoint, undoPoint, sessionPoints, finish, cancel };
}

// ————————————————————————————————————————————————————————————————————————
// CALX128 — LES GESTES CLAVIER DU MODE MESURE
//
// La mesure n'avait aucune entrée clavier : `addPoint` n'était appelé que depuis le clic
// de la carte. Les gestes ci-dessous sont la MÊME session (`MesureUi`), routée depuis le
// plan clavier — les gestes souris/tactile ne changent pas d'un octet.
//
// Chaque geste rend un VERDICT : accepté, il dit ce qui a été fait ET avec quelle
// précision ; refusé, il NOMME ce qui manque (jamais un « mesure invalide » générique).
// ————————————————————————————————————————————————————————————————————————

/** Le verdict d'un geste clavier — même forme que `clavier.ts::VerdictGeste` (déclaré ici
 *  pour que `mesureUi.ts` ne dépende pas du module de routage : c'est lui qui dépend d'elle). */
export type VerdictMesure = { ok: true; texte: string } | { ok: false; motif: string };

export interface GestesMesure {
  poser: () => VerdictMesure;
  'annuler-dernier': () => VerdictMesure;
  terminer: () => VerdictMesure;
  sortir: () => VerdictMesure;
}

/**
 * CALX128 — les gestes clavier du mode mesure, branchés sur une session `MesureUi` et sur
 * le curseur de pose (`curseur()` rend le point courant du curseur clavier).
 *
 * `poser` refuse hors session en le DISANT ; `terminer` refuse une mesure incomplète en
 * nommant combien de points manquent et garde la session ouverte (rien n'est enregistré,
 * rien n'est perdu).
 */
export function gestesMesure(mesure: MesureUi, curseur: () => LngLat | null): GestesMesure {
  return {
    poser: () => {
      const kind = mesure.activeKind();
      if (!kind) {
        return { ok: false, motif: 'Aucune mesure en cours — démarrez une mesure avant de poser un point.' };
      }
      const p = curseur();
      if (!p) {
        return { ok: false, motif: 'Point non posé : le curseur de pose n’a pas encore de position sur la carte.' };
      }
      const avant = mesure.sessionPoints().length;
      mesure.addPoint(p);
      const apres = mesure.sessionPoints().length;
      if (apres === avant) {
        // Le genre « angle » se plafonne à 3 points : on le DIT plutôt que de l'ignorer.
        return {
          ok: false,
          motif: `Point refusé : une ${(LIBELLE_GENRE_MESURE[kind] ?? 'mesure').toLowerCase()} n’accepte pas plus de ${avant} points.`,
        };
      }
      const provisoire = { kind, points: mesure.sessionPoints() };
      const valeur = isMeasureValid(provisoire) ? ` ${formatMesurePrecise(provisoire).texteComplet}.` : '';
      return { ok: true, texte: `Point ${apres} posé.${valeur}` };
    },
    'annuler-dernier': () => {
      const avant = mesure.sessionPoints().length;
      if (avant === 0) {
        return { ok: false, motif: 'Rien à annuler : aucun point de mesure n’est posé.' };
      }
      mesure.undoPoint();
      return { ok: true, texte: `Dernier point annulé — ${mesure.sessionPoints().length} point(s) restant(s).` };
    },
    terminer: () => {
      const kind = mesure.activeKind();
      if (!kind) return { ok: false, motif: 'Aucune mesure en cours à terminer.' };
      const poses = mesure.sessionPoints().length;
      const posee = mesure.finish();
      if (!posee) return { ok: false, motif: motifMesureIncomplete(kind, poses) };
      return { ok: true, texte: `Mesure enregistrée. ${decrireMesure(posee)}` };
    },
    sortir: () => {
      if (!mesure.isActive()) return { ok: false, motif: 'Aucune mesure en cours — rien à quitter.' };
      mesure.cancel();
      return { ok: true, texte: 'Mesure abandonnée — aucun point n’a été enregistré.' };
    },
  };
}
