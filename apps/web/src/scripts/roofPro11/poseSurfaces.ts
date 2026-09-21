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
import * as THREE from 'three';
import { geodesicAreaM2, type LngLat } from '../../lib/roof';
import { DEG2M, DEG2RAD } from './constants';
import { esc } from './dom';
// CALX125 — la normale SORTANTE d'une arête est déjà posée et prouvée par CALX99 ; c'est
// elle, et pas une seconde formule, qui donne l'azimut d'une façade.
import { azimutNormaleArete, distanceEntreM } from './snap';
import type { Ctx } from './context';
// CALX124 — la géométrie de placement de CAL89/CAL91 existe et est testée depuis des
// mois sans qu'aucun fichier applicatif ne l'importe : c'est ICI qu'elle est branchée.
// On la RÉUTILISE telle quelle — il n'y a pas une seconde formule de placement.
import {
  construireChampPose,
  construireOmbriere,
  // `ChampPose` de `scene3d` est le PLACEMENT rendu ; `ChampPose` d'ici est un champ de
  // SAISIE. Deux notions, deux noms : on renomme l'importé plutôt que de les confondre.
  type ChampPose as PlacementPose,
  type PlanMoteurSurface,
  type TablePlacee,
} from './scene3d';

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
  | 'hauteurHaute'
  | 'retraits';

/** Libellé FRANÇAIS de chaque genre de surface — l'écran n'affiche jamais la clé. */
export const LIBELLE_GENRE: Readonly<Record<GenrePose, string>> = {
  sol: 'Champ au sol',
  ombriere: 'Ombrière',
  facade: 'Façade',
};

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
  retraits: 'retraits de la bande posable',
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
  /** Libellé propre quand plusieurs entrées partagent le même `champ` de refus
   *  (les trois retraits de façade). Absent = le libellé du champ. */
  libelle?: string;
}

/** Les champs numériques du panneau, dans l'ordre d'affichage. */
const CHAMPS_PANNEAU: readonly ChampNumerique[] = [
  { champ: 'penteTerrain', cle: 'pente', unite: '°', genres: ['sol'] },
  { champ: 'azimutRangee', cle: 'azimut', unite: '°', genres: ['sol', 'ombriere'] },
  { champ: 'inclinaison', cle: 'inclinaison', unite: '°', genres: ['sol', 'ombriere'] },
  { champ: 'hauteurLibre', cle: 'hauteurLibre', unite: 'm', genres: ['ombriere'] }, // CALX124
  { champ: 'sensEcoulement', cle: 'ecoulement', unite: '°', genres: ['ombriere'] }, // CALX124
  { champ: 'pasAppui', cle: 'pasAppui', unite: 'm', genres: ['ombriere'] }, // CALX124
  { champ: 'sectionAppui', cle: 'sectionAppui', unite: 'm', genres: ['ombriere'] }, // CALX124
  { champ: 'mur', cle: 'mur', unite: 'n° du côté', genres: ['facade'] }, // CALX125
  { champ: 'hauteurBasse', cle: 'hauteurBasse', unite: 'm', genres: ['facade'] }, // CALX125
  { champ: 'hauteurHaute', cle: 'hauteurHaute', unite: 'm', genres: ['facade'] }, // CALX125
  { champ: 'retraits', cle: 'retraitLateral', unite: 'm', genres: ['facade'], libelle: 'retrait latéral' }, // CALX125
  { champ: 'retraits', cle: 'retraitBas', unite: 'm', genres: ['facade'], libelle: 'retrait bas' }, // CALX125
  { champ: 'retraits', cle: 'retraitHaut', unite: 'm', genres: ['facade'], libelle: 'retrait haut' }, // CALX125
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
        <option value="ombriere">Ombrière</option>
        <option value="facade">Façade</option>
      </select>
    </label>
    ${CHAMPS_PANNEAU.map(
      (c) => `<label class="mb-2 block" data-pose-ligne="${esc(c.cle)}">${esc(c.libelle ?? LIBELLE_CHAMP_POSE[c.champ])} (${esc(c.unite)})
        <input type="number" inputmode="decimal" data-pose-champ="${esc(c.cle)}" class="mt-1 w-full rounded border border-white/20 bg-nuit-900/60 px-2 py-1" />
        ${c.libelle ? '' : `<span class="mt-1 block text-[11px] text-rose-300" data-pose-erreur="${esc(c.champ)}"></span>`}
      </label>`,
    ).join('')}
    <span class="mb-2 block text-[11px] text-rose-300" data-pose-erreur="retraits"></span>
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
      const ligne = racine!.querySelector(`[data-pose-ligne="${c.cle}"]`) as HTMLElement | null;
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
    label: `${LIBELLE_GENRE[genre]} ${rang}`,
    vertices,
    buildingId: ctx.activeArea?.()?.buildingId ?? undefined,
  };
  if (genre === 'facade') {
    // CALX125 — le mur est désigné par son NUMÉRO DE CÔTÉ (1 = le premier côté tracé) :
    // un numéro d'écran commence à 1, l'index du contour à 0.
    const numeroMur = lireChamp(racine, 'mur');
    return creerFacade({
      id: base.id,
      label: base.label,
      buildingId: base.buildingId,
      contourBatiment: vertices,
      areteIndex: estSaisi(numeroMur) ? Math.round(numeroMur) - 1 : -1,
      hauteurBasseM: lireChamp(racine, 'hauteurBasse'),
      hauteurHauteM: lireChamp(racine, 'hauteurHaute'),
      retraitsM: {
        lateralM: lireChamp(racine, 'retraitLateral'),
        basM: lireChamp(racine, 'retraitBas'),
        hautM: lireChamp(racine, 'retraitHaut'),
      },
    });
  }
  if (genre === 'ombriere') {
    return creerOmbriere({
      ...base,
      azimutRangeeDeg: lireChamp(racine, 'azimut'),
      inclinaisonDeg: lireChamp(racine, 'inclinaison'),
      hauteurLibreM: lireChamp(racine, 'hauteurLibre'), // CALX124
      sensEcoulementDeg: lireChamp(racine, 'ecoulement'), // CALX124
      pasAppuiM: lireChamp(racine, 'pasAppui'), // CALX124
      sectionAppuiM: lireChamp(racine, 'sectionAppui'), // CALX124
    });
  }
  return creerChampSol({
    ...base,
    penteTerrainDeg: lireChamp(racine, 'pente'),
    azimutRangeeDeg: lireChamp(racine, 'azimut'),
    inclinaisonDeg: lireChamp(racine, 'inclinaison'),
  });
}

