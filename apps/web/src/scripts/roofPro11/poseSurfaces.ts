/**
 * ════════════════════════════════════════════════════════════════════════════
 * CALX123 — LE CHAMP AU SOL SE TRACE DANS L'ATELIER, IL NE SE TAPE PLUS.
 * ----------------------------------------------------------------------------
 * Constat : le mode terrain est un formulaire de dix nombres, sans carte ni 3D,
 * alors que la géométrie de placement existe et est testée depuis CAL89
 * (`scene3d.ts` : `construireChampPose`) et que le contrat porte déjà
 * `poseSurfaces[]` (`roof_layout_v2.schema.json`, `$defs/poseSurface`). Ce
 * module est le chaînon manquant : la SAISIE GÉOMÉTRIQUE.
 *
 * LE PARTAGE DES RÔLES, ET IL N'EN CHANGE PAS :
 *   * l'écran « Mode terrain » (CALX50) et l'écran « Ombrière » (CALX51) sont la
 *     LECTURE CHIFFRÉE de la surface — ils ne tracent rien ;
 *   * ce module est la SAISIE — il ne recalcule rien de ce que ces écrans lisent ;
 *   * le MOTEUR serveur rend le plan (`POST /calepinage/moteur/pose/`) — ni l'un
 *     ni l'autre ne le refait.
 * Aucun pas inter-rangées, aucune charge, aucune structure n'est calculé ici :
 * le pas vient du moteur (CAL88) et n'a AUCUNE seconde formule côté client.
 *
 * ZÉRO CHIFFRE INVENTÉ : une valeur qui n'a pas été SAISIE n'est pas écrite —
 * ni 0, ni une valeur « raisonnable ». Elle est NOMMÉE dans `nonSaisi`, et
 * l'atelier le dit. Un refus nomme le CHAMP fautif, jamais un « non enregistré »
 * générique.
 *
 * Les seules constantes de ce module sont des CONVENTIONS DE DESSIN, nommées et
 * commentées comme telles : aucune constante d'ingénierie neuve.
 * ══════════════════════════════════════════════════════════════════════════ */
import { geodesicAreaM2, type LngLat } from '../../lib/roof';
import { DEG2M, DEG2RAD } from './constants';
import { esc } from './dom';
import type { Ctx } from './context';

// ═══════════════ LE DOCUMENT : MIROIR EXACT DE `$defs/poseSurface` ═══════════════

/** Genre de surface de pose — énumération FERMÉE du contrat (CAL89/CAL91/CALX87). */
export type GenrePose = 'sol' | 'ombriere' | 'facade';

/** CALX87 — les POTEAUX d'une ombrière, tels qu'ils ont été SAISIS. Deux mesures,
 *  rien d'autre : ni matériau, ni charge admissible, ni prix. */
export interface AppuisOmbriere {
  /** Entraxe entre deux appuis (m), SAISI. Absent = aucun appui décrit. */
  pasM?: number | null;
  /** Dimension SAISIE de la section d'un appui (m). */
  sectionM?: number | null;
}

/** CAL89 — une TABLE rendue par le moteur, recopiée telle quelle. */
export interface TablePoseDocument {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  kit?: string;
}

/** CAL89 — ce que le MOTEUR a rendu pour cette surface. Aucune de ces valeurs
 *  n'est calculée par un écran ; une valeur non publiée vaut `null`, jamais `0`. */
export interface PlanMoteurPose {
  modules?: number | null;
  rowPitchM?: number | null;
  tables?: TablePoseDocument[];
  groundCoverageRatio?: number | null;
  versionMoteur?: string | null;
  hashEntree?: string | null;
}

/** Une SURFACE DE POSE du document — miroir EXACT de `$defs/poseSurface`. Toute
 *  clé absente est ABSENTE : elle n'a pas été saisie, et rien ne la remplace. */