/* ════════════════════════════════════════════════════════════════════════════
   CALX124 — L'OMBRIÈRE SE DESSINE, POTEAUX COMPRIS.
   ----------------------------------------------------------------------------
   Constat : l'ombrière était un second formulaire de nombres sans visuel, et
   `construireOmbriere` (CAL91, `scene3d.ts`) n'était importée par AUCUN fichier
   applicatif. Ce bloc la BRANCHE : contour tracé, hauteur libre, sens
   d'écoulement et inclinaison SAISIS, poteaux rendus au pas et à la section
   SAISIS (`appuis`, contrat CALX87).

   AUCUNE CHARGE, AUCUNE STRUCTURE n'est calculée — le contrat le dit et ce
   module s'y tient : il place des volumes, il ne dimensionne aucun ouvrage.

   CE QUI RESTE SANS SAISIE : sans hauteur libre, la couverture n'est PAS levée
   à une hauteur supposée — elle reste au sol et le motif est affiché ; sans
   entraxe, AUCUN poteau n'est dessiné — on n'en pose pas au jugé.
   ══════════════════════════════════════════════════════════════════════════ */

/** CONVENTION DE DESSIN — au-delà de ce nombre d'appuis, la scène cesse d'en
 *  instancier : un entraxe minuscule sur un grand contour ferait des dizaines de
 *  milliers de volumes et figerait l'atelier. Ce n'est PAS une règle de structure
 *  (aucune charge n'est calculée ici) : c'est une borne de rendu, et le nombre
 *  écarté est DIT plutôt que masqué. */
export const PLAFOND_APPUIS_DESSINES = 2000;

/** CONVENTION DE DESSIN — épaisseur (m) des volumes de pose rendus en 3D. Elle ne
 *  décrit aucun ouvrage : c'est ce qui donne un volume visible et une vraie ombre
 *  portée plutôt qu'un plan d'épaisseur nulle. */
export const EPAISSEUR_COUVERTURE_DESSIN_M = 0.08;

/** Un nombre saisi ET strictement positif (hauteur, entraxe, section…). */
function estPositif(v: unknown): v is number {
  return estSaisi(v) && v > 0;
}

/** Ce que l'atelier recueille pour une ombrière (CAL91 + appuis CALX87). */
export interface SaisieOmbriere {
  id: string;
  label?: string;
  vertices: readonly LngLat[];
  buildingId?: string;
  /** Orientation des rangées (degrés), SAISIE. */
  azimutRangeeDeg?: number | null;
  /** Inclinaison de la COUVERTURE (degrés), SAISIE. */
  inclinaisonDeg?: number | null;
  /** Hauteur libre sous la couverture (m), SAISIE. */
  hauteurLibreM?: number | null;
  /** Sens d'écoulement de la couverture (degrés, 0=N, 90=E), SAISI. */
  sensEcoulementDeg?: number | null;
  /** Entraxe des appuis (m), SAISI. Absent ⇒ AUCUN poteau n'est décrit. */
  pasAppuiM?: number | null;
  /** Section d'un appui (m), SAISIE. */
  sectionAppuiM?: number | null;
}