export interface SurfacePose {
  kind: GenrePose;
  id: string;
  label?: string;
  /** Contour tracé en [[lng, lat], …] — même convention que `zones[].vertices`. */
  vertices?: LngLat[];
  /** Contour en MÈTRES [[x, y], …], EXACTEMENT ce qui part au moteur. */
  contourM?: number[][];
  /** Surface MESURÉE sur le contour tracé (m²). `null` = contour incomplet. */
  areaM2?: number | null;
  /** Pente du TERRAIN (degrés), SAISIE. */
  terrainSlopeDeg?: number | null;
  /** Orientation des RANGÉES (degrés, 0=N, 90=E), SAISIE. */
  rowAzimuthDeg?: number | null;
  /** Inclinaison des TABLES (degrés), SAISIE. */
  tiltDeg?: number | null;
  /** CAL91 — hauteur libre sous l'ombrière (m), SAISIE. */
  clearHeightM?: number | null;
  /** CAL91 — sens d'écoulement de la couverture (degrés), SAISI. */
  flowAzimuthDeg?: number | null;
  /** CAL91 — bâtiment auquel la surface est rattachée (même clé que `zones[].buildingId`). */
  buildingId?: string;
  /** CALX87 — hauteur du BAS de la bande posable d'un mur (m). */
  hauteurBasseM?: number | null;
  /** CALX87 — hauteur du HAUT de la bande posable d'un mur (m). */
  hauteurHauteM?: number | null;
  /** CALX87 — les appuis de l'ombrière, SAISIS. */
  appuis?: AppuisOmbriere;
  /** CAL89 — le plan rendu par le moteur, recopié tel quel. */
  engine?: PlanMoteurPose;
}

// ═══════════════ REFUS : TOUJOURS LE CHAMP FAUTIF, JAMAIS UN MESSAGE MUET ═══════════════

/** Les champs de saisie d'une surface de pose — un refus en NOMME toujours un. */
export type ChampPose =
  | 'identifiant'
  | 'contour'
  | 'penteTerrain'
  | 'azimutRangee'
  | 'inclinaison'
  | 'hauteurLibre'
  | 'sensEcoulement'
  | 'pasAppui'
  | 'sectionAppui'
  | 'mur'
  | 'hauteurBasse'
  | 'hauteurHaute';

/** Libellé FRANÇAIS de chaque champ — c'est lui que l'atelier affiche, jamais la clé. */
export const LIBELLE_CHAMP_POSE: Readonly<Record<ChampPose, string>> = {
  identifiant: 'identifiant de la surface',
  contour: 'contour tracé sur la carte',
  penteTerrain: 'pente du terrain',
  azimutRangee: 'orientation des rangées',
  inclinaison: 'inclinaison des tables',
  hauteurLibre: 'hauteur libre',
  sensEcoulement: 'sens d’écoulement',
  pasAppui: 'entraxe des appuis',
  sectionAppui: 'section des appuis',
  mur: 'mur désigné',
  hauteurBasse: 'hauteur basse de la bande posable',
  hauteurHaute: 'hauteur haute de la bande posable',
};

/** Verdict d'une saisie de surface : la surface écrite + ce qui n'a PAS été saisi
 *  (nommé, pour que l'atelier le dise), ou un refus qui NOMME le champ fautif. */
export type VerdictSurface =
  | { ok: true; surface: SurfacePose; nonSaisi: string[] }
  | { ok: false; champ: ChampPose; motif: string };