/**
 * CALX124 — crée la surface de pose d'une OMBRIÈRE depuis le contour tracé.
 *
 * Le contour suit exactement les règles du champ au sol (CALX123) ; s'y ajoutent
 * la hauteur libre, le sens d'écoulement et les appuis, chacun écrit SEULEMENT
 * s'il est saisi et NOMMÉ dans `nonSaisi` sinon. La pente du TERRAIN n'est pas
 * une donnée d'ombrière : elle n'est ni écrite, ni réclamée.
 */
export function creerOmbriere(saisie: SaisieOmbriere): VerdictSurface {
  const verdict = creerChampSol({
    id: saisie.id,
    label: saisie.label,
    vertices: saisie.vertices,
    buildingId: saisie.buildingId,
    azimutRangeeDeg: saisie.azimutRangeeDeg,
    inclinaisonDeg: saisie.inclinaisonDeg,
    // Marqueur interne : le terrain n'est pas le sujet d'une ombrière, donc on ne le
    // réclame pas — et la clé est retirée juste en dessous, jamais publiée.
    penteTerrainDeg: 0,
  });
  if (!verdict.ok) return verdict;
  const surface = verdict.surface as unknown as Record<string, unknown>;
  surface.kind = 'ombriere';
  delete surface.terrainSlopeDeg;
  const nonSaisi = verdict.nonSaisi.slice();

  poserSaisie(surface, 'clearHeightM', saisie.hauteurLibreM, 'hauteurLibre', nonSaisi);
  poserSaisie(surface, 'flowAzimuthDeg', saisie.sensEcoulementDeg, 'sensEcoulement', nonSaisi);

  const appuis: Record<string, unknown> = {};
  if (estPositif(saisie.pasAppuiM)) appuis.pasM = saisie.pasAppuiM;
  else nonSaisi.push(LIBELLE_CHAMP_POSE.pasAppui);
  if (estPositif(saisie.sectionAppuiM)) appuis.sectionM = saisie.sectionAppuiM;
  else nonSaisi.push(LIBELLE_CHAMP_POSE.sectionAppui);
  if (Object.keys(appuis).length) surface.appuis = appuis;

  return { ok: true, surface: surface as unknown as SurfacePose, nonSaisi };
}

/**
 * CALX124 — les POSITIONS des appuis le long du contour, à l'entraxe SAISI.
 *
 * On marche le périmètre fermé et on pose un appui tous les `pasM` mètres depuis
 * le premier coin. Entraxe absent, nul ou négatif ⇒ tableau VIDE : l'atelier ne
 * décide pas d'un entraxe, il n'en propose aucun, et la scène ne dessine alors
 * aucun poteau (contrat CALX87 : « absent = aucun appui décrit »).
 */
export function positionsAppuis(
  contourM: readonly (readonly number[])[] | null | undefined,
  pasM: number | null | undefined,
): [number, number][] {
  if (!Array.isArray(contourM) || contourM.length < 3 || !estPositif(pasM)) return [];
  const points: [number, number][] = [];
  let reste = 0;
  for (let i = 0; i < contourM.length; i++) {
    const a = contourM[i];
    const b = contourM[(i + 1) % contourM.length];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const longueur = Math.hypot(dx, dy);
    if (!(longueur > 0)) continue;
    for (let d = reste; d < longueur; d += pasM) {
      points.push([a[0] + (dx * d) / longueur, a[1] + (dy * d) / longueur]);
      if (points.length >= PLAFOND_APPUIS_DESSINES) return points;
    }
    reste = (((reste - longueur) % pasM) + pasM) % pasM;
  }
  return points;
}

/** CALX124 — ce que la scène a pu dessiner pour une surface, et ce qu'elle n'a
 *  PAS dessiné, nommé. */
export interface RenduPose {
  maillages: THREE.Mesh[];
  /** Le placement rendu par le moteur (CAL89/CAL91), ou `null` sans contour. */
  placement: PlacementPose | null;
  /** Ce qui manque, NOMMÉ — l'atelier l'affiche, il ne le comble pas. */
  nonDessine: string[];
}

/** Décalage ENU (m) entre l'origine d'une surface et l'origine de la scène. */
function decalageScene(surface: SurfacePose, origineScene: LngLat): [number, number] {
  const o = origineContour(surface.vertices ?? []);
  if (!o || !Array.isArray(origineScene)) return [0, 0];
  const cosLat = Math.cos(origineScene[1] * DEG2RAD);
  return [(o[0] - origineScene[0]) * DEG2M * cosLat, (o[1] - origineScene[1]) * DEG2M];
}

/** Le plan du moteur d'une surface, au format que `construireChampPose` attend. */
function planMoteur(surface: SurfacePose): PlanMoteurSurface | null {
  const e = surface.engine;
  if (!e) return null;
  return { modules: e.modules ?? undefined, tables: e.tables ?? [] };
}

/** Matériau des volumes de pose — même teinte que les volumes de bâtiment, subduée
 *  pour une scène en lecture seule (`dim`), comme le fait déjà `construireAcrotere`. */
function materiauPose(dim: boolean): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: dim ? 0x9aa3b4 : 0xe2e7f2,
    roughness: 0.85,
    metalness: 0,
    transparent: dim,
    opacity: dim ? 0.55 : 1,
  });
}

/** Centroïde (moyenne des sommets) d'un contour métrique. */
function centreContour(contourM: readonly (readonly number[])[]): [number, number] {
  let sx = 0;
  let sy = 0;
  for (const p of contourM) {
    sx += p[0];
    sy += p[1];
  }
  return [sx / contourM.length, sy / contourM.length];
}

/** Le contour d'une surface, recentré sur son centroïde, prêt pour un `THREE.Shape`. */
function formeContour(
  contourM: readonly (readonly number[])[],
  centre: [number, number],
): THREE.Shape {
  const shape = new THREE.Shape();
  contourM.forEach((p, i) => {
    const x = p[0] - centre[0];
    const y = p[1] - centre[1];
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });
  shape.closePath();
  return shape;
}

/** Les TABLES posées par le moteur, en volumes — une par rectangle rendu. */
function volumesTables(
  tables: readonly TablePlacee[],
  offX: number,
  offY: number,
  dim: boolean,
  prefixe: string,
): THREE.Mesh[] {
  const out: THREE.Mesh[] = [];
  for (let i = 0; i < tables.length; i++) {
    const t = tables[i];
    if (!(t.largeurM > 0) || !(t.profondeurM > 0)) continue;
    const geo = new THREE.BoxGeometry(t.largeurM, t.profondeurM, EPAISSEUR_COUVERTURE_DESSIN_M);
    const mesh = new THREE.Mesh(geo, materiauPose(dim));
    mesh.name = `${prefixe}-table-${i}`;
    mesh.position.set(t.cx + offX, t.cy + offY, t.z);
    mesh.rotation.x = t.inclinaisonRad;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    out.push(mesh);
  }
  return out;
}

/**
 * CALX124 — les volumes 3D d'une OMBRIÈRE : sa couverture, ses poteaux, et les
 * tables que le moteur a posées dessus.
 *
 * La couverture est levée à la hauteur libre SAISIE ; sans hauteur libre elle reste
 * AU SOL (z = 0) et le motif est affiché. Les poteaux n'existent que si l'entraxe ET
 * la section sont saisis ET que la couverture est levée : un poteau de hauteur nulle
 * ou de section inconnue ne se dessine pas au jugé.
 *
 * Tous les volumes PROJETTENT leur ombre (`castShadow`) : c'est le seul intérêt de
 * dessiner une ombrière plutôt que de la tabuler.
 */