/** Un nombre réellement SAISI ? (fini — le seul « saisi » qu'on accepte). */
function estSaisi(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

// ═══════════════ CALX123 — DU CONTOUR TRACÉ AU CONTOUR EN MÈTRES ═══════════════

/**
 * CONVENTION DE DESSIN — le repère métrique d'une surface de pose est la
 * projection ENU locale centrée sur le CENTROÏDE de son contour : exactement la
 * projection utilisée partout ailleurs dans roofPro11 (`scene3d.shapeToEnu`,
 * `freeMode.toEnu`). Ce n'est pas une constante d'ingénierie : c'est le repère
 * de dessin, et c'est LUI que `contourM` porte, donc lui que le moteur reçoit.
 */
export function origineContour(vertices: readonly LngLat[]): LngLat | null {
  if (!Array.isArray(vertices) || vertices.length < 3) return null;
  let sLng = 0;
  let sLat = 0;
  for (const v of vertices) {
    if (!Array.isArray(v) || !estSaisi(v[0]) || !estSaisi(v[1])) return null;
    sLng += v[0];
    sLat += v[1];
  }
  return [sLng / vertices.length, sLat / vertices.length];
}

/**
 * CALX123 — le contour TRACÉ (lng/lat) rendu en MÈTRES, tel qu'il partira au
 * moteur. `null` quand le tracé n'a pas de quoi faire une surface (< 3 coins, ou
 * un coin illisible) : on ne complète jamais un contour à moitié.
 *
 * L'aire de ce contour en mètres et l'aire géodésique du tracé disent la MÊME
 * surface (`aireAnneauM2(contourMetres(v))` ≈ `geodesicAreaM2(v)`, à 10⁻³ près
 * en relatif) — c'est ce qui garantit qu'un client qui lit « 1 200 m² » sur la
 * carte envoie bien 1 200 m² au moteur.
 */
export function contourMetres(vertices: readonly LngLat[]): number[][] | null {
  const origine = origineContour(vertices);
  if (!origine) return null;
  const cosLat = Math.cos(origine[1] * DEG2RAD);
  return vertices.map((v) => [
    (v[0] - origine[0]) * DEG2M * cosLat,
    (v[1] - origine[1]) * DEG2M,
  ]);
}

/** Aire (m²) d'un anneau métrique — formule du lacet, sens d'enroulement indifférent. */
export function aireAnneauM2(contourM: readonly (readonly number[])[] | null | undefined): number {
  if (!Array.isArray(contourM) || contourM.length < 3) return 0;
  let s = 0;
  for (let i = 0; i < contourM.length; i++) {
    const a = contourM[i];
    const b = contourM[(i + 1) % contourM.length];
    if (!estSaisi(a?.[0]) || !estSaisi(a?.[1]) || !estSaisi(b?.[0]) || !estSaisi(b?.[1])) return 0;
    s += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(s / 2);
}

// ═══════════════ CALX123 — LA SAISIE D'UN CHAMP AU SOL ═══════════════

/** Ce que l'atelier recueille pour un champ au sol. Tout y est OPTIONNEL sauf le
 *  contour et l'identifiant : une valeur absente reste absente du document. */
export interface SaisieChampSol {
  id: string;
  label?: string;
  /** Le contour TRACÉ sur la carte, comme un pan (`ctx.vertices`). */
  vertices: readonly LngLat[];
  buildingId?: string;
  /** Pente du terrain (degrés), SAISIE. Absente ⇒ rien n'est écrit. */
  penteTerrainDeg?: number | null;
  /** Orientation des rangées (degrés), SAISIE. */
  azimutRangeeDeg?: number | null;
  /** Inclinaison des tables (degrés), SAISIE. */
  inclinaisonDeg?: number | null;
}

/** Motif de refus d'un contour, ou `null` quand il est exploitable. */
function refusContour(vertices: readonly LngLat[]): string | null {
  if (!Array.isArray(vertices) || vertices.length < 3) {
    return 'Tracez au moins trois coins sur la carte avant d’enregistrer la surface — un contour à deux points n’a aucune aire.';
  }
  const contourM = contourMetres(vertices);
  if (!contourM) {
    return 'Un coin du tracé n’a pas de position lisible : reprenez le contour sur la carte.';
  }
  // La surface qui compte est celle du contour MÉTRIQUE — c'est lui qui part au moteur.
  if (!(aireAnneauM2(contourM) > 0)) {
    return 'Le contour tracé n’a aucune surface (coins alignés ou confondus) : reprenez-le sur la carte.';
  }
  return null;
}

/** L'identifiant nettoyé, ou `null` quand il est vide. */
function idNettoye(id: string | null | undefined): string | null {
  const t = (id ?? '').trim();
  return t.length ? t : null;
}

/** Écrit dans `cible` la clé `nom` SI et SEULEMENT SI elle a été saisie ; sinon
 *  nomme le champ dans `nonSaisi`. C'est ici, et nulle part ailleurs, que se joue
 *  « une valeur non saisie est ABSENTE ». */
function poserSaisie(
  cible: Record<string, unknown>,
  cle: string,
  valeur: unknown,
  champ: ChampPose,
  nonSaisi: string[],
): void {
  if (estSaisi(valeur)) cible[cle] = valeur;
  else nonSaisi.push(LIBELLE_CHAMP_POSE[champ]);
}

/**
 * CALX123 — crée la surface de pose d'un CHAMP AU SOL depuis le contour tracé.
 *
 * Le contour voyage DEUX fois : en `vertices` (lng/lat, ce que la carte montre)
 * et en `contourM` (mètres, ce que le moteur reçoit) — les deux disent la même
 * surface. `areaM2` est MESURÉE sur le tracé, jamais supposée.
 *
 * Aucune pente, aucun azimut, aucune inclinaison n'est écrit tant qu'il n'est pas
 * SAISI : le champ manquant est nommé dans `nonSaisi` et l'atelier l'affiche.
 * Aucun pas inter-rangées n'est calculé — il vient du moteur, et de lui seul.
 */
export function creerChampSol(saisie: SaisieChampSol): VerdictSurface {
  const id = idNettoye(saisie?.id);
  if (!id) {
    return {
      ok: false,
      champ: 'identifiant',
      motif: 'Nommez la surface avant de l’enregistrer : un identifiant vide ne se retrouve pas dans le document.',
    };
  }
  const motifContour = refusContour(saisie.vertices);
  if (motifContour) return { ok: false, champ: 'contour', motif: motifContour };

  const vertices = saisie.vertices.map((v) => [v[0], v[1]] as LngLat);
  const contourM = contourMetres(vertices) as number[][];
  const nonSaisi: string[] = [];
  const surface: Record<string, unknown> = {
    kind: 'sol',
    id,
    vertices,
    contourM,
    areaM2: geodesicAreaM2(vertices),
  };
  const label = (saisie.label ?? '').trim();
  if (label) surface.label = label;
  const batiment = (saisie.buildingId ?? '').trim();
  if (batiment) surface.buildingId = batiment;

  poserSaisie(surface, 'terrainSlopeDeg', saisie.penteTerrainDeg, 'penteTerrain', nonSaisi);
  poserSaisie(surface, 'rowAzimuthDeg', saisie.azimutRangeeDeg, 'azimutRangee', nonSaisi);
  poserSaisie(surface, 'tiltDeg', saisie.inclinaisonDeg, 'inclinaison', nonSaisi);

  return { ok: true, surface: surface as unknown as SurfacePose, nonSaisi };
}

// ═══════════════ CALX123 — CE QUI VOYAGE PAR LE DOCUMENT ═══════════════

/** Copie DÉFENSIVE d'une surface (le document ne doit jamais partager une référence
 *  avec l'état vivant de l'atelier). Les clés absentes le restent. */
function copierSurface(s: SurfacePose): SurfacePose {
  const out: Record<string, unknown> = { kind: s.kind, id: s.id };
  if (typeof s.label === 'string' && s.label.length) out.label = s.label;
  if (Array.isArray(s.vertices)) out.vertices = s.vertices.map((v) => [v[0], v[1]] as LngLat);
  if (Array.isArray(s.contourM)) out.contourM = s.contourM.map((p) => [p[0], p[1]]);
  if (s.areaM2 !== undefined) out.areaM2 = s.areaM2;
  if (s.terrainSlopeDeg !== undefined) out.terrainSlopeDeg = s.terrainSlopeDeg;
  if (s.rowAzimuthDeg !== undefined) out.rowAzimuthDeg = s.rowAzimuthDeg;
  if (s.tiltDeg !== undefined) out.tiltDeg = s.tiltDeg;
  if (s.clearHeightM !== undefined) out.clearHeightM = s.clearHeightM;
  if (s.flowAzimuthDeg !== undefined) out.flowAzimuthDeg = s.flowAzimuthDeg;
  if (typeof s.buildingId === 'string' && s.buildingId.length) out.buildingId = s.buildingId;
  if (s.hauteurBasseM !== undefined) out.hauteurBasseM = s.hauteurBasseM;
  if (s.hauteurHauteM !== undefined) out.hauteurHauteM = s.hauteurHauteM;
  if (s.appuis) {
    const a: Record<string, unknown> = {};
    if (s.appuis.pasM !== undefined) a.pasM = s.appuis.pasM;
    if (s.appuis.sectionM !== undefined) a.sectionM = s.appuis.sectionM;
    out.appuis = a;
  }
  if (s.engine) out.engine = JSON.parse(JSON.stringify(s.engine));
  return out as unknown as SurfacePose;
}

/**
 * CALX123 — ce que `serializeLayout` ajoute au document : la clé `poseSurfaces`
 * du contrat, et RIEN quand aucune surface n'est tracée (le document repart alors
 * inchangé, octet pour octet — même discipline que `emettreBatiments`).
 */
export function emettreSurfacesPose(
  list: readonly SurfacePose[] | null | undefined,
): { poseSurfaces?: SurfacePose[] } {
  if (!Array.isArray(list) || !list.length) return {};
  const surfaces = list.filter((s) => s && typeof s.id === 'string' && s.id.length).map(copierSurface);
  return surfaces.length ? { poseSurfaces: surfaces } : {};
}

/** Les genres que le contrat admet — une valeur hors de cette liste n'est pas lue. */
const GENRES: readonly GenrePose[] = ['sol', 'ombriere', 'facade'];

/** Une surface du document, relue sans jamais compléter ce qui manque. `null` quand
 *  l'entrée n'est pas exploitable (genre inconnu, identifiant vide). */
export function normaliserSurfacePose(brut: unknown): SurfacePose | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const id = idNettoye(typeof o.id === 'string' ? o.id : null);
  const kind = GENRES.find((g) => g === o.kind);
  if (!id || !kind) return null;
  return copierSurface({ ...(o as unknown as SurfacePose), id, kind });
}

/** CALX123 — relit `poseSurfaces[]` d'un document. Une entrée illisible est IGNORÉE
 *  (jamais « réparée ») ; un document sans la clé rend une liste vide. */
export function lireSurfacesPose(json: unknown): SurfacePose[] {
  const brut = (json as { poseSurfaces?: unknown } | null | undefined)?.poseSurfaces;
  if (!Array.isArray(brut)) return [];
  const out: SurfacePose[] = [];
  for (const e of brut) {
    const s = normaliserSurfacePose(e);
    if (s) out.push(s);
  }
  return out;
}

/** CALX123 — les modules POSÉS sur une surface : ceux que le MOTEUR a rendus, et
 *  `null` tant qu'aucun plan n'est revenu. Jamais un recompte côté atelier. */
export function modulesPoses(surface: SurfacePose | null | undefined): number | null {
  const n = surface?.engine?.modules;
  return estSaisi(n) && n >= 0 ? n : null;
}

/**
 * CALX123 — le pas inter-rangées AFFICHÉ pour une surface : celui que le moteur a
 * publié, et `null` sinon. Il n'existe AUCUNE seconde formule de pas côté client —
 * le pas vient de CAL88 (`core/calepinage/surfaces/sol.py`), et deux formules
 * divergeraient mathématiquement. Un `null` s'affiche vide, jamais comblé.
 */
export function pasInterRangeeAffiche(surface: SurfacePose | null | undefined): number | null {
  const p = surface?.engine?.rowPitchM;
  return estSaisi(p) && p >= 0 ? p : null;
}

// ═══════════════ CALX123 — L'ATELIER « SURFACES DE POSE » ═══════════════

/** Un champ numérique du panneau : sa clé de saisie, son libellé, son unité. */
interface ChampNumerique {
  champ: ChampPose;
  cle: string;
  unite: string;
  /** Les genres qui affichent ce champ (les autres ne le montrent même pas). */
  genres: readonly GenrePose[];
}

/** Les champs numériques du panneau, dans l'ordre d'affichage. */
const CHAMPS_PANNEAU: readonly ChampNumerique[] = [
  { champ: 'penteTerrain', cle: 'pente', unite: '°', genres: ['sol'] },
  { champ: 'azimutRangee', cle: 'azimut', unite: '°', genres: ['sol'] },
  { champ: 'inclinaison', cle: 'inclinaison', unite: '°', genres: ['sol'] },
];

/** Dépendances d'écran du panneau — toutes OPTIONNELLES : sans elles, le panneau
 *  se contente d'écrire dans `ctx.surfacesPose`. */
export interface AtelierPoseDeps {
  /** Bandeau de statut de l'atelier (refus nommés, confirmations). */
  setStatus?: (msg: string) => void;
  /** Re-rendu de la scène après l'ajout d'une surface. */
  recalc?: () => void;
}

/** Ce que le panneau expose (testable sans DOM réel). */
export interface AtelierPose {
  /** Enregistre le contour COURANT de l'atelier comme surface du genre choisi. */
  enregistrerContour: (genre: GenrePose) => VerdictSurface;
  /** Les surfaces actuellement portées par l'atelier. */
  surfaces: () => SurfacePose[];
}

/** Lit un champ numérique du panneau : `null` quand il est vide (= NON SAISI). */
function lireChamp(racine: HTMLElement, cle: string): number | null {
  const el = racine.querySelector(`[data-pose-champ="${cle}"]`) as HTMLInputElement | null;
  const brut = (el?.value ?? '').trim().replace(',', '.');
  if (!brut.length) return null;
  const v = Number(brut);
  return Number.isFinite(v) ? v : null;
}

/** Affiche (ou efface) le motif SOUS le champ fautif — jamais un message muet. */
function afficherRefus(racine: HTMLElement, champ: ChampPose | null, motif: string): void {
  racine.querySelectorAll('[data-pose-erreur]').forEach((el) => {
    (el as HTMLElement).textContent = '';
  });
  if (!champ) return;
  const cible = racine.querySelector(`[data-pose-erreur="${champ}"]`) as HTMLElement | null;
  if (cible) cible.textContent = motif;
}

/**
 * CALX123 — monte le panneau « Surfaces de pose » dans l'atelier, en le CRÉANT si
 * la page hôte ne le fournit pas (même patron qu'`ensureStatsTable`, `zones.ts`) :
 * aucune page n'a à être modifiée.
 *
 * Rend `null` quand il n'y a pas de DOM (tests unitaires isolés) — l'atelier
 * fonctionne alors exactement comme avant.
 */
export function monterAtelierPose(ctx: Ctx, deps: AtelierPoseDeps = {}): AtelierPose | null {
  if (typeof document === 'undefined' || typeof document.createElement !== 'function') return null;
  const hote = ctx.dom?.areasWindowEl;
  if (!hote) return null;
  let racine = document.getElementById('rp11-surfaces-pose');
  if (!racine) {
    racine = document.createElement('div');
    racine.id = 'rp11-surfaces-pose';
    racine.className = 'mt-3 border-t border-white/10 pt-3 text-xs text-lune-soft';
    hote.appendChild(racine);
  }
  racine.innerHTML = `
    <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-lune-faint">Surfaces de pose</p>
    <p class="mb-2 text-[11px] text-lune-faint">Tracez le contour sur la carte comme un pan, puis enregistrez-le ici. Le plan de pose est rendu par le moteur : l’atelier ne le recalcule jamais.</p>
    <label class="mb-2 block">Genre
      <select data-pose-genre class="mt-1 w-full rounded border border-white/20 bg-nuit-900/60 px-2 py-1">
        <option value="sol">Champ au sol</option>
      </select>
    </label>
    ${CHAMPS_PANNEAU.map(
      (c) => `<label class="mb-2 block" data-pose-ligne="${esc(c.champ)}">${esc(LIBELLE_CHAMP_POSE[c.champ])} (${esc(c.unite)})
        <input type="number" inputmode="decimal" data-pose-champ="${esc(c.cle)}" class="mt-1 w-full rounded border border-white/20 bg-nuit-900/60 px-2 py-1" />
        <span class="mt-1 block text-[11px] text-rose-300" data-pose-erreur="${esc(c.champ)}"></span>
      </label>`,
    ).join('')}
    <span class="mb-2 block text-[11px] text-rose-300" data-pose-erreur="contour"></span>
    <span class="mb-2 block text-[11px] text-rose-300" data-pose-erreur="identifiant"></span>
    <button type="button" data-pose-enregistrer class="w-full rounded border border-white/25 px-2 py-1 text-white">Enregistrer le contour tracé</button>
    <ul data-pose-liste class="mt-2 space-y-1"></ul>`;

  const listeEl = racine.querySelector('[data-pose-liste]') as HTMLElement | null;
  const genreEl = racine.querySelector('[data-pose-genre]') as HTMLSelectElement | null;

  /** N'affiche que les champs du genre choisi : un champ sans objet ne se saisit pas. */
  function synchroniserGenre(): void {
    const genre = (genreEl?.value as GenrePose) ?? 'sol';
    for (const c of CHAMPS_PANNEAU) {
      const ligne = racine!.querySelector(`[data-pose-ligne="${c.champ}"]`) as HTMLElement | null;
      if (ligne) ligne.style.display = c.genres.includes(genre) ? '' : 'none';
    }
  }

  function rendreListe(): void {
    if (!listeEl) return;
    const list = ctx.surfacesPose ?? [];
    listeEl.innerHTML = list
      .map((s) => {
        const n = modulesPoses(s);
        const aire = estSaisi(s.areaM2) ? `${Math.round(s.areaM2)} m²` : '—';
        const mods = n === null ? '— (plan du moteur non reçu)' : `${n} modules`;
        return `<li data-pose-ligne-surface="${esc(s.id)}">${esc(s.label || s.id)} — ${esc(aire)} · ${esc(mods)}</li>`;
      })
      .join('');
  }

  function enregistrerContour(genre: GenrePose): VerdictSurface {
    const list = ctx.surfacesPose ?? (ctx.surfacesPose = []);
    const verdict = saisirSurface(genre, racine!, ctx, list.length + 1);
    if (!verdict.ok) {
      afficherRefus(racine!, verdict.champ, verdict.motif);
      deps.setStatus?.(`Surface non enregistrée — ${LIBELLE_CHAMP_POSE[verdict.champ]} : ${verdict.motif}`);
      return verdict;
    }
    afficherRefus(racine!, null, '');
    list.push(verdict.surface);
    rendreListe();
    deps.recalc?.();
    const manque = verdict.nonSaisi.length
      ? ` Non renseigné : ${verdict.nonSaisi.join(', ')} — la valeur reste absente du document.`
      : '';
    deps.setStatus?.(`Surface « ${verdict.surface.label || verdict.surface.id} » enregistrée.${manque}`);
    return verdict;
  }

  genreEl?.addEventListener('change', synchroniserGenre);
  (racine.querySelector('[data-pose-enregistrer]') as HTMLElement | null)?.addEventListener('click', () => {
    enregistrerContour((genreEl?.value as GenrePose) ?? 'sol');
  });
  synchroniserGenre();
  rendreListe();

  return { enregistrerContour, surfaces: () => (ctx.surfacesPose ?? []).slice() };
}

/** Lit le panneau et construit la surface du genre demandé. Extrait pour rester
 *  lisible : un genre = une fonction de création, jamais un aiguillage caché. */
function saisirSurface(
  genre: GenrePose,
  racine: HTMLElement,
  ctx: Ctx,
  rang: number,
): VerdictSurface {
  const vertices = (ctx.vertices ?? []).map((v) => [v[0], v[1]] as LngLat);
  const base = {
    id: `${genre}-${rang}`,
    label: `${genre === 'ombriere' ? 'Ombrière' : 'Champ au sol'} ${rang}`,
    vertices,
    buildingId: ctx.activeArea?.()?.buildingId ?? undefined,
  };
  return creerChampSol({
    ...base,
    penteTerrainDeg: lireChamp(racine, 'pente'),
    azimutRangeeDeg: lireChamp(racine, 'azimut'),
    inclinaisonDeg: lireChamp(racine, 'inclinaison'),
  });
}