export function construireOmbrierePose(
  surface: SurfacePose,
  origineScene: LngLat,
  dim: boolean,
): RenduPose {
  const nonDessine: string[] = [];
  const contourM = surface.contourM;
  if (!Array.isArray(contourM) || contourM.length < 3) {
    return { maillages: [], placement: null, nonDessine: ['contour de l’ombrière non tracé'] };
  }
  const [offX, offY] = decalageScene(surface, origineScene);
  const centre = centreContour(contourM);

  // Le PLACEMENT de CAL91 — réutilisé tel quel, jamais recalculé ici.
  const placement = construireOmbriere(planMoteur(surface), {
    tiltDeg: estSaisi(surface.tiltDeg) ? surface.tiltDeg : 0,
    penteTerrainDeg: null,
    hauteurLibreM: surface.clearHeightM ?? null,
    aireTerrainM2: surface.areaM2 ?? null,
  });
  const hauteurLibre = estPositif(surface.clearHeightM) ? surface.clearHeightM : 0;
  if (hauteurLibre === 0) {
    nonDessine.push(
      'hauteur libre non renseignée : la couverture reste au sol (aucune hauteur supposée)',
    );
  }

  const maillages: THREE.Mesh[] = [];

  // LA COUVERTURE — le contour extrudé d'une épaisseur de dessin, levé à la hauteur
  // libre saisie. Inclinaison et sens d'écoulement SAISIS l'orientent ; absents, elle
  // reste horizontale plutôt que penchée au jugé.
  const geoCouverture = new THREE.ExtrudeGeometry(formeContour(contourM, centre), {
    depth: EPAISSEUR_COUVERTURE_DESSIN_M,
    bevelEnabled: false,
  });
  const couverture = new THREE.Mesh(geoCouverture, materiauPose(dim));
  couverture.name = `rp11-ombriere-${surface.id}-couverture`;
  couverture.position.set(centre[0] + offX, centre[1] + offY, hauteurLibre);
  const tiltRad = (estSaisi(surface.tiltDeg) ? surface.tiltDeg : 0) * DEG2RAD;
  const azRad = (estSaisi(surface.flowAzimuthDeg) ? surface.flowAzimuthDeg : 0) * DEG2RAD;
  couverture.quaternion
    .setFromAxisAngle(new THREE.Vector3(0, 0, 1), -azRad)
    .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), tiltRad));
  couverture.castShadow = true;
  couverture.receiveShadow = true;
  maillages.push(couverture);

  // LES POTEAUX — au pas et à la section SAISIS, et à ces conditions seulement.
  const pasM = surface.appuis?.pasM;
  const sectionM = surface.appuis?.sectionM;
  const points = positionsAppuis(contourM, pasM);
  if (!estPositif(pasM)) {
    nonDessine.push('entraxe des appuis non renseigné : aucun poteau n’est dessiné');
  } else if (!estPositif(sectionM)) {
    nonDessine.push('section des appuis non renseignée : aucun poteau n’est dessiné');
  } else if (hauteurLibre === 0) {
    nonDessine.push('aucun poteau dessiné : la couverture n’est pas levée');
  } else {
    for (let i = 0; i < points.length; i++) {
      const geo = new THREE.BoxGeometry(sectionM, sectionM, hauteurLibre);
      const poteau = new THREE.Mesh(geo, materiauPose(dim));
      poteau.name = `rp11-ombriere-${surface.id}-appui-${i}`;
      poteau.position.set(points[i][0] + offX, points[i][1] + offY, hauteurLibre / 2);
      poteau.castShadow = true;
      poteau.receiveShadow = true;
      maillages.push(poteau);
    }
    if (points.length >= PLAFOND_APPUIS_DESSINES) {
      nonDessine.push(
        `appuis dessinés plafonnés à ${PLAFOND_APPUIS_DESSINES} : l’entraxe saisi en produit davantage`,
      );
    }
  }

  // LES TABLES — celles du MOTEUR, placées par CAL91, jamais repavées ici.
  maillages.push(...volumesTables(placement.tables, offX, offY, dim, `rp11-ombriere-${surface.id}`));
  if (!placement.tables.length) nonDessine.push('plan du moteur non reçu : aucune table posée');

  return { maillages, placement, nonDessine };
}

/**
 * CALX124 — les volumes 3D d'un CHAMP AU SOL : les tables que le moteur a posées,
 * placées par CAL89 (`construireChampPose`) et par personne d'autre.
 */
export function construireChampSolPose(
  surface: SurfacePose,
  origineScene: LngLat,
  dim: boolean,
): RenduPose {
  const contourM = surface.contourM;
  if (!Array.isArray(contourM) || contourM.length < 3) {
    return { maillages: [], placement: null, nonDessine: ['contour du champ non tracé'] };
  }
  const [offX, offY] = decalageScene(surface, origineScene);
  const placement = construireChampPose(planMoteur(surface), {
    tiltDeg: estSaisi(surface.tiltDeg) ? surface.tiltDeg : 0,
    penteTerrainDeg: surface.terrainSlopeDeg ?? null,
    hauteurLibreM: null,
    aireTerrainM2: surface.areaM2 ?? null,
  });
  const maillages = volumesTables(placement.tables, offX, offY, dim, `rp11-sol-${surface.id}`);
  const nonDessine = placement.tables.length ? [] : ['plan du moteur non reçu : aucune table posée'];
  return { maillages, placement, nonDessine };
}

/* ════════════════════════════════════════════════════════════════════════════
   CALX125 — POSER DES MODULES EN FAÇADE, SUR UN MUR DÉSIGNÉ DU BÂTIMENT.
   ----------------------------------------------------------------------------
   Constat : aucune occurrence de « façade » n'existait dans roofPro11 ni dans
   `lib/roofPro2.ts`, et les murs n'étaient qu'une extrusion décorative. Le
   contrat, lui, admet depuis CALX87 un troisième genre de surface — `facade` —
   BORNÉ EN HAUTEUR au lieu de l'être au sol, avec ses deux hauteurs obligatoires.

   CE QUI DÉFINIT UNE FAÇADE, ET CE QUI N'EST PAS UNE HYPOTHÈSE :
     * l'AZIMUT est la NORMALE SORTANTE du mur désigné — `azimutNormaleArete`
       (CALX99), déjà prouvée sur un carré tracé SO→SE→NE→NO ; aucune seconde
       formule ici ;
     * l'INCLINAISON vaut 90° : ce n'est pas une valeur « raisonnable », c'est la
       définition d'un mur vertical, celle-là même qui fait que le contrat borne
       la façade en hauteur ;
     * les DEUX HAUTEURS sont SAISIES. Aucune n'est déduite de l'autre ni d'une
       hauteur de bâtiment (CALX84) : ce sont deux mesures. Sans les deux, AUCUNE
       surface n'est créée et le champ manquant est nommé — « non mesuré » ne se
       pave pas.
   ══════════════════════════════════════════════════════════════════════════ */

/** CONVENTION DE DESSIN — épaisseur (m) de la bande de façade et des modules
 *  plaqués, pour qu'ils aient un volume visible et une vraie ombre portée plutôt
 *  qu'un plan d'épaisseur nulle. Ne décrit aucun ouvrage. */
export const EPAISSEUR_FACADE_DESSIN_M = 0.06;

/** CALX125 — inclinaison d'une façade : un mur est VERTICAL, donc 90°. Ce n'est pas
 *  une constante d'ingénierie choisie, c'est la définition du genre `facade`. */
export const INCLINAISON_FACADE_DEG = 90;

/** Les RETRAITS SAISIS de la bande posable d'un mur (m). Chacun absent = aucun
 *  retrait appliqué de ce côté, et le manque est NOMMÉ — jamais un retrait supposé. */
export interface RetraitsFacade {
  /** Retrait de chaque côté vertical du mur (m), SAISI. */
  lateralM?: number | null;
  /** Retrait sous la hauteur haute (m), SAISI (bandeau, acrotère…). */
  hautM?: number | null;
  /** Retrait au-dessus de la hauteur basse (m), SAISI. */
  basM?: number | null;
}

/** Ce que l'atelier recueille pour une façade : un MUR désigné + deux hauteurs. */
export interface SaisieFacade {
  id: string;
  label?: string;
  /** Le contour du BÂTIMENT (CALX100) dont on désigne un mur. */
  contourBatiment: readonly LngLat[];
  /** L'arête désignée : le mur va de `contourBatiment[areteIndex]` au suivant. */
  areteIndex: number;
  buildingId?: string;
  /** Hauteur du BAS de la bande posable (m au-dessus du terrain), SAISIE. */
  hauteurBasseM?: number | null;
  /** Hauteur du HAUT de la bande posable (m au-dessus du terrain), SAISIE. */
  hauteurHauteM?: number | null;
  /** Les retraits SAISIS de la bande posable. */
  retraitsM?: RetraitsFacade;
}

/** Un retrait SAISI, ou 0 quand il ne l'est pas — et le manque est nommé par l'appelant. */
function retraitSaisi(v: unknown): number {
  return estSaisi(v) && v >= 0 ? v : 0;
}

/**
 * CALX125 — la SURFACE POSABLE d'un mur (m²) : sa longueur et sa bande de hauteur,
 * DIMINUÉES des retraits saisis. C'est exactement la surface qui part au moteur,
 * donc exactement celle que le nombre de modules posés suit.
 *
 * `null` quand la bande n'a plus d'étendue (retraits plus larges que le mur) :
 * une surface négative ne se pave pas, et on ne la ramène pas à zéro en silence.
 */
export function surfacePosableFacadeM2(
  longueurM: number,
  hauteurBasseM: number,
  hauteurHauteM: number,
  retraits?: RetraitsFacade,
): number | null {
  const largeur = longueurM - 2 * retraitSaisi(retraits?.lateralM);
  const hauteur =
    hauteurHauteM - retraitSaisi(retraits?.hautM) - (hauteurBasseM + retraitSaisi(retraits?.basM));
  if (!(largeur > 0) || !(hauteur > 0)) return null;
  return largeur * hauteur;
}

/**
 * CALX125 — le contour POSABLE d'un mur, dans le repère du mur : `x` = distance le
 * long du mur depuis son premier coin, `y` = hauteur au-dessus du terrain. C'est
 * lui que `contourM` porte, donc lui que le moteur reçoit.
 */
export function contourFacadeM(
  longueurM: number,
  hauteurBasseM: number,
  hauteurHauteM: number,
  retraits?: RetraitsFacade,
): number[][] | null {
  const lat = retraitSaisi(retraits?.lateralM);
  const bas = hauteurBasseM + retraitSaisi(retraits?.basM);
  const haut = hauteurHauteM - retraitSaisi(retraits?.hautM);
  const x0 = lat;
  const x1 = longueurM - lat;
  if (!(x1 > x0) || !(haut > bas)) return null;
  return [
    [x0, bas],
    [x1, bas],
    [x1, haut],
    [x0, haut],
  ];
}

/**
 * CALX125 — désigne un MUR du bâtiment et en fait une surface de pose `facade`.
 *
 * Refus NOMMÉS : contour de bâtiment absent, mur inexistant, hauteur basse ou haute
 * non saisie (⇒ AUCUNE surface n'est créée), bande sans étendue. Aucune hauteur
 * n'est déduite : deux mesures, ou rien.
 */
export function creerFacade(saisie: SaisieFacade): VerdictSurface {
  const id = idNettoye(saisie?.id);
  if (!id) {
    return {
      ok: false,
      champ: 'identifiant',
      motif: 'Nommez la façade avant de l’enregistrer : un identifiant vide ne se retrouve pas dans le document.',
    };
  }
  const contour = saisie.contourBatiment;
  if (!Array.isArray(contour) || contour.length < 3) {
    return {
      ok: false,
      champ: 'contour',
      motif: 'Tracez d’abord le contour du bâtiment : un mur se désigne sur un contour fermé.',
    };
  }
  const i = saisie.areteIndex;
  if (!Number.isInteger(i) || i < 0 || i >= contour.length) {
    return {
      ok: false,
      champ: 'mur',
      motif: 'Désignez un mur du bâtiment : cette arête n’existe pas sur le contour tracé.',
    };
  }
  const a = contour[i];
  const b = contour[(i + 1) % contour.length];
  const longueurM = distanceEntreM(a, b);
  if (!(longueurM > 0)) {
    return {
      ok: false,
      champ: 'mur',
      motif: 'Le mur désigné a une longueur nulle : reprenez le contour du bâtiment.',
    };
  }
  if (!estSaisi(saisie.hauteurBasseM) || saisie.hauteurBasseM < 0) {
    return {
      ok: false,
      champ: 'hauteurBasse',
      motif: 'Saisissez la hauteur basse de la bande posable : sans elle, aucune surface de façade n’est créée (une hauteur non mesurée ne se pave pas).',
    };
  }
  if (!estSaisi(saisie.hauteurHauteM) || saisie.hauteurHauteM < 0) {
    return {
      ok: false,
      champ: 'hauteurHaute',
      motif: 'Saisissez la hauteur haute de la bande posable : sans elle, aucune surface de façade n’est créée (elle n’est jamais déduite de la hauteur du bâtiment).',
    };
  }
  if (!(saisie.hauteurHauteM > saisie.hauteurBasseM)) {
    return {
      ok: false,
      champ: 'hauteurHaute',
      motif: 'La hauteur haute doit dépasser la hauteur basse : sinon la bande posable n’a aucune étendue verticale.',
    };
  }
  const contourM = contourFacadeM(
    longueurM,
    saisie.hauteurBasseM,
    saisie.hauteurHauteM,
    saisie.retraitsM,
  );
  const areaM2 = surfacePosableFacadeM2(
    longueurM,
    saisie.hauteurBasseM,
    saisie.hauteurHauteM,
    saisie.retraitsM,
  );
  if (!contourM || areaM2 === null) {
    return {
      ok: false,
      champ: 'retraits',
      motif: 'Les retraits saisis ne laissent aucune bande posable sur ce mur : réduisez-les ou désignez un autre mur.',
    };
  }

  const azimut = azimutNormaleArete(a, b);
  const nonSaisi: string[] = [];
  if (!estSaisi(saisie.retraitsM?.lateralM)) nonSaisi.push('retrait latéral de la façade');
  if (!estSaisi(saisie.retraitsM?.basM)) nonSaisi.push('retrait bas de la façade');
  if (!estSaisi(saisie.retraitsM?.hautM)) nonSaisi.push('retrait haut de la façade');

  const surface: Record<string, unknown> = {
    kind: 'facade',
    id,
    vertices: [[a[0], a[1]], [b[0], b[1]]],
    contourM,
    areaM2,
    hauteurBasseM: saisie.hauteurBasseM,
    hauteurHauteM: saisie.hauteurHauteM,
    // L'azimut de la surface EST la normale sortante du mur (CALX99) ; c'est la seule
    // clé d'orientation que le contrat porte pour une surface de pose.
    rowAzimuthDeg: azimut,
    tiltDeg: INCLINAISON_FACADE_DEG,
  };
  const label = (saisie.label ?? '').trim();
  if (label) surface.label = label;
  const batiment = (saisie.buildingId ?? '').trim();
  if (batiment) surface.buildingId = batiment;

  return { ok: true, surface: surface as unknown as SurfacePose, nonSaisi };
}

/**
 * CALX125 — les volumes 3D d'une FAÇADE : la bande posable plaquée sur le mur, et
 * les modules que le moteur y a posés, plaqués avec elle.
 *
 * Le repère du moteur pour une façade est celui du mur (`x` le long du mur, `y` en
 * hauteur) : chaque table rendue est donc reportée à sa distance le long du mur et
 * à sa hauteur, jamais « à plat ». Tous les volumes portent leur ombre.
 */
export function construireFacadePose(
  surface: SurfacePose,
  origineScene: LngLat,
  dim: boolean,
): RenduPose {
  const v = surface.vertices;
  const contourM = surface.contourM;
  if (!Array.isArray(v) || v.length < 2 || !Array.isArray(contourM) || contourM.length < 4) {
    return { maillages: [], placement: null, nonDessine: ['mur de la façade non désigné'] };
  }
  const cosLat = Math.cos(origineScene[1] * DEG2RAD);
  const enu = (p: LngLat): [number, number] => [
    (p[0] - origineScene[0]) * DEG2M * cosLat,
    (p[1] - origineScene[1]) * DEG2M,
  ];
  const a = enu(v[0]);
  const b = enu(v[1]);
  const longueur = Math.hypot(b[0] - a[0], b[1] - a[1]);
  if (!(longueur > 0)) {
    return { maillages: [], placement: null, nonDessine: ['mur de la façade dégénéré'] };
  }
  const ux = (b[0] - a[0]) / longueur;
  const uy = (b[1] - a[1]) / longueur;
  const azRad = (estSaisi(surface.rowAzimuthDeg) ? surface.rowAzimuthDeg : 0) * DEG2RAD;
  // Normale SORTANTE en repère ENU (est, nord) pour un cap depuis le nord vrai.
  const nx = Math.sin(azRad);
  const ny = Math.cos(azRad);
  const angleZ = Math.atan2(uy, ux);
  const demiEpaisseur = EPAISSEUR_FACADE_DESSIN_M / 2;

  /** Pose un volume PLAQUÉ sur le mur, à `long` mètres du premier coin et `haut` m du sol. */
  const plaquer = (
    largeurM: number,
    hauteurM: number,
    long: number,
    haut: number,
    nom: string,
  ): THREE.Mesh => {
    const geo = new THREE.BoxGeometry(largeurM, EPAISSEUR_FACADE_DESSIN_M, hauteurM);
    const mesh = new THREE.Mesh(geo, materiauPose(dim));
    mesh.name = nom;
    mesh.position.set(
      a[0] + ux * long + nx * demiEpaisseur,
      a[1] + uy * long + ny * demiEpaisseur,
      haut,
    );
    mesh.rotation.z = angleZ;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  };

  const x0 = contourM[0][0];
  const x1 = contourM[1][0];
  const yBas = contourM[0][1];
  const yHaut = contourM[2][1];
  const maillages: THREE.Mesh[] = [
    plaquer(x1 - x0, yHaut - yBas, (x0 + x1) / 2, (yBas + yHaut) / 2, `rp11-facade-${surface.id}-bande`),
  ];

  // Le PLACEMENT du moteur, réutilisé tel quel (CAL89) : la façade ne pave pas plus
  // que le sol ou l'ombrière — elle affiche ce que le moteur a posé.
  const placement = construireChampPose(planMoteur(surface), {
    tiltDeg: 0, // le repère du mur est déjà vertical : aucune seconde inclinaison
    penteTerrainDeg: 0, // un mur n'a pas de pente de terrain
    hauteurLibreM: 0,
    aireTerrainM2: surface.areaM2 ?? null,
  });
  for (let i = 0; i < placement.tables.length; i++) {
    const t = placement.tables[i];
    if (!(t.largeurM > 0) || !(t.profondeurM > 0)) continue;
    maillages.push(
      plaquer(t.largeurM, t.profondeurM, t.cx, t.cy, `rp11-facade-${surface.id}-module-${i}`),
    );
  }
  const nonDessine = placement.tables.length ? [] : ['plan du moteur non reçu : aucun module posé'];
  return { maillages, placement, nonDessine };
}

/** CALX124/125 — le rendu d'UNE surface de pose, quel que soit son genre. */
export function construireSurfacePose(
  surface: SurfacePose,
  origineScene: LngLat,
  dim: boolean,
): RenduPose {
  if (surface.kind === 'ombriere') return construireOmbrierePose(surface, origineScene, dim);
  if (surface.kind === 'sol') return construireChampSolPose(surface, origineScene, dim);
  if (surface.kind === 'facade') return construireFacadePose(surface, origineScene, dim); // CALX125
  return { maillages: [], placement: null, nonDessine: [] };
}

/**
 * CALX124 — TOUS les volumes des surfaces de pose du document, prêts à être ajoutés
 * à la scène. Liste vide (aucune surface tracée) ⇒ tableau vide, et la scène reste
 * EXACTEMENT celle d'aujourd'hui.
 */
export function construireMaillagesPose(
  surfaces: readonly SurfacePose[] | null | undefined,
  origineScene: LngLat,
  dim: boolean,
): THREE.Mesh[] {
  if (!Array.isArray(surfaces) || !surfaces.length || !Array.isArray(origineScene)) return [];
  const out: THREE.Mesh[] = [];
  for (const s of surfaces) {
    if (!s) continue;
    out.push(...construireSurfacePose(s, origineScene, dim).maillages);
  }
  return out;
}

